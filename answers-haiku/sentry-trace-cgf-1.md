Based on my exploration of the codebase, here's the complete trace of an error event from the ingest Kafka consumer to a stored issue:

## Event Flow: Kafka Consumer → Stored Issue

### 1. **Kafka Consumer Entry Point**
- **`src/sentry/ingest/consumer/simple_event.py:25`** — `process_simple_event_message()` 
  - Entry point that decodes msgpack Kafka payload
  - Fetches project from cache
  - Calls `process_event()` at line 68

### 2. **Event Processing**
- **`src/sentry/ingest/consumer/simple_event.py`** — `process_event()` (defined elsewhere, called at line 68)
- Eventually schedules the `save_event` task via taskbroker

### 3. **Save Event Task**
- **`src/sentry/tasks/store.py:679`** — `@instrumented_task save_event()`
  - Entry point for the Celery task that saves events
  - Calls `_do_save_event()` at line 687

- **`src/sentry/tasks/store.py:532`** — `_do_save_event()` 
  - Retrieves event data from cache
  - Creates `EventManager` instance at line 537
  - Calls `EventManager.save()` with project

### 4. **Event Manager: Core Normalization & Save**
- **`src/sentry/event_manager.py:441`** — `EventManager.save()`
  - Normalizes event if needed (line 476-479)
  - Extracts event type and routes accordingly:
    - Line 498: Transaction → `save_transaction_events()`
    - Line 502: Generic → `save_generic_events()`
    - Otherwise → error event path

### 5. **Error Event Processing** (Generic Events)
- **`src/sentry/event_manager.py:2928`** — `@trace save_generic_events()`
  - Processes error/issue events
  - Calls multiple helper functions in sequence:
    - Line 2938: `_get_or_create_release_many()`
    - Line 2939: `_get_event_user_many()`
    - Line 2940: `_derive_tags_many()`
    - Line 2942: `_materialize_metadata_many()`
    - Line 2943: `_get_or_create_environment_many()` → **`src/sentry/models/environment.py:91`** `get_or_create()`
    - Line 2945: `_nodestore_save_many()` — saves event to node storage

### 6. **Transaction Event Processing**
- **`src/sentry/event_manager.py:2862`** — `@trace save_transaction_events()`
  - Similar processing pipeline for transactions
  - Line 2889: `_calculate_span_grouping()` — calculates grouping hashes
  - Line 2895: `_nodestore_save_many()` — saves to node storage
  - Line 2896: `_eventstream_insert_many()` — writes to eventstream/Snuba

### 7. **Grouping Hash Calculation**
- **`src/sentry/spans/grouping/utils.py:17`** — `class Hash`
  - Line 18-19: `__init__()` — initializes MD5 hasher
  - Line 21-24: `update()` — adds values to hash
  - Line 26-29: `hexdigest()` — returns 16-char hex digest
- **`src/sentry/spans/grouping/utils.py:32`** — `hash_values()` — convenience function

### 8. **GroupHash Model: Hash → Group Mapping**
- **`src/sentry/models/grouphash.py:70`** — `@cell_silo_model class GroupHash(Model)`
  - Line 77: `project` — FlexibleForeignKey to Project
  - Line 78: `hash` — CharField(max_length=32) stores the grouping hash
  - Line 79: `group` — FlexibleForeignKey to Group (null for unassigned hashes)
  - Line 82: `group_tombstone_id` — for discarded events
  - Line 96: `unique_together = (("project", "hash"))` — enforces hash uniqueness per project

### 9. **Group Creation/Assignment**
- **`src/sentry/event_manager.py`** — event processing eventually:
  - Creates new `Group` record if hash doesn't exist
  - Or retrieves existing `Group` if hash already mapped
  - Updates `GroupHash.group` foreign key

### 10. **Event Storage & Indexing**
- **`src/sentry/services/eventstore/models.py:706`** — `class GroupEvent(BaseEvent)`
  - Line 709-721: `__init__()` — wraps event with Group relationship
  - Line 756-766: `from_event()` — creates GroupEvent from Event + Group
- Stored in:
  - NodeStore (via `_nodestore_save_many()`)
  - Eventstream/Snuba (via `_eventstream_insert_many()` or `eventstream.insert()`)
  - PostgreSQL Group/GroupHash tables

### 11. **Related Models**
- **`src/sentry/models/groupenvironment.py:11`** — `@cell_silo_model class GroupEnvironment`
  - Tracks first occurrence per environment
  - Line 41-42: `get_or_create()` with caching
- **`src/sentry/models/groupemailthread.py:9`** — `@cell_silo_model class GroupEmailThread`
  - Stores email threading metadata for notifications

---

## Summary of Key Entry Points

| Stage | File:Line | Function |
|-------|-----------|----------|
| **Kafka Consumer** | `src/sentry/ingest/consumer/simple_event.py:25` | `process_simple_event_message()` |
| **Save Task** | `src/sentry/tasks/store.py:679` | `save_event()` |
| **Core Processing** | `src/sentry/tasks/store.py:532` | `_do_save_event()` |
| **Event Manager** | `src/sentry/event_manager.py:441` | `EventManager.save()` |
| **Error Events** | `src/sentry/event_manager.py:2928` | `save_generic_events()` |
| **Transactions** | `src/sentry/event_manager.py:2862` | `save_transaction_events()` |
| **Grouping Hash** | `src/sentry/spans/grouping/utils.py:17` | `class Hash` |
| **Hash → Group** | `src/sentry/models/grouphash.py:70` | `class GroupHash` |
| **Grouped Event** | `src/sentry/services/eventstore/models.py:706` | `class GroupEvent` |