Based on my CodeGraph exploration, here's the comprehensive plan for adding a per-database QUERY_TIMEOUT option:

## Files and Functions to Change

### 1. **Core Infrastructure**

**`django/db/backends/base/base.py`**
- `BaseDatabaseWrapper.__init__:53` — Extract and store QUERY_TIMEOUT from settings_dict
- `BaseDatabaseWrapper.connect:237` — Potentially apply timeout to connection if backend supports it (or leave to backend-specific code)
- `BaseDatabaseWrapper.check_settings:263` — Add validation check for QUERY_TIMEOUT

### 2. **Backend Validation Classes**

**`django/db/backends/base/validation.py`**
- `BaseDatabaseValidation.check:10` — Add QUERY_TIMEOUT validation call (or leave to subclasses)

**`django/db/backends/postgresql/validation.py`** — NEW FILE
- Create `DatabaseValidation` class extending `BaseDatabaseValidation`
- Implement `check()` method with QUERY_TIMEOUT validation

**`django/db/backends/mysql/validation.py`**
- `DatabaseValidation.check:7` — Add QUERY_TIMEOUT validation to existing check

**`django/db/backends/sqlite3/validation.py`** — NEW FILE
- Create `DatabaseValidation` class extending `BaseDatabaseValidation`
- Implement `check()` method with QUERY_TIMEOUT validation

**`django/db/backends/oracle/validation.py`**
- `DatabaseValidation.check:5` (if it exists as a method; create if only has `check_field_type`) — Add QUERY_TIMEOUT validation

### 3. **Backend Connection Parameter Extraction**

**`django/db/backends/postgresql/base.py`**
- `DatabaseWrapper.get_connection_params:??` — Extract QUERY_TIMEOUT from OPTIONS and set connect_timeout
- `DatabaseWrapper.get_new_connection:318` — Apply timeout (psycopg3 supports `connect_timeout` in connection string)

**`django/db/backends/mysql/base.py`**
- `DatabaseWrapper.get_connection_params:214` — Extract QUERY_TIMEOUT from OPTIONS and set connection_timeout
- `DatabaseWrapper.get_new_connection:254` — Apply timeout (MySQLdb/pymysql support `connection_timeout` parameter)

**`django/db/backends/sqlite3/base.py`**
- `DatabaseWrapper.get_connection_params:154` — Extract QUERY_TIMEOUT from OPTIONS and set timeout
- `DatabaseWrapper.get_new_connection:204` — Apply timeout (sqlite3.connect supports `timeout` parameter)

**`django/db/backends/oracle/base.py`**
- `DatabaseWrapper.get_connection_params:294` — Extract QUERY_TIMEOUT from OPTIONS
- `DatabaseWrapper.get_new_connection:301` — Apply timeout (cx_Oracle supports connection timeout via connection string)

### 4. **PostgreSQL Wrapper Classes**

**`django/contrib/gis/db/backends/postgis/base.py`**
- `DatabaseWrapper.__init__:103` — Ensure validation_class is inherited properly (if custom validation needed)

### 5. **Validation Test Files**

**`tests/backends/postgresql/tests.py`**
- Add `test_query_timeout_valid_int()` 
- Add `test_query_timeout_valid_float()`
- Add `test_query_timeout_invalid_string()`
- Add `test_query_timeout_negative_value()`
- Add `test_query_timeout_zero_valid()`

**`tests/backends/mysql/tests.py`**
- Add same test cases as PostgreSQL

**`tests/backends/sqlite/tests.py`**
- Add same test cases as PostgreSQL

**`tests/backends/oracle/tests.py`**
- Add same test cases as PostgreSQL

**`tests/backends/base/test_base.py`** — NEW FILE or extend existing
- Add `test_query_timeout_setting_validation()`
- Add integration tests for each backend

### 6. **Documentation & Reference**

**`django/core/checks/__init__.py`** or **`django/core/checks/databases.py`** — NEW FILE
- Create or extend check functions for database QUERY_TIMEOUT validation (errors like `databases.E001`, `databases.W001`)

---

## Implementation Pattern Summary

**Core changes needed:**
1. Define error/warning message templates for invalid QUERY_TIMEOUT values
2. Add validation logic in `BaseDatabaseValidation.check()` or backend-specific subclasses
3. Extend each backend's `get_connection_params()` to extract QUERY_TIMEOUT from OPTIONS and translate to backend-specific parameter name
4. Map QUERY_TIMEOUT to backend-native timeout parameters:
   - PostgreSQL: `connect_timeout` (in connection string or via psycopg parameter)
   - MySQL: `connection_timeout` (in MySQLdb/pymysql kwargs)
   - SQLite: `timeout` (in sqlite3.connect kwargs)
   - Oracle: Connection timeout in connection string via `dsn()` or via connection parameters
5. Add comprehensive test coverage for valid/invalid values, type checking, and edge cases

**Validation should check:**
- Type (must be int, float, or None)
- Sign (must be >= 0)
- Reasonableness (warning if > reasonable max, e.g., 300000ms)