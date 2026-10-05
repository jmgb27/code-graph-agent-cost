Based on my complete search of the codebase, here are all the locations where `sentry:scrub_ip_address` (project option) and `sentry:require_scrub_ip_address` (organization option) are used:

## **Definition/Registration**
- `src/sentry/models/options/project_option.py:53` — Project option definition

## **Read Operations**
- `src/sentry/relay/datascrubbing.py:63-64` — Reads both org and project options in `get_datascrubbing_settings()`
- `src/sentry/issues/endpoints/project_event_details.py:204-206` — Reads both org and project options to determine if IP scrubbing should apply

## **Write/Update Operations**
- `src/sentry/core/endpoints/project_details.py:837` — `project.update_option("sentry:scrub_ip_address", ...)`
- `src/sentry/core/endpoints/project_details.py:1177` — `project.update_option("sentry:scrub_ip_address", ...)`
- `src/sentry/core/endpoints/organization_details.py:174` — Lists option for organization endpoint update handling

## **Serialization to API Responses**
- `src/sentry/api/serializers/models/project.py:1139` — Serializes as `"scrubIPAddresses"` in project API response
- `src/sentry/api/serializers/models/organization.py:807` — Serializes organization option as `"scrubIPAddresses"` in organization API response

## **Sent to Relay (PII Config)**
- `src/sentry/relay/datascrubbing.py:49-77` — `get_datascrubbing_settings()` function creates config with `"scrubIpAddresses": True` sent to Relay via `get_all_pii_configs()` at line 80-88

## **Frontend/UI Type Definitions**
- `static/app/types/project.tsx:112` — TypeScript type definition for project
- `static/app/types/organization.tsx:95` — TypeScript type definition for organization

## **Frontend/UI Settings Forms**
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:33` — Form schema definition
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:207` — Form field name
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:210` — Form initial value (reads both org and project)
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:228` — Shows org override indicator
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:47` — Form schema definition
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:348` — Form field name
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:350` — Form initial value

## **Frontend Field Registry**
- `static/app/views/settings/fieldRegistry.generated.ts:425-426` — Project field registry
- `static/app/views/settings/fieldRegistry.generated.ts:675-676` — Organization field registry

## **Tests**
- `tests/sentry/relay/test_datascrubbing.py:40` — Updates org option
- `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68` — Updates project option
- `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25` — Updates project option
- `tests/sentry/models/test_organization.py:117, 119` — Tests organization option
- `tests/sentry/core/endpoints/test_project_details.py:662, 761-762, 922-928` — Tests project option updates and reads
- `tests/sentry/core/endpoints/test_organization_details.py:796` — Tests organization option
- `tests/snuba/api/endpoints/test_project_event_details.py:482, 492, 502` — Tests scrubbing behavior with both options
- `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72` — Frontend test

## **API Documentation Examples**
- `src/sentry/apidocs/examples/project_examples.py:149` — Example project configuration