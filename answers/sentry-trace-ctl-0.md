Here's how an error event gets from the `ingest-events` Kafka topic to a stored issue (`Group`). I read the code to build this and ran nothing.

## 1. Kafka consumer

- **Consumer registration:** `src/sentry/consumers/__init__.py:371-377`. The `"ingest-events"` consumer reads `Topic.INGEST_EVENTS` using `IngestStrategyFactory` with `consumer_type=ConsumerType.Events`.
- **`IngestStrategyFactory.create_with_partitions`** (`src/sentry/ingest/consumer/factory.py:118-139`): for any topic other than attachments, it wraps `process_simple_event_message` in a `partial` and chains a multiprocess step, a backpressure step and `CommitOffsets`.
- **`process_simple_event_message`** (`src/sentry/ingest/consumer/simple_event.py:25-83`):
  - Unpacks the msgpack envelope (`:54`), rejects any type other than `"event"` (`:59`) and loads the `Project` from cache (`:64`).
  - Calls `processors.process_event` (`:68`).
  - Non-`Retriable` errors are turned into `InvalidMessage`, which sends the message to the DLQ (`:76-83`).
  - There's another entry point: `process_event_from_kafka` (`simple_event.py:92`) is spawned directly by taskbroker in "raw mode" and can save inline based on options (`:129-130`).
- **`processors.process_event`** (`src/sentry/ingest/consumer/processors.py:79`):
  - Checks a dedup cache key `ev:{project_id}:{event_id}` (`:117-131`) and two load-shed killswitches (`:133`, `:162`).
  - Parses the JSON payload with `orjson.loads` (`:150`).
  - Stores attachments (`:203`) and writes the payload to `event_processing_store` (Redis), which returns the `cache_key` (`:212`).
  - Transactions and feedback branch off here (`:247`, `:267`). Error events go to `preprocess_event(...)` (`:288-306`).
  - Afterwards it sets the dedup key (`:310`) and sends `event_accepted` (`:314`). Any other exception becomes `Retriable` (`:317-320`).

## 2. Preprocess, symbolicate/process, then `save_event`

All of these are in `src/sentry/tasks/store.py`:

- **`preprocess_event`** (`:273`) calls **`_do_preprocess_event`** (`:123`):
  - GPU-crash events go to their own task (`:183-203`).
  - Events that need symbolication are backed up for reprocessing (`reprocessing2.backup_unprocessed_event`) and sent to `submit_symbolicate` (`:209-244`).
  - Events that need plugin preprocessors (`should_process`, `:51`) go to `submit_process` (`:248-257`), which runs the `process_event` task (`:465`) → `do_process_event` (`:343`). That step runs the preprocessors (`:421-437`), re-normalizes and re-stores the event if it changed (`:446-454`), then calls `submit_save_event` (`:373-385`, `:456`).
  - Otherwise it goes straight to `submit_save_event` (`:259-270`).
- **`submit_save_event`** (`:91-120`) picks `save_event_attachments` or `save_event` and either calls it inline or with `.delay()`.
- **`save_event` task** (`:673-695`) calls **`_do_save_event`** (`:521`):
  - Reloads the data from the processing store by `cache_key` (`:551-552`) and resolves the project (`:597`).
  - Checks the `store.load-shed-save-event-projects` killswitch (`:606-614`).
  - Runs `EventManager(data)` and `manager.save(project=..., assume_normalized=True, ...)` (`:616-624`).
  - Writes the updated payload back to Redis for post-process (`:627-633`), unless the `post_process.delete-processing-store-in-save-event` option is on. In that case it deletes the payload in the `finally` block (`:647-654`).
  - `HashDiscarded` deletes the cached payload (`:635-642`).

## 3. `EventManager.save` → `save_error_events`

In `src/sentry/event_manager.py`:

- **`EventManager.save`** (`:441`) normalizes if needed (skipped here because `assume_normalized=True`) (`:476-479`). It then builds a `job` dict (`:481`), and `_pull_out_data` builds the `Event` object (`:489`, defined at `:660`).
  - Transaction and generic events branch off (`:496-503`). Error events go to `save_error_events` (`:504-518`).
- **`save_error_events`** (`:521`):
  - Before grouping: release (`:535`), user (`:536`), tags (`:545-547`).
  - **Grouping and group assignment:** `assign_event_to_group(...)` (`:550`). On `HashDiscarded` (a tombstone or load shed), it runs `discard_event` and re-raises (`:552-555`).
  - After a group is assigned: environment, group environment, release models, group release and TSDB counters (`:564-569`).
  - `_nodestore_save_many` saves the event body to nodestore (`:582`, defined at `:1083`).
  - `_eventstream_insert_many` publishes to the eventstream, which feeds Snuba and post-process (`:610`, defined at `:1114`).
  - Then attachments (`:618-634`) and the accepted outcome (`:652`).

## 4. Grouping hash calculation

- **`assign_event_to_group`** (`event_manager.py:1318`) runs primary grouping via `get_hashes_and_grouphashes(job, run_primary_grouping, ...)` (`:1327`).
- **`get_hashes_and_grouphashes`** (`:1385`):
  - Calls the hash function (`:1405`).
  - `get_or_create_grouphashes` (`:1408`) gets or creates a `GroupHash` row per hash.
  - `find_grouphash_with_group` (`:1412`) finds the first hash that already has a group.

