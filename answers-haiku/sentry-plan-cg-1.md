Based on my exploration of the codebase, here's the comprehensive plan for adding a per-project cap on new issues created per hour, enforced at ingestion:

## Files and Functions to Change

### 1. **Option Registration**
- **File**: `src/sentry/projectoptions/defaults.py` (lines 1-150+)
  - **Function to add**: Call to `register()` to define `"sentry:issue_hourly_cap"` with default value (e.g., `None` or `0` for unlimited)

### 2. **API Serializer** (Project Settings)
- **File**: `src/sentry/api/serializers/models/project.py`
  - **Function to add**: Extend project serializer to include `issue_hourly_cap` field (lookup via `project.get_option()`)

### 3. **API Endpoint** (Project Settings Update)
- **File**: `src/sentry/api/endpoints/project_performance_general_settings.py` as a template
  - **New file**: `src/sentry/api/endpoints/project_issue_hourly_cap.py` OR extend existing project settings endpoint
  - **Classes to add**:
    - `ProjectIssueHourlyCap Serializer` (with `int` field for cap value)
    - `ProjectIssueHourlyCap Endpoint` (inherit from `ProjectEndpoint`, permission check via `ProjectSettingPermission`)
  - **Methods**:
    - `get()` - return current cap value
    - `post()` - validate and update cap (use `project.update_option()`)

- **File**: `src/sentry/api/urls.py`
  - Add route: `/organizations/{org}/projects/{project}/issue-hourly-cap/`

### 4. **Frontend Settings Form**
- **File**: `static/app/views/settings/projectGeneralSettings/index.tsx` (or new file)
  - Add form field for issue hourly cap (e.g., `<NumberField>` or similar from `@sentry/scraps/form`)
  - Wire up to fetch/update via new endpoint above

### 5. **Event Pipeline Enforcement** (Group Creation Check)
- **File**: `src/sentry/event_manager.py`
  - **Function**: `create_group_with_grouphashes()` (line 1478)
    - Before `_create_group()` call (line 1535), add check:
      - Get current cap from `project.get_option("sentry:issue_hourly_cap")`
      - Check Redis for hourly count of new groups created in past hour (use Redis key like `sentry:new_issues:{project_id}:{hour_timestamp}`)
      - If cap exceeded, raise `HashDiscarded` exception (will prevent group creation)
  
  - **New helper function**: `check_hourly_issue_cap(project: Project) -> None`
    - Read cap value
    - Query Redis for count
    - Raise `HashDiscarded` if exceeded

- **File**: `src/sentry/event_manager.py` 
  - **Function**: `_create_group()` (line 1549)
    - After group creation, increment Redis counter for the hour

### 6. **Metrics/Logging** (Optional but recommended)
- **File**: `src/sentry/event_manager.py`
  - Add metrics tracking in `check_hourly_issue_cap()`:
    - `metrics.incr("event_manager.issue_hourly_cap_exceeded")`
    - `metrics.gauge("event_manager.issue_hourly_cap_remaining", remaining_capacity)`

### 7. **Tests**
- **File**: `tests/sentry/api/endpoints/test_project_issue_hourly_cap.py` (new)
  - Test GET endpoint
  - Test POST endpoint with valid/invalid values
  - Test permission checks

- **File**: `tests/sentry/event_manager/test_issue_hourly_cap.py` (new)
  - Test `check_hourly_issue_cap()` with cap enabled/disabled
  - Test cap enforcement during group creation
  - Test Redis counter increment

## Summary of Components

| Component | File | Type | Purpose |
|-----------|------|------|---------|
| Option definition | `src/sentry/projectoptions/defaults.py` | Registration | Define `sentry:issue_hourly_cap` option |
| Serializer | `src/sentry/api/serializers/models/project.py` | API | Expose setting in responses |
| Endpoint | `src/sentry/api/endpoints/project_issue_hourly_cap.py` | API | GET/POST cap configuration |
| URL routing | `src/sentry/api/urls.py` | Config | Route to endpoint |
| Frontend form | `static/app/views/settings/projectGeneralSettings/index.tsx` | UI | Form field for cap value |
| Cap check | `src/sentry/event_manager.py:create_group_with_grouphashes()` | Logic | Enforce cap at ingestion |
| Counter increment | `src/sentry/event_manager.py:_create_group()` | Logic | Track hourly count in Redis |
| Tests | `tests/sentry/api/endpoints/test_project_issue_hourly_cap.py` | Tests | API testing |
| Tests | `tests/sentry/event_manager/test_issue_hourly_cap.py` | Tests | Enforcement testing |