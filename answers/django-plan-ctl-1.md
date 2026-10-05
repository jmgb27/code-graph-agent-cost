This is a plan only; I haven't changed any files. It uses one new key, `DATABASES[alias]["QUERY_TIMEOUT"]`, measured in seconds (int or float). The default `None` means no timeout. The value is validated in the one place where settings are already checked, and each backend applies it in its own hook that sets up new connections.

## 1. Add the default setting and validate it

**`django/db/utils.py:150` `ConnectionHandler.configure_settings()`**
- Add `conn.setdefault("QUERY_TIMEOUT", None)` next to the `CONN_HEALTH_CHECKS` and `TIME_ZONE` defaults (`:169`–`:171`). Every backend can then read `settings_dict["QUERY_TIMEOUT"]` without a `.get()`.

**`django/db/backends/base/base.py:263` `BaseDatabaseWrapper.check_settings()`**
- `connect()` already calls this at `:240`, before any connection is opened. Add these checks next to the existing `TIME_ZONE` check:
  - The value must be `None`, or an `int`/`float` that is greater than 0. Reject `bool` explicitly, because `True` counts as an int.
    - Otherwise raise `ImproperlyConfigured(f"settings.DATABASES[{alias!r}]['QUERY_TIMEOUT'] must be None or a positive number of seconds.")`.
    - Rejecting 0 avoids a trap: 0 means "disabled" on PostgreSQL and MySQL but "fire at once" in a SQLite progress handler.
  - If the value is not `None` and `self.features.supports_query_timeout` is False, raise `NotSupportedError`. That way third-party backends that ignore the key fail loudly instead of running with no timeout.
- Add a small helper `query_timeout_ms()` that returns `None` or `round(QUERY_TIMEOUT * 1000)`. Three backends need milliseconds.

**`django/db/backends/base/features.py`** (in the `supports_*` block, around `:25`)
- Add `supports_query_timeout = False` with a comment.

**Each built-in backend's `features.py`**
- `postgresql/features.py`, `mysql/features.py`, `sqlite3/features.py`, `oracle/features.py`: set `supports_query_timeout = True`.

## 2. Apply the timeout in each backend

### PostgreSQL: `django/db/backends/postgresql/base.py`
- **`_configure_connection()` (`:381`)**: add `commit_timeout = self._configure_query_timeout(connection)` and include it in the returned `or`.
  - This covers both code paths. `init_connection_state()` (`:410`) calls it on plain connections. The psycopg pool calls it as the `configure=` callback (`:227`) for every new pooled connection.
  - Setting the timeout inside `get_connection_params()` (`:250`) with libpq `options='-c statement_timeout=…'` would be the wrong place. It would clash with a user's `OPTIONS["options"]`, and PgBouncer rejects startup parameters it doesn't know.
- **New `_configure_query_timeout(connection)`**: modelled on `_configure_role()` (`:373`). If a timeout is set, run `cursor.execute(self.ops.compose_sql("SET statement_timeout = %s", [ms]))` and return True.
  - Returning True triggers the commit that already exists at `:416` when autocommit is off.
- **`ensure_timezone()` (`:357`)**: no change. It already closes the pool, so a `QUERY_TIMEOUT` changed via `override_settings` is picked up the same way.

### MySQL / MariaDB: `django/db/backends/mysql/base.py`
- **`init_connection_state()` (`:258`)**: add one entry to `assignments`:
  - MariaDB (`self.mysql_is_mariadb`, `:435`): `SET SESSION max_statement_time = <seconds>`. MariaDB takes seconds as a float.
  - MySQL: `SET SESSION max_execution_time = <ms>`.
  - The existing `"; ".join(assignments)` then sends everything in one round trip.
- Caveat for the docs: MySQL's `max_execution_time` only applies to read-only `SELECT`s, while MariaDB's applies to all statements.
- **`CursorWrapper` (`:55`)**: no mapping change is needed. Timeout errors (MySQL 3024 `ER_QUERY_TIMEOUT`, MariaDB 1969 `ER_STATEMENT_TIMEOUT`) already surface as `OperationalError`. Don't add them to `codes_for_integrityerror`.

### SQLite: `django/db/backends/sqlite3/base.py`
SQLite has no server-side statement timeout, so the timeout is enforced on the client with `sqlite3.Connection.set_progress_handler()`.
- **`get_new_connection()` (`:204`)**: if `QUERY_TIMEOUT` is set, call `conn.set_progress_handler(self._check_query_deadline, 1000)` (1000 = number of VM instructions between checks).
  - Initialise `self._query_deadline = None`.
- **New `DatabaseWrapper._check_query_deadline()`**: return `1` when `self._query_deadline` is set and `time.monotonic()` has passed it; otherwise return `0`.
  - Returning non-zero makes sqlite3 raise `OperationalError("interrupted")`.
- **`create_cursor()` (`:217`)**: after creating the `SQLiteCursorWrapper`, attach the `DatabaseWrapper` to it, e.g. `cursor.db = self`.
  - The cursor class is pure Python, so it accepts attributes. The raw `sqlite3.Connection` does not.