In `src/sentry/grouping/ingest/hashing.py`:

- **`run_primary_grouping`** (`:132`) gets the project's grouping config and saves it into `job["data"]["grouping_config"]` (`:139-140`). It then calls `_calculate_primary_hashes_and_variants` (`:154`), which calls **`_calculate_event_grouping`** (`:50`). That function:
  1. Loads the strategy config (`:64`).
  2. Applies server-side fingerprint rules (`:67-70`).
  3. Normalizes stacktraces for grouping, which sets in-app via enhancements (`:77`, implemented at `services/eventstore/models.py:392`).
  4. Calls `event.get_hashes_and_variants(...)` (`:80`).
- **`Event.get_hashes_and_variants`** (`src/sentry/services/eventstore/models.py:337`):
  - Calls `get_grouping_variants` (`:404`), which calls `grouping/api.py:get_grouping_variants_for_event` (`:358`). That function handles:
    - checksum variants (`:366-373`)
    - fingerprint resolution (`:387-399`)
    - strategy variants such as app/system/default (`:410`)
    - custom or hybrid fingerprint variants (`:422-447`)
    - a fallback variant (`:456-457`)
  - Hashes each variant with `variant.get_hash()` (`models.py:346-348`), sorts the `system` variant last (`:352-355`) and writes the result to `event.data["hashes"]` (`:365`).
- **`get_or_create_grouphashes`** (`hashing.py:260`):
  - Secondary hashes are kept only if they already exist (`:271-279`).
  - Each hash goes through `_get_or_create_single_grouphash`, which does a cached `GroupHash.objects.get_or_create` (`:224-257`, `:247`).
  - Grouphash metadata is written if that's enabled (`:284-298`).
- **`find_grouphash_with_group`** (`hashing.py:165`) returns the first grouphash with a `group_id` and raises `HashDiscarded` if any hash is tombstoned (`:181-186`).
- **Secondary grouping:** if the project is in a grouping-config transition, `maybe_run_secondary_grouping` (`:85`) computes hashes with the old config on a deep copy of the event (`:107-129`).

## 5. Group creation or assignment

The decision tree is in `assign_event_to_group` (`event_manager.py:1330-1360`):

1. **Primary hash matches an existing group:** `handle_existing_grouphash` (`:1331`).
2. **Otherwise, the secondary hash matches:** `handle_existing_grouphash` with all grouphashes (`:1340-1344`).
3. **Otherwise, Seer similarity finds a match:** `maybe_check_seer_for_matching_grouphash` (`:1351-1356`).
4. **Otherwise:** `create_group_with_grouphashes` (`:1359`).

Afterwards it records metrics, may update the grouping config (`:1364-1372`) and sets `event.group` (`:1377-1379`).

**Existing group: `handle_existing_grouphash`** (`:1420`)
- Loads the group with `Group.objects.get_from_cache` (`:1448`) and returns `None` for non-error group types (`:1454`).
- `add_group_id_to_grouphashes` links any new hashes to the group (`:1463`, defined at `grouping/ingest/utils.py:22-34`).
- `_process_existing_aggregate` updates the group and detects regressions (`:1465`, defined at `:1900`; regressions are handled by `_handle_regression` at `:1711`).
- `ensure_association_with_detector` (`:1473`), then it returns `GroupInfo(is_new=False)`.

**New group: `create_group_with_grouphashes`** (`:1478`)
- Checks the group-creation load-shed killswitch (`:1491`, defined at `grouping/ingest/utils.py:37`).
- Inside `transaction.atomic`, it locks the grouphash rows with `select_for_update()` (`:1516-1520`) and checks again for a group (`:1526`). This double-checked locking handles races between identical events.
- If there's still no group: `_create_group` (`:1535`), `associate_new_group_with_detector` (`:1536`), then `add_group_id_to_grouphashes` (`:1537`), and it returns `GroupInfo(is_new=True)`.
- If another process won the race, it falls back to `handle_existing_grouphash` (`:1546`).

**`_create_group`** (`:1549`)
- Gets the next short ID (`:1556`, `_get_next_short_id` at `:1700`).
- Adds SDK and severity metadata (`:1571-1584`), sets priority (`:1587-1592`) and sets `times_seen` (`:1596-1600`).
- `Group.objects.create(...)` (`:1606`). If the project short-ID counter is stuck, it retries on `IntegrityError` (`:1613-1635`).
- `create_open_period` (`:1637`).

## Summary chain

`IngestStrategyFactory` → `process_simple_event_message` → `processors.process_event` (Redis store) → `preprocess_event` → [symbolicate / `process_event`] → `save_event` → `_do_save_event` → `EventManager.save` → `save_error_events` → `assign_event_to_group` → `run_primary_grouping` → `_calculate_event_grouping` → `Event.get_hashes_and_variants` → `get_or_create_grouphashes` / `find_grouphash_with_group` → `handle_existing_grouphash` **or** `create_group_with_grouphashes` → `_create_group` → then nodestore save and eventstream insert, which feeds Snuba and post-process.