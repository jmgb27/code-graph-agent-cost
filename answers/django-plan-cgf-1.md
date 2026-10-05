Here's a plan for adding `QUERY_TIMEOUT`. No files were edited. Line numbers are from the current tree.

## Design

- **The setting:** `DATABASES[alias]["QUERY_TIMEOUT"]`. It's a positive number of seconds (int or float, same unit as `CONN_MAX_AGE`), or `None` for no timeout. The default is `None`, so nothing changes for existing projects.
- **Validation:** when a connection is opened, in the same place Django already checks `TIME_ZONE` (`BaseDatabaseWrapper.check_settings`). A bad value raises `ImproperlyConfigured`.
- **Enforcement:** each backend applies the timeout when it sets up a new connection, using that database's own mechanism:

| Backend | Mechanism | Where it's applied |
|---|---|---|
| PostgreSQL | `SET statement_timeout = <ms>` | `_configure_connection`, which runs both for normal connections and for psycopg pool connections |
| MySQL | `SET SESSION max_execution_time = <ms>` | `init_connection_state` |
| MariaDB | `SET SESSION max_statement_time = <seconds>` | `init_connection_state` |
| Oracle | `connection.call_timeout = <ms>` (python-oracledb) | `init_connection_state` |
| SQLite | Python-side deadline checked by `set_progress_handler`; SQLite has no server-side timeout | `get_new_connection` plus the cursor's `execute`/`executemany` |

- **Errors:** a timed-out query surfaces as `django.db.OperationalError` on every backend. The existing error wrapper (`django/db/utils.py:73-94`, `DatabaseErrorWrapper.__exit__`) already does that translation and sets `errors_occurred`, so health checks will drop a broken connection.

## Files and functions to change

### 1. Default value
- `django/db/utils.py:162-171`, `ConnectionHandler.configure_settings`: add `conn.setdefault("QUERY_TIMEOUT", None)` next to the `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS` defaults.

### 2. Validation and shared helper (`django/db/backends/base/base.py`)
- `BaseDatabaseWrapper.check_settings` (`:263-268`), which `connect()` already calls at `:240`:
  - Reject anything that isn't `None` or a positive, finite int/float.
  - Explicitly reject `bool`, `0`, negative numbers, strings and `inf`.
  - Error message in the existing style: `"Connection '%s' has an invalid QUERY_TIMEOUT ..."`.
  - This runs before `get_connection_params()` (`:255`) and before any pool is built, so no backend can ever see an invalid value.
- Add a small helper near `timezone_name` (`:157-167`), e.g. a `query_timeout_ms` property. It returns `None` or `max(1, round(seconds * 1000))`. All four backends use it.
- `connect()` (`:236-261`) needs no change. It already calls `check_settings()`, then `get_new_connection()`, then `init_connection_state()`.

### 3. PostgreSQL (`django/db/backends/postgresql/base.py`)
- New method `_configure_query_timeout(self, connection)`, placed next to `_configure_role` (`:373-379`) and written the same way:
  - Run `cursor.execute(self.ops.compose_sql("SET statement_timeout = %s", [ms]))`.
  - Return `True` so the caller commits.
- `_configure_connection` (`:381-392`): call the new method and OR its result into the returned commit flag.
  - This single hook covers normal connections (via `init_connection_state`, `:410-417`, which commits when autocommit is off).
  - It also covers pooled connections, because the pool passes `configure=self._configure_connection` (`:227`).
- Why a `SET` rather than adding `options="-c statement_timeout=…"` in `get_connection_params` (`:250-315`): it doesn't conflict with a user's own `OPTIONS["options"]`, and it works behind pgbouncer, which rejects startup parameters.
- PostGIS (`django/contrib/gis/db/backends/postgis/base.py:91`) inherits this with no change.

### 4. MySQL / MariaDB (`django/db/backends/mysql/base.py`)
- `init_connection_state` (`:258-276`): add one entry to `assignments`:
  - MariaDB: `"SET SESSION max_statement_time = %s" % (ms / 1000)`.
  - MySQL: `"SET SESSION max_execution_time = %d" % ms`.
  - Branch on `self.mysql_is_mariadb` (`:434-436`). This adds no extra query, because `mysql_server_data` is already fetched for `features.is_sql_auto_is_null_enabled`.
- Document a limitation: on MySQL (not MariaDB), `max_execution_time` only applies to read-only `SELECT` statements.
- GIS MySQL (`django/contrib/gis/db/backends/mysql/base.py:9`) inherits this.

### 5. Oracle (`django/db/backends/oracle/base.py`)
- `init_connection_state` (`:311-352`): next to `self.connection.stmtcachesize = 20` (`:349`), always set `self.connection.call_timeout = self.query_timeout_ms or 0`.
  - Setting it every time matters. Pooled connections from `pool.acquire()` (`:302-303`) are reused, so a stale value has to be reset. `init_connection_state` runs on every acquire.
- Leave `get_connection_params` (`:294-298`) alone. `call_timeout` is a connection attribute, not a `connect()` keyword argument.
- GIS Oracle (`django/contrib/gis/db/backends/oracle/base.py:9`) inherits this.

