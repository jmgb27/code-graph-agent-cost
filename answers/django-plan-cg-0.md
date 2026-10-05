# Plan: per-database `QUERY_TIMEOUT` for all four built-in backends

I only read files for this; nothing was edited or run. Line numbers are from the current `main` (9332b16).

## Design choices

- **Where the setting lives:** a new top-level key, `DATABASES[alias]["QUERY_TIMEOUT"]`, next to `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS`. It should not go in `OPTIONS`, for two reasons:
  - Every backend passes `OPTIONS` straight to its database driver (`postgresql/base.py:270-279`, `mysql/base.py:236,247`, `sqlite3/base.py:161-165`, `oracle/base.py:295`). A new key there would have to be removed in four places.
  - SQLite already uses `OPTIONS["timeout"]` for something different: how long to wait for a lock.
- **Value:** `None` (the default) means no timeout. Otherwise a positive `int` or `float`, in seconds. Each backend converts it to the unit its database expects.
- **When the limit is hit:** the query raises `django.db.OperationalError`. The existing `wrap_database_errors` already converts the driver's error to this.

## 1. Default value

**`django/db/utils.py:150` `ConnectionHandler.configure_settings`**
- In the defaults loop (lines 162-173), add `conn.setdefault("QUERY_TIMEOUT", None)` after the `CONN_HEALTH_CHECKS` line (`:169`).

## 2. Validation

**`django/db/backends/base/base.py:263` `BaseDatabaseWrapper.check_settings`**
- `connect()` calls this for every backend (`:240`), before any driver call, so it covers all four.
- Next to the existing `TIME_ZONE` check, raise `ImproperlyConfigured` unless the value is `None`, or an `int`/`float` that is not a `bool` and is greater than 0.
- Message format: `"settings.DATABASES[%r]['QUERY_TIMEOUT'] must be None or a positive number of seconds."`
- Optionally add a helper `BaseDatabaseWrapper.query_timeout_ms()` that returns `None` or `round(value * 1000)`. PostgreSQL, MySQL and Oracle all need milliseconds.

**PostgreSQL and Oracle pools.** Both build their pool from `get_connection_params()` (`postgresql/base.py:215`, `oracle/base.py:270`) without going through `connect()`. So:
- Call `self.check_settings()` at the top of the `pool` property in `postgresql/base.py:194` and `oracle/base.py:259`, or
- Rely on `connect()` always running `check_settings()` before `get_new_connection()` touches the pool. It does today; add a test so that stays true.

**Optional system check.** `django/db/backends/base/validation.py:10` `BaseDatabaseValidation.check` could return `checks.Error(id="database.E001")` for the same bad values.
- This only runs with `check --database`, so it adds to the runtime validation rather than replacing it.
- If you add it, `mysql/validation.py:7` already calls `super().check()`. `oracle/validation.py` doesn't override `check()`, so it needs nothing.
- Document the ID in `docs/ref/checks.txt` under "Database" (around line 139).

## 3. Backend changes

### PostgreSQL: `django/db/backends/postgresql/base.py`
- **Add `_configure_query_timeout(self, connection)`**, modelled on `_configure_role` (`:373`). If a timeout is set, run `cursor.execute("SET statement_timeout = %s", [ms])` (or `ops.compose_sql`) and return `True`.
  - Also compare the current value with `connection.info.parameter_status("statement_timeout")` if you want to skip the round trip when nothing changes.
- **`_configure_connection` (`:381`):** call the new method and include its result in the returned commit flag (`:392`).
  - This one hook covers both the non-pooled path (`init_connection_state`, `:410-416`) and pooled connections, because the pool is created with `configure=self._configure_connection` (`:227`).
- **Don't** use `OPTIONS["options"] = "-c statement_timeout=…"`. It would clash with a user-supplied `options` value and doesn't work behind PgBouncer.
- **Decision needed:** `ensure_timezone` (`:357`) closes the pool when settings change. If tests change `QUERY_TIMEOUT` at runtime, the pool needs the same reset (the "Ensure the correct pool is returned" workaround at `:399-401`).

### MySQL / MariaDB: `django/db/backends/mysql/base.py`
- **`init_connection_state` (`:258`):** add to the `assignments` list (`:260`):
  - MariaDB (`self.mysql_is_mariadb`, `:435`): `SET SESSION max_statement_time = <seconds>` (a float, in seconds).
  - MySQL: `SET SESSION max_execution_time = <ms>`. This only limits read-only `SELECT` statements; document that.
  - This is the right place because `mysql_is_mariadb` is a cached property that needs a live connection.
- **Optional:** add `DatabaseOperations.set_query_timeout_sql(seconds)` in `django/db/backends/mysql/operations.py` to keep the MySQL/MariaDB branching out of `base.py`.

### SQLite: `django/db/backends/sqlite3/base.py`
SQLite has no server-side query timeout, so this has to be done on the client side:
- **`get_new_connection` (`:204`):** if a timeout is set, call `conn.set_progress_handler(self._check_query_deadline, 1000)`.
  - The handler returns a non-zero value once `time.monotonic()` passes `self._query_deadline`. SQLite then aborts the statement with `sqlite3.OperationalError: interrupted`, which Django wraps.
