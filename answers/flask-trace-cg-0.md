This checkout is Flask 3.2-era code, where `RequestContext` has been merged into `AppContext`. A single `AppContext` holds both the app state and the request state.

## Request lifecycle, in call order

**0. Entry point**
- `Flask.__call__`: `src/flask/app.py:1621`. It just calls `self.wsgi_app(environ, start_response)` (line 1628).
- `Flask.wsgi_app`: `src/flask/app.py:1569`.

**1. Build the context** (`app.py:1595`)
1. `Flask.request_context(environ)`: `src/flask/app.py:1504`. Calls the next step.
2. `AppContext.from_environ`: `src/flask/ctx.py:340`. Creates `app.request_class(environ)`, sets `json_module`, then runs `cls(app, request=...)`.
3. `AppContext.__init__`: `src/flask/ctx.py:300`. Creates `g` and an empty `_after_request_functions` list, then calls:
4. `Flask.create_url_adapter(request)`: `src/flask/app.py:510`. Applies `TRUSTED_HOSTS` and returns `url_map.bind_to_environ(...)` (line 549). If binding raises an `HTTPException`, it is saved as `request.routing_exception` (`ctx.py:325-329`).

**2. Push the context** (`app.py:1599`)
5. `AppContext.push`: `src/flask/ctx.py:416`.
   - Sets `_cv_app` and sends the `appcontext_pushed` signal (`ctx.py:433-434`).
   - `AppContext._get_session`: `src/flask/ctx.py:381`. Calls `session_interface.open_session`, falling back to `make_null_session` (`ctx.py:387-391`).
   - **URL matching:** `AppContext.match_request`: `src/flask/ctx.py:405`. Calls `url_adapter.match(return_rule=True)` and stores `request.url_rule` and `request.view_args`. If matching fails, it stores `routing_exception` instead (`ctx.py:409-414`).

**3. Dispatch** (`app.py:1600`)
6. `Flask.full_dispatch_request`: `src/flask/app.py:995`.
   - Sends the `request_started` signal (`app.py:1016`).
7. **before_request:** `Flask.preprocess_request`: `src/flask/app.py:1369`.
   - Runs `url_value_preprocessors` for the app, then each blueprint (`app.py:1382-1385`).
   - Runs `before_request_funcs` through `ensure_sync(before_func)()` (`app.py:1387-1393`).
   - If a function returns something other than `None`, dispatch is skipped and that value is used as the response.
8. **View dispatch:** `Flask.dispatch_request`: `src/flask/app.py:969`.
   - If `routing_exception` is set, calls `Flask.raise_routing_exception` (`src/flask/app.py:563`).
   - For an automatic `OPTIONS` request, calls `make_default_options_response` (`app.py:986-990`).
   - Otherwise runs `self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)` (`app.py:993`).
   - Class-based views go through the `view` closure from `View.as_view`, which calls `View.dispatch_request` (`src/flask/views.py:110/116`, `views.py:78`).
   - If an exception is raised here, `Flask.handle_user_exception` (`src/flask/app.py:868`) handles it (`app.py:1020-1021`).

**4. Finalize** (`app.py:1022`)
9. `Flask.finalize_request`: `src/flask/app.py:1024`.
   - `Flask.make_response(rv)`: `src/flask/app.py:1227`. Converts the return value into a `Response`.
10. **after_request:** `Flask.process_response`: `src/flask/app.py:1397`.
    - Runs the per-request `ctx._after_request_functions` first (`app.py:1410-1411`).
    - Then runs `after_request_funcs` for each blueprint and then the app, in reverse order of registration (`app.py:1413-1416`).
    - `session_interface.save_session(...)`, only if the session is not a null session (`app.py:1418-1419`).
    - Back in `finalize_request`, it sends the `request_finished` signal (`app.py:1047`).

If an unhandled exception escapes step 6, `wsgi_app` calls `Flask.handle_exception` instead (`src/flask/app.py:900`, called at `app.py:1603`). That also ends in `finalize_request(..., from_error_handler=True)`.

**5. Send the response** (`app.py:1607`)
11. `response(environ, start_response)`: the Werkzeug `Response` is called as a WSGI app.

**6. Teardown** (`finally` block in `wsgi_app`, `app.py:1608-1619`)
12. The optional `werkzeug.debug.preserve_context` hook runs, then the deprecated `should_ignore_error` check (`app.py:1609-1617`).
13. `AppContext.pop(error)`: `src/flask/ctx.py:446`. It returns early while nested pushes remain (`_push_count > 0`, `ctx.py:483`).
    - `Flask.do_teardown_request`: `src/flask/app.py:1423`. Runs `teardown_request_funcs` for each blueprint and then the app, in reverse order, and sends the `request_tearing_down` signal (`app.py:1445-1452`).
    - `request.close()` (`ctx.py:493`).
    - `Flask.do_teardown_appcontext`: `src/flask/app.py:1456`. Runs `teardown_appcontext_funcs` in reverse order and sends the `appcontext_tearing_down` signal.
    - Resets `_cv_app` and sends the `appcontext_popped` signal (`ctx.py:498-502`).
    - `_CollectErrors.raise_any`: every teardown callback runs even if an earlier one fails, and the collected errors are raised together at the end (`ctx.py:504`).

## Condensed call chain
```
__call__ → wsgi_app
  → request_context → AppContext.from_environ → AppContext.__init__ → create_url_adapter
  → AppContext.push → _get_session (open_session) → match_request (url_adapter.match)
  → full_dispatch_request
      → [request_started]
      → preprocess_request (url_value_preprocessors, before_request_funcs)
      → dispatch_request (raise_routing_exception? → view_functions[endpoint])
      → handle_user_exception (on error)
      → finalize_request → make_response → process_response (after_request, save_session) → [request_finished]
  → response(environ, start_response)
  → AppContext.pop → do_teardown_request → request.close → do_teardown_appcontext → [appcontext_popped]
```