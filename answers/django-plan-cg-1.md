I've read the connection code in all four backends and am writing up the plan now. Nothing was edited.

# Plan: per-database `QUERY_TIMEOUT` in `DATABASES`

## Design decisions

- **A top-level key, not an `OPTIONS` entry.** Every backend passes `OPTIONS` straight to the driver's `connect()`. You can see this in `postgresql/base.py:272`, `mysql/base.py:236,251`, `sqlite3/base.py:164` and `oracle/base.py:295`. An `OPTIONS["query_timeout"]` would be sent to the driver, so each backend would have to strip it out. A sibling of `CONN_MAX_AGE` and `TIME_ZONE` avoids that.
- **Units and default:** seconds, as an int or float, matching `CONN_MAX_AGE`. `None` (the default) means no timeout. Each backend converts to what its database expects (ms or seconds).
- **Validation happens when connecting, in `check_settings()`.** This follows the existing `TIME_ZONE`/`USE_TZ` check, which raises `ImproperlyConfigured`. A system check in `BaseDatabaseValidation` would only run with `check --database`, so it isn't enough alone.
- **Add a `supports_query_timeout` feature flag.** Third-party backends default to `False` and raise an error rather than silently ignoring the timeout.

---

## 1. Core settings and validation

| File:line | Change |
|---|---|
| `django/db/utils.py:168-171` (`ConnectionHandler.configure_settings`) | Add `conn.setdefault("QUERY_TIMEOUT", None)` next to `CONN_HEALTH_CHECKS` and `TIME_ZONE`. |
| `django/db/backends/base/features.py:5` (`BaseDatabaseFeatures`) | Add `supports_query_timeout = False`. |
| `django/db/backends/base/base.py:263` (`BaseDatabaseWrapper.check_settings`) | Read `self.settings_dict.get("QUERY_TIMEOUT")`. Raise `ImproperlyConfigured` if it isn't `None` and is any of: a `bool`, not an `int`/`float`, or `<= 0`. Also raise if it's set and `not self.features.supports_query_timeout`. Use `.get()`: several tests build or patch `settings_dict` by hand (e.g. `tests/backends/base/test_base.py:270-280`), and third-party code may build connections without going through `configure_settings`. |
| `django/db/backends/base/base.py` (near `get_connection_params`, line 208) | Add a helper property, e.g. `query_timeout_ms`, that returns `None` or `round(QUERY_TIMEOUT * 1000)`. Backends then share one conversion. |

`check_settings()` is called at the start of `connect()` (`base/base.py:237-240`), so every backend gets the validation.

## 2. Per-backend changes

### PostgreSQL: `django/db/backends/postgresql/`
- `base.py:381` `_configure_connection`: add a `commit_timeout = self._configure_query_timeout(connection)` step and include it in the returned value.
- New method `_configure_query_timeout(connection)`, modelled on `_configure_role` (`base.py:373`): run `SET statement_timeout = %s` through `self.ops.compose_sql`, passing the value in ms, and return `True`.
- Pooled and non-pooled connections both go through this one method:
  - non-pooled: `init_connection_state`, `base.py:410-416`
  - pooled: `ConnectionPool(configure=self._configure_connection)`, `base.py:224-228`
- `features.py`: `supports_query_timeout = True`.
- Rejected alternative: injecting `-c statement_timeout=` through `conn_params["options"]` in `get_connection_params` (`base.py:250`). It would clash with a user-supplied `OPTIONS["options"]` and with PgBouncer.

### MySQL / MariaDB: `django/db/backends/mysql/`
- `base.py:258` `init_connection_state`: append to `assignments`.
  - MariaDB (`self.mysql_is_mariadb`): `SET SESSION max_statement_time = <seconds>`.
  - MySQL: `SET SESSION max_execution_time = <ms>`.
- `features.py`: `supports_query_timeout = True`.
- Document that on MySQL `max_execution_time` only applies to read-only `SELECT` statements. MariaDB's setting covers all statements.

