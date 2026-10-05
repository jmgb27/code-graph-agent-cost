# Plan: a per-database `QUERY_TIMEOUT` setting

I haven't edited any files. Every file:line reference below is from reading the current `main` (9332b16, Django 6.2 alpha).

## Design

- **Setting:** `DATABASES[alias]["QUERY_TIMEOUT"]` is the timeout in seconds, as an `int` or `float`. The default `None` means no timeout. It sits at the top level, next to `CONN_MAX_AGE`, rather than in `OPTIONS`, because `OPTIONS` is passed straight to the driver on every backend.
- **Validation:** do it in `BaseDatabaseWrapper.check_settings()`, next to the existing `TIME_ZONE` check. That runs on every `connect()`. Reject `bool`, non-numbers, and values of zero or less by raising `ImproperlyConfigured`.
- **Errors:** a timed-out query raises `django.db.OperationalError` on all four backends. `DatabaseErrorWrapper` already maps driver errors to it (`django/db/utils.py:53-78`).
- **Feature flag:** add `supports_query_timeout` so a third-party backend that can't honour the setting fails loudly instead of silently ignoring it.

## Core changes

| File | Function | Change |
|---|---|---|
| `django/db/utils.py:162-173` | `ConnectionHandler.configure_settings` | Add `conn.setdefault("QUERY_TIMEOUT", None)` next to `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS` (lines 168-169). |
| `django/db/backends/base/base.py:263` | `BaseDatabaseWrapper.check_settings` | Validate the type and require a value above 0. If it's set and `not self.features.supports_query_timeout`, raise `ImproperlyConfigured`. |
| `django/db/backends/base/base.py` (near `timezone_name`, line 158) | new `query_timeout_ms` property | Return `None`, or `max(1, round(QUERY_TIMEOUT * 1000))`. Three backends need milliseconds, so this avoids repeating the conversion. |
| `django/db/backends/base/features.py:~101` | `BaseDatabaseFeatures` | Add `supports_query_timeout = False`, and set it to `True` in each built-in backend's `features.py`. |

## Per-backend changes

**PostgreSQL** (`django/db/backends/postgresql/base.py`)
- **New `_configure_query_timeout(connection)`**, placed next to `_configure_timezone` and `_configure_role` (lines 364 and 373). It runs `SET statement_timeout = %s` with `query_timeout_ms`, using `self.ops.compose_sql` like `_configure_role` does, and returns `True` when it ran something.
- **`_configure_connection` (line 381):** call the new helper and OR its result into the returned commit flag.
  - This one hook covers both connection paths: `init_connection_state` (line 410) for plain connections, and the psycopg pool's `configure=` callback (line 227) for pooled ones.
- **Why `SET` rather than `get_connection_params` (line 250):** injecting `-c statement_timeout` into libpq `options` would clash with any `OPTIONS["options"]` the user already sets.
- **Limitation to document:** PgBouncer in transaction mode doesn't keep session `SET`s.

**MySQL / MariaDB** (`django/db/backends/mysql/base.py`)
- **`init_connection_state` (line 258):** add one entry to the existing `assignments` list:
  - MySQL: `SET SESSION max_execution_time = <ms>`.
  - MariaDB: `SET SESSION max_statement_time = <seconds>`.
  - Branch on `self.mysql_is_mariadb` (line 435).
- **Limitation to document:** MySQL's `max_execution_time` only applies to read-only `SELECT`s; MariaDB's applies to all statements.

**SQLite** (`django/db/backends/sqlite3/base.py`)

SQLite has no server-side timeout. Its connection `timeout` is the busy/lock wait, which is a different thing and shouldn't be reused.
- **`get_connection_params` (line 154):** store `self.query_timeout = settings_dict["QUERY_TIMEOUT"]` so the cursor can read it.
- **`SQLiteCursorWrapper.execute` / `executemany` (lines 353 and 361):** when a timeout is set:
  1. Compute a deadline with `time.monotonic()`.
  2. Install `self.connection.set_progress_handler(lambda: time.monotonic() > deadline, 1000)`.
  3. Run the query.
  4. Remove the handler in a `finally`.
