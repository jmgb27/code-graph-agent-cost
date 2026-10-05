Now I have the complete request flow. Here's the trace from `Flask.wsgi_app` to the response, listing all functions in call order:

## Request Flow: Flask.wsgi_app to Response

**1. Entry Point & Context Creation**
- **`wsgi_app`** — src/flask/app.py:1569
  - Creates request context and manages overall request lifecycle

- **`request_context`** — src/flask/app.py:1504
  - Creates an `AppContext` from WSGI environ

**2. Context Activation & Routing**
- **`ctx.push`** — src/flask/ctx.py:416
  - Pushes context into context var
  - Sends `appcontext_pushed` signal
  - Opens session via `_get_session`
  - Calls `match_request` for URL routing

- **`match_request`** — src/flask/ctx.py:405
  - Uses `url_adapter.match()` to perform URL routing
  - Sets `request.url_rule` and `request.view_args` or stores routing exception

**3. Request Pre-Processing**
- **`full_dispatch_request`** — src/flask/app.py:995
  - Orchestrates the full dispatch pipeline

- Sends **`request_started` signal** — src/flask/app.py:1016

- **`preprocess_request`** — src/flask/app.py:1369
  - Calls `url_value_preprocessors` registered with app/blueprint
  - Calls `before_request_funcs` (app-level and blueprint-level in reverse blueprint order)
  - Early return if any before_request handler returns non-None

**4. View Dispatch**
- **`dispatch_request`** — src/flask/app.py:969
  - Checks for routing exceptions
  - Handles automatic OPTIONS responses
  - Calls the view function via `view_functions[endpoint]`
  - (Note: For class-based views, this calls the view wrapper which calls `dispatch_request` on the view class)

**5. Response Finalization**
- **`finalize_request`** — src/flask/app.py:1024
  - **`make_response`** — Converts return value to Response object
  - **`process_response`** — src/flask/app.py:1397
    - Calls request-scoped `_after_request_functions` (in order)
    - Calls app/blueprint-level `after_request_funcs` (in reverse order)
    - Saves session via `session_interface.save_session`
  - Sends **`request_finished` signal** — src/flask/app.py:1045

**6. Error Handling (if exception occurs)**
- **`handle_user_exception`** — src/flask/app.py:868 (called if exception during dispatch)
  - Routes to `handle_http_exception` for HTTPException
  - Finds registered error handler via `_find_error_handler`

- **`handle_exception`** — src/flask/app.py:900 (called for unhandled exceptions)
  - Sends `got_request_exception` signal
  - Logs exception via `log_exception`
  - Creates InternalServerError and finds handler
  - Calls `finalize_request` with error context

**7. Context Cleanup**
- **`ctx.pop`** — src/flask/ctx.py:446
  - Decrements push count (allows multiple push/pop pairs)
  - Calls **`do_teardown_request`** — src/flask/app.py:1423
    - Calls `teardown_request_funcs` (blueprint-specific, then app-level, in reverse order)
    - Sends `request_tearing_down` signal
  - Closes request via `request.close()`
  - Calls **`do_teardown_appcontext`** — src/flask/app.py:1456
    - Calls `teardown_appcontext_funcs` (blueprint-specific, then app-level, in reverse order)
    - Sends `appcontext_tearing_down` signal
  - Resets context var
  - Sends **`appcontext_popped` signal**

**8. WSGI Response**
- **`response(environ, start_response)`** — src/flask/app.py:1607
  - Calls the Response object as WSGI application to send to client