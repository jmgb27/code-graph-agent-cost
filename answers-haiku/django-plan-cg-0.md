Now I have enough information to provide a comprehensive plan. Let me compile the files and functions that would need to be changed.

## Plan: Per-Database QUERY_TIMEOUT Option

Based on the Django codebase structure, here's every file and function that needs to be modified to implement a per-database `QUERY_TIMEOUT` option:

### **Settings & Configuration**

1. **django/db/backends/base/base.py:53** — `BaseDatabaseWrapper.__init__`
   - Add `QUERY_TIMEOUT` to settings_dict parsing

2. **django/db/backends/base/base.py:208-220** — `get_connection_params()` method
   - Extract timeout from settings and pass to backend-specific connection

3. **django/db/backends/postgresql/base.py:250-315** — `get_connection_params()` 
   - Add timeout to psycopg connection params

4. **django/db/backends/postgresql/base.py:318-355** — `get_new_connection()`
   - Apply timeout to psycopg connection (via `options` or `timeout` parameter)

5. **django/db/backends/mysql/base.py:214-251** — `get_connection_params()`
   - Add timeout to MySQLdb/PyMySQL connection params

6. **django/db/backends/mysql/base.py:254-256** — `get_new_connection()`
   - Apply timeout to MySQL connection

7. **django/db/backends/sqlite3/base.py:204-215** — `get_new_connection()`
   - Add timeout via `timeout` parameter to sqlite3.connect()

8. **django/db/backends/oracle/base.py:294-309** — `get_connection_params()` and `get_new_connection()`
   - Add timeout to oracledb connection params

### **Validation & Checks**

9. **django/db/backends/base/validation.py:10** — `BaseDatabaseValidation.check()`
   - Add method to validate QUERY_TIMEOUT setting type/value

10. **django/db/backends/base/validation.py** — Add new validation method (new)
    - `_check_query_timeout()` to ensure timeout is numeric and positive

11. **django/db/backends/mysql/validation.py:6-10** — `DatabaseValidation.check()`
    - Call parent check, may add MySQL-specific timeout validation

12. **django/db/backends/oracle/validation.py:5-22** — `DatabaseValidation.check()`
    - Add Oracle-specific timeout validation if needed

### **Query Execution (Optional - for query-level timeout enforcement)**

13. **django/db/backends/base/base.py:294-298** — `_cursor()` method
    - Could optionally wrap cursor to track/enforce query timeout

14. **django/db/backends/utils.py:78-105** — `CursorWrapper.execute()` and `_execute()`
    - Could optionally wrap execution with timeout handling

### **Test Files**

15. **tests/check_framework/test_database.py** (new tests)
    - Add `test_query_timeout_valid_values()`
    - Add `test_query_timeout_invalid_values()`
    - Add `test_query_timeout_none_allowed()`

16. **tests/backends/base/test_base.py** (new tests)
    - Add `test_query_timeout_passed_to_connection()`
    - Add `test_query_timeout_applies_to_all_backends()`

17. **tests/backends/postgresql/tests.py** (new tests)
    - Add `test_postgresql_query_timeout_in_connection_params()`

18. **tests/backends/mysql/tests.py** (new tests - create if needed)
    - Add `test_mysql_query_timeout_in_connection_params()`

19. **tests/backends/sqlite/tests.py** (new tests - create if needed)
    - Add `test_sqlite_query_timeout_in_connection_params()`

20. **tests/backends/oracle/tests.py** (new tests)
    - Add `test_oracle_query_timeout_in_connection_params()`

### **Documentation Files (not code, but reference)**

21. **docs/ref/settings.txt** — DATABASES section
    - Document QUERY_TIMEOUT option for each backend

22. **docs/ref/databases.txt** — Database-specific docs
    - PostgreSQL, MySQL, SQLite, Oracle specific timeout behavior

### **Summary of Changes by Backend**

| File | Lines | Function | Change Type |
|------|-------|----------|-------------|
| django/db/backends/base/base.py | 53 | `__init__` | Parse QUERY_TIMEOUT from settings |
| django/db/backends/base/validation.py | 10-32 | `check()` / new method | Validate timeout values |
| django/db/backends/postgresql/base.py | 250-315, 318-355 | `get_connection_params()`, `get_new_connection()` | Pass timeout to psycopg |
| django/db/backends/mysql/base.py | 214-251, 254-256 | `get_connection_params()`, `get_new_connection()` | Pass timeout to MySQLdb |
| django/db/backends/sqlite3/base.py | 204-215 | `get_new_connection()` | Pass timeout to sqlite3 |
| django/db/backends/oracle/base.py | 294-309 | `get_connection_params()`, `get_new_connection()` | Pass timeout to oracledb |
| tests/check_framework/test_database.py | — | Multiple new tests | Validation tests |
| tests/backends/base/test_base.py | — | Multiple new tests | Integration tests |
| tests/backends/postgresql/tests.py | — | New test | PostgreSQL-specific |
| tests/backends/mysql/tests.py | — | New test | MySQL-specific |
| tests/backends/sqlite/tests.py | — | New test | SQLite-specific |
| tests/backends/oracle/tests.py | — | New test | Oracle-specific |

**Total estimate: ~12-15 files to modify, ~40-50 test cases to add.**