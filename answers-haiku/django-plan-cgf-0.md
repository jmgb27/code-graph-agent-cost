Based on my code analysis, here's a comprehensive plan for adding a per-database `QUERY_TIMEOUT` option that all built-in backends will honour:

## Plan: Adding Per-Database QUERY_TIMEOUT Option

### 1. **Configuration Validation & Storage**

#### Backend `get_connection_params()` methods
Each backend needs to validate and extract the QUERY_TIMEOUT from OPTIONS:

- **PostgreSQL**: `django/db/backends/postgresql/base.py:250` — Add validation similar to how `isolation_level` is handled (line 282-283)
- **MySQL**: `django/db/backends/mysql/base.py:214` — Add validation similar to `isolation_level` (lines 236-248)
- **SQLite**: `django/db/backends/sqlite3/base.py:154` — Add validation similar to `transaction_mode` (lines 181-194)
- **Oracle**: `django/db/backends/oracle/base.py:294` — Add validation for QUERY_TIMEOUT extraction

#### Backend `__init__()` methods (store timeout at instance level)
- **PostgreSQL**: `django/db/backends/postgresql/base.py` — In `__init__` (likely around L230-240 area)
- **MySQL**: `django/db/backends/mysql/base.py:103` — After parent `__init__` call
- **SQLite**: `django/db/backends/sqlite3/base.py` — In `get_connection_params()` result processing
- **Oracle**: `django/db/backends/oracle/base.py:246` — In existing `__init__`

### 2. **Cursor Wrapper Enhancement**

#### Base cursor timeout application
- **Base CursorWrapper**: `django/db/backends/utils.py:17` — Modify `__init__` to accept/store timeout, then apply in `execute()` and `executemany()` methods (lines 78-86 and 83-86)
- **MySQL CursorWrapper**: `django/db/backends/mysql/base.py:55` — Override `execute()` and `executemany()` to apply timeout before calling parent

#### How timeout is applied (backend-specific):
- **PostgreSQL**: Set via `set_statement_timeout()` before query execution or connection parameter
- **MySQL**: Set via `SET max_statement_time=...` or connection parameter
- **SQLite**: Set via `sqlite3` timeout mechanism or `SET` pragma
- **Oracle**: Set via session parameter or execute timeout on cursor

### 3. **Connection Initialization**

#### `init_connection_state()` methods
After connection is established, apply the timeout setting:
- **PostgreSQL**: `django/db/backends/postgresql/base.py` — around L315+ area
- **MySQL**: `django/db/backends/mysql/base.py:258` — in existing `init_connection_state()`
- **SQLite**: `django/db/backends/sqlite3/base.py` — may need new method
- **Oracle**: `django/db/backends/oracle/base.py:311` — in existing `init_connection_state()`

### 4. **Features Declaration**

Declare `supports_query_timeout` in each backend's features:
- `django/db/backends/postgresql/features.py` — Add boolean flag
- `django/db/backends/mysql/features.py` — Add boolean flag  
- `django/db/backends/sqlite3/features.py` — Add boolean flag
- `django/db/backends/oracle/features.py` — Add boolean flag

### 5. **Test Files to Create/Modify**

#### Core test module
- **`tests/backends/test_query_timeout.py`** — New file containing:
  - `QueryTimeoutTestCase` testing valid configuration
  - `test_query_timeout_valid_values` — test integer timeout values
  - `test_query_timeout_invalid_type` — test non-integer values
  - `test_query_timeout_applies_to_queries` — test timeout actually works
  - `test_query_timeout_none_disables` — test None value
  - `test_query_timeout_zero_invalid` — test zero (if backend doesn't allow it)

#### Backend-specific tests
- `tests/backends/postgresql/test_query_timeout.py` — PostgreSQL-specific timeout tests
- `tests/backends/mysql/test_query_timeout.py` — MySQL-specific timeout tests
- `tests/backends/sqlite/test_query_timeout.py` — SQLite-specific timeout tests
- `tests/backends/oracle/test_query_timeout.py` — Oracle-specific timeout tests

#### Validation tests
- `tests/backends/test_query_timeout_validation.py` — Configuration validation tests in each backend's `get_connection_params()`

### 6. **Documentation Updates**

- `docs/ref/databases/` — Add QUERY_TIMEOUT option to each backend's documentation
- Update `DATABASES` configuration examples

### 7. **Summary of Files to Change**

**Configuration validation:**
- `django/db/backends/postgresql/base.py:250`
- `django/db/backends/mysql/base.py:214`
- `django/db/backends/sqlite3/base.py:154`
- `django/db/backends/oracle/base.py:294`

**Connection initialization:**
- `django/db/backends/postgresql/base.py` (init_connection_state or __init__)
- `django/db/backends/mysql/base.py:258`
- `django/db/backends/sqlite3/base.py`
- `django/db/backends/oracle/base.py:311`

**Cursor timeout enforcement:**
- `django/db/backends/utils.py:17-86` (CursorWrapper.execute/executemany)
- `django/db/backends/mysql/base.py:55-98` (CursorWrapper)

**Features:**
- `django/db/backends/postgresql/features.py`
- `django/db/backends/mysql/features.py`
- `django/db/backends/sqlite3/features.py`
- `django/db/backends/oracle/features.py`

**Tests (new files):**
- `tests/backends/test_query_timeout.py` (core tests)
- `tests/backends/postgresql/test_query_timeout.py`
- `tests/backends/mysql/test_query_timeout.py`
- `tests/backends/sqlite/test_query_timeout.py`
- `tests/backends/oracle/test_query_timeout.py`

This modular approach ensures each backend honours the timeout setting consistently while allowing for backend-specific implementation details.