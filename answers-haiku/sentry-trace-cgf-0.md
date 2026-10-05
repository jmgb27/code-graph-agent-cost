Based on my exploration using CodeGraph, here's the complete trace of an error event from the Kafka ingest consumer to a stored issue:

## Event Flow: Kafka Consumer → Stored Issue

### 1. **Ingest Consumer Entry Point**
- **src/sentry/ingest/consumer/processors.py:79** — `process_event()` — The main ingest processor receives and deserializes Kafka messages
- Parses the JSON payload and routes to either transaction or error event processing stores

### 2. **Task Submission**
- **src/sentry/tasks/store.py:679** — `save_event()` — Enqueued task (decorated with `@instrumented_task`)
- Calls `_do_save_event()` with `ConsumerType.Events`

### 3. **Event Processing**
- **src/sentry/tasks/store.py:343** — `do_process_event()` — Processes event (normalization, datascrubbing, plugins)
- **src/sentry/tasks/store.py:465** — `process_event()` — Main processing task
- Ultimately calls `submit_save_event()` to move to the save phase

### 4. **Event Saving & Grouping**
- **src/sentry/event_manager.py:441** — `EventManager.save()` — Core save method
- **src/sentry/event_manager.py:521** — `save_error_events()` — Handles error event-specific logic
- **src/sentry/event_manager.py:550** — Calls `assign_event_to_group()`

### 5. **Grouping Hash Calculation**
- **src/sentry/event_manager.py:1318** — `assign_event_to_group()` — Main grouping orchestrator
  - Calls `get_hashes_and_grouphashes()` with `run_primary_grouping()` (primary strategy)
  
- **src/sentry/event_manager.py:1385** — `get_hashes_and_grouphashes()` — Calculates and creates hashes
  - Calls `hash_calculation_function()` (primary or secondary grouping)
  - **src/sentry/grouping/ingest/hashing.py:132** — `run_primary_grouping()` — Computes primary grouping config and hashes
  - **src/sentry/grouping/ingest/hashing.py:85** — `maybe_run_secondary_grouping()` — Fallback secondary config (if in transition period)

### 6. **Grouping Variants & Hash Computation**
- **src/sentry/grouping/api.py** — `get_grouping_components()` retrieves grouping strategies
- **src/sentry/grouping/strategies/base.py:137** — `Strategy.get_grouping_components()` — Applies strategy (exception, message, fingerprint, etc.)
- **src/sentry/grouping/strategies/base.py:220** — `iter_strategies()` — Iterates over strategies by score
- **src/sentry/spans/grouping/utils.py:17** — `Hash` class — MD5-based hash computation
- **src/sentry/spans/grouping/utils.py:21** — `Hash.update()` — Hashes values
- **src/sentry/spans/grouping/utils.py:26** — `Hash.hexdigest()` — Returns 16-char MD5 digest

### 7. **GroupHash Creation**
- **src/sentry/grouping/ingest/hashing.py:260** — `get_or_create_grouphashes()` — Creates `GroupHash` entries for each variant
- **src/sentry/models/grouphash.py:70** — `GroupHash` model — Links hash to group
- **src/sentry/models/grouphash.py:78** — Fields: `project`, `hash` (32-char), `group` (FK), `group_tombstone_id`

### 8. **Group Assignment or Creation**
- **src/sentry/grouping/ingest/hashing.py:165** — `find_grouphash_with_group()` — Searches for existing GroupHash with associated Group
  
- **If existing group found:**
  - **src/sentry/event_manager.py:1420** — `handle_existing_grouphash()` — Assigns event to existing group

- **If no existing group:**
  - **src/sentry/grouping/ingest/hashing.py** — `create_group_with_grouphashes()` — Creates new Group and associates with GroupHash entries

### 9. **Event Storage & Finalization**
- **src/sentry/event_manager.py:582** — `_nodestore_save_many()` — Persists event to node store
- **src/sentry/event_manager.py:610** — `_eventstream_insert_many()` — Inserts into Snuba/eventstream for post-processing
- **src/sentry/services/eventstore/models.py:706** — `GroupEvent` — Final event model with group association

---

## Key Components

| Component | File:Line | Purpose |
|-----------|-----------|---------|
| Grouping Strategy | `src/sentry/grouping/strategies/base.py:96` | Selects which event interface (exception, message, etc.) to hash |
| Fingerprinting Rules | `src/sentry/grouping/fingerprinting/rules.py:19` | Custom per-project grouping rules |
| Hash Value | `src/sentry/spans/grouping/utils.py:17` | MD5-based 16-char hash digest |
| GroupHash Model | `src/sentry/models/grouphash.py:70` | Persisted hash→group mapping |
| GroupEvent Model | `src/sentry/services/eventstore/models.py:706` | Final event with group reference |