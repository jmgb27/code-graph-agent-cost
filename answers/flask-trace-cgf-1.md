Here is the path a request takes from `Flask.wsgi_app` to the response, in call order. In this version of Flask there is no separate `RequestContext`: one `AppContext` holds both the app and the request.

### 0. Entry
- `Flask.__call__` passes the request to `self.wsgi_app(environ, start_response)` at `src/flask/app.py:1621-1628`.
- `Flask.wsgi_app` is at `src/flask/app.py:1569`.

### 1. Build the context (no routing yet)
1. `Flask.request_context(environ)` at `src/flask/app.py:1595` → `app.py:1504`
2. `AppContext.from_environ` at `src/flask/ctx.py:340`: builds `app.request_class(environ)` and sets `request.json_module`.
3. `AppContext.__init__` at `src/flask/ctx.py:300`: creates `g` and an empty `_after_request_functions` list.
   - `Flask.create_url_adapter(request)` at `ctx.py:326` → `app.py:510` binds the URL map to the request. If binding raises `HTTPException`, it is saved as `request.routing_exception` (`ctx.py:327-329`).

### 2. Push the context and match the URL
4. `AppContext.push()` at `app.py:1599` → `src/flask/ctx.py:416`
   - Increments `_push_count`, then `_cv_app.set(self)` makes `current_app`, `g`, `request` and `session` available (`ctx.py:428-433`).
   - Sends the `appcontext_pushed` signal (`ctx.py:434`).
   - `AppContext._get_session()` at `ctx.py:439` → `ctx.py:381` calls `session_interface.open_session`, falling back to `make_null_session`.
   - `AppContext.match_request()` at `ctx.py:444` → `ctx.py:405` calls `url_adapter.match(return_rule=True)`, then sets `request.url_rule` and `request.view_args`. If matching raises `HTTPException`, it is saved as `request.routing_exception` instead (`ctx.py:409-414`).

### 3. Full dispatch
5. `Flask.full_dispatch_request(ctx)` at `app.py:1600` → `app.py:995`
   - Sets `_got_first_request` and sends the `request_started` signal (`app.py:1013-1016`).
6. **before_request:** `Flask.preprocess_request(ctx)` at `app.py:1017` → `app.py:1369`
   - Runs `url_value_preprocessors` for the app (`None`) and then for each blueprint (`app.py:1382-1385`).
   - Runs each `before_request_funcs` entry through `ensure_sync` (`app.py:1387-1393`; `ensure_sync` is at `app.py:1068`).
   - If any of them returns something other than `None`, that value becomes `rv` and the view is skipped.
7. **View dispatch:** `Flask.dispatch_request(ctx)` at `app.py:1019` → `app.py:969`
   - If routing failed earlier, `raise_routing_exception(req)` raises it now (`app.py:981-982` → `app.py:563`).
   - For automatic OPTIONS handling, it returns `make_default_options_response(ctx)` (`app.py:986-990`).
   - Otherwise it calls `ensure_sync(self.view_functions[rule.endpoint])(**view_args)` (`app.py:993`).
   - For class-based views, that function is the `view` closure from `View.as_view` (`src/flask/views.py:106`/`115`), which calls `View.dispatch_request`. `MethodView.dispatch_request` (`views.py:182`) then picks the method handler, falling back from HEAD to GET.
   - If any exception is raised in steps 6–7, `Flask.handle_user_exception(ctx, e)` (`app.py:1021` → `app.py:868`) turns it into `rv`. HTTP errors go through `handle_http_exception` (`app.py:833`).
8. **Build the response:** `Flask.finalize_request(ctx, rv)` at `app.py:1022` → `app.py:1024`
   - `Flask.make_response(rv)` at `app.py:1042` → `app.py:1227` converts the return value (str, dict, tuple, WSGI callable, …) into a `Response` (`src/flask/wrappers.py:222`).
   - **after_request:** `Flask.process_response(ctx, response)` at `app.py:1044` → `app.py:1397`
     - First runs the per-request `ctx._after_request_functions` (`app.py:1410-1411`).
     - Then runs `after_request_funcs` for each blueprint and then the app, each list in reverse registration order (`app.py:1413-1416`).
     - Finally calls `session_interface.save_session(...)` unless the session is a null session (`app.py:1418-1419`).
   - Sends the `request_finished` signal (`app.py:1045`).

### 4. Errors that escape dispatch
- If an exception gets past `full_dispatch_request`, `Flask.handle_exception(ctx, e)` (`app.py:1603` → `app.py:900`) builds a 500 response and records the error for teardown.

### 5. Send the response
9. `response(environ, start_response)` at `app.py:1607`: the Werkzeug `Response` is called as a WSGI app.

### 6. Teardown (the `finally` block, `app.py:1608-1619`)
10. If `werkzeug.debug.preserve_context` is in the environ, it is called with the context (`app.py:1609-1610`).
11. The deprecated `should_ignore_error(error)` hook can clear the error (`app.py:1612-1617`).
12. `AppContext.pop(error)` at `app.py:1619` → `src/flask/ctx.py:446`
    - Checks the context is the active one and decrements `_push_count`; cleanup only runs when the count reaches 0 (`ctx.py:465-484`).
    - `Flask.do_teardown_request(ctx, exc)` at `ctx.py:490` → `app.py:1423` runs `teardown_request_funcs` for blueprints and then the app, in reverse order, and sends the `request_tearing_down` signal.
    - `request.close()` at `ctx.py:493`.
    - `Flask.do_teardown_appcontext(ctx, exc)` at `ctx.py:496` → `app.py:1456` runs `teardown_appcontext_funcs` in reverse and sends the `appcontext_tearing_down` signal.
    - `_cv_app.reset(token)` deactivates the context (`ctx.py:498`), and the `appcontext_popped` signal is sent (`ctx.py:502`).
    - Each teardown step runs inside `_CollectErrors`, so one failing callback doesn't stop the rest. The collected errors are re-raised together at the end with `raise_any` (`ctx.py:504`; `src/flask/helpers.py:654`/`676`).

### Condensed call order
```
Flask.__call__ → wsgi_app
  → request_context → AppContext.from_environ → AppContext.__init__ → create_url_adapter
  → AppContext.push → [appcontext_pushed] → _get_session → match_request
  → full_dispatch_request
      → [request_started] → preprocess_request (url_value_preprocessors, before_request_funcs)
      → dispatch_request → (raise_routing_exception?) → ensure_sync(view_func)(**view_args)
      → (handle_user_exception on error)
      → finalize_request → make_response → process_response (after_request, save_session) → [request_finished]
  → (handle_exception if the error escaped)
  → response(environ, start_response)
  → finally: AppContext.pop → do_teardown_request → request.close → do_teardown_appcontext → [appcontext_popped]
```