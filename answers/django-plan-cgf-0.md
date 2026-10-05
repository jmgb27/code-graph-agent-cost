I checked the connection code for all four backends and the matching tests. Nothing was edited.

# Plan: per-database `QUERY_TIMEOUT` setting

**How it would work.** `DATABASES[alias]["QUERY_TIMEOUT"]` is a positive number of seconds (int or float), or `None`, which is the default and means no limit. Seconds match `CONN_MAX_AGE`. Each backend turns the value into its own native mechanism when a connection opens:

| Backend | Mechanism | Hook |
|---|---|---|
| PostgreSQL | `SET statement_timeout = <ms>` | `_configure_connection` (also used by the psycopg pool) |
| MySQL | `SET SESSION max_execution_time = <ms>` (only affects read-only `SELECT`s) | `init_connection_state` |
| MariaDB | `SET SESSION max_statement_time = <seconds>` | `init_connection_state` |
| SQLite | `set_progress_handler` plus a deadline set for each statement | `get_new_connection` and `SQLiteCursorWrapper` |
| Oracle | `connection.call_timeout = <ms>` (python-oracledb) | `init_connection_state` |

## 1. Core: defaults, validation, feature flag

- **`django/db/utils.py:150` `ConnectionHandler.configure_settings`**: add `conn.setdefault("QUERY_TIMEOUT", None)` next to `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS` (`:168-171`).
- **`django/db/backends/base/base.py:263` `BaseDatabaseWrapper.check_settings`**: this already runs on every `connect()` (`:240`). Add checks that raise `ImproperlyConfigured`:
  - The value must be `None` or an `int`/`float` greater than 0. Reject `bool` explicitly, since `True` is an `int`.
  - If a value is set but `self.features.supports_query_timeout` is false, raise too. Third-party and dummy backends then fail loudly instead of silently ignoring the setting.
- **`django/db/backends/base/base.py`, near `timezone_name` (`:157`)**: add a small helper, e.g. a `query_timeout_ms` property returning `None` or `int(QUERY_TIMEOUT * 1000)`. PostgreSQL, MySQL and Oracle share it.
- **`django/db/backends/base/features.py:5` `BaseDatabaseFeatures`**: add `supports_query_timeout = False`. Set it to `True` in:
  - `django/db/backends/postgresql/features.py:9`
  - `django/db/backends/mysql/features.py:7`
  - `django/db/backends/sqlite3/features.py:13`
  - `django/db/backends/oracle/features.py:6`

## 2. PostgreSQL: `django/db/backends/postgresql/base.py`

- **New `_configure_query_timeout(self, connection)`**, next to `_configure_role` (`:373`). If `query_timeout_ms` is set, run `SET statement_timeout = %s` through `self.ops.compose_sql` and return `True`, otherwise return `False`.
- **`_configure_connection` (`:381-392`)**: call it and include its result in the returned commit flag.
  - This one hook covers both kinds of connection: plain ones via `init_connection_state` (`:410-417`) and pooled ones via `configure=self._configure_connection` (`:227`).
- A timeout raises psycopg `QueryCanceled`, which Django surfaces as `OperationalError`.
- The GIS subclasses (`django/contrib/gis/db/backends/postgis/base.py` and the MySQL, SpatiaLite and Oracle GIS backends) inherit all of these hooks, so they need no changes.

## 3. MySQL / MariaDB: `django/db/backends/mysql/base.py`

- **`init_connection_state` (`:258-276`)**: when a timeout is set, add one more statement to `assignments`:
  - MariaDB: `SET SESSION max_statement_time = <seconds>`
  - MySQL: `SET SESSION max_execution_time = <ms>`
  - Branch on `self.mysql_is_mariadb` (`:435`).
- The existing test `test_auto_is_null_auto_config` (`tests/backends/mysql/tests.py:48`) still passes, because it uses `assertIn` on the joined statement.
- Nothing is needed in `get_connection_params` (`:214`).
- Timeouts show up as `OperationalError` (errno 3024 on MySQL, 1969 on MariaDB). They are not in `CursorWrapper.codes_for_integrityerror` (`:72-94`), so they won't be misclassified as `IntegrityError`.
- This caveat needs documenting: MySQL's `max_execution_time` only applies to read-only `SELECT` statements.

## 4. SQLite: `django/db/backends/sqlite3/base.py`

SQLite has no server-side statement timeout, so the timeout has to be enforced on the client side:

- **`get_new_connection` (`:204-215`)**: if a timeout is set, call `conn.set_progress_handler(self._query_timeout_handler, N)` with N around 1000 VM instructions. The handler returns non-zero once `time.monotonic()` passes `self._query_deadline`, and SQLite then raises `OperationalError: interrupted`.
- **`create_cursor` (`:217-218`)**: attach the wrapper to the cursor (`cursor.db = self`). This works because `SQLiteCursorWrapper` is a Python subclass and can hold attributes.
- **`SQLiteCursorWrapper.execute` / `executemany` (`:340-370`)**: set `db._query_deadline = monotonic() + QUERY_TIMEOUT` before calling `super()`, and reset it in a `finally` block.
- **`get_connection_params` (`:154-198`)**: leave it alone. The existing `OPTIONS["timeout"]` is sqlite3's lock-wait (busy) timeout, which is a different thing. The docs must spell out the difference.
- The SpatiaLite subclass (`django/contrib/gis/db/backends/spatialite/base.py:40`) calls `super().get_new_connection`, so it inherits this.

## 5. Oracle: `django/db/backends/oracle/base.py`

- **`init_connection_state` (`:311-352`)**: set `self.connection.call_timeout = self.query_timeout_ms or 0`.
  - Always assign it, including 0, because pooled connections from `pool.acquire()` (`:302-303`) are reused and would otherwise keep an old value.
  - Unlike PostgreSQL, this method runs for pooled connections too.
- A timeout raises DPI-1067/ORA-03156, which Django surfaces as `DatabaseError`.
- `get_connection_params` (`:294`) is unchanged.

## 6. Tests

- **`tests/db_utils/tests.py:12` `ConnectionHandlerTests`**: after `configure_settings`, `QUERY_TIMEOUT` defaults to `None`.
- **`tests/backends/base/test_base.py:18` `DatabaseWrapperTests`**: validation through `check_settings()`:
  - `0`, `-1`, `"5"` and `True` raise `ImproperlyConfigured`.
  - `None`, `5` and `0.5` pass.
  - A backend with `supports_query_timeout=False` raises (mock the features).
- **`tests/backends/tests.py:310` `BackendTestCase`** (or a new `QueryTimeoutTests(TransactionTestCase)`): a check that runs on every backend.
  - Use `connection.copy()` (`base.py:780`), then set `settings_dict["QUERY_TIMEOUT"] = 0.5`.
  - Run a slow query and assert `DatabaseError`.
  - Then run a fast query to show the connection still works.
- **`tests/backends/postgresql/tests.py:34` `Tests`**:
  - `SHOW statement_timeout` returns `'500ms'`.
  - `SELECT pg_sleep(2)` raises `OperationalError`.
  - A pooled variant sits alongside `test_connect_pool` (`:237`) and `test_connect_pool_with_timezone` (`:287`).
- **`tests/backends/mysql/tests.py:105` `Tests`**:
  - `SELECT @@SESSION.max_execution_time` (or `max_statement_time` on MariaDB) returns the expected value.
  - `SELECT SLEEP(2)` is interrupted.
- **`tests/backends/sqlite/tests.py:28` `Tests`**:
  - A long recursive CTE raises `OperationalError`.
  - The deadline resets between statements.
  - `executemany` is covered.
  - `OPTIONS["timeout"]` is unaffected.
- **`tests/backends/oracle/tests.py:23` `Tests`**:
  - `connection.connection.call_timeout == 500`.
  - `DBMS_SESSION.SLEEP(2)` raises `DatabaseError`.
  - Pooled connections are reset to 0 when no timeout is set.

## 7. Docs

- **`docs/ref/settings.txt`**: add a `.. setting:: DATABASE-QUERY_TIMEOUT` section before `DATABASE-TIME_ZONE` (`:654`). Cover units, the default, validation, and a cross-reference from `CONN_HEALTH_CHECKS` (`:606`).
- **`docs/ref/databases.txt`**: add a short note to each backend section:
  - PostgreSQL (`:119`): `statement_timeout`, including with the connection pool (`:254`).
  - MySQL (`:444`): the `SELECT`-only limitation, and MariaDB's behaviour.
  - SQLite (`:827`): the progress-handler approach, and how it differs from `OPTIONS["timeout"]`.
  - Oracle (`:1005`): `call_timeout` and pooling (`:1118`).
- **`docs/releases/6.2.txt:137`**: add an entry under "Database backends", replacing the `* ...` placeholder.

## Decision needed before building it

The timeout applies to every statement on that alias, including `migrate` and test-database creation (`django/db/backends/base/creation.py`). Long migrations would hit it. I'd recommend documenting this and suggesting a separate alias, or `TEST`-level overrides, for migrations. The alternative is to skip the timeout during schema-editor operations, which would be a larger change.