### 6. SQLite (`django/db/backends/sqlite3/base.py`)
- `get_new_connection` (`:203-215`): if a timeout is set, call `conn.set_progress_handler(handler, N)` (e.g. N=1000 VM instructions).
  - The handler returns a truthy value once `time.monotonic()` passes the current deadline.
  - SQLite then raises `sqlite3.OperationalError("interrupted")`, which the error wrapper maps to Django's `OperationalError`.
- `create_cursor` (`:217-218`) and `SQLiteCursorWrapper.execute` / `executemany` (`:353-368`):
  - Arm the deadline (`monotonic() + timeout`) before calling `super().execute…`, and clear it afterwards.
  - The cursor needs access to where the deadline is stored. Options: a small `sqlite3.Connection` subclass passed as `factory=` from `get_connection_params` (`:154-189`) using `setdefault`, or a mutable state object that `create_cursor` attaches to the cursor.
- **Docs note:** this is a different thing from `OPTIONS["timeout"]`, which is sqlite3's busy/lock wait. Spell that out in the docs.
- SpatiaLite (`django/contrib/gis/db/backends/spatialite/base.py:40`) calls `super().get_new_connection()`, so it inherits this.

### 7. Optional
- Add `supports_query_timeout = True` to `django/db/backends/base/features.py`, so third-party backends can advertise support and tests can use `skipUnlessDBFeature`.

## Tests

- **`tests/db_utils/tests.py`**, `ConnectionHandlerTests` (`:12`): add `test_query_timeout_default`, asserting `ConnectionHandler({...})["default"].settings_dict["QUERY_TIMEOUT"] is None`.
- **`tests/backends/base/test_base.py`**, `DatabaseWrapperTests` (`:18`), which is a `SimpleTestCase`:
  - Invalid values `0`, `-1`, `"5"`, `True`, `float("inf")`: build a wrapper with `connection.copy()` (`base.py:780`) and assert `check_settings()` raises `ImproperlyConfigured` with the exact message.
  - Valid values `None`, `1`, `0.25`: no error.
  - `query_timeout_ms` rounding cases.
- **`tests/backends/tests.py`**, `BackendTestCase` (`:310`), cross-backend behaviour:
  - Copy the connection with `QUERY_TIMEOUT=0.2` and run a vendor-specific slow statement. Assert `OperationalError` (or `DatabaseError` for Oracle, depending on how the driver classifies the timeout).
  - Slow statements: PostgreSQL `SELECT pg_sleep(2)`; Oracle a PL/SQL `DBMS_SESSION.SLEEP(2)` block; SQLite an unbounded recursive CTE; MariaDB `SELECT SLEEP(2)`.
  - MySQL `SLEEP()` returns 1 instead of raising when interrupted, so assert that result instead. Then check the connection is still usable (or gets closed by health checks).
- **`tests/backends/postgresql/tests.py`**, `Tests` (`:34`):
  - `SHOW statement_timeout` returns `'200ms'`.
  - A pool variant modelled on `test_connect_pool` (`:237`) / `test_connect_pool_with_timezone` (`:287`) checks that pooled connections get the timeout through the `configure` hook.
  - A variant with `AUTOCOMMIT=False` checks the `SET` is committed.
- **`tests/backends/mysql/tests.py`**, `Tests` (`:105`): `SELECT @@SESSION.max_execution_time` (MySQL) or `@@SESSION.max_statement_time` (MariaDB) matches the setting.
- **`tests/backends/oracle/tests.py`**, `Tests` (`:23`):
  - `connection.connection.call_timeout == 200`.
  - With `None`, it resets to `0`.
- **`tests/backends/sqlite/tests.py`**, `Tests` (`:28`), modelled on `test_init_command` (`:124`):
  - An in-memory `ConnectionHandler` with `QUERY_TIMEOUT` interrupts a runaway recursive CTE.
  - A fast query still succeeds afterwards, which proves the deadline was reset.
  - Without the setting, no progress handler is installed.

## Docs
- **`docs/ref/settings.txt`**: add a new `.. setting:: DATABASE-QUERY_TIMEOUT` section in alphabetical order before `DATABASE-TIME_ZONE` (`:654`). Link it from `CONN_HEALTH_CHECKS` (`:606`) if useful.
- **`docs/ref/databases.txt`**: per-backend notes covering:
  - PostgreSQL connection management and pooling (`:47`, `:254`).
  - The MySQL `SELECT`-only limitation (near `:647`).
  - SQLite timeout vs. `OPTIONS["timeout"]` (near `:914` / `:983`).
  - Oracle `call_timeout` (near `:1118`).
- **`docs/releases/6.2.txt`**: an entry under "Database backends" (`:137`).

## Risks to handle
1. **Test-database setup inherits the timeout.** Admin and maintenance connections (e.g. PostgreSQL's `_nodb_cursor` / `NO_DB_ALIAS`, `create_test_db`, and long migrations) would all be subject to it. I'd skip the timeout for `NO_DB_ALIAS` in `_configure_connection`, and document that `migrate` is also affected.
2. **The timeout is fixed when the connection opens.** Changing the setting only affects new connections, like `TIME_ZONE`. With the PostgreSQL pool, you'd need `close_pool()`, the same way `ensure_timezone` (`postgresql/base.py:357`) handles time-zone changes.