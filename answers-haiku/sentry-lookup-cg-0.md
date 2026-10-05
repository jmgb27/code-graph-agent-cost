Based on my comprehensive search, here's every place where `sentry:scrub_ip_address` (project-level) and `sentry:require_scrub_ip_address` (organization-level) are read, written, serialized, sent to Relay, or shown in the UI:

## **Option Registration & Configuration**

- `src/sentry/models/options/project_option.py:53` — project option registered in allowlist
- `src/sentry/constants.py:729` — `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT` constant

## **Backend — Reading Options**

- `src/sentry/relay/datascrubbing.py:63-66` — both options read in `get_datascrubbing_settings()` to build config
- `src/sentry/issues/endpoints/project_event_details.py:205` — organization option read for event display logic
- `src/sentry/issues/endpoints/project_event_details.py` (earlier in same file) — project option read

## **Backend — Writing/Setting Options**

- `src/sentry/core/endpoints/project_details.py` — project option set via `project.update_option("sentry:scrub_ip_address", ...)`
- `src/sentry/core/endpoints/organization_details.py:174` — organization option written

## **Serialization — API Responses**

- `src/sentry/api/serializers/models/organization.py:807` — organization option read and serialized to `scrubIPAddresses` field
- `src/sentry/api/serializers/models/organization.py:654` — `scrubIPAddresses: bool` in response type
- `src/sentry/api/serializers/models/project.py` — project option serialized to `scrubIPAddresses` field
- `src/sentry/core/endpoints/project_details.py` — response includes serialized `scrubIPAddresses`
- `src/sentry/core/endpoints/organization_details.py` — response includes serialized `scrubIPAddresses`

## **Sent to Relay**

- `src/sentry/relay/datascrubbing.py:49-77` — `get_datascrubbing_settings()` builds config with `scrubIpAddresses: True` sent to Relay
- `src/sentry/relay/datascrubbing.py:80-88` — `get_all_pii_configs()` converts datascrubbing settings to PII config for Relay
- `tests/sentry/api/endpoints/test_relay_projectconfigs.py:147` — Relay config test verifies `scrubIpAddresses` in output
- `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:103` — Relay config v2 test verifies `scrubIpAddresses` in output

## **Frontend UI — Settings Pages**

- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx` — project setting form with `scrubIPAddresses` field
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx` — organization setting form with `scrubIPAddresses` field
- `static/app/views/settings/fieldRegistry.generated.ts` — field registry entries for both settings

## **Frontend — Types**

- `static/app/types/project.tsx` — `scrubIPAddresses: boolean` field type
- `static/app/types/organization.tsx` — `scrubIPAddresses: boolean` field type

## **Tests — Backend**

- `tests/sentry/core/endpoints/test_project_details.py:922-929` — project option set/get test
- `tests/sentry/core/endpoints/test_organization_details.py:758`, `796`, `830` — organization option set/get test
- `tests/sentry/models/test_organization.py:117-119` — organization option creation test
- `tests/snuba/api/endpoints/test_project_event_details.py:482`, `492`, `502` — event details tests read both options
- `tests/sentry/relay/test_datascrubbing.py:40` — datascrubbing test with option set
- `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68` — relay config v1 test sets option
- `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25` — relay config v2 test sets option

## **Tests — Frontend**

- `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx` — UI test for project setting

## **Examples/Documentation**

- `src/sentry/apidocs/examples/organization_examples.py` — example organization config
- `src/sentry/apidocs/examples/project_examples.py` — example project config