### SQLite: `django/db/backends/sqlite3/`
SQLite has no server-side statement timeout, so this has to be done in Django:
- `base.py:204` `get_new_connection`: when a timeout is set, register `conn.set_progress_handler(self._check_query_deadline, N)`, with N around 1000 VM instructions. The handler returns non-zero once `time.monotonic()` passes `self._query_deadline`. SQLite then aborts with `sqlite3.OperationalError: interrupted`.
- `base.py:353` `SQLiteCursorWrapper.execute` and `:361` `executemany`: set the deadline before running and clear it in a `finally`. The cursor needs to reach the wrapper's deadline, e.g. through a small attribute set in `create_cursor` (`base.py:~213`).
- `features.py`: `supports_query_timeout = True`.
- Document the difference from the existing `OPTIONS["timeout"]`, which is the lock-busy timeout passed to `sqlite3.connect` and is unrelated.

### Oracle: `django/db/backends/oracle/`
- `base.py:311` `init_connection_state`: set `self.connection.call_timeout = self.query_timeout_ms` (an oracledb round-trip timeout in ms). Set it to `0` when the setting is `None`, so a pooled connection from `pool.acquire()` (`base.py:302-303`) doesn't keep a previous value.
- `features.py`: `supports_query_timeout = True`.
- Document that a timeout (DPI-1067) can leave the connection unusable. `errors_occurred` plus health checks will then reconnect.

### Dummy backend
No change. It inherits `supports_query_timeout = False`, and connecting already raises `ImproperlyConfigured`.

## 3. Tests

| File | Tests to add |
|---|---|
| `tests/db_utils/tests.py:12` `ConnectionHandlerTests` | `QUERY_TIMEOUT` defaults to `None` after `configure_settings`. |
| `tests/backends/base/test_base.py:18` `DatabaseWrapperTests` | `check_settings` rejects `0`, `-1`, `"5"` and `True`, and accepts `None`, `5` and `0.5`. It raises when the feature flag is `False` (patch `features.supports_query_timeout`). `query_timeout_ms` converts correctly. Use the `patch.dict(connection.settings_dict, …)` pattern from `test_base.py:270-280`. |
| `tests/backends/postgresql/tests.py` | `SHOW statement_timeout` matches the setting. Add a pooled variant modelled on `test_connect_pool_with_timezone` (`:287`). `SELECT pg_sleep(…)` raises `OperationalError` (`QueryCanceled`). |
| `tests/backends/mysql/tests.py` | The right session variable is set for MySQL vs MariaDB (mock `mysql_is_mariadb`). `SELECT SLEEP(…)` is interrupted. |
| `tests/backends/sqlite/tests.py` | A long recursive CTE raises `OperationalError("interrupted")`. The deadline is cleared after `execute()`, and the connection stays usable. With `None`, no progress handler is registered. |
| `tests/backends/oracle/tests.py` | `connection.connection.call_timeout` equals the value in ms, and `0` when unset. The pool path resets it. |
| `tests/check_framework/test_database.py` | Only needed if you also add a system check. The plan above validates in `check_settings` instead. |

The slow-query tests should call `connection.close()` in cleanup, since a timeout can poison the connection.

## 4. Docs

- `docs/ref/settings.txt`: new `.. setting:: DATABASE-QUERY_TIMEOUT` section between `CONN_HEALTH_CHECKS` (`:606`) and `OPTIONS` (`:621`). Cover the default `None`, seconds as the unit, per-backend semantics and `.. versionadded:: 6.2`.
- `docs/ref/databases.txt`: a note in each backend section:
  - PostgreSQL, around `:130`: `statement_timeout`, including with pooling (`:252`).
  - MySQL, around `:645`: `max_execution_time` only covers `SELECT`; MariaDB's `max_statement_time` covers all statements.
  - SQLite: progress-handler approach, and how it differs from `OPTIONS["timeout"]`.
  - Oracle: `call_timeout` semantics.
- `docs/releases/6.2.txt:137` ("Database backends"): add a release note. The version is 6.2 alpha (`django/__init__.py:3`).

## Summary of functions touched
`ConnectionHandler.configure_settings`, `BaseDatabaseWrapper.check_settings`, new `BaseDatabaseWrapper.query_timeout_ms`, `BaseDatabaseFeatures.supports_query_timeout`, PostgreSQL `_configure_connection` plus new `_configure_query_timeout`, MySQL `init_connection_state`, SQLite `get_new_connection`, `create_cursor`, `SQLiteCursorWrapper.execute`/`executemany` plus a new deadline handler, Oracle `init_connection_state`, and each backend's `features.py`.

**Out of scope:** each backend raises its own exception on timeout (usually `OperationalError`). Mapping them all to a shared `QueryTimeout` exception would be a separate change.