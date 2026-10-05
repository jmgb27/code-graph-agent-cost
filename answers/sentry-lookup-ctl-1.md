The project option is `sentry:scrub_ip_address`. Its organization-level counterpart is `sentry:require_scrub_ip_address`. Both appear as `scrubIPAddresses` in the API and UI, and as `scrubIpAddresses` in the config sent to Relay. I didn't include test files.

## Definitions and defaults
- `src/sentry/models/options/project_option.py:53`: `"sentry:scrub_ip_address"` is registered in the project option key list (`OPTION_KEYS`). Because of this, the project serializer loads it at `src/sentry/api/serializers/models/project.py:1047`.
- `src/sentry/constants.py:729`: `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT = False`, the org default.

## Written
**Project:**
- `src/sentry/core/endpoints/project_details.py:342`: the request field `scrubIPAddresses = serializers.BooleanField(...)`.
- `src/sentry/core/endpoints/project_details.py:836-838`: `project.update_option("sentry:scrub_ip_address", ...)`. It also records the change in `changed_proj_settings`, which feeds the audit log.
- `src/sentry/core/endpoints/project_details.py:1175-1177`: an older write path through the raw `options` dict (`options["sentry:scrub_ip_address"]`).

**Organization:**
- `src/sentry/core/endpoints/organization_details.py:172-177`: the `ORG_OPTIONS` entry that maps `scrubIPAddresses` to `sentry:require_scrub_ip_address`. The default comes from the import at `:69`.
- `src/sentry/core/endpoints/organization_details.py:323`: the request field `scrubIPAddresses = serializers.BooleanField(required=False)`.
- `src/sentry/core/endpoints/organization_details.py:648-669`: the generic `ORG_OPTIONS` save loop. It writes the `OrganizationOption` and records changes in `changed_data` for the audit log.
- `src/sentry/core/endpoints/organization_details.py:1017`: the second `scrubIPAddresses` field, with the public API help text.

## Serialized in API responses
- `src/sentry/api/serializers/models/project.py:1012` declares the field type. `:1139` sets `"scrubIPAddresses": bool(attrs["options"].get("sentry:scrub_ip_address", False))`.
- `src/sentry/api/serializers/models/organization.py:654` declares the field type. `:806-807` sets `"scrubIPAddresses": bool(obj.get_option("sentry:require_scrub_ip_address", REQUIRE_SCRUB_IP_ADDRESS_DEFAULT))`. The default is imported at `:51`.
- API docs and examples:
  - `api-docs/components/schemas/project.json:255, :507`
  - `api-docs/components/schemas/organization-details.json:27, :171`
  - `src/sentry/apidocs/examples/project_examples.py:149, :175`
  - `src/sentry/apidocs/examples/organization_examples.py:287`

## Sent to Relay and used for server-side scrubbing
- `src/sentry/relay/datascrubbing.py:63-66`: `get_datascrubbing_settings()` sets `rv["scrubIpAddresses"] = True` when the org option or the project option is on.
  - `src/sentry/relay/config/__init__.py:831` puts this into the project config sent to Relay as `"datascrubbingSettings": get_datascrubbing_settings(project)`. The import is at `:40`.
  - `src/sentry/relay/datascrubbing.py:86` also passes it through `get_all_pii_configs()` into `convert_datascrubbing_config`. Sentry's own `scrub_data()` uses that at `:92`.

## Other reads
- `src/sentry/issues/endpoints/project_event_details.py:204-208`: if the org option or the project option is on, the endpoint removes `user.ip` (and `user` values that start with an IP) from span `sentry_tags` in the event response.

## UI
- Types:
  - `static/app/types/organization.tsx:95`
  - `static/app/types/project.tsx:112`
- Org settings: `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx`
  - `:47` has the schema.
  - `:347-350` has the `AutoSaveForm name="scrubIPAddresses"` toggle, with a confirm prompt when it's turned off.
- Project settings: `static/app/views/settings/projectSecurityAndPrivacy/index.tsx`
  - `:33` has the schema.
  - `:207-210` sets the initial value to `organization.scrubIPAddresses || project.scrubIPAddresses`.
  - `:226-229` disables the switch when the org setting forces it (`orgOverride: Boolean(organization.scrubIPAddresses)`).
- Settings search registry, with the label "Prevent Storing of IP Addresses":
  - `static/app/views/settings/fieldRegistry.generated.ts:425-431` for the project field.
  - `:675-682` for the org field.
- Spec fixture: `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72`.

In every place that applies the setting (Relay config, `scrub_data`, event details, and the project UI), IP scrubbing is on when either the org option or the project option is true.