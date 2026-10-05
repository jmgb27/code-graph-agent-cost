Here is the path an error event takes, traced by reading the code. Nothing was edited.

## 1. Kafka consumer (ingest-events)

- **Consumer registration:** `src/sentry/consumers/__init__.py:371` maps `"ingest-events"` to `sentry.ingest.consumer.factory.IngestStrategyFactory`.
- **Strategy:** `IngestStrategyFactory.create_with_partitions` at `src/sentry/ingest/consumer/factory.py:118`. For topics other than attachments, it wraps `process_simple_event_message` (`factory.py:128-134`) in a step that can run across multiple processes, adds backpressure, then commits offsets.
- **Per-message handling:** `process_simple_event_message` at `src/sentry/ingest/consumer/simple_event.py:25`:
  - msgpack-decodes the message (`:54`).
  - Loads the `Project` from cache (`:64`).
  - Calls `processors.process_event` (`:68`).
  - Errors that shouldn't be retried become `InvalidMessage`, which sends them to the DLQ (`:83`).
  - There is a second entry point with the same logic: the taskbroker "raw mode" task `process_event_from_kafka` (`simple_event.py:92`).
- **`process_event`** at `src/sentry/ingest/consumer/processors.py:79`:
  - Dedup check on `ev:{project_id}:{event_id}` (`:118-131`).
  - Load-shed killswitches (`:134`, `:165`).
  - `orjson.loads` of the payload (`:150`).
  - Writes the payload to the event processing store in Redis (`:212`).
  - Transactions branch to `save_event_transaction` (`:247-261`) and feedback to `save_event_feedback` (`:267`). Errors fall through to `preprocess_event(...)`, which is called directly in the consumer (`:306`).
  - Sets the dedup cache entry (`:310`).

## 2. Preprocess, process, then `save_event` (`src/sentry/tasks/store.py`)

- **`_do_preprocess_event`** (`store.py:123`):
  - GPU crashes go to their own task (`:183-203`).
  - Events that need symbolication go to `submit_symbolicate` (`:218-244`).
  - Events that need processing go to `submit_process`, which enqueues the `process_event` task (`:248-257`, `:62`).
  - Everything else goes straight to `submit_save_event` (`:259`).
- **`do_process_event`** (`store.py:343`, task at `:465`): re-scrubs data, runs plugin preprocessors (`:421-437`), re-normalizes and re-stores if anything changed (`:446-454`), then calls `submit_save_event` (`:373-388`).
- **`submit_save_event`** (`store.py:91`): chooses `save_event` or `save_event_attachments` (`:104-107`) and either calls it inline or enqueues it with `.delay` (`:117-120`).
- **`save_event` task** (`store.py:679`) calls `_do_save_event(..., consumer_type=ConsumerType.Events)` (`:687`).
- **`_do_save_event`** (`store.py:521`):
  - Loads data from the processing store (`:552`) and resolves the project (`:597`).
  - Checks the `store.load-shed-save-event-projects` killswitch (`:606`).
  - Runs **`EventManager(data).save(project=..., assume_normalized=True, ...)`** (`:616-624`).
  - Writes the updated payload back to Redis so post-processing can read it (`:628-633`).
  - `HashDiscarded` deletes the cached payload (`:635-642`).

## 3. `EventManager.save` → `save_error_events` (`src/sentry/event_manager.py`)

- **`save`** (`:441`):
  - Normalizes the event if needed (`:476-479`).
  - Builds the `job` dict (`:481`).
  - `_pull_out_data` (`:489`, defined at `:659`) creates the `Event` instance and copies release, env, level and other fields into tags.
  - Routes by type: transaction (`:496`), generic (`:500`), otherwise **`save_error_events`** (`:516`).
- **`save_error_events`** (`:521`):
  1. Releases, users, tags and the sampling rate (`:535-547`).
  2. **`assign_event_to_group(...)`** (`:550`). `HashDiscarded` (tombstones or load shedding) leads to `discard_event` (`:552-555`).
  3. Environment, GroupEnvironment, release models, GroupRelease, TSDB (`:564-569`).
  4. `_nodestore_save_many` (`:582`, def `:1083`).
  5. Sets `project.first_event` and sends the `first_event_received` signal (`:585-589`).
  6. `_eventstream_insert_many` (`:610`, def `:1114`) sends the event to Kafka for Snuba and post-processing.
  7. Attachments and the accepted outcome (`:619-652`).

## 4. Grouping hash calculation

- **`assign_event_to_group`** (`event_manager.py:1318`) calls **`get_hashes_and_grouphashes(job, run_primary_grouping, ...)`** (`:1327`, def `:1384`). That function:
  - Runs the hash function (`:1405`).
  - Calls `get_or_create_grouphashes` (`:1408`).
  - Calls `find_grouphash_with_group` (`:1412`).
