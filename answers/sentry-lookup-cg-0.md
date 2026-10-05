The project option is `sentry:scrub_ip_address`. The organization-level option is `sentry:require_scrub_ip_address`. Both appear as `scrubIPAddresses` in the API and UI. Relay receives them as a single `scrubIpAddresses` flag. I found every reference by searching the codebase for these names, then read the code around each one.

## Option registration and defaults
- `src/sentry/models/options/project_option.py:53`: `"sentry:scrub_ip_address"` is in `OPTION_KEYS` (the set starts at `:20`). That set decides which project options the detailed project serializer loads (`api/serializers/models/project.py:1047`).
- `src/sentry/constants.py:729`: `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT = False`, the org default.

## Writes
**Project**
- `src/sentry/core/endpoints/project_details.py:342`: the `scrubIPAddresses` BooleanField on the project PUT serializer.
- `src/sentry/core/endpoints/project_details.py:836-838`: `project.update_option("sentry:scrub_ip_address", result["scrubIPAddresses"])`. The change is also recorded in `changed_proj_settings`, which feeds the audit log.
- `src/sentry/core/endpoints/project_details.py:1175-1177`: a second path, where the value is written from a raw `options` dict as `bool(options["sentry:scrub_ip_address"])`.

**Organization**
- `src/sentry/core/endpoints/organization_details.py:172-177`: the `ORG_OPTIONS` entry mapping `scrubIPAddresses` to `sentry:require_scrub_ip_address` (`bool`, default `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT`). The constant is imported at `:69`.
- `src/sentry/core/endpoints/organization_details.py:323`: `scrubIPAddresses = serializers.BooleanField(required=False)` on the org serializer.
- `src/sentry/core/endpoints/organization_details.py:648-669`: the generic `ORG_OPTIONS` loop in `save()`. It writes the `OrganizationOption` and records the change for the audit log.
- `src/sentry/core/endpoints/organization_details.py:1017`: the `scrubIPAddresses` field with its public API docs help text.

## Reads and serialization
- `src/sentry/api/serializers/models/project.py:1012` declares the response type. `:1139` serializes `bool(attrs["options"].get("sentry:scrub_ip_address", False))`.
- `src/sentry/api/serializers/models/organization.py:654` declares the response type. `:806-807` serializes `obj.get_option("sentry:require_scrub_ip_address", REQUIRE_SCRUB_IP_ADDRESS_DEFAULT)`; the constant is imported at `:51`.
- `src/sentry/issues/endpoints/project_event_details.py:204-208`: reads `org require_scrub_ip_address OR project scrub_ip_address`. If either is set, IP data (`user.ip`, `user`) is removed from span `sentry_tags` in the event details response.

## Sent to Relay
- `src/sentry/relay/datascrubbing.py:63-66`, in `get_datascrubbing_settings()`: if `org sentry:require_scrub_ip_address OR project sentry:scrub_ip_address`, it sets `rv["scrubIpAddresses"] = True`.
- `src/sentry/relay/config/__init__.py:831`: puts that dict in the project config as `"datascrubbingSettings"`, which Relay fetches.
- The same settings are also used for scrubbing inside Sentry: `datascrubbing.py:86` (`get_all_pii_configs`) → `:93` (`scrub_data`) → `src/sentry/tasks/store.py:413`.

## API docs and examples
- `api-docs/components/schemas/project.json:255, 507`
- `api-docs/components/schemas/organization-details.json:27, 171`
- `src/sentry/apidocs/examples/project_examples.py:149` (the `sentry:scrub_ip_address` option) and `:175` (`scrubIPAddresses`)
- `src/sentry/apidocs/examples/organization_examples.py:287`

## Frontend
- Types: `static/app/types/project.tsx:112`, `static/app/types/organization.tsx:95`
- Project settings page, `static/app/views/settings/projectSecurityAndPrivacy/index.tsx`:
  - `:33` is the schema field.
  - `:206-237` is the "Prevent Storing of IP Addresses" toggle. Its initial value is `org || project` (`:210`), and it is disabled when the org setting forces it on (`orgOverride`, `:228`).
- Org settings page, `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx`:
  - `:47` is the schema field.
  - `:347-350` onward is the toggle, with an "affects ALL projects" confirmation when you disable it.
- Settings search registry: `static/app/views/settings/fieldRegistry.generated.ts:425` (project) and `:675` (org).

## Tests and fixtures
- JS fixtures: `tests/js/fixtures/project.ts:70`, `tests/js/fixtures/organization.ts:86`
- JS spec: `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72`
- Project details: `tests/sentry/core/endpoints/test_project_details.py:662, 761-762, 922-929`
- Org details: `tests/sentry/core/endpoints/test_organization_details.py:758, 796, 830`
- Org model: `tests/sentry/models/test_organization.py:117-119`
- Relay project configs: `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68, 147` and `test_relay_projectconfigs_v2.py:25, 103`
- Datascrubbing: `tests/sentry/relay/test_datascrubbing.py:40`. This test sets the project key `sentry:scrub_ip_address` on the organization, not the org key `sentry:require_scrub_ip_address`, so that call has no effect on scrubbing.
- Event details: `tests/snuba/api/endpoints/test_project_event_details.py:482, 492, 502`