- **Add `_check_query_deadline` and a `_query_deadline = None` attribute** to `DatabaseWrapper` (class at `:60`).
- **`create_cursor` (`:219`):** pass the wrapper to the cursor, e.g. `factory=functools.partial(SQLiteCursorWrapper, db=self)`, so the cursor can reset the deadline.
  - `sqlite3.Connection` is a C type and can't hold custom attributes, which is why the deadline lives on the wrapper.
- **`SQLiteCursorWrapper` (`:340`):**
  - Add `__init__(self, connection, db=None)`.
  - In `execute` (`:353`) and `executemany` (`:361`), set `db._query_deadline = time.monotonic() + timeout` before calling `super()`.
  - Handle the `params is None` early return at `:354-355` as well.
- **Document** that this timeout does not include waiting for locks. That wait is still controlled by `OPTIONS["timeout"]`.

### Oracle: `django/db/backends/oracle/base.py`
- **`get_new_connection` (`:301`):** on both the `self.pool.acquire()` result (`:303-304`) and the `Database.connect(...)` result (`:305-309`), set `conn.call_timeout = ms`.
  - It has to be set on every `acquire()`, because a connection taken from the pool may have been used with a different value.
- **`init_connection_state` (`:311`)** doesn't need a change.
- **Document** that `call_timeout` limits each network round trip to the server, not the whole statement.

### Dummy backend
No change. It never connects.

## 4. Tests

| File | Test |
|---|---|
| `tests/db_utils/tests.py` `ConnectionHandlerTests` (`:12`) | `configure_settings({"default": {...}})` sets `QUERY_TIMEOUT` to `None`. |
| `tests/backends/base/test_base.py` `DatabaseWrapperTests` (`:18`) | `check_settings()` raises `ImproperlyConfigured` for `0`, `-1`, `"5"`, `True` and `[]`, and accepts `None`, `5` and `0.5`. Use a copy of `connection.settings_dict` and don't connect. |
| `tests/backends/postgresql/tests.py` `Tests` (`:34`) | New connection with `QUERY_TIMEOUT=2`: `SHOW statement_timeout` returns `'2s'`. `SELECT pg_sleep(5)` with `QUERY_TIMEOUT=0.5` raises `OperationalError`. A pooled version following `test_pooling_health_checks` (`:311`, `no_pool_connection(alias="default_pool")`) checks the value is applied through `configure`. |
| `tests/backends/mysql/tests.py` `Tests` (`:105`) | Check `SELECT @@SESSION.max_statement_time` (MariaDB) or `@@SESSION.max_execution_time` (MySQL). On MySQL, an interrupted `SELECT SLEEP(n)` returns `1` instead of raising an error, so either assert on the variable or use a slow query without `SLEEP`. |
| `tests/backends/sqlite/tests.py` `Tests` (`:28`) | A long recursive-CTE query with `QUERY_TIMEOUT=0.1` raises `OperationalError`. A fast query run after a delay longer than the timeout still succeeds, which shows the deadline resets on each `execute`. `executemany` is covered too. No progress handler is installed when the value is `None`. |
| `tests/backends/oracle/tests.py` `Tests` (`:23`) | `connection.connection.call_timeout == ms`. `DBMS_SESSION.SLEEP(5)` raises `OperationalError`. Pooled case: the value is re-applied after `acquire()`. |
| `tests/check_framework/test_database.py` (`:9`) | Only if you add `database.E001`. |

For the per-backend tests, build a separate connection (`connection.copy()` or the `no_pool_connection` helper) with a changed `settings_dict`, and close it in `finally`, as the existing pool tests do.

## 5. Docs

- **`docs/ref/settings.txt`:** add a `.. setting:: QUERY_TIMEOUT` entry after `CONN_HEALTH_CHECKS` (`:606-620`), covering the default `None`, the units and the per-backend caveats.
- **`docs/ref/databases.txt`:** add a short "Query timeout" subsection in each backend section:
  - PostgreSQL notes (`:119`): `statement_timeout`, and that it works with pools.
  - MySQL notes (`:444`): `max_execution_time` only applies to `SELECT`; MariaDB uses `max_statement_time`.
  - SQLite notes (`:827`): progress-handler approach, and how it differs from `OPTIONS["timeout"]`.
  - Oracle notes (`:1005`): `call_timeout` is per round trip.
- **`docs/releases/6.2.txt`:** add an entry under "Database backends" (`:137`). The current dev version is 6.2 alpha (`django/__init__.py:3`).
- **`docs/ref/checks.txt`:** only if you add the system check.

## Open questions

- **Test database setup:** PostgreSQL's `_nodb_cursor` and test-database cloning copy `settings_dict`, so the timeout would also apply to `CREATE DATABASE`. You may want to skip it when `alias == NO_DB_ALIAS` (see `postgresql/base.py:195`).
- **MySQL write statements:** decide whether it's acceptable that plain MySQL only limits `SELECT`, or whether to warn about it.