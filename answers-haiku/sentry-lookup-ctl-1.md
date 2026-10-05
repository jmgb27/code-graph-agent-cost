Based on my comprehensive search, here are all the places where `sentry:scrub_ip_address` (project-level) and `sentry:require_scrub_ip_address` (organization-level) are referenced:

## Option Definition

**src/sentry/models/options/project_option.py:53** - Project option key definition in OPTION_KEYS
**src/sentry/constants.py:729** - Organization-level default constant: `REQUIRE_SCRUB_IP_ADDRESS_DEFAULT = False`

## Reading & Writing Options

**src/sentry/core/endpoints/project_details.py:837** - Writing project option from API request
**src/sentry/core/endpoints/project_details.py:838** - Tracking project option change
**src/sentry/core/endpoints/project_details.py:1175** - Reading project option for internal update
**src/sentry/core/endpoints/project_details.py:1177** - Writing project option
**src/sentry/core/endpoints/organization_details.py:174** - Organization-level option field definition

## Serialization (Sent to API Clients)

**src/sentry/api/serializers/models/project.py:1139** - Serializing project option to `scrubIPAddresses` field
**src/sentry/api/serializers/models/organization.py:807** - Serializing organization option to `scrubIPAddresses` field

## Relay & Data Processing (Sent to/Used by Relay)

**src/sentry/relay/datascrubbing.py:63** - Reading organization-level option
**src/sentry/relay/datascrubbing.py:64** - Reading project-level option
**src/sentry/issues/endpoints/project_event_details.py:204-206** - Reading both organization and project options for span data scrubbing

## UI Display (Frontend)

**static/app/views/settings/fieldRegistry.generated.ts:425** - Project security settings field registry
**static/app/views/settings/fieldRegistry.generated.ts:675** - Organization security settings field registry

## Documentation/Examples

**src/sentry/apidocs/examples/project_examples.py:149** - Example project configuration

## Tests

**tests/sentry/relay/test_datascrubbing.py:40**
**tests/sentry/core/endpoints/test_project_details.py:662, 761-762, 922-928**
**tests/sentry/core/endpoints/test_organization_details.py:796**
**tests/sentry/models/test_organization.py:117, 119**
**tests/snuba/api/endpoints/test_project_event_details.py:482, 492, 502**
**tests/sentry/api/endpoints/test_relay_projectconfigs.py:68**
**tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25**