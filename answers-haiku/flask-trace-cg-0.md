## Flask Request Flow: Entry to Response

Here's the complete request flow traced from `wsgi_app` through context management, routing, hooks, and teardown:

### 1. **WSGI Entry Point**
- `wsgi_app()` — src/flask/app.py:1569
  - Creates the request context from WSGI environ

### 2. **Request Context Creation & Push**
- `request_context()` — src/flask/app.py:1504
  - Creates `AppContext.from_environ()`
- `ctx.push()` — src/flask/ctx.py:416
  - Opens session via `_get_session()` — src/flask/ctx.py:381
  - **Triggers URL matching**: calls `match_request()` — src/flask/ctx.py:405

### 3. **URL Matching / Routing**
- `match_request()` — src/flask/ctx.py:405
  - Calls `url_adapter.match(return_rule=True)` (Werkzeug routing)
  - Stores matched endpoint and view_args in request
  - On error, stores routing exception in request

### 4. **Full Dispatch & Before-Request Hooks**
- `full_dispatch_request()` — src/flask/app.py:995
  - Sends `request_started` signal
  - Calls `preprocess_request()` — src/flask/app.py:1369

### 5. **Before-Request Processing**
- `preprocess_request()` — src/flask/app.py:1369
  - Runs `url_value_preprocessors` (registered on app/blueprints)
  - Runs `before_request_funcs` (can return early to skip view dispatch)

### 6. **View Dispatch**
- `dispatch_request()` — src/flask/app.py:969
  - Checks for routing exceptions, raises if present
  - Handles automatic OPTIONS responses
  - Looks up and calls the view function: `view_functions[endpoint](**view_args)`

### 7. **Response Creation**
- `finalize_request()` — src/flask/app.py:1024
  - Calls `make_response()` to convert view return value to Response object
  - Calls `process_response()` — src/flask/app.py:1397

### 8. **After-Request Hooks**
- `process_response()` — src/flask/app.py:1397
  - Runs `after_request_funcs` in reverse registration order
  - Saves session via `session_interface.save_session()`
  - Sends `request_finished` signal

### 9. **Teardown & Context Pop**
- `ctx.pop()` — src/flask/ctx.py:446
  - Calls `do_teardown_request()` — src/flask/app.py:1423
    - Runs `teardown_request_funcs` (in reverse order)
    - Sends `request_tearing_down` signal
  - Calls `do_teardown_appcontext()` — src/flask/app.py:1456
    - Runs `teardown_appcontext_funcs` (in reverse order)
    - Sends `appcontext_tearing_down` signal

### 10. **WSGI Response**
- Returns response via WSGI `start_response` callback

**Exception Handling Path:**
- `handle_user_exception()` — src/flask/app.py:868 (catches view/hook errors)
- `handle_exception()` — src/flask/app.py:900 (wraps entire request, guarantees teardown runs)