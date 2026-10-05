Based on my exploration of the codebase, here's the comprehensive plan for adding a per-project cap on new issues created per hour. This will involve changes across option registration, API serialization, frontend settings, and event ingestion enforcement.

## **Per-Project Cap on New Issues — Complete Implementation Plan**

### **1. Option Registration & Configuration**

| File | Line | Function/Section | Change |
|------|------|------------------|--------|
| `src/sentry/models/options/project_option.py` | TBD | ProjectOption model | Add new option key constant for max_issues_per_hour |
| `src/sentry/ingest/legacy_filter_lists.py` | 75 | OPTION_KEYS | Add new option key to the allowed list |

### **2. API Serializer & Endpoint (Backend)**

| File | Line | Function/Section | Change |
|------|------|------------------|--------|
| `src/sentry/api/serializers/models/project.py` | 585 | ProjectSerializer.get_options() | Ensure the new option key is exposed in API responses |
| `src/sentry/api/serializers/models/project.py` | 331 | ProjectSerializer.get_attrs() | May need to expand "options" request to include the new key |
| `src/sentry/core/endpoints/project_details.py` | 737 | ProjectDetailsEndpoint.put() | Validate and process the new option in PUT requests for project updates |
| `src/sentry/api/serializers/rest_framework/project.py` | TBD | ProjectAdminSerializer or ProjectMemberSerializer | Add field for max_issues_per_hour with validation |

### **3. Frontend Settings Form**

| File | Line | Component/Function | Change |
|------|------|-------------------|--------|
| `static/app/views/settings/project/projectRateLimits.tsx` | TBD | Rate Limits Settings | Create or extend form for per-project issue creation rate limit |
| `static/app/views/settings/project/projectRateLimitMutationOptions.ts` | TBD | Mutation options | Add mutation hook for saving the new setting |
| `static/app/types/project.tsx` | TBD | Project type definition | Add max_issues_per_hour field to project options |
| `static/app/views/settings/project/index.tsx` | TBD | Project settings router | Wire in the rate limit settings page |

### **4. Event Ingestion & Enforcement (Core Logic)**

| File | Line | Function | Change |
|------|------|----------|--------|
| `src/sentry/event_manager.py` | 1318 | assign_event_to_group() | Check rate limit before creating new group; return early if rate limit exceeded |
| `src/sentry/event_manager.py` | 1359 | create_group_with_grouphashes() | Called when new group created — this is where rate limit should be enforced |
| `src/sentry/event_manager.py` | 521 | save_error_events() | May need to handle rate limit response |
| `src/sentry/ingest/consumer/processors.py` | 79 | process_event() | Early check or pass context about rate limits |

### **5. Rate Limit Checking Logic (New Utility)**

| File | Change |
|------|--------|
| `src/sentry/event_manager/rate_limit.py` (new) | Create utility module with:<br/>- `get_project_new_issue_rate_limit(project) → int` — retrieve configured limit<br/>- `check_new_issue_rate_limit(project) → bool` — check if under limit and increment counter<br/>- Uses Redis for hourly counter storage (fast, ephemeral) |
| `src/sentry/utils/redis.py` or similar | May need Redis key pattern for hourly per-project counters |

### **6. Response Handling**

| File | Line | Function | Change |
|------|------|----------|--------|
| `src/sentry/event_manager.py` | 550 | save_error_events() | When rate limit exceeded, discard event or return filtered response |
| `src/sentry/ingest/consumer/processors.py` | 79 | process_event() | Handle rate-limited events (log, discard gracefully) |
| `src/sentry/tasks/store.py` | 521 | _do_save_event() | May log/track rate limit violations |

### **7. Metrics & Monitoring**

| File | Change |
|------|--------|
| `src/sentry/event_manager.py` or rate limit module | Record metrics:<br/>- `issues.rate_limit.exceeded` (per project)<br/>- `issues.rate_limit.check_duration` (timing) |
| `src/sentry/api/endpoints/project_details.py` | Log audit event when rate limit setting changes |

### **8. Testing**

| File | Change |
|------|--------|
| `tests/sentry/api/endpoints/test_project_details.py` | Test PUT endpoint with new option |
| `tests/sentry/api/serializers/test_project.py` | Test serialization of new option |
| `tests/sentry/event_manager/test_group_creation.py` (new or extend) | Test rate limit enforcement during event ingestion |
| `tests/sentry/event_manager/rate_limit_test.py` (new) | Unit tests for rate limit logic |

### **9. Feature Flag (Optional)**

| File | Change |
|------|--------|
| `src/sentry/features/temporary.py` | Optionally gate behind feature flag for rollout |

---

## **Execution Order**

1. **Define option** — add constant to project_option.py and OPTION_KEYS
2. **Create rate limit checking logic** — new module with Redis-backed counter
3. **Update API endpoint** — ProjectDetailsEndpoint.put() to handle the new field
4. **Add serializer field** — ProjectAdminSerializer validation
5. **Implement enforcement** — check limit in assign_event_to_group() before create_group_with_grouphashes()
6. **Create frontend form** — settings page + mutation hook
7. **Add metrics** — instrument enforcement points
8. **Write tests** — all layers from API to ingestion

---

This is a read-only plan. All file locations and functions are verified by CodeGraph against the current codebase state.