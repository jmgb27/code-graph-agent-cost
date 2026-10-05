Here is the path an error event takes from the `ingest-events` Kafka topic to a stored `Group`. I only read files; nothing was edited.

## 1. Kafka consumer

- **Consumer registration.** `src/sentry/consumers/__init__.py:371` maps `"ingest-events"` to `IngestStrategyFactory` with `consumer_type=ConsumerType.Events` and a DLQ topic.
- **Strategy.** `IngestStrategyFactory.create_with_partitions` (`src/sentry/ingest/consumer/factory.py:118`) wraps `process_simple_event_message` in a `partial` (`:128`). It then adds optional multiprocessing and backpressure steps before `CommitOffsets` (`:125`, `:134-139`).
- **Message decode.** `process_simple_event_message` (`src/sentry/ingest/consumer/simple_event.py:25`):
  - Unpacks the msgpack envelope (`:54`) and checks that `type == "event"` (`:59`).
  - Loads the project from cache (`:64`) and calls `process_event` (`:68`).
  - Any error that isn't `Retriable` becomes `InvalidMessage`, which sends the message to the DLQ (`:76-83`).
- **Alternative entry point.** Taskbroker "raw mode" calls `process_event_from_kafka` (`simple_event.py:92`), which reaches the same `process_event` (`:124`). Options can make it save inline.
- **`process_event`** (`src/sentry/ingest/consumer/processors.py:79`):
  - Checks a dedup cache key `ev:{project_id}:{event_id}` (`:117-131`) and two load-shed killswitches (`:133`, `:162`).
  - Parses the JSON payload with `orjson.loads` (`:150`) and picks `event_processing_store` for errors (`:157`).
  - Stores any attachments (`:203`) and writes the payload to the processing store (Redis), which returns a `cache_key` (`:212`).
  - Transactions and feedback branch off at `:247` and `:267`. Errors go to the `else` branch and call `preprocess_event(...)` (`:288-306`).
  - Afterwards it sets the dedup key (`:310`) and sends the `event_accepted` signal (`:314`).

## 2. Preprocess / process → `save_event`

In `src/sentry/tasks/store.py`:

- **`preprocess_event`** (`:273`) calls **`_do_preprocess_event`** (`:123`), which routes the event one of three ways:
  - Events that need symbolication go to `submit_symbolicate` (`:218-244`). GPU crash dumps are split off to their own task first (`:183-203`).
  - Events that `should_process` go to `submit_process`, then the `process_event` task (`:248-257`, `:465`). `do_process_event` (`:343`) runs datascrubbing and the event preprocessors, re-normalizes, and re-stores the payload (`:412-454`). It then continues to save (`:373-385`, `:456`).
  - Everything else goes straight to `submit_save_event` (`:259`).
- **`submit_save_event`** (`:91`) picks `save_event`, or `save_event_attachments` when there are attachments (`:104-107`). It either runs the task inline or calls `.delay` (`:117-120`).
- **`save_event` task** (`:679`) calls **`_do_save_event`** (`:521`), which:
  - Reads the payload from the processing store (`:551-552`).
  - Resolves the project (`:597`) and checks the `store.load-shed-save-event-projects` killswitch (`:606`).
  - Calls **`EventManager(data).save(project=..., assume_normalized=True, ...)`** (`:616-624`).
  - Writes the updated data back for post-processing (`:628-633`).
  - On `HashDiscarded`, deletes the cached payload and marks attachments for cleanup (`:635-642`).

## 3. `EventManager.save` → `save_error_events`

In `src/sentry/event_manager.py`:

- **`save`** (`:441`) builds a `job` dict (`:481`) and calls `_pull_out_data` (`:489`, defined at `:660`), which creates the `Event` object.
  - Transactions and generic events branch off at `:496` and `:500`.
  - Errors set `in_grouping_transition` (`:506`) and call `save_error_events` (`:516`).
- **`save_error_events`** (`:521`) runs these steps in order:
  1. Releases, users, and tags: `_get_or_create_release_many`, `_get_event_user_many`, `_derive_tags_many` (`:535-547`).
  2. **`assign_event_to_group`** (`:550`). A `HashDiscarded` here (for example, a hash that matches a tombstone) discards the event (`:552-555`).
  3. Environment, group-environment, release, and TSDB bookkeeping (`:564-569`).
  4. `_materialize_event_metrics` (`:575`), then the nodestore write `_nodestore_save_many` (`:582`, defined at `:1083`).
  5. `_eventstream_insert_many` (`:610`, defined at `:1114`). This hands the event to Snuba and post-processing.
  6. Attachments are saved (`:618-634`).

## 4. Grouping hash calculation

`assign_event_to_group` (`event_manager.py:1318`) calls `get_hashes_and_grouphashes(job, run_primary_grouping, ...)` (`:1327`).

- **`get_hashes_and_grouphashes`** (`:1385`):
  - Calls the hash function (`:1405`).
  - Calls `get_or_create_grouphashes` (`:1408`).
  - Calls `find_grouphash_with_group` to find a hash that already has a group (`:1412`).

