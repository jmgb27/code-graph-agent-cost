Based on my exploration of the Django codebase, here's a comprehensive plan for adding per-database QUERY_TIMEOUT support:

## Files to Modify

### 1. **Base Framework** (Core validation and initialization)

**django/db/backends/base/base.py:263** — `check_settings()` method
- Add validation for QUERY_TIMEOUT value (must be positive number or None)
- Raise `ImproperlyConfigured` if invalid

### 2. **Backend Implementations** (Handle timeout in connection params and initialization)

#### MySQL Backend
**django/db/backends/mysql/base.py:214** — `get_connection_params()` method (lines 214-251)
- Extract QUERY_TIMEOUT from OPTIONS, validate it
- Pass to MySQLdb via connection kwargs (if supported)

**django/db/backends/mysql/base.py:258** — `init_connection_state()` method (lines 258-276)
- Set session timeout via SQL command like `SET SESSION max_execution_time = <timeout>`

#### PostgreSQL Backend
**django/db/backends/postgresql/base.py:250** — `get_connection_params()` method (lines 250-315)
- Extract QUERY_TIMEOUT, pass as `statement_timeout` to psycopg/psycopg2

**django/db/backends/postgresql/base.py:410** — `init_connection_state()` method (lines 410-417)
- Set statement_timeout via `SET statement_timeout` if not already in connection params

#### Oracle Backend
**django/db/backends/oracle/base.py:294** — `get_connection_params()` method (lines 294-298)
- Extract QUERY_TIMEOUT from OPTIONS

**django/db/backends/oracle/base.py:311** — `init_connection_state()` method (lines 311-352)
- Set timeout using Oracle's `call.timeout` or session-level settings

#### SQLite Backend
**django/db/backends/sqlite3/base.py:154** — `get_connection_params()` method (lines 154-198)
- Extract QUERY_TIMEOUT, handle via sqlite3 timeout parameter
- SQLite uses `timeout` parameter for lock timeout, may need different handling

### 3. **Test Files** (Validation and integration tests)

**tests/backends/test_utils.py**
- Add test class for QUERY_TIMEOUT validation
- Test valid values (positive integers/floats, None)
- Test invalid values (negative, non-numeric, wrong types)

**tests/backends/tests.py** (BackendTestCase around line 310)
- Add integration test for each backend to verify timeout is applied
- Test that ImproperlyConfigured is raised for invalid configs

**tests/backends/base/test_base.py** (if exists)
- Add test for base validation logic

**tests/backends/mysql/tests.py**
- MySQL-specific timeout test

**tests/backends/postgresql/tests.py**
- PostgreSQL-specific timeout test  

**tests/backends/oracle/tests.py**
- Oracle-specific timeout test

**tests/backends/sqlite/tests.py**
- SQLite-specific timeout test

### 4. **GIS Backend Wrappers** (Usually inherit parent behavior, might not need changes)

- `django/contrib/gis/db/backends/mysql/base.py` (inherits from MySQLDatabaseWrapper)
- `django/contrib/gis/db/backends/oracle/base.py` (inherits from OracleDatabaseWrapper)
- `django/contrib/gis/db/backends/postgis/base.py` (inherits from PostgreSQLDatabaseWrapper)
- `django/contrib/gis/db/backends/spatialite/base.py` (inherits from SQLiteDatabaseWrapper)

These shouldn't need explicit changes if parent classes handle it properly.

---

## Implementation Points by Backend

### **Django/db/backends/mysql/base.py**

| Line Range | Method | Change |
|-----------|--------|--------|
| 214-251 | `get_connection_params()` | Extract `QUERY_TIMEOUT` from `OPTIONS`, pop it, pass appropriate kwarg to MySQLdb |
| 258-276 | `init_connection_state()` | Execute SQL to set `max_execution_time` session variable |
| 103 | Class definition | May add `query_timeout` instance variable |

### **Django/db/backends/postgresql/base.py**

| Line Range | Method | Change |
|-----------|--------|--------|
| 250-315 | `get_connection_params()` | Extract `QUERY_TIMEOUT`, convert to milliseconds if needed, set as `statement_timeout` in conn_params |
| 410-417 | `init_connection_state()` | If QUERY_TIMEOUT not in conn_params, execute `SET statement_timeout` |

### **Django/db/backends/oracle/base.py**

| Line Range | Method | Change |
|-----------|--------|--------|
| 294-298 | `get_connection_params()` | Extract `QUERY_TIMEOUT` from OPTIONS dict |
| 311-352 | `init_connection_state()` | Use Oracle's timeout mechanism (likely via `dbms_session.set_context` or similar) |

### **Django/db/backends/sqlite3/base.py**

| Line Range | Method | Change |
|-----------|--------|--------|
| 154-198 | `get_connection_params()` | Handle QUERY_TIMEOUT - note: SQLite has different timeout semantics (lock timeout, not query execution timeout) |

### **Django/db/backends/base/base.py**

| Line Range | Method | Change |
|-----------|--------|--------|
| 263-268 | `check_settings()` | Add validation for QUERY_TIMEOUT if present in settings_dict |

---

## Key Implementation Details

1. **Validation Logic**: In `BaseDatabaseWrapper.check_settings()`, validate that if `QUERY_TIMEOUT` is set in `settings_dict`, it's either:
   - A positive number (int/float)
   - None
   - Otherwise raise `ImproperlyConfigured`

2. **Backend-specific handling**:
   - **MySQL**: Uses session variable `max_execution_time` (in milliseconds)
   - **PostgreSQL**: Uses `statement_timeout` parameter (in milliseconds)  
   - **Oracle**: Uses DBMS_SESSION calls or connection-level timeout
   - **SQLite**: Limited support (timeout is for locks, not query execution)

3. **Test Coverage**: Each backend needs tests validating:
   - Valid timeout values are accepted
   - Invalid values raise `ImproperlyConfigured`
   - Timeout is actually applied to connections

This is a read-only task, so I'm providing the file locations and functions/line numbers to modify as reference.