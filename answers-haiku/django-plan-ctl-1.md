## Plan for Adding Per-Database QUERY_TIMEOUT Option

Here's every file and function that needs to change to implement per-database QUERY_TIMEOUT:

### 1. **Core Configuration & Defaults**
- **django/db/utils.py:150** — `ConnectionHandler.configure_settings()` 
  - Add: `conn.setdefault("QUERY_TIMEOUT", None)` after line 171
  - This sets the default value for QUERY_TIMEOUT to None (no timeout)

### 2. **Base Backend Validation**
- **django/db/backends/base/base.py:263** — `BaseDatabaseWrapper.check_settings()`
  - Add validation to ensure QUERY_TIMEOUT is None or a positive number
  - Raise `ImproperlyConfigured` for invalid values (negative, non-numeric)

### 3. **PostgreSQL Backend**
- **django/db/backends/postgresql/base.py:250** — `PostgreSQL.get_connection_params()`
  - Extract `QUERY_TIMEOUT` from `settings_dict`
  - Apply to connection params as `statement_timeout` (PostgreSQL native parameter)
  - Convert seconds to milliseconds for PostgreSQL (multiply by 1000)

### 4. **MySQL Backend**
- **django/db/backends/mysql/base.py:214** — `MySQL.get_connection_params()`
  - Extract `QUERY_TIMEOUT` from `settings_dict`
  - Apply to connection params as `max_allowed_packet`/connection timeout option
  - MySQL uses seconds directly for timeouts

### 5. **SQLite Backend**
- **django/db/backends/sqlite3/base.py:154** — `SQLite.get_connection_params()`
  - Extract `QUERY_TIMEOUT` from `settings_dict`
  - Apply via `timeout` parameter to `sqlite3.connect()`
  - SQLite uses seconds directly

### 6. **Oracle Backend**
- **django/db/backends/oracle/base.py:294** — `Oracle.get_connection_params()`
  - Extract `QUERY_TIMEOUT` from `settings_dict`
  - Apply via oracledb session timeout parameters
  - Requires per-cursor or session setup in `init_connection_state()`

### 7. **Documentation**
- **docs/ref/settings.txt** — Add documentation section after line 619 (after CONN_HEALTH_CHECKS)
  - Add: `.. setting:: QUERY_TIMEOUT` directive
  - Document default value (None)
  - Explain behavior per backend (PostgreSQL in ms, MySQL/SQLite in seconds, Oracle session-level)
  - Add warning about backend-specific handling

### 8. **Tests** (create new or extend existing)
- **tests/backends/base/test_base.py** — Add validation tests
  - Test default value is None
  - Test valid numeric values are accepted
  - Test invalid values raise ImproperlyConfigured

- **tests/backends/postgresql/test_creation.py** or new **tests/backends/test_query_timeout.py**
  - Test QUERY_TIMEOUT applied correctly per backend
  - Test timeout values in correct units for each DB
  - Test None (no timeout) behavior
  - Test connection params include timeout settings

- **tests/check_framework/test_database.py** — Add settings validation check
  - Test database configuration check validates QUERY_TIMEOUT format

### 9. **Release Notes** (optional but recommended)
- **docs/releases/X.Y.txt** — Document new feature with example usage

### Key Implementation Details by Backend:

| Backend | Parameter Name | Unit | Location |
|---------|---|---|---|
| PostgreSQL | `statement_timeout` | Milliseconds (multiply by 1000) | `get_connection_params()` |
| MySQL | Connection timeout option | Seconds | `get_connection_params()` |
| SQLite | `timeout` | Seconds | `get_connection_params()` |
| Oracle | Session timeout | Seconds | `init_connection_state()` |