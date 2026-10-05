Now I have the complete flow. Here's the trace of an error event from ingest Kafka consumer to stored issue:

## Error Event Flow: Kafka Consumer → Stored Issue

### 1. **Kafka Consumer Entry Point**
- **`src/sentry/ingest/consumer/simple_event.py`** — receives ingest-events messages
- **`src/sentry/ingest/consumer/attachment_event.py`** — receives ingest-attachments messages

### 2. **Message Processing**
- **`src/sentry/ingest/consumer/processors.py:79`** — `process_event()` 
  - Deserializes payload, stores attachments
  - Caches event data in Redis
  - Submits async task via `submit_save_event()`

### 3. **Save Event Task**
- **`src/sentry/tasks/store.py:679`** — `save_event()` task
  - Calls **`src/sentry/tasks/store.py:532`** — `_do_save_event()`
    - Instantiates EventManager at line 537
    - Calls `EventManager.save()` at line 616

### 4. **EventManager Main Processing**
- **`src/sentry/event_manager.py:441`** — `EventManager.save()`
  - Normalizes event (line 476-479)
  - For errors, calls **`src/sentry/event_manager.py:521`** — `save_error_events()`

### 5. **Error Event Grouping Assignment**
- **`src/sentry/event_manager.py:521`** — `save_error_events()`
  - Line 550: calls **`src/sentry/event_manager.py:1318`** — `assign_event_to_group()`

### 6. **Hash Calculation & Grouping**
- **`src/sentry/event_manager.py:1318`** — `assign_event_to_group()`
  - Line 1327: calls **`src/sentry/event_manager.py:1385`** — `get_hashes_and_grouphashes()` with **`src/sentry/grouping/ingest/hashing.py:132`** — `run_primary_grouping()`

- **`src/sentry/event_manager.py:1385`** — `get_hashes_and_grouphashes()`
  - Line 1405: calls the hash calculation function
  - Line 1408: calls **`src/sentry/grouping/ingest/hashing.py:260`** — `get_or_create_grouphashes()`

### 7. **Fingerprinting & Grouping Config**
- **`src/sentry/grouping/ingest/hashing.py:132`** — `run_primary_grouping()`
  - Line 139: loads grouping config via `get_grouping_config_dict_for_project()`
  - Line 149: calls **`src/sentry/grouping/ingest/hashing.py:154`** — `_calculate_primary_hashes_and_variants()`

- **`src/sentry/grouping/ingest/hashing.py:154`** — `_calculate_primary_hashes_and_variants()`
  - Line 162: calls **`src/sentry/grouping/ingest/hashing.py:50`** — `_calculate_event_grouping()`

- **`src/sentry/grouping/ingest/hashing.py:50`** — `_calculate_event_grouping()`
  - Line 68: applies server-side fingerprinting via `apply_server_side_fingerprinting()` using **`src/sentry/grouping/fingerprinting/__init__.py:46`** — `FingerprintingConfig.get_fingerprint_values_for_event()`
  - Line 77: normalizes stacktraces via `event.normalize_stacktraces_for_grouping()`
  - Line 80: calculates hashes via `event.get_hashes_and_variants(loaded_grouping_config)`
    - Uses strategy pattern: **`src/sentry/grouping/strategies/base.py:54`** — `@strategy` decorator
    - Returns list of hash strings and variants dict

### 8. **GroupHash Creation/Lookup**
- **`src/sentry/grouping/ingest/hashing.py:260`** — `get_or_create_grouphashes()`
  - Line 282: for each hash, calls `_get_or_create_single_grouphash()`
    - Line 243: **`src/sentry/models/grouphash.py:70`** — `GroupHash.objects.get_or_create(project, hash)`
  - Line 288: creates/updates **`src/sentry/models/grouphashmetadata.py:66`** — `GroupHashMetadata` if enabled
  - Returns list of GroupHash objects

### 9. **Group Assignment or Creation**
Back in **`src/sentry/event_manager.py:1318`** — `assign_event_to_group()`:
  - Line 1330-1331: If existing GroupHash has group → calls `handle_existing_grouphash()`
  - Line 1359: If no match found → calls **`src/sentry/event_manager.py:1478`** — `create_group_with_grouphashes()`

### 10. **Group Creation with Race Condition Protection**
- **`src/sentry/event_manager.py:1478`** — `create_group_with_grouphashes()`
  - Line 1516-1520: Uses `select_for_update()` for double-checked locking on GroupHash rows
  - Line 1526: checks again if another event already created the group
  - Line 1530-1551: if not, creates new group via `_create_group()` at line 1554
  - Updates GroupHash with group_id

### 11. **Alternative Group Creation Path (used in some contexts)**
- **`src/sentry/event_manager.py:2811`** — `save_grouphash_and_group()`
  - Line 2819: `GroupHash.objects.get_or_create(project, hash)`
  - Line 2821: if created, calls `_create_group()` to create new Group
  - Line 2822: updates GroupHash with group reference

### 12. **Hash Implementation**
- **`src/sentry/spans/grouping/utils.py:17`** — `Hash` class
  - Line 19: uses MD5 algorithm
  - Line 23: updates with normalized byte strings
  - Line 29: `hexdigest()` returns first 16 chars of MD5 hash

### 13. **Event Storage & Post-Processing**
Back in **`src/sentry/event_manager.py:521`** — `save_error_events()` after grouping:
  - Line 562-582: saves event nodestore, creates Group/GroupEnvironment
  - Line 584-589: handles first event signals
  - Returns event with group assigned

## Key Data Models
- **`src/sentry/models/grouphash.py:70`** — `GroupHash` — links hash value to Group
- **`src/sentry/models/group.py`** — `Group` — represents an issue
- **`src/sentry/services/eventstore/models.py:706`** — `GroupEvent` — event with group association
- **`src/sentry/grouping/fingerprinting/types.py`** — fingerprinting types: `FingerprintWithAttributes`, `FingerprintRuleMatch`