In `src/sentry/grouping/ingest/hashing.py`:

- **`run_primary_grouping`** (`:132`) gets the project's grouping config and stores it in `job["data"]["grouping_config"]` (`:139-140`). It then calls `_calculate_primary_hashes_and_variants` (`:154`), which calls **`_calculate_event_grouping`** (`:50`). That function:
  - Loads the strategy config (`:64`).
  - Applies server-side fingerprinting rules (`:67-70`).
  - Normalizes stacktraces for grouping (`:77`), which leads to `src/sentry/stacktraces/processing.py:151`.
  - Calls `event.get_hashes_and_variants(...)` (`:80`).
- **`Event.get_hashes_and_variants`** (`src/sentry/services/eventstore/models.py:337`):
  - Gets the variants via `get_grouping_variants` (`:404`), which calls `get_grouping_variants_for_event` (`:459`).
  - Hashes each variant (`:346-348`) and sorts so the `system` variant comes last (`:352-355`).
  - Writes `data["hashes"]` (`:365`).
- **`get_grouping_variants_for_event`** (`src/sentry/grouping/api.py:358`):
  - A checksum short-circuits everything (`:366-373`).
  - Otherwise it resolves the fingerprint (`:387-399`) and runs the strategies in `_get_variants_from_strategies` (`:279`). The first strategy with a contributing component wins, and the others are marked non-contributing (`:290-327`).
  - Custom or hybrid fingerprints then adjust the variants (`:422+`).
- **Secondary grouping.** `maybe_run_secondary_grouping` (`hashing.py:85`) only runs while the project is in a config transition (`:96`). It hashes a deep copy of the event (`:107-129`).
- **GroupHash rows.** `get_or_create_grouphashes` (`hashing.py:260`):
  - For secondary hashes, keeps only hashes that already exist (`:271-279`).
  - Calls `GroupHash.objects.get_or_create(project, hash)` through a 60s cache (`:224-257`, `:247`).
  - Writes grouphash metadata (`:288`).
- **Finding an existing group.** `find_grouphash_with_group` (`hashing.py:165`) returns the first grouphash that has a `group_id`. It raises `HashDiscarded` if any hash has a `group_tombstone_id` (`:181-186`).

## 5. Assigning to a group or creating one

In `assign_event_to_group` (`event_manager.py:1318`), four outcomes are tried in order:

1. **Primary hash matches an existing group:** `handle_existing_grouphash` (`:1330-1331`).
2. **Otherwise, secondary hashes are tried:** `:1337-1343`.
3. **Otherwise, Seer is asked for a similar-issue match:** `maybe_check_seer_for_matching_grouphash` (`:1351`, defined at `src/sentry/grouping/ingest/seer.py:629`).
4. **Otherwise, a new group is created:** `create_group_with_grouphashes` (`:1359`).

After that it updates the grouping config if needed (`:1372`), sets `event.group` (`:1378`), and sets `job["groups"]` (`:1379`).

**Existing group** — `handle_existing_grouphash` (`:1420`):
- Loads the `Group` from cache (`:1448`) and returns `None` if it isn't an error-type group (`:1454`).
- `add_group_id_to_grouphashes` links any new hashes to the group (`:1463`, defined at `src/sentry/grouping/ingest/utils.py:22`).
- `_process_existing_aggregate` (`:1465`, defined at `:1900`):
  - Updates `last_seen`, message, level, culprit, and `first_seen` (`:1906-1928`).
  - Checks for regression with `_handle_regression` (`:1931`).
  - Merges data and metadata (`:1942-1951`).
  - Increments `times_seen` via `buffer_incr` (`:1963`).
- Ensures the group is linked to a detector (`:1473`) and returns `GroupInfo(is_new=False)`.

**New group** — `create_group_with_grouphashes` (`:1478`):
- Checks the group-creation load-shed killswitch (`:1491`, `utils.py:37`).
- Opens a transaction and locks the grouphash rows with `select_for_update` (`:1499`, `:1516-1520`).
- Re-checks `find_grouphash_with_group` (double-checked locking, `:1526`). If another process won the race, it falls back to `handle_existing_grouphash` (`:1544-1546`).
- Otherwise it calls `_create_group(project, event, **_get_group_processing_kwargs(job))` (`:1535`). The kwargs builder is at `:882` and supplies metadata, message, level, culprit, and timestamps.
- Then `associate_new_group_with_detector` (`:1536`) and `add_group_id_to_grouphashes` (`:1537`).
- **`_create_group`** (`:1549`):
  - Allocates a short ID with `project.next_short_id`; a timeout raises `HashDiscarded` (`:1556`, `:1700-1706`).
  - Adds SDK and severity metadata and sets priority (`:1571-1592`), with `times_seen=1` (`:1596`).
  - Runs **`Group.objects.create(...)`** (`:1606`). A unique-violation on a stuck short-ID counter is retried (`:1613-1630`).
  - Calls `create_open_period` (`:1637`).

Control then returns to `save_error_events` (`event_manager.py:557`) with a `GroupInfo`, and the environment, nodestore, and eventstream steps from section 3 run.