- **`SQLiteCursorWrapper.execute()` (`:353`) / `executemany()` (`:361`)**:
  - Set `self.db._query_deadline = time.monotonic() + timeout` before calling `super()`.
  - Clear it in a `finally` block. It's cheapest to factor this into a context manager.
- **`get_connection_params()` (`:154`)**: no change. The docs must say that the existing `OPTIONS["timeout"]` is sqlite3's lock/busy timeout, which is unrelated to `QUERY_TIMEOUT`.

### Oracle: `django/db/backends/oracle/base.py`
- **`init_connection_state()` (`:311`)**: set `self.connection.call_timeout = self.query_timeout_ms() or 0` next to `stmtcachesize` (`:350`).
  - This runs for both direct and pooled connections. `get_new_connection()` (`:301`) acquires from the pool, so the value is re-applied on every checkout. Always assigning it, even as 0, means a pooled connection never keeps an old value.
- **Risk to verify**: when python-oracledb's `call_timeout` fires, the connection may be unusable afterwards.
  - Check which exception class results (DPY-4024 / ORA-03156), and whether `wrap_oracle_errors`/`DatabaseErrorWrapper` (`django/db/utils.py:73`) ends up as `OperationalError`.
  - If not, map it in `FormatStylePlaceholderCursor.execute()`/`executemany()` (`:630`/`:636`) and make sure `errors_occurred` gets set, so the health check drops the connection.

## 3. Tests

- **`tests/db_utils/tests.py` `ConnectionHandlerTests` (`:12`)**: check that `QUERY_TIMEOUT` defaults to `None` for `{}` and for `{"default": {...}}`.
- **`tests/backends/base/test_base.py` `DatabaseWrapperTests` (`:18`)**: `SimpleTestCase` tests on a copy of `connection.settings_dict` that call `check_settings()`:
  - Values `-1`, `0`, `True`, `"5"` and `timedelta(...)` each raise `ImproperlyConfigured` with the message.
  - `None`, `5` and `0.5` pass.
  - With `features.supports_query_timeout` patched to False, a non-`None` value raises `NotSupportedError`.
- **`tests/backends/tests.py` `BackendTestCase` (`:310`)**, next to `test_timezone_none_use_tz_false` (`:619`): a backend-agnostic `@skipUnlessDBFeature("supports_query_timeout")` test.
  - Open a new connection with `QUERY_TIMEOUT=0.2`, run a query that never finishes, and `assertRaises(OperationalError)`.
  - Then check that a `QUERY_TIMEOUT=None` connection runs `SELECT 1` normally.
- **Per-backend tests** that the setting is applied and that a slow query is actually cut off:
  - `tests/backends/postgresql/tests.py` `Tests` (`:34`):
    - `SHOW statement_timeout` returns `'200ms'`, and `SELECT pg_sleep(5)` raises `OperationalError`.
    - A pooled variant, modelled on `test_connect_pool_with_timezone` (`:287`), shows the `configure=` path applies it.
    - A test with `AUTOCOMMIT=False` checks the commit path.
  - `tests/backends/mysql/tests.py` `Tests` (`:105`):
    - Check `@@SESSION.max_execution_time` or `@@SESSION.max_statement_time`, depending on `mysql_is_mariadb`.
    - Use `SELECT BENCHMARK(...)` for the timeout test, not `SLEEP()`. MySQL returns `1` from an interrupted `SLEEP()` instead of raising an error. Confirm on both servers that `BENCHMARK` raises.
  - `tests/backends/sqlite/tests.py` `Tests` (`:28`):
    - An endless recursive CTE (`WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c`) raises `OperationalError`.
    - The deadline is cleared after the query, so the next fast query succeeds.
    - With no timeout, no progress handler is installed.
  - `tests/backends/oracle/tests.py` `Tests` (`:23`):
    - `connection.connection.call_timeout == 200`.
    - A `DBMS_SESSION.SLEEP(5)` block raises `OperationalError`.
    - The connection is discarded or still usable afterwards, depending on what the risk check above finds.

## 4. Docs

- **`docs/ref/settings.txt`**: add a new `.. setting:: DATABASE-QUERY_TIMEOUT` section in alphabetical order between `PORT` (`:644`) and `DATABASE-TIME_ZONE` (`:654`). Mark it `.. versionadded:: 6.2` and include:
  - Units, the `None` default, and that 0 is rejected.
  - How each backend enforces it, and the MySQL SELECT-only caveat.
  - The difference from the SQLite `OPTIONS["timeout"]` lock timeout.
- **`docs/ref/databases.txt`**: add short notes to the PostgreSQL (`:119`), MySQL (`:444`), SQLite (`:827`) and Oracle (`:1005`) sections. Mention that PgBouncer in transaction mode can reset session `SET`s.
- **`docs/releases/6.2.txt`**: add a bullet under "Database backends" (`:137`).
- **`docs/ref/databases.txt`, "Persistent connections" (`:30`)**: optionally note that the timeout is applied once per connection, so changing it takes effect on the next new connection.

## Order of work
1. Default setting, feature flag, validation, and the tests for them.
2. PostgreSQL and SQLite; both can be tested locally with the recursive-CTE and `pg_sleep` tests.
3. MySQL/MariaDB.
4. Oracle, after checking how `call_timeout` fails.
5. Docs.