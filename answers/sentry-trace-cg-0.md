An error event goes through Kafka, then the preprocess/process tasks, then `save_event`, then `EventManager.save`, where grouping produces hashes that either match an existing `Group` or create a new one. Paths are relative to `src/sentry/`.

## 1. Ingest Kafka consumer

- **Consumer registration:** `consumers/__init__.py:371` registers the `"ingest-events"` consumer, whose `strategy_factory` is `sentry.ingest.consumer.factory.IngestStrategyFactory` (`:373`).
- **Strategy:** `IngestStrategyFactory.create_with_partitions` (`ingest/consumer/factory.py:118`) wraps `process_simple_event_message` in a `partial` (`:128-133`). That step can run multiprocessed and behind backpressure, and it ends in `CommitOffsets`.
- **Message decode:** `process_simple_event_message` (`ingest/consumer/simple_event.py:25`):
  - It msgpack-decodes the Relay envelope and rejects any message whose type isn't `"event"`.
  - It loads the project with `Project.objects.get_from_cache`.
  - It then calls `processors.process_event`.
- **`process_event`** (`ingest/consumer/processors.py:79`):
  - Deduplicates on the `ev:{project_id}:{event_id}` cache key (`:117-131`).
  - Checks the load-shed killswitches (`:133`, `:162`) and parses the JSON with orjson (`:150`).
  - Stores attachments, then writes the payload to `event_processing_store` in Redis to get a `cache_key` (`:198-212`).
  - Error events go to the `else` branch and call `preprocess_event(...)` (`:288-306`). Transactions and feedback take other branches (`:247`, `:267`).
  - Sets the dedup key (`:310`) and sends the `event_accepted` signal (`:314`).

## 2. Preprocess / process, then `save_event`

- **`preprocess_event`** (`tasks/store.py:273`) calls `_do_preprocess_event` (`:123`), which picks one of three routes:
  - If the event needs symbolication, it calls `submit_symbolicate` (`:233`).
  - If it needs processing (plugins, enhancers, etc.), it calls `submit_process` (`:248-257`). `do_process_event` (`:343`) later continues to save via `_continue_to_save_event` (`:373`).
  - Otherwise it goes straight to `submit_save_event` (`:259`).
- **`submit_save_event`** (`tasks/store.py:91`) picks `save_event_attachments` or `save_event`. It runs the task with `.delay()`, or inline when `inline=True`.
- **`save_event` task** (`tasks/store.py:679`, registered as `sentry.tasks.store.save_event`) calls `_do_save_event(..., consumer_type=ConsumerType.Events)`.
- **`_do_save_event`** (`tasks/store.py:521`):
  - Reloads `data` from the processing store using `cache_key` (`:551-552`).
  - Resolves the project (`:597`) and checks the `store.load-shed-save-event-projects` killswitch (`:606`).
  - Runs `EventManager(data).save(project=..., assume_normalized=True, ...)` (`:616-624`).
  - Writes the updated payload back to Redis for post-processing (`:628-633`).
  - Handles `HashDiscarded` by deleting the cached payload (`:635`).

## 3. `EventManager.save`

- **`EventManager.save`** (`event_manager.py:441`):
  - Normalizes the event if needed (`:476`).
  - Builds the `job` dict and calls `_pull_out_data` (`:660`). That builds the `Event` object, copies level, logger, environment and transaction into tags, and sets `job["groups"] = []`.
  - Transactions (`:496`) and generic events (`:500`) branch off here. Errors call `save_error_events` (`:516`).
- **`save_error_events`** (`event_manager.py:521`) runs these steps in order:
  1. Releases (`:535`), the event user (`:536`), the project key (`:538`), and tag derivation (`:545-547`).
  2. **`assign_event_to_group(...)`** (`:550`). If it raises `HashDiscarded` because the hash matches a tombstone, the event is discarded (`:552-555`).
  3. Environments, `GroupEnvironment`, release models, `GroupRelease` and TSDB counters (`:564-569`).
  4. Writes the event body to nodestore with `_nodestore_save_many` (`:582`, defined at `:1083`).
  5. Sets `project.first_event` (`:585`) and handles reprocessing cleanup (`:599`).
  6. Inserts into the eventstream with `_eventstream_insert_many` (`:610`, defined at `:1114`). Snuba and post-process pick the event up from there.
  7. Saves attachments (`:619`, `:628`) and records the accepted outcome (`:652`).

## 4. Grouping hash calculation

- **`assign_event_to_group`** (`event_manager.py:1318`) calls `get_hashes_and_grouphashes(job, run_primary_grouping, ...)` (`:1327`).
- **`get_hashes_and_grouphashes`** (`event_manager.py:1385`) does three things:
  - Calls the hash function (`:1405`).
  - Turns the hashes into `GroupHash` rows with `get_or_create_grouphashes` (`:1408`).
  - Looks for one that already has a group with `find_grouphash_with_group` (`:1412`).
