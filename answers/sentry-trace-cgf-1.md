Here is the path an error event takes, from the Kafka consumer to a stored `Group` (issue).

## 1. Kafka consumer (`ingest-events`)

- **`IngestStrategyFactory.create_with_partitions`** (`src/sentry/ingest/consumer/factory.py:118`) builds the Arroyo pipeline. For topics other than attachments, it wraps `process_simple_event_message` in a `partial` (`factory.py:128-133`). That goes into a multiprocess step (`factory.py:134`) and then a backpressure step (`factory.py:135`). The pipeline ends with `CommitOffsets` (`factory.py:125`).
- **`process_simple_event_message`** (`src/sentry/ingest/consumer/simple_event.py:25`):
  - msgpack-decodes the message (`:54`) and rejects any type other than `"event"` (`:59`).
  - Loads the `Project` from cache (`:64`) and calls `processors.process_event` (`:68`).
  - Non-retriable exceptions become `InvalidMessage` and go to the DLQ (`:76-83`).
  - There is a second entry point, the taskbroker "raw mode" task `process_event_from_kafka` (`simple_event.py:92`). It calls the same `process_event` (`:124`), with optional inline save.
- **`processors.process_event`** (`src/sentry/ingest/consumer/processors.py:79`):
  - Dedup check against the cache key `ev:{project_id}:{event_id}` (`:117-131`), then load-shed killswitches (`:133-175`).
  - `orjson.loads` of the payload (`:150`), then picks the processing store (`:154-157`).
  - Writes the event to the Redis processing store with `cache_key = processing_store.store(data)` (`:212`).
  - Transactions branch off to `save_event_transaction` (`:247-261`) and feedback to `save_event_feedback` (`:267`). **Errors** call `preprocess_event(...)` (`:288-306`).
  - Sets the dedup key (`:310`) and sends `event_accepted` (`:314`). Any other exception is re-raised as `Retriable` (`:317-320`).

## 2. Preprocess → `save_event` task

- `preprocess_event` (`src/sentry/tasks/store.py:273`) calls `_do_preprocess_event` (`store.py:123`).
  - If the event needs symbolication or processing, it goes through `submit_symbolicate` / `submit_process` (`store.py:62`) first. Those tasks eventually rejoin the save path.
  - Otherwise `_continue_to_save_event` (`store.py:373`) calls `submit_save_event` (`store.py:91`). That picks `save_event` or `save_event_attachments` (`:104-107`) and runs it inline or with `.delay` (`:117-120`).
- The **`save_event`** task (`store.py:679`) calls **`_do_save_event`** (`store.py:521`):
  - Loads data from the processing store if needed (`:551-552`).
  - Checks the `store.load-shed-save-event-projects` killswitch (`:606-614`).
  - Runs `manager = EventManager(data)` and then `manager.save(project=..., assume_normalized=True, start_time, cache_key, attachments)` (`:616-624`).

## 3. `EventManager.save` / `save_error_events`

- **`EventManager.save`** (`src/sentry/event_manager.py:441`):
  - Normalizes only if needed (`:476-479`) and builds the `job` dict (`:481`).
  - `_pull_out_data` (`:489`, defined at `:660`) creates the `Event` instance (`:691`) and pulls out level, release, environment, tags and so on.
  - Dispatches on type: transactions (`:496`), generic (`:500`), everything else to **`save_error_events`** (`:504-518`).
- **`save_error_events`** (`event_manager.py:521`):
  - Before grouping: release and user (`:535-536`), project key (`:538-543`), and derived tags (`:545-547`).
  - Grouping: **`assign_event_to_group(...)`** (`:550`). A `HashDiscarded` exception (tombstone or load-shed) increments the tombstone counter, discards the event and re-raises (`:552-555`).
  - After grouping: environment and GroupEnvironment (`:564-565`), release-associated models and GroupRelease (`:566-568`), TSDB (`:569`).
  - Stores the event to nodestore (`:582`, `_nodestore_save_many` at `:1083`) and publishes it to the eventstream (`:610`, `_eventstream_insert_many` at `:1114`). From the eventstream it goes to Snuba and post-processing.
  - Then saves attachments (`:619`) and records the accepted outcomes (`:652`).

## 4. Grouping hash calculation

- **`assign_event_to_group`** (`event_manager.py:1318`) calls `get_hashes_and_grouphashes(job, run_primary_grouping, ...)` (`:1327`).
- **`get_hashes_and_grouphashes`** (`event_manager.py:1385`):
  - Runs the hash callback (`:1405`).
  - Calls `get_or_create_grouphashes` (`:1408`).
  - Calls `find_grouphash_with_group` (`:1412`).
