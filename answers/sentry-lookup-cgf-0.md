There are two settings. The project one is stored as `sentry:scrub_ip_address`. The organization one is stored as `sentry:require_scrub_ip_address`, and when it's on, every project in the org is forced to scrub. Both appear in the API and the UI as `scrubIPAddresses`, and Relay receives them combined as `scrubIpAddresses`.

## Project option `sentry:scrub_ip_address`

**Registered and serialized**
- `src/sentry/models/options/project_option.py:53`: listed in `OPTION_KEYS`.
- `src/sentry/api/serializers/models/project.py:1047`: loads the `OPTION_KEYS` project options in bulk.
- `src/sentry/api/serializers/models/project.py:1115`: included in the raw `"options"` map returned by the API.
- `src/sentry/api/serializers/models/project.py:1012`: `scrubIPAddresses: bool` type.
- `src/sentry/api/serializers/models/project.py:1139`: returned as `"scrubIPAddresses": bool(attrs["options"].get("sentry:scrub_ip_address", False))`.

**Written (project details PUT)**
- `src/sentry/core/endpoints/project_details.py:342`: `scrubIPAddresses` serializer field.
- `src/sentry/core/endpoints/project_details.py:836-838`: `project.update_option("sentry:scrub_ip_address", ...)`, and the change is recorded for the audit log.
- `src/sentry/core/endpoints/project_details.py:1175-1178`: a second write path, through the raw `options` dict, as `bool(...)`.

**Read**
- `src/sentry/relay/datascrubbing.py:63-66`: combined with the org option.
- `src/sentry/issues/endpoints/project_event_details.py:204-208`: combined with the org option to strip `user.ip` from span `sentry_tags` in the event details response.

## Organization option `sentry:require_scrub_ip_address`

- `src/sentry/constants.py:729`: `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT = False`.
- **Written:**
  - `src/sentry/core/endpoints/organization_details.py:173-176`: an `ORG_OPTIONS` entry that maps `scrubIPAddresses` to the option, with the default above.
  - `src/sentry/core/endpoints/organization_details.py:323`: `scrubIPAddresses` serializer field.
  - `src/sentry/core/endpoints/organization_details.py:648-669`: the generic `ORG_OPTIONS` loop that writes the `OrganizationOption` and records the audit-log change.
  - `src/sentry/core/endpoints/organization_details.py:1017`: the documented PUT serializer field.
- **Serialized:**
  - `src/sentry/api/serializers/models/organization.py:654`: type.
  - `src/sentry/api/serializers/models/organization.py:806-807`: `"scrubIPAddresses": bool(obj.get_option("sentry:require_scrub_ip_address", REQUIRE_SCRUB_IP_ADDRESS_DEFAULT))`.
- **Read:** `src/sentry/relay/datascrubbing.py:63` and `src/sentry/issues/endpoints/project_event_details.py:204-205`.

## Sent to Relay
- `src/sentry/relay/datascrubbing.py:49` `get_datascrubbing_settings`: sets `rv["scrubIpAddresses"] = True` if the org option **or** the project option is on (lines 63-66).
- `src/sentry/relay/config/__init__.py:831`: included in the project config as `"datascrubbingSettings": get_datascrubbing_settings(project)`.
- `src/sentry/relay/datascrubbing.py:86-88`: the same settings are converted into a PII config (`convert_datascrubbing_config`) for Sentry-side scrubbing in `scrub_data`.

## UI (frontend)
- Types: `static/app/types/organization.tsx:95` and `static/app/types/project.tsx:112`.
- Organization settings: `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:47` (schema) and `:348-350` (the `scrubIPAddresses` form, initialised from `organization.scrubIPAddresses`).
- Project settings, "Prevent Storing of IP Addresses": `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:33` (schema) and `:206-237`.
  - The toggle shows as on if either the org or the project setting is on (`:210`).
  - It is disabled when the org setting forces scrubbing (`orgOverride`, `:228`).
  - Turning it off asks for confirmation (`:213-217`).
- Settings search registry: `static/app/views/settings/fieldRegistry.generated.ts:425-426` (project) and `:675-676` (org).

## API docs and examples
- `api-docs/components/schemas/project.json:255, 507`
- `api-docs/components/schemas/organization-details.json:27, 171`
- `src/sentry/apidocs/examples/project_examples.py:149, 175`
- `src/sentry/apidocs/examples/organization_examples.py:287`

## Tests and fixtures
- Project details: `tests/sentry/core/endpoints/test_project_details.py:662, 761-762, 922-929`
- Org details: `tests/sentry/core/endpoints/test_organization_details.py:758, 796, 830`
- Org option model: `tests/sentry/models/test_organization.py:117-119`
- Relay project configs: `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68, 147` and `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25, 103`
- Event details: `tests/snuba/api/endpoints/test_project_event_details.py:482, 492, 502`
- `tests/sentry/relay/test_datascrubbing.py:40` sets `sentry:scrub_ip_address` on the **organization**. Production code never reads that org key; the org setting is `sentry:require_scrub_ip_address`, so this line likely has no effect.
- JS fixtures: `tests/js/fixtures/project.ts:70`, `tests/js/fixtures/organization.ts:86`, `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72`

The `sentry` MCP server needs authorization before it can be used. It wasn't needed for this task. You can authorize it with `claude mcp` or `/mcp` in an interactive session.