- **`run_primary_grouping`** (`grouping/ingest/hashing.py:132`) loads the project's grouping config and stores it in `job["data"]["grouping_config"]` (`:139-140`). It then goes through `_calculate_primary_hashes_and_variants` (`:154`) to `_calculate_event_grouping` (`:50`), which:
  - Loads the strategy config (`:64`).
  - Applies server-side fingerprint rules with `apply_server_side_fingerprinting` (`:66-70`).
  - Normalizes stacktraces for grouping, which sets in-app flags (`:77`).
  - Calls `event.get_hashes_and_variants(config)` (`:80`).
- **`Event.get_hashes_and_variants`** (`services/eventstore/models.py:337`):
  - Calls `get_grouping_variants` (`:404`), which calls `get_grouping_variants_for_event` (`grouping/api.py:358`).
  - That function handles a checksum, resolves the fingerprint, and runs the grouping strategies to build the app, system, default or fingerprint variants.
  - Each variant's `get_hash()` calls `hash_from_values` (`grouping/variants.py:210`, `:271`).
  - Hashes are sorted with the system hash last and written to `event.data["hashes"]`. `get_primary_hash()` (`:461`) returns `hashes[0]`.
- **`get_or_create_grouphashes`** (`grouping/ingest/hashing.py:260`):
  - Secondary hashes are kept only if a row for them already exists (`:271-279`).
  - For each hash, `_get_or_create_single_grouphash` (`:224`) runs `GroupHash.objects.get_or_create(project, hash)` (`:247`), with an optional 60s cache.
  - It also writes grouphash metadata (`:288`).
- **`find_grouphash_with_group`** (`grouping/ingest/hashing.py:165`) returns the first grouphash that has a `group_id`. It raises `HashDiscarded` if any grouphash has a `group_tombstone_id` (`:181-186`).

## 5. Group assignment or creation

Back in `assign_event_to_group` (`event_manager.py:1318`), the lookup runs in this order:

1. **Primary match** (`:1330`): calls `handle_existing_grouphash`.
2. **Otherwise, secondary config** (`:1337`): used while the project is switching grouping configs. It runs `maybe_run_secondary_grouping` (`hashing.py:85`); a match (`:1340`) goes to `handle_existing_grouphash`.
3. **Otherwise, Seer similarity** (`:1351`): `maybe_check_seer_for_matching_grouphash`; a match goes to `handle_existing_grouphash`.
4. **Otherwise, a new group** (`:1359`): `create_group_with_grouphashes`.

After that it may update the project's grouping config (`:1372`), then sets `event.group` and `job["groups"]` (`:1377-1379`).

**Existing group:** `handle_existing_grouphash` (`event_manager.py:1420`):
- Loads the group with `Group.objects.get_from_cache` (`:1448`) and gives up if it's not an error-type group (`:1454`).
- Links any new hashes to the group with `add_group_id_to_grouphashes` (`:1463`, defined at `grouping/ingest/utils.py:22`).
- Calls `_process_existing_aggregate` (`:1900`). That merges `last_seen`, message, level, culprit, `first_seen` and title/metadata, and checks for regressions with `_handle_regression` (`:1711`). It then writes through the buffer with `buffer_incr(Group, {"times_seen": ...}, ...)` (`:1963`).
- Ensures the detector association (`:1473`) and returns `GroupInfo(is_new=False, is_regression=...)`.

**New group:** `create_group_with_grouphashes` (`event_manager.py:1478`):
- Checks the load-shed killswitch for group creation (`:1491`).
- Opens `transaction.atomic` and locks the grouphash rows with `select_for_update()` (`:1499-1520`).
- Runs `find_grouphash_with_group` again (`:1526`). This double-checked lock covers the case where another worker created the group first; if so, it falls back to `handle_existing_grouphash` (`:1546`).
- Otherwise, calls `_create_group(project, event, **_get_group_processing_kwargs(job))` (`:1535`; the kwargs come from `:882`).
- Links the detector and grouphashes (`:1536-1537`) and returns `GroupInfo(is_new=True)`.

**`_create_group`** (`event_manager.py:1549`):
- Gets the next short ID with `_get_next_short_id` → `project.next_short_id` (`:1556`, `:1700`). A timeout here raises `HashDiscarded`.
- Adds SDK and severity metadata and sets the priority (`:1571-1592`), and sets `times_seen` (`:1596-1600`).
- **Creates the row with `Group.objects.create(project=..., short_id=..., ...)` (`:1606`).**
- Retries once if the project's short-ID counter is stuck behind existing groups (`:1613-1630`).
- Finishes with `create_open_period` (`:1637`).

With the group resolved, `save_error_events` continues to the nodestore write and eventstream insert described in section 3. Post-process (alerts, workflows) runs later from the eventstream.