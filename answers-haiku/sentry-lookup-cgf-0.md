Perfect! Now I have the complete picture. Here's a comprehensive summary of all references to `sentry:scrub_ip_address` (project-level) and `sentry:require_scrub_ip_address` (organization-level):

## Backend - Read/Write Operations

**Project-level option reads:**
- `src/sentry/api/serializers/models/project.py:1139` - Serialized to API response as `scrubIPAddresses`
- `src/sentry/issues/endpoints/project_event_details.py:206` - Read to determine if IP scrubbing should apply
- `src/sentry/relay/datascrubbing.py:64` - Read to send IP scrubbing config to Relay

**Project-level option writes:**
- `src/sentry/core/endpoints/project_details.py:837` - Written via `project.update_option()`
- `src/sentry/core/endpoints/project_details.py:838` - Tracked in changed settings
- `src/sentry/core/endpoints/project_details.py:1177` - Written via `project.update_option()` (from Relay push)

**Organization-level option reads:**
- `src/sentry/api/serializers/models/organization.py:807` - Serialized to API response as `scrubIPAddresses`
- `src/sentry/issues/endpoints/project_event_details.py:204-205` - Read to determine if IP scrubbing should apply
- `src/sentry/relay/datascrubbing.py:63` - Read to send IP scrubbing config to Relay

**Organization-level option definition:**
- `src/sentry/core/endpoints/organization_details.py:174` - Defined as `sentry:require_scrub_ip_address` option

**Project-level option definition:**
- `src/sentry/models/options/project_option.py:53` - Listed in `SENTRY_PROJECT_OPTIONS`

**API Documentation:**
- `src/sentry/apidocs/examples/project_examples.py:149` - Example showing project option

## Frontend - UI Display & Serialization

**Type definitions:**
- `static/app/types/organization.tsx:95` - `scrubIPAddresses: boolean` in Organization type
- `static/app/types/project.tsx:112` - `scrubIPAddresses: boolean` in Project type

**Settings UI - Project level:**
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:33` - Form schema definition
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:207` - Form field `name="scrubIPAddresses"`
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:210` - Form value resolution (org OR project)
- `static/app/views/settings/projectSecurityAndPrivacy/index.tsx:228` - Org override tracking

**Settings UI - Organization level:**
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:47` - Form schema definition
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:348` - Form field `name="scrubIPAddresses"`
- `static/app/views/settings/organizationSecurityAndPrivacy/index.tsx:350` - Initial value binding

**Generated field registry:**
- `static/app/views/settings/fieldRegistry.generated.ts:425-426` - Project setting metadata
- `static/app/views/settings/fieldRegistry.generated.ts:675-676` - Organization setting metadata

## Tests

**Test files:**
- `tests/sentry/core/endpoints/test_project_details.py:662` - Test data
- `tests/sentry/core/endpoints/test_project_details.py:761-762` - Assertion checking project option
- `tests/sentry/core/endpoints/test_project_details.py:922-929` - Test function `test_scrub_ip_address()`
- `tests/sentry/core/endpoints/test_organization_details.py:796` - Assertion checking org option
- `tests/snuba/api/endpoints/test_project_event_details.py:482` - Project-level test setup
- `tests/snuba/api/endpoints/test_project_event_details.py:492` - Organization-level test setup  
- `tests/snuba/api/endpoints/test_project_event_details.py:502` - Organization-level test setup
- `tests/sentry/relay/test_datascrubbing.py:40` - Test setup (note: incorrectly set on org)
- `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68` - Test fixture setup
- `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25` - Test fixture setup
- `tests/sentry/models/test_organization.py:117-119` - Organization option change tracking test
- `static/app/views/settings/projectSecurityAndPrivacy/index.spec.tsx:72` - Frontend test

**Project-level option spec test:**