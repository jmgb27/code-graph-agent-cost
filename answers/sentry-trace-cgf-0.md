Here's how an error event travels from the `ingest-events` Kafka topic to a stored `Group`. I traced this by reading the code, not by running it.

## 1. Kafka consumer
- **Consumer registration:** `src/sentry/consumers/__init__.py:371`. The `"ingest-events"` entry binds `Topic.INGEST_EVENTS` to `sentry.ingest.consumer.factory.IngestStrategyFactory`.
- **Strategy factory:** `IngestStrategyFactory` is at `src/sentry/ingest/consumer/factory.py:78`. `create_with_partitions` (`factory.py:118`) wraps `process_simple_event_message` in a `partial` (`factory.py:128`) for every topic except attachments. Attachments go through `process_attachments_and_events`. There is a multiprocess step and a backpressure step, and it finishes with `CommitOffsets`.
- **Message decoding:** `process_simple_event_message` (`src/sentry/ingest/consumer/simple_event.py:25`):
  - Unpacks the msgpack envelope (`:54`) and rejects anything that isn't `type == "event"` (`:59`).
  - Loads the `Project` from cache (`:64`) and calls `process_event` (`:68`).
  - Other exceptions become `InvalidMessage`, which sends the message to the DLQ (`:83`). `Retriable` exceptions are re-raised instead.
  - There's a second entry point: the taskbroker raw-mode task `process_event_from_kafka` (`:92`). It feeds the same `process_event` (`:124`) and can set `inline_save_event`.
- **Filtering and routing:** `process_event` (`src/sentry/ingest/consumer/processors.py:79`):
  - Checks the deduplication key `ev:{project_id}:{event_id}` (`:117-131`).
  - Checks the load-shed killswitches (`:133`, `:165`).
  - Parses the JSON payload (`:150`) and picks `event_processing_store` for error events (`:154-157`).
  - Stores attachments (`:203`) and writes the payload to the processing store with `processing_store.store(data)` (`:212`), which returns `cache_key`.
  - Transactions go to `save_event_transaction` and feedback goes to `save_event_feedback`. Errors fall through to `preprocess_event(...)` (`:288-306`).

## 2. Preprocess, symbolicate, process, then `save_event`
All of this is in `src/sentry/tasks/store.py`:
- `preprocess_event` (`:273`) calls `_do_preprocess_event` (`:123`). That function checks whether the event needs symbolication (`:209-217`):
  - If it does, `submit_symbolicate` runs (`:233`).
  - If it needs processing, `submit_process` runs and leads to `do_process_event` (`:248-256`).
  - Otherwise it goes straight to `submit_save_event` (`:259`).
- `do_process_event` (`:343`) does the following:
  - Runs a second datascrubbing pass (`:412`) and then the platform preprocessors (`:421-437`).
  - Re-normalizes the event if it changed (`:451`).
  - Calls `_continue_to_save_event()` (`:373`, `:456`), which calls `submit_save_event`.
- `submit_save_event` (`:91`) picks either `save_event` or `save_event_attachments` (`:104-107`). It runs the task inline or calls `.delay()` on it (`:117-120`).
- The `save_event` task (`:679`) calls `_do_save_event(..., consumer_type=ConsumerType.Events)` (`:687`).
- `_do_save_event` (from `:532`):
  - Loads the data from the processing store by `cache_key` (`:551-552`) and resolves the project (`:597`).
  - Checks the `store.load-shed-save-event-projects` killswitch (`:606`).
  - Calls `EventManager(data)` (`:616`) and then `manager.save(project=..., assume_normalized=True, ...)` (`:618`).
  - In a `finally`-style cleanup, deletes the processing-store key (`:654`) and cached attachments (`:665`).

## 3. `EventManager.save`, then `save_error_events`
All in `src/sentry/event_manager.py`:
- `EventManager.save` (`:441`):
  - Normalizes the event only if it wasn't already normalized (`:476-479`).
  - Builds the `job` dict (`:481`) and calls `_pull_out_data` (`:489`), which creates `job["event"]`.
  - Dispatches on type: transaction goes to `:496`, generic to `:500`, and anything else counts as an error. For errors it sets `in_grouping_transition` and calls `self.save_error_events(...)` (`:505-518`).
- `save_error_events` (`:521`):
  - Handles releases and users (`:535-536`), then derives tags (`:545-547`).
  - Calls `assign_event_to_group(event=job["event"], job=job, metric_tags=...)` (`:550`). If that raises `HashDiscarded` (a tombstone or load-shed), the event is discarded (`:552-555`).
  - Once a group is known, it writes the environment and GroupEnvironment rows, release links, GroupRelease rows and TSDB counts (`:564-569`).
  - Calls `_nodestore_save_many` (`:582`, defined at `:1083`) and sets `first_event` (`:585`).
  - Calls `_eventstream_insert_many` (`:610`). This is where the event reaches Snuba and post-processing.
  - Saves attachments (`:619`, `:628`).

