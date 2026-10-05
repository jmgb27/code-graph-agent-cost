## `sentry:scrub_ip_address` and `sentry:require_scrub_ip_address` References

Here's a complete mapping of where these options are read, written, serialized, sent to Relay, or shown in the UI:

### **Project Option Definition & Registration**
- `src/sentry/models/options/project_option.py:53` — `sentry:scrub_ip_address` registered in OPTION_KEYS frozenset

### **Organization Option Mapping**
- `src/sentry/core/endpoints/organization_details.py:173-177` — `sentry:require_scrub_ip_address` mapped in ORG_OPTIONS tuple with defaults

### **Relay/Datascrubbing (Read & Sent to Relay)**
- `src/sentry/relay/datascrubbing.py:63-66` — Both org (`sentry:require_scrub_ip_address`) and project (`sentry:scrub_ip_address`) options read and converted to `scrubIpAddresses` in config sent to Relay

### **Project API Endpoint (Write)**
- `src/sentry/core/endpoints/project_details.py:836-838` — Serializer field `scrubIPAddresses` → project option write
- `src/sentry/core/endpoints/project_details.py:1175-1178` — Legacy options dict path for project option write

### **Organization API Endpoint (Write)**
- `src/sentry/core/endpoints/organization_details.py:123-177` — Serializer field `scrubIPAddresses` handles org option in ORG_OPTIONS tuple

### **Project Serializer (Read & Serialize)**
- `src/sentry/api/serializers/models/project.py:1139` — Project option serialized as `scrubIPAddresses` in API response

### **Organization Serializer (Read & Serialize)**
- `src/sentry/api/serializers/models/organization.py:806-808` — Org option `sentry:require_scrub_ip_address` read and serialized as `scrubIPAddresses`

### **Event Details Endpoint (Read for UI)**
- `src/sentry/issues/endpoints/project_event_details.py:204-208` — Both options read to determine if IP addresses should be scrubbed when returning event data to UI

### **API Examples/Documentation**
- `src/sentry/apidocs/examples/project_examples.py:149` — Example value for project option in API docs

### **Test Files**
- `tests/sentry/relay/test_datascrubbing.py:40` — Org option write in datascrubbing test
- `tests/snuba/api/endpoints/test_project_event_details.py:482` — Project option write
- `tests/snuba/api/endpoints/test_project_event_details.py:492` — Org option write
- `tests/snuba/api/endpoints/test_project_event_details.py:502` — Org option write
- `tests/sentry/api/endpoints/test_relay_projectconfigs.py:68` — Project option write for Relay config test
- `tests/sentry/api/endpoints/test_relay_projectconfigs_v2.py:25` — Project option write for Relay config v2 test
- `tests/sentry/core/endpoints/test_organization_details.py:796` — Org option read assertion
- `tests/sentry/core/endpoints/test_project_details.py:662` — Example option value
- `tests/sentry/core/endpoints/test_project_details.py:761-762` — Project option read assertion
- `tests/sentry/core/endpoints/test_project_details.py:922-929` — Project option write and read in dedicated test
- `tests/sentry/models/test_organization.py:117-122` — Org option creation and change tracking