Now I have all the information needed. Here's the complete request flow through Flask from `wsgi_app` to response:

## Flask Request Flow — Call Order

**1. Entry Point**
- `wsgi_app` (src/flask/app.py:1569) — WSGI application entry point

**2. Context Creation**
- `request_context` (src/flask/app.py:1504) — Creates AppContext from WSGI environ
- `AppContext.from_environ` (src/flask/ctx.py:348) — Static factory for context creation

**3. Context Push — Initialization**
- `ctx.push()` (src/flask/ctx.py:416) — Activates request context:
  - Increments push count
  - Sets context variable
  - Sends `appcontext_pushed` signal
  - Opens session via `_get_session()` (src/flask/ctx.py:381)

**4. URL Routing**
- `match_request()` (src/flask/ctx.py:405) — Matches request URL to endpoint/view_args:
  - Calls `url_adapter.match()` from Werkzeug
  - Stores result in `request.url_rule` and `request.view_args`

**5. Request Processing — Before Hooks**
- `full_dispatch_request` (src/flask/app.py:995) — Orchestrates entire request handling
- `preprocess_request` (src/flask/app.py:1369) — Executes before-request handlers:
  - Calls `url_value_preprocessors` (src/flask/app.py:1383–1385)
  - Calls `before_request_funcs` for app and blueprint (src/flask/app.py:1388–1393)
  - Returns early if any handler returns non-None

**6. View Dispatch**
- `dispatch_request` (src/flask/app.py:969) — Executes the view function:
  - Checks for routing exceptions
  - Handles OPTIONS requests
  - Calls view function with `view_args` from routing

**7. Response Finalization — After Hooks**
- `finalize_request` (src/flask/app.py:1024) — Converts return value to Response:
  - `make_response` — Converts view return value to Response object
  - `process_response` (src/flask/app.py:1397) — Post-processes response:
    - Calls `_after_request_functions` (src/flask/ctx.py:323) — Per-request handlers registered via `@after_this_request`
    - Calls `after_request_funcs` for blueprint and app (src/flask/app.py:1413–1416)
    - Calls `session_interface.save_session()` (src/flask/app.py:1419)
    - Sends `request_finished` signal (src/flask/app.py:1045–1047)

**8. Context Pop — Teardown**
- `ctx.pop()` (src/flask/ctx.py:446) — Finalizes and removes context:
  - Calls `do_teardown_request()` (src/flask/app.py:1423) — Executes teardown_request handlers (src/flask/app.py:1445–1449)
  - Closes request via `request.close()`
  - Calls `do_teardown_appcontext()` — Executes teardown_appcontext handlers
  - Sends `appcontext_popped` signal (src/flask/ctx.py:502)

**9. Response Sent**
- WSGI response yielded back to server

**Exception Handling** (within full_dispatch_request try/except):
- `handle_user_exception` (src/flask/app.py:868) — Routes exception to appropriate handler
- `handle_http_exception` or custom error handler
- `handle_exception` (src/flask/app.py:900) — Logs unhandled exceptions, sends `got_request_exception` signal
- Response still goes through `finalize_request` and teardown (src/flask/app.py:951)