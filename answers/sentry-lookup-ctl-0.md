There are two options. The project option is `sentry:scrub_ip_address`. The organization-level one is `sentry:require_scrub_ip_address`. Both are exposed through the API as `scrubIPAddresses` and sent to Relay as `scrubIpAddresses`. I found them by grepping every spelling (`scrub_ip`, `SCRUB_IP`, `scrubIP`, `scrubIp`), not by tracing through an indexer.

## Project option `sentry:scrub_ip_address`

**Registration and defaults**
- `src/sentry/models/options/project_option.py:53`: listed in the `OPTION_KEYS` frozenset of known project option keys.

**Written by `src/sentry/core/endpoints/project_details.py` (PUT)**
- Line 342: the `scrubIPAddresses` BooleanField on the serializer ("Discard client IP addresses rather than storing them on events").
- Lines 836–838: `project.update_option("sentry:scrub_ip_address", result["scrubIPAddresses"])`, which also records the change in `changed_proj_settings` for the audit log.
- Lines 1175–1177: the older raw `options` dict path, which writes `bool(options["sentry:scrub_ip_address"])`.

**Serialized**
- `src/sentry/api/serializers/models/project.py:1012`: the `scrubIPAddresses: bool` field on the response TypedDict.
- `src/sentry/api/serializers/models/project.py:1139`: `bool(attrs["options"].get("sentry:scrub_ip_address", False))`.

## Organization option `sentry:require_scrub_ip_address`

**Default**
- `src/sentry/constants.py:729`: `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT = False`.

**Written by `src/sentry/core/endpoints/organization_details.py`**
- Line 69: imports the default.
- Lines 172–177: the `ORG_OPTIONS` entry that maps `scrubIPAddresses` to `sentry:require_scrub_ip_address` (bool, with that default).
- Lines 647–668: the generic `ORG_OPTIONS` loop does the actual write and records the change for the audit log.
- Line 323: the `scrubIPAddresses` BooleanField on the internal serializer.
- Line 1017: the `scrubIPAddresses` BooleanField on the public, documented serializer ("…on all projects").

**Serialized**
- `src/sentry/api/serializers/models/organization.py:51`: imports the default.
- `src/sentry/api/serializers/models/organization.py:654`: the `scrubIPAddresses: bool` field on the TypedDict.
- `src/sentry/api/serializers/models/organization.py:806–807`: `obj.get_option("sentry:require_scrub_ip_address", REQUIRE_SCRUB_IP_ADDRESS_DEFAULT)`.

## Reads that combine both options (org OR project)

- **Relay:** `src/sentry/relay/datascrubbing.py:63–66`, in `get_datascrubbing_settings`, sets `rv["scrubIpAddresses"] = True` if either option is on.
  - `src/sentry/relay/config/__init__.py:831` sends this result to Relay as `config.datascrubbingSettings`.
  - `src/sentry/relay/datascrubbing.py:86–88` also uses it in `get_all_pii_configs`, which feeds the Python-side `scrub_data` at line 92.
- **Event details API:** `src/sentry/issues/endpoints/project_event_details.py:204–208` removes `user.ip` and IP-based `user` values from span `sentry_tags` in the response when either option is on.

## UI (`static/`)

**Types**
- `static/app/types/project.tsx:112`
- `static/app/types/organization.tsx:95`

**Project settings: `static/app/views/settings/projectSecurityAndPrivacy/index.tsx`**
- Line 33: the zod schema field.
- Lines 206–234: the "Prevent Storing of IP Addresses" `AutoSaveForm`.
  - Line 210: the initial value is `organization.scrubIPAddresses || project.scrubIPAddresses`.
  - Line 228: the switch is disabled when the org enforces it (`orgOverride`).

**Organization settings: `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx`**
- Line 47: the zod schema field.
- Lines 347–360: the `AutoSaveForm`, with a confirmation dialog that warns about ALL projects when disabling.

**Field registry for settings search:** `static/app/views/settings/fieldRegistry.generated.ts`
- Lines 425–431: the project entry.
- Lines 675–682: the organization entry.

## API docs and examples

- `api-docs/components/schemas/project.json:255, 507`
- `api-docs/components/schemas/organization-details.json:27, 171`
- `src/sentry/apidocs/examples/project_examples.py:149` (raw option) and `:175`
- `src/sentry/apidocs/examples/organization_examples.py:287`

## Tests and fixtures

**Backend**
- Relay config:
  - `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68, 147`
  - `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25, 103`
- `tests/sentry/relay/test_datascrubbing.py:40`: this sets `sentry:scrub_ip_address` on the **organization**, but the organization key is `require_scrub_ip_address`. That looks like a mismatched key, so the setting probably has no effect.
- Project endpoint: `tests/sentry/core/endpoints/test_project_details.py:662, 761–762, 922–929`
- Organization endpoint: `tests/sentry/core/endpoints/test_organization_details.py:758, 796, 830`
- Event details: `tests/snuba/api/endpoints/test_project_event_details.py:482, 492, 502`
- `tests/sentry/models/test_organization.py:117–119`

**Frontend**
- `tests/js/fixtures/project.ts:70`
- `tests/js/fixtures/organization.ts:86`
- `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72`