- **`run_primary_grouping`** (`src/sentry/grouping/ingest/hashing.py:132`):
  - Loads the project's config with `get_grouping_config_dict_for_project` (`:139`) and stores it on the event data (`:140`).
  - Calls `_calculate_primary_hashes_and_variants` (`:154`), which calls `_calculate_event_grouping` (`hashing.py:50`).
- **`_calculate_event_grouping`** (`hashing.py:50`):
  - Loads the grouping config (`:64`).
  - Sets the default `{{ default }}` fingerprint and applies server-side fingerprint rules (`:67-70`).
  - Normalizes stacktraces for grouping, which affects `in_app` (`:77`).
  - Calls `event.get_hashes_and_variants(config)` (`:80`).
- **`Event.get_hashes_and_variants`** (`src/sentry/services/eventstore/models.py:337`):
  - Builds the variants with `get_grouping_variants` (`:404`, which calls `grouping/api.py:358` `get_grouping_variants_for_event`).
  - Hashes each variant and sorts the `system` variant last (`:346-362`).
  - Writes the result to `event.data["hashes"]` (`:365`).
- **Secondary grouping** (only while a project is moving between grouping configs): `maybe_run_secondary_grouping` (`hashing.py:85`) hashes a deep copy of the event with the old config (`:107-129`).
- **`get_or_create_grouphashes`** (`hashing.py:260`):
  - New secondary hashes are dropped (`:271-279`).
  - For each hash, `_get_or_create_single_grouphash` (`:224`) runs `GroupHash.objects.get_or_create(project, hash)` (`:247`). Rows that already have a group are optionally cached.
  - GroupHash metadata is also written (`:288`).
- **`find_grouphash_with_group`** (`hashing.py:165`) returns the first grouphash that has a `group_id`. If any hash has a `group_tombstone_id`, it raises `HashDiscarded` (`:181-186`).

## 5. Group assignment or creation

`assign_event_to_group` (`event_manager.py:1330-1360`) tries, in order:

1. The primary hashes matched an existing group. That goes to `handle_existing_grouphash` (`:1331`).
2. Otherwise, the secondary hashes matched. Also `handle_existing_grouphash` (`:1337-1343`).
3. Otherwise, a Seer similarity match with `maybe_check_seer_for_matching_grouphash` (`:1351-1356`).
4. Otherwise, **`create_group_with_grouphashes`** (`:1359`).

After that it updates the grouping config if needed (`:1372`) and sets `event.group` and `job["groups"]` (`:1377-1379`).

- **Existing group: `handle_existing_grouphash`** (`event_manager.py:1420`):
  - Fetches the group with `Group.objects.get_from_cache` (`:1448`) and skips non-error group types (`:1454`).
  - Links any new hashes with `add_group_id_to_grouphashes` (`:1463`, defined in `grouping/ingest/utils.py:22`).
  - Calls `_process_existing_aggregate` (`:1465`, defined at `:1900`). It updates last_seen, message, level, culprit and first_seen, and handles regressions (`:1931`).
  - Makes sure the detector association exists (`:1473`) and returns `GroupInfo(is_new=False)`.
- **New group: `create_group_with_grouphashes`** (`event_manager.py:1478`):
  - Runs the load-shed check (`:1491`, defined in `grouping/ingest/utils.py:37`).
  - Opens `transaction.atomic` (`:1499`) and locks the GroupHash rows with `select_for_update()` (`:1516-1520`).
  - Checks again with `find_grouphash_with_group` (`:1526`) — double-checked locking against concurrent events with the same hash. If it loses the race, it falls back to `handle_existing_grouphash` (`:1546`).
  - Otherwise it calls **`_create_group`** (`:1535`), then `associate_new_group_with_detector` (`:1536`) and `add_group_id_to_grouphashes` (`:1537`). It returns `GroupInfo(is_new=True)` (`:1539`).
- **`_create_group`** (`event_manager.py:1549`):
  - Gets the next short ID (`:1556`, `_get_next_short_id` at `:1700`).
  - Sets first_release, `substatus=NEW`, SDK and severity metadata, priority and times_seen (`:1561-1600`).
  - **`Group.objects.create(project, short_id, ...)`** (`:1606`), with a stuck-project-counter retry (`:1613-1635`).
  - `create_open_period` (`:1637`).

Once `save_error_events` finishes, the event (now carrying `group_id`) is in nodestore and the eventstream. `post_process_group` picks it up later to handle alerts, assignment rules and similar.