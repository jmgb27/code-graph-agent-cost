Based on my codegraph exploration, here are all the places where `sentry:scrub_ip_address` and its organization-level counterpart `sentry:require_scrub_ip_address` are read, written, serialized, sent to Relay, or shown in the UI:

## Core Settings & Serialization

**Backend - Option Reading & Serialization:**
- `src/sentry/relay/datascrubbing.py:63-66` — Reads both org and project options and converts to `scrubIpAddresses` for Relay
- `src/sentry/constants.py:729` — Defines `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT` constant

**Backend - API Serializers (Organization Level):**
- `src/sentry/api/serializers/models/organization.py` — Serializes org-level option for API response
- `src/sentry/core/endpoints/organization_details.py` — Exposes org-level option in organization details endpoint

**Backend - Project Option Model:**
- `src/sentry/models/options/project_option.py:122-137` — `ProjectOptionManager.get_value()` retrieves project-level option
- `src/sentry/models/options/organization_option.py:135` — `get_option()` function retrieves org-level option

## Relay Integration

**Datascrubbing Config Sent to Relay:**
- `src/sentry/relay/datascrubbing.py:49-77` — `get_datascrubbing_settings()` builds config with `scrubIpAddresses` field
- `src/sentry/relay/datascrubbing.py:80-88` — `get_all_pii_configs()` yields converted config for Relay

**Data Processing:**
- `src/sentry/relay/datascrubbing.py:92-109` — `scrub_data()` applies datascrubbing (traces to production)
- `src/sentry/tasks/store.py:343` — `do_process_event()` calls `scrub_data()` during event processing

## Frontend UI

**Data Scrubbing Settings Component:**
- `static/app/views/settings/components/dataScrubbing/index.tsx:44` — `DataScrubbing` component displays/edits rules
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx` — Organization-level security settings
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx` — Project-level security settings

## Tests

- `tests/sentry/relay/test_datascrubbing.py` — Tests datascrubbing settings conversion
- `tests/sentry/core/endpoints/test_organization_details.py` — Tests org details endpoint
- `static/app/views/settings/components/dataScrubbing/index.spec.tsx` — Tests UI component