- When the handler fires, sqlite raises `sqlite3.OperationalError("interrupted")`, which Django wraps.
- The cursor is a `sqlite3.Cursor` subclass (line 340), so it needs access to the timeout value, e.g. through an attribute set on the raw connection in `get_new_connection` (line 204).
- **Limitation to document:** the timeout covers `execute()` only, not rows fetched lazily afterwards.

**Oracle** (`django/db/backends/oracle/base.py`)
- **`init_connection_state` (line 311):** set `self.connection.call_timeout = self.query_timeout_ms`, or `0` when unset.
  - `call_timeout` is a connection attribute, not a connect kwarg, so it can't go through `get_connection_params` (line 294) or `create_pool` (line 275).
  - `init_connection_state` runs after every `get_new_connection` (line 301), including `pool.acquire()`. Resetting to `0` stops a pooled session from carrying over a stale value.
- **Limitation to document:** `call_timeout` limits each round trip, and after a timeout the driver may mark the connection unusable. `is_usable()` (line 387) and health checks deal with that.

## Tests

- **`tests/db_utils/tests.py` → `ConnectionHandlerTests` (line 12):** check that `QUERY_TIMEOUT` defaults to `None`.
- **`tests/backends/base/test_base.py` → `DatabaseWrapperTests` (line 18):**
  - `check_settings` rejects `0`, `-1`, `True`, `"5"` and `[]` with `ImproperlyConfigured`, and accepts `None`, `5` and `0.5`.
  - `query_timeout_ms` rounds correctly: `0.0001` becomes `1`, and `1.5` becomes `1500`.
  - A backend with `supports_query_timeout = False` raises when the setting is set.
  - Patch `settings_dict` with the `patch.dict` pattern used by `ConnectionHealthChecksTests` (lines 261-275).
- **`tests/backends/base/test_features.py`:** the default flag is `False`.
- **`tests/backends/postgresql/tests.py` → `Tests` (line 34):**
  - After connecting, `SHOW statement_timeout` matches the setting.
  - `SELECT pg_sleep(1)` with a 0.1s timeout raises `OperationalError`.
  - A pooled variant, modelled on `test_connect_pool` / `test_connect_pool_with_timezone` (lines 237 and 287), so the `configure=` path is covered.
- **`tests/backends/mysql/tests.py` → `Tests` (line 105):**
  - `SELECT @@SESSION.max_execution_time` or `max_statement_time`, depending on the vendor.
  - `SELECT SLEEP(1)` raises.
  - Note: MySQL's `SLEEP` returns 1 instead of raising when interrupted, so the MySQL test may need a slow `SELECT`, or should assert on the result.
- **`tests/backends/sqlite/tests.py` → `Tests` (line 28):**
  - A recursive CTE that runs long raises `OperationalError`.
  - Afterwards, the progress handler has been removed: a normal query runs and the connection is still usable.
- **`tests/backends/oracle/tests.py` → `Tests` (line 23):**
  - `connection.connection.call_timeout` equals the setting in milliseconds.
  - `DBMS_SESSION.SLEEP(1)` raises.
  - `call_timeout` goes back to `0` when the setting is `None`.
- Each backend test uses its own `connection.copy()` or a patched `settings_dict` plus `connection.close()`, so the shared test connection isn't left with a timeout.

## Docs

- **`docs/ref/settings.txt`:** add a `.. setting:: QUERY_TIMEOUT` section in alphabetical order, between `PORT` and `DATABASE-TIME_ZONE` (around line 654). Cover the default `None`, the units (seconds), and the per-backend mechanism.
- **`docs/ref/databases.txt`:**
  - One paragraph under "Connection management" (line 47).
  - Short caveats in the PostgreSQL (line 119, PgBouncer), MySQL (line 442, `SELECT`-only on MySQL), SQLite (line 825, `execute()` only) and Oracle (line 1003, connection may become unusable) notes.
- **`docs/releases/6.2.txt:137`:** add an entry under "Database backends".
- **Third-party backends:** add a note in the 6.2 "Backwards incompatible changes" section (line 280), because `check_settings` now reads `features.supports_query_timeout`.

## Open decision

Test-database creation and migrations use the same settings dict, so a short `QUERY_TIMEOUT` could make `migrate` or test setup time out. I'd accept this and document it, rather than adding a `TEST["QUERY_TIMEOUT"]` override now. If you want the override, it's a `default_test_settings` entry at `django/db/utils.py:176` plus handling in `django/db/backends/base/creation.py`.