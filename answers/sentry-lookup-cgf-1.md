Two options control this. The project one is `sentry:scrub_ip_address`. The organization one is `sentry:require_scrub_ip_address`, which defaults to `False` (`REQUIRE_SCRUB_IP_ADDRESS_DEFAULT` at `src/sentry/constants.py:729`). The API and UI call both of them `scrubIPAddresses`. When the value goes to Relay it is called `scrubIpAddresses`, with a lowercase "p". I searched every spelling of both option keys and field names across the repo, and the lists below are what turned up.

## Read (backend logic)
- **Relay settings:** `src/sentry/relay/datascrubbing.py:63-66`. In `get_datascrubbing_settings()`, if either the org or the project option is on, it sets `rv["scrubIpAddresses"] = True`.
- **Event details endpoint:** `src/sentry/issues/endpoints/project_event_details.py:204-208`. It uses the same "org or project" check, and when it's true it strips `user.ip` (and the IP form of `user`) from span `sentry_tags` in the response.

## Sent to Relay
- `src/sentry/relay/config/__init__.py:831`: `_get_project_config()` puts `"datascrubbingSettings": get_datascrubbing_settings(project)` into the project config Relay receives.
- `src/sentry/relay/datascrubbing.py:86-88`: `get_all_pii_configs()` turns the same settings into a PII config using `convert_datascrubbing_config`.

## Written
- **Project, through the API field:** `src/sentry/core/endpoints/project_details.py:342` declares the serializer field. `:836-838` calls `project.update_option("sentry:scrub_ip_address", …)` and records the change for the audit log.
- **Project, through the raw `options` dict:** `src/sentry/core/endpoints/project_details.py:1175-1177`.
- **Project option key registration:** `src/sentry/models/options/project_option.py:53` lists `sentry:scrub_ip_address` among the known project option keys.
- **Organization:** the `ORG_OPTIONS` tuple maps `scrubIPAddresses` to `sentry:require_scrub_ip_address` at `src/sentry/core/endpoints/organization_details.py:172-177` (imported at `:69`). The generic save loop at `:647-668` writes it and records the audit-log change. The serializer fields are at `:323` and `:1017` (the second one carries the API docs help text).

## Serialized (API output)
- **Project:** `src/sentry/api/serializers/models/project.py:1012` (the type) and `:1139` (`"scrubIPAddresses": bool(attrs["options"].get("sentry:scrub_ip_address", False))`).
- **Organization:** `src/sentry/api/serializers/models/organization.py:654` (the type) and `:806-807` (import at `:51`).
- **API docs and examples:**
  - `api-docs/components/schemas/project.json:255, 507`
  - `api-docs/components/schemas/organization-details.json:27, 171`
  - `src/sentry/apidocs/examples/project_examples.py:149, 175`
  - `src/sentry/apidocs/examples/organization_examples.py:287`

## UI
- **Types:** `static/app/types/project.tsx:112` and `static/app/types/organization.tsx:95`.
- **Project settings page:** `static/app/views/settings/projectSecurityAndPrivacy/index.tsx`
  - `:33` is the schema.
  - `:206-235` is the "Prevent Storing of IP Addresses" toggle. Its starting value is `organization.scrubIPAddresses || project.scrubIPAddresses`, and it is disabled when the org setting forces it on (`orgOverride`, `:228`).
- **Org settings page:** `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx`
  - `:47` is the schema.
  - `:347-360` is the toggle, which asks for confirmation before it is turned off.
- **Settings search registry:** `static/app/views/settings/fieldRegistry.generated.ts:425-430` (project) and `:675-680` (org).

## Tests and fixtures
- **Relay:**
  - `tests/sentry/relay/test_datascrubbing.py:40`. This test sets `sentry:scrub_ip_address` on the organization, but the org-level key is `sentry:require_scrub_ip_address`, so that line probably has no effect.
  - `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68, 147`
  - `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25, 103`
- **Endpoints:**
  - `tests/sentry/core/endpoints/test_project_details.py:662, 761-762, 922-929`
  - `tests/sentry/core/endpoints/test_organization_details.py:758, 796, 830`
  - `tests/snuba/api/endpoints/test_project_event_details.py:482, 492, 502`
- **Models:** `tests/sentry/models/test_organization.py:117-119`
- **JS:**
  - `tests/js/fixtures/project.ts:70`
  - `tests/js/fixtures/organization.ts:86`
  - `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72`