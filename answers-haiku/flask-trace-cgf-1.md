Based on CodeGraph's analysis, here's the complete request flow from Flask's `wsgi_app` to the response, with functions in call order:

## Request Flow Trace

### 1. **Entry & Context Creation**
- **wsgi_app** (src/flask/app.py:1569) — Entry point, receives WSGI environ and start_response
- **request_context** (src/flask/app.py:1504) — Creates AppContext with request information (called at src/flask/app.py:1595)

### 2. **Context Push & URL Matching**
- **ctx.push()** (src/flask/ctx.py:416) — Pushes context active (called at src/flask/app.py:1599)
  - Sends `appcontext_pushed` signal (src/flask/signals.py:15)
  - Opens session via `_get_session()` (src/flask/ctx.py:381)
  - **match_request()** (src/flask/ctx.py:405) — Performs URL routing via `url_adapter.match()` (called at src/flask/ctx.py:444)
    - Stores endpoint and view_args or sets routing_exception

### 3. **Request Dispatch**
- **full_dispatch_request** (src/flask/app.py:995) — Orchestrates pre/post processing (called at src/flask/app.py:1600)
  - Sends `request_started` signal (src/flask/app.py:1016)
  - **preprocess_request** (src/flask/app.py:1369) — Runs before-request hooks (called at src/flask/app.py:1017)
    - Calls `url_value_preprocessors` (src/flask/app.py:1383-1385)
    - Calls `before_request_funcs` (src/flask/app.py:1388-1393)

### 4. **View Dispatch**
- **dispatch_request** (src/flask/app.py:969) — Calls the matched view function (called at src/flask/app.py:1019)
  - Retrieves view function from `view_functions[endpoint]`
  - Calls with `**view_args`

### 5. **Exception Handling (if needed)**
- **handle_user_exception** (src/flask/app.py:868) — Handles view exceptions (called at src/flask/app.py:1021)
  - Sends `got_request_exception` signal (src/flask/signals.py:13)
  - Calls registered error handler if exists

### 6. **Response Finalization**
- **finalize_request** (src/flask/app.py:1024) — Finalizes response (called at src/flask/app.py:1022)
  - Creates response via `make_response()`
  - **process_response** (src/flask/app.py:1397) — Runs after-request hooks (called at src/flask/app.py:1044)
    - Calls `after_request_funcs` in reverse registration order (src/flask/app.py:1410-1416)
    - Saves session via `session_interface.save_session()` (src/flask/app.py:1418)
  - Sends `request_finished` signal (src/flask/app.py:1045)

### 7. **Context Pop & Teardown**
- **ctx.pop()** (src/flask/ctx.py:446) — Pops context and runs cleanup (called at src/flask/app.py:1619)
  - **do_teardown_request** (src/flask/app.py:1423) — Runs teardown_request handlers (called at src/flask/ctx.py:490)
    - Sends `request_tearing_down` signal (src/flask/signals.py:12)
  - **do_teardown_appcontext** (src/flask/app.py:1456) — Runs teardown_appcontext handlers
    - Sends `appcontext_tearing_down` signal (src/flask/signals.py:14)

### 8. **Response Return**
- Response callable invoked with WSGI environ/start_response (src/flask/app.py:1607)