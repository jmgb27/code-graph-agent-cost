Based on the code exploration, here's the complete trace of an error event from ingest to a stored issue:

## Event Flow: Kafka Ingest to Stored Issue

### 1. **Entry Point — Kafka Consumer to Task Queue**
- **Consumer**: `src/sentry/ingest/inbound_filters.py` (filters incoming events) 
- **Task**: `src/sentry/tasks/store.py:679` — `save_event()` task (queued by consumer)

### 2. **Event Processing Entry**
- **Function**: `src/sentry/tasks/store.py:521` — `_do_save_event()` 
  - Loads event data from cache (L552)
  - Creates EventManager instance (L616)
  - Calls `manager.save()` (L618)

### 3. **EventManager Normalization & Routing**
- **Method**: `src/sentry/event_manager.py:441` — `EventManager.save()`
  - Normalizes event if needed (L476-479)
  - Routes by event type: error events → `save_error_events()` (L516)

### 4. **Error Event Processing**
- **Method**: `src/sentry/event_manager.py:521` — `EventManager.save_error_events()`
  - Prepares job data (L545-548)
  - **Calls grouping logic** (L550): `assign_event_to_group()`

### 5. **Grouping & Group Assignment**
- **Function**: `src/sentry/event_manager.py:1318` — `assign_event_to_group()`
  - Tries primary grouping (L1327): `get_hashes_and_grouphashes()` 
  - If found existing group, calls `handle_existing_grouphash()` (L1331)
  - If no match, tries secondary grouping (L1337)
  - If still no match, tries Seer ML matching (L1351)
  - **If no group found, creates new group** (L1359): `create_group_with_grouphashes()`
  - Assigns group to event (L1378): `event.group = group_info.group`

### 6. **Hash Calculation & GroupHash Creation**
- **Function**: `src/sentry/event_manager.py:1385` — `get_hashes_and_grouphashes()`
  - Calculates hashes via `run_primary_grouping()` (L1405)
  - Creates GroupHash records (L1408): `get_or_create_grouphashes()`
  - Finds existing group link (L1412): `find_grouphash_with_group()`

### 7. **Grouping Config & Hash Calculation**
- **Function**: `src/sentry/grouping/ingest/hashing.py:132` — `run_primary_grouping()`
  - Loads grouping config (L139): `get_grouping_config_dict_for_project()`
  - Calculates hashes (L149): `_calculate_primary_hashes_and_variants()`
  - Returns config, hashes, variants (L151)

### 8. **GroupHash Records (DB)**
- **Function**: `src/sentry/grouping/ingest/hashing.py:260` — `get_or_create_grouphashes()`
  - Creates/retrieves GroupHash records per hash value (L281-282)
  - Returns list of GroupHash objects with group_id links

### 9. **Finding Existing Group**
- **Function**: `src/sentry/grouping/ingest/hashing.py:165` — `find_grouphash_with_group()`
  - Searches GroupHash records for one with `group_id` (L177-178)
  - Checks for group tombstones (deleted groups) (L181-186)
  - Returns GroupHash with group reference or None

### 10. **Group Model & Storage**
- **Model**: `src/sentry/models/group.py` — `Group` (Django model)
  - Either an existing Group is found and linked via GroupHash
  - Or a new Group is created by `create_group_with_grouphashes()` (referenced in L1359)
  - Group stores: `id`, `project_id`, `status`, `first_seen`, `last_seen`, etc.

### 11. **Event-to-Group Linking**
- **Model**: `src/sentry/models/grouphash.py` — `GroupHash` (many-to-one to Group)
  - Stores the hash value and links to Group via `group_id`
  - Allows finding which group an event belongs to by its hash

### 12. **Final Storage**
After grouping (back in `save_error_events`):
- Saves GroupEvent to eventstore (L610): `_eventstream_insert_many()`
- Stores attachments if any (L619): `save_attachments()`
- Event now accessible via `GroupEvent` model with `group_id` populated

## Summary of Key File:Line References

| Component | File | Line |
|-----------|------|------|
| Kafka task entry | `src/sentry/tasks/store.py` | 679 |
| Save event logic | `src/sentry/tasks/store.py` | 521 |
| EventManager.save | `src/sentry/event_manager.py` | 441 |
| Error processing | `src/sentry/event_manager.py` | 521 |
| Group assignment | `src/sentry/event_manager.py` | 1318 |
| Grouping hash flow | `src/sentry/event_manager.py` | 1385 |
| Primary grouping | `src/sentry/grouping/ingest/hashing.py` | 132 |
| GroupHash creation | `src/sentry/grouping/ingest/hashing.py` | 260 |
| Find group link | `src/sentry/grouping/ingest/hashing.py` | 165 |
| Group model | `src/sentry/models/group.py` | (model definition) |
| GroupHash model | `src/sentry/models/grouphash.py` | (model definition) |