## 4. Grouping hash calculation
- `assign_event_to_group` (`event_manager.py:1318`) first calls `get_hashes_and_grouphashes(job, run_primary_grouping, ...)` (`:1327`).
- `get_hashes_and_grouphashes` (`event_manager.py:1385`):
  - Calls the hashing function (`:1405`).
  - Calls `get_or_create_grouphashes` (`:1408`).
  - Calls `find_grouphash_with_group` (`:1412`).
  - Returns a `GroupHashInfo`.
- `run_primary_grouping` (`src/sentry/grouping/ingest/hashing.py:132`) loads the project's grouping config with `get_grouping_config_dict_for_project` (`:139`). It stores the config in `job["data"]["grouping_config"]` and then calls `_calculate_primary_hashes_and_variants`, which calls `_calculate_event_grouping` (`:149`, `:162`).
- `_calculate_event_grouping` (`hashing.py:50`) does four things in order:
  1. Loads the config (`:64`).
  2. Applies server-side fingerprinting rules (`:67-70`).
  3. Runs `event.normalize_stacktraces_for_grouping` (`:77`).
  4. Calls `event.get_hashes_and_variants(...)` (`:80`).
- `Event.get_hashes_and_variants` (`src/sentry/services/eventstore/models.py:337`):
  - Calls `get_grouping_variants` (`:345`, defined at `:404`), which calls `get_grouping_variants_for_event` (`:459`).
  - Takes `variant.get_hash()` for each variant (`:346-348`) and sorts so the `system` variant comes last (`:352`).
- `get_grouping_variants_for_event` (`src/sentry/grouping/api.py:358`):
  - Checksum shortcut: if a checksum is set, it's the only variant (`:366-373`).
  - Otherwise it resolves the fingerprint (`:387-399`) and runs the strategy components through `_get_variants_from_strategies` (`:410`). The strategies are tried in priority order (`:290`).
  - It then handles custom or hybrid fingerprint variants (`:422`+).
  - Hash values ultimately come from `hash_from_values` (`src/sentry/grouping/utils.py:20`).
- `get_or_create_grouphashes` (`hashing.py:260`):
  - For the secondary config, it drops hashes that don't already exist (`:271-279`).
  - For each hash, it calls `_get_or_create_single_grouphash` (`:224`, `:282`), which is cached for 60 seconds, then writes GroupHash metadata (`:288`).
- `find_grouphash_with_group` (`hashing.py:165`) returns the first grouphash that already has a `group_id`. If any of the hashes has a `group_tombstone_id`, it raises `HashDiscarded` (`:181-186`).

## 5. Assigning to an existing group or creating a new one
Back in `assign_event_to_group` (`event_manager.py:1318-1381`):
1. **Primary hit:** a primary hash already points to a group, so it calls `handle_existing_grouphash` (`:1330-1333`).
2. **Otherwise it tries secondary grouping:** `get_hashes_and_grouphashes(job, maybe_run_secondary_grouping, ...)` (`:1337`). This only does work while the project is moving between grouping configs. A hit there calls `handle_existing_grouphash` with all the grouphashes (`:1340-1343`).
3. **Otherwise it asks Seer:** `maybe_check_seer_for_matching_grouphash` looks for a similar existing issue (`:1351-1356`).
4. **Otherwise it creates a group:** `create_group_with_grouphashes(job, all_grouphashes)` (`:1359`).
5. **Housekeeping:** records hash metrics (`:1364`), updates the grouping config if needed (`:1372`), sets `event.group = group_info.group` (`:1378`) and `job["groups"] = [group_info]` (`:1379`).

- **Existing group:** `handle_existing_grouphash` (`:1420`):
  - Loads the `Group` from cache (`:1448`) and bails out if it's a non-error group (`:1454`).
  - Links any new hashes to the group with `add_group_id_to_grouphashes` (`:1463`).
  - Updates the group and detects regressions via `_process_existing_aggregate` (`:1465`), then calls `ensure_association_with_detector` (`:1473`).
  - Returns `GroupInfo(is_new=False, ...)`.
- **New group:** `create_group_with_grouphashes` (`:1478`):
  - Checks the load-shed switch (`:1491`) and opens `transaction.atomic` (`:1499`).
  - Locks the rows with `GroupHash.objects...select_for_update()` (`:1516-1520`), then re-checks `find_grouphash_with_group` (`:1526`). This is double-checked locking.
  - If there's still no group, it calls `_create_group` (`:1535`), `associate_new_group_with_detector` (`:1536`) and `add_group_id_to_grouphashes` (`:1537`), and returns `GroupInfo(is_new=True)`.
  - If another worker won the race, it falls back to `handle_existing_grouphash` (`:1546`).
- `_create_group` (`:1549`):
  - Gets the next short ID (`:1556`) and fills in severity, priority and metadata (`:1574-1593`), with `times_seen=1` or a sample-rate-weighted value (`:1596-1600`).
  - Calls `Group.objects.create(...)` (`:1606`). If that hits the stuck short-ID counter, it retries with a new ID (`:1613-1630`).
  - Calls `create_open_period` (`:1637`).

Control then returns to `save_error_events` (`:557`+), which writes the environment and release rows, nodestore and eventstream as listed in section 3. Post-processing (alerts and workflows) is triggered from the eventstream.