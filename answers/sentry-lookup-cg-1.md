I found all the call sites. There are two options: the project option `sentry:scrub_ip_address` and the organization option `sentry:require_scrub_ip_address`. The API and UI call both of them `scrubIPAddresses`, and Relay receives the combined result as `scrubIpAddresses`. I didn't edit any files.

## Backend: reads, writes, and serialization

**Project option `sentry:scrub_ip_address`**
- **Registration:** `src/sentry/models/options/project_option.py:53`. It's in `OPTION_KEYS`, and the project serializer bulk-loads those keys at `src/sentry/api/serializers/models/project.py:1047`.
- **API input field:** `src/sentry/core/endpoints/project_details.py:342`, a `BooleanField` for `scrubIPAddresses`.
- **Write via the `scrubIPAddresses` field:** `src/sentry/core/endpoints/project_details.py:836-838`. It calls `project.update_option` and records the change in `changed_proj_settings`.
- **Write via the raw `options` dict:** `src/sentry/core/endpoints/project_details.py:1175-1177`, which saves the value with `bool(...)`.
- **Serialized (read):** the type is declared at `src/sentry/api/serializers/models/project.py:1012`, and the value is filled in at `:1139` with a default of `False`.

**Org option `sentry:require_scrub_ip_address`**
- **Default constant:** `src/sentry/constants.py:729` sets `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT = False`.
- **API field mapping:** `src/sentry/core/endpoints/organization_details.py:172-177` is the `ORG_OPTIONS` entry that maps `scrubIPAddresses` to the option.
- **API input fields:** `organization_details.py:323` and `:1017`, both `BooleanField`s.
- **Write:** the generic `ORG_OPTIONS` save loop at `organization_details.py:648-669`, which also records the change for the audit log.
- **Serialized (read):** the type is declared at `src/sentry/api/serializers/models/organization.py:654`, and the value is read at `:806-807`.

## Sent to Relay and applied to events
- **Combined value:** `src/sentry/relay/datascrubbing.py:63-66`, in `get_datascrubbing_settings`. If the org option or the project option is on, it sets `rv["scrubIpAddresses"] = True`.
- **Relay project config:** `src/sentry/relay/config/__init__.py:831` puts that result in `"datascrubbingSettings"`.
- **Python-side scrubbing:** `datascrubbing.py:86` converts the same settings into a PII config inside `get_all_pii_configs`, which is used by `scrub_data`. `scrub_data` is called from `src/sentry/tasks/store.py:413`.

## Read at query time
- `src/sentry/issues/endpoints/project_event_details.py:204-208` applies the same OR of org and project options, then strips `user.ip` and IP-based `user` tags from spans in the event response.

## API docs and examples
- `api-docs/components/schemas/project.json:255` and `:507`
- `api-docs/components/schemas/organization-details.json:27` and `:171`
- `src/sentry/apidocs/examples/project_examples.py:149` (the raw option) and `:175` (the API field)
- `src/sentry/apidocs/examples/organization_examples.py:287`

## Frontend UI
- **Types:** `static/app/types/organization.tsx:95` and `static/app/types/project.tsx:112`
- **Org settings page:** `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:47` (schema) and `:348-357` (the `AutoSaveForm`, which asks for confirmation before turning it off).
- **Project settings page:** `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:33` (schema) and `:207-228`.
  - The toggle shows as on if either the org or the project setting is on (`:210`).
  - It is disabled when the org setting forces it (`orgOverride`, `:228`).
- **Settings search registry:** `static/app/views/settings/fieldRegistry.generated.ts:425` (project) and `:675` (org).

## Tests and fixtures
- **Backend:**
  - `tests/sentry/core/endpoints/test_project_details.py:662`, `:761-762`, `:922-929`
  - `tests/sentry/core/endpoints/test_organization_details.py:758`, `:796`, `:830`
  - `tests/sentry/models/test_organization.py:117-119`
  - `tests/snuba/api/endpoints/test_project_event_details.py:482`, `:492`, `:502`
  - `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68`, `:147`
  - `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25`, `:103`
- **Frontend:** `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72`, plus the fixtures `tests/js/fixtures/organization.ts:86` and `tests/js/fixtures/project.ts:70`

One likely bug: `tests/sentry/relay/test_datascrubbing.py:40` sets `sentry:scrub_ip_address` on the **organization**. The code only reads `sentry:require_scrub_ip_address` at the org level, so that line has no effect.