- **`run_primary_grouping`** (`src/sentry/grouping/ingest/hashing.py:132`):
  - Gets the project's config with `get_grouping_config_dict_for_project` (`:139`, defined at `grouping/api.py:151`) and stores it in `job["data"]["grouping_config"]` (`:140`).
  - Calls `_calculate_primary_hashes_and_variants` (`:154`), which calls **`_calculate_event_grouping`** (`:50`).
- **`_calculate_event_grouping`**:
  - `load_grouping_config` (`:64`).
  - Server-side fingerprinting with a default of `["{{ default }}"]` (`:67-70`).
  - `event.normalize_stacktraces_for_grouping` (`:77`, which runs `services/eventstore/models.py:392` and then `stacktraces/processing.py:151`).
  - **`event.get_hashes_and_variants`** (`:80`).
- **`Event.get_hashes_and_variants`** (`src/sentry/services/eventstore/models.py:337`):
  - `get_grouping_variants` (`:404`, which calls `get_grouping_variants_for_event` at `grouping/api.py:358`) returns the variants, and each variant's `get_hash()` gives its hash (`:346-348`).
  - The `system` variant is sorted last (`:352-355`), `None` hashes are dropped, and the result is written to `event.data["hashes"]` (`:365`).
- **Secondary grouping**, used only during a grouping-config transition: `maybe_run_secondary_grouping` (`hashing.py:85`) calls `_calculate_secondary_hashes` (`:107`), which runs on a deep copy of the event (`:122`).
- **GroupHash rows:** `get_or_create_grouphashes` (`hashing.py:260`):
  - For the secondary config, it keeps only hashes that already exist (`:271-279`).
  - Calls `_get_or_create_single_grouphash`, which is `GroupHash.objects.get_or_create(project, hash)` with a 60s cache (`:224`, `:247`).
  - Writes grouphash metadata (`:284-290`).
- **`find_grouphash_with_group`** (`hashing.py:165`) returns the first grouphash that has a `group_id`. If any grouphash has a `group_tombstone_id`, it raises `HashDiscarded` (`:181-186`).

## 5. Group assignment or creation

The decision is made in `assign_event_to_group` (`event_manager.py:1318`):

1. **Primary hash matched:** `handle_existing_grouphash` (`:1330-1331`).
2. **Otherwise, secondary hash matched:** `handle_existing_grouphash` with primary and secondary grouphashes combined (`:1337-1343`).
3. **Otherwise, Seer similarity match:** `maybe_check_seer_for_matching_grouphash` (`:1351-1356`).
4. **Otherwise, new group:** `create_group_with_grouphashes` (`:1359`).

After that, it records metrics, may update the project's grouping config (`:1364-1372`), and sets `event.group` and `job["groups"]` (`:1377-1379`).

**Existing group:** `handle_existing_grouphash` (`:1420`)
- Loads the `Group` from cache (`:1448`).
- Returns `None` if it's a non-error group (`:1454`, check at `grouping/ingest/utils.py:51`).
- `add_group_id_to_grouphashes` links any new hashes to this group (`:1463`, defined at `grouping/ingest/utils.py:22`).
- `_process_existing_aggregate` (`:1465`, def `:1900`):
  - Updates `last_seen`, message, level, culprit, `first_seen` and merged data/metadata.
  - Checks for a regression with `_handle_regression` (`:1931`, def `:1711`).
  - Increments `times_seen` through `buffer_incr` (`:1963`).
- `ensure_association_with_detector` (`:1473`), then returns `GroupInfo(is_new=False)`.

**New group:** `create_group_with_grouphashes` (`:1478`)
- Load-shed check (`:1491`, `grouping/ingest/utils.py:37`).
- Inside `transaction.atomic`, it locks the GroupHash rows with `select_for_update()` (`:1516-1520`).
- It checks again with `find_grouphash_with_group` (`:1526`). This double-checked lock is what stops two identical events from both creating a group.
- If there's still no group: `_create_group` (`:1535`), then `associate_new_group_with_detector` (`:1536`), then `add_group_id_to_grouphashes` (`:1537`), and returns `GroupInfo(is_new=True)`.
- If another worker created the group first, it falls back to `handle_existing_grouphash` (`:1546`).

**`_create_group`** (`:1549`)
- Gets the next short ID from `project.next_short_id` (`:1556`, `:1700`).
- Sets `first_release_id`, `substatus=NEW`, SDK and severity metadata, priority and `times_seen` (`:1561-1600`).
- **`Group.objects.create(...)`** (`:1606`). If an `IntegrityError` is caused by the "stuck project counter" problem, it repairs the counter and retries (`:1613-1630`).
- `create_open_period` (`:1637`).

Control then returns to `save_error_events` (step 3), which saves to nodestore and inserts into the eventstream. Post-processing and Snuba pick the event up from there.