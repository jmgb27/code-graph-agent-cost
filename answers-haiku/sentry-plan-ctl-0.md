Now I have a comprehensive understanding of the codebase. Here's the complete plan for implementing a per-project cap on new issues created per hour:

## Files and Functions to Change

### 1. **Option Registration - Global Default**
- **File**: `src/sentry/options/defaults.py`
  - **Line**: After line 200+ (add near end of file with other project-related options)
  - **Function to add**: Register a global option for default cap, e.g., `register("store.max-new-issues-per-hour", default=1000, type=Int)`

### 2. **Project Option Registration**
- **File**: `src/sentry/projectoptions/defaults.py`
  - **Line**: After line 200+ (add new project option registration)
  - **Function to add**: Register per-project option, e.g., `register(key="sentry:max_new_issues_per_hour", default=None)` with epoch defaults if needed

### 3. **Project Serializer - API Response**
- **File**: `src/sentry/api/serializers/models/project.py`
  - **Lines**: `663-720` (class `ProjectWithOrganizationSerializer` and related)
  - **Functions**:
    - `get_attrs()` (around line 664): Add bulk query to fetch the cap option value
    - `serialize()` (around line 674): Add the cap to the returned dict with key `maxNewIssuesPerHour`

### 4. **Project Details Endpoint - Update Handler**
- **File**: `src/sentry/core/endpoints/project_details.py`
  - **Lines**: `107-150+` (class `ProjectMemberSerializer`)
  - **Functions**:
    - Add `maxNewIssuesPerHour = serializers.IntegerField(required=False, ...)` field to `ProjectMemberSerializer`
  - **Lines**: Search for the `put()` method (likely around line 400+)
  - **Functions**: `put()` method - add logic to handle the new field and call `ProjectOption.objects.set_value()`

### 5. **Event Pipeline - Cap Enforcement (Pre-processing)**
- **File**: `src/sentry/ingest/consumer/simple_event.py`
  - **Lines**: `25-74` (function `process_simple_event_message`)
  - **Function**: Add Redis-based counter check before calling `process_event()` to verify hourly cap not exceeded

### 6. **Event Pipeline - Cap Enforcement (Processing)**
- **File**: `src/sentry/ingest/consumer/processors.py`
  - **Lines**: `77-100+` (function `process_event()`)
  - **Function**: Add cap check early in processing; if exceeded, return early or raise exception

### 7. **Event Manager - Group Creation Check**
- **File**: `src/sentry/event_manager.py`
  - **Lines**: Search for `create_group_with_grouphashes()` function
  - **Function**: Before creating new Group, check if adding this event would exceed cap; if so, filter the event or raise `RateLimitExceeded`

### 8. **Frontend Settings Form**
- **File**: `static/app/views/settings/projectGeneralSettings/index.tsx`
  - **Lines**: Around `600-800` (inside form fields section)
  - **Function**: Add `IntegerField` or `NumberField` component for `maxNewIssuesPerHour` with min/max validation

### 9. **Rate Limiting / Outcome Tracking (Optional but Recommended)**
- **File**: `src/sentry/utils/outcomes.py` or similar
  - Add outcome reason constant for "exceeded_issue_cap" or similar
  - Track in `processors.py` when events are dropped due to cap

### 10. **Tests** (Not listed since read-only, but affected files would be):
- `tests/sentry/api/endpoints/test_project_details.py`
- `tests/sentry/ingest/consumer/test_processors.py`
- `tests/sentry/event_manager/test_*.py`

## Key Implementation Points

**Database/Storage**: Use Redis with hourly TTL for per-project issue creation counters (key pattern: `project:{project_id}:issues_created_this_hour`)

**API Payload**: The project endpoint response should include `"maxNewIssuesPerHour"` (camelCase per API conventions)

**Enforcement Location**: Best approach is dual-layer:
1. Early check in `simple_event.py` to fail fast on Kafka consumption
2. Secondary check in `event_manager.py` before actual Group creation for accuracy

**Edge Case**: Decide if `null`/`0` means "unlimited" or if organization-level override applies when project option is not set