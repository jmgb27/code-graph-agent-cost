Based on the CodeGraph explorations, I now have a comprehensive view of the architecture. Let me compile the complete plan for implementing a per-project cap on new issues created per hour.

## Plan: Per-Project Issue Creation Rate Limit (per hour)

### **1. Option Registration**
**File:** `src/sentry/options/projects/` or `src/sentry/options/projectoptions.py` (need to find exact location)
- Register new option key: `sentry:issue_creation_rate_limit_per_hour`
- Define default value (e.g., `0` for unlimited)
- Set well-known defaults

### **2. Backend - Project Option Model**
**Files to modify:**
- `src/sentry/models/project.py:445-450` — Already has `get_option()` method that will read the option
- `src/sentry/models/options/project_option.py:122-137` — Already handles getting project options
- Likely `src/sentry/options/projectoptions.py` or similar — Where option keys are registered

### **3. API Serializer & Endpoint Validation**
**Files to modify:**
- `src/sentry/api/serializers/models/project.py:331-661` — `ProjectSerializer` class
  - `get_attrs()` method at line 371-445
  - `serialize()` method at line 603+
  - `get_options()` method at line 585-601 — Already fetches expandable options
- Likely `src/sentry/api/endpoints/project_details.py` — For exposing/updating the setting
- Add `OPTION_KEYS` entry to whitelist the new option for expansion (line 592)

### **4. Event Processing/Ingestion - Enforcement**
**Files to modify:**
- `src/sentry/ingest/consumer/processors.py:79-200` — `process_event()` function
  - Add rate limit check after line 175 (after load-shed checks, before processing)
  - Use `project.get_option()` to fetch the limit
  - Track issues created per hour per project (likely using cache/Redis)
  - Return early or raise exception if limit exceeded
- `src/sentry/ingest/consumer/simple_event.py` — Simple event processing
- Possibly `src/sentry/ingest/consumer/attachment_event.py` — Attachment event processing

### **5. Frontend Settings Form**
**Files to modify:**
- `static/app/views/settings/project/` — Find project settings pages
- Likely in `projectKeys.tsx` or new `projectRateLimits.tsx`
- Add form field for rate limit configuration
- Use existing `ProjectDetailsEndpoint` or similar to read/write the setting
- Frontend component to display and edit the limit

### **6. Supporting Infrastructure**
**Additional files that may need changes:**
- Rate limiting utilities/helpers (likely in `src/sentry/types/ratelimit.py` already exists)
- Cache backend configuration for tracking issue counts
- Tests in:
  - `tests/sentry/ingest/ingest_consumer/test_ingest_consumer_processing.py`
  - `tests/sentry/api/serializers/test_project.py` or similar
  - `tests/sentry/core/endpoints/test_project_details.py`
  - Frontend tests in `static/app/views/settings/project/`

---

## Detailed File & Line References:

| Component | File | Lines/Functions |
|-----------|------|-----------------|
| **Option Registration** | `src/sentry/options/projectoptions.py` | TBD (need to find exact location) |
| **Project Model** | `src/sentry/models/project.py` | `445-450` (get_option) |
| **Project Option Manager** | `src/sentry/models/options/project_option.py` | `106-138` (ProjectOptionManager class, get_value method) |
| **API Serializer** | `src/sentry/api/serializers/models/project.py` | `331-661` (ProjectSerializer), `585-601` (get_options), `371-445` (get_attrs), `603+` (serialize) |
| **Event Processing** | `src/sentry/ingest/consumer/processors.py` | `79-200` (process_event function) |
| **Simple Event Processing** | `src/sentry/ingest/consumer/simple_event.py` | TBD |
| **Attachment Event Processing** | `src/sentry/ingest/consumer/attachment_event.py` | TBD |
| **Rate Limit Types** | `src/sentry/types/ratelimit.py` | `1-80` (RateLimit, RateLimitMeta, RateLimitType classes) |
| **Frontend Settings** | `static/app/views/settings/project/` | TBD (need to find specific project settings pages) |
| **Tests - Ingest** | `tests/sentry/ingest/ingest_consumer/test_ingest_consumer_processing.py` | TBD |
| **Tests - Serializer** | `tests/sentry/api/serializers/` | TBD |
| **Tests - Endpoint** | `tests/sentry/core/endpoints/test_project_details.py` | TBD |

This completes the read-only planning task. The implementation would require changes across the options registration system, API serialization/endpoints, event ingestion pipeline, and frontend UI.