Here is the request lifecycle in call order. In this version of Flask a single `AppContext` holds both the app and the request data; there is no separate `RequestContext`.

### 0. Entry
1. **`Flask.__call__`**, `src/flask/app.py:1621`: the WSGI server calls the app, which calls `self.wsgi_app(environ, start_response)` (line 1628).
2. **`Flask.wsgi_app`**, `src/flask/app.py:1569`: runs the whole lifecycle (lines 1595–1619).

### 1. Context creation
3. **`Flask.request_context`**, `src/flask/app.py:1504`, called at line 1595. It calls:
4. **`AppContext.from_environ`**, `src/flask/ctx.py:340`. This builds `app.request_class(environ)` and sets `request.json_module` (lines 346–347), then calls:
5. **`AppContext.__init__`**, `src/flask/ctx.py:300`. It creates `g` (line 312) and calls:
   - **`Flask.create_url_adapter(request)`**, `src/flask/app.py:510` (called at `ctx.py:326`). This binds the URL map to the request. If binding raises an `HTTPException`, it is stored as `request.routing_exception` (lines 327–329).

### 2. Context push, session and URL matching
6. **`AppContext.push`**, `src/flask/ctx.py:416`, called at `app.py:1599`:
   - Sets the context variable with `_cv_app.set(self)` (line 433) and sends the `appcontext_pushed` signal (line 434).
   - **`AppContext._get_session`**, `src/flask/ctx.py:381` (called at line 439), calls `session_interface.open_session(...)`, or `make_null_session` if that returns `None` (lines 388–391).
   - **`AppContext.match_request`**, `src/flask/ctx.py:405` (called at line 444). It runs `url_adapter.match(return_rule=True)` (line 410) and sets `request.url_rule` and `request.view_args` (line 414). If matching raises an `HTTPException`, that is stored as `request.routing_exception` instead (line 412).

The session is opened before URL matching (comment at lines 441–442), so the session is available inside URL converters.

### 3. Full dispatch
7. **`Flask.full_dispatch_request`**, `src/flask/app.py:995`, called at line 1600:
   - Sets `_got_first_request` (line 1013) and sends the `request_started` signal (line 1016).
8. **`Flask.preprocess_request`**, `src/flask/app.py:1369`, called at line 1017. Hook names run in the order app (`None`) first, then blueprints from outermost to innermost (line 1380).
   - `url_value_preprocessors` run first (lines 1382–1385).
   - Then `before_request_funcs`, each through `ensure_sync` (lines 1387–1390). If one returns a non-`None` value, that value is returned straight away and the view is skipped (lines 1392–1393, 1018).
9. **`Flask.dispatch_request`**, `src/flask/app.py:969`, called at line 1019, only if `rv is None`:
   - If `routing_exception` is set, it calls **`raise_routing_exception`** (`app.py:563`, called at line 982).
   - For an `OPTIONS` request on a rule with automatic options, it returns `make_default_options_response` (line 990).
   - Otherwise it calls `self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)` (line 993).
   - For class-based views, that view function is the `view` closure built by `View.as_view`. It calls `current_app.ensure_sync(self.dispatch_request)(**kwargs)` (`src/flask/views.py:110` or `:116`), which reaches the subclass's `View.dispatch_request` (`views.py:78`).
   - If any exception is raised in steps 7–9, **`Flask.handle_user_exception`** (`app.py:868`, called at line 1021) turns it into a return value.

### 4. Response and after_request hooks
10. **`Flask.finalize_request`**, `src/flask/app.py:1024`, called at line 1022:
    - **`Flask.make_response(rv)`**, `app.py:1227` (called at line 1042), converts the view's return value into a `Response`.
11. **`Flask.process_response`**, `src/flask/app.py:1397`, called at line 1044:
    - First, per-request `ctx._after_request_functions` run (these are registered with `after_this_request`) (lines 1410–1411).
    - Then `after_request_funcs` run: innermost blueprint first, then outward, with the app last. Each list runs in reverse registration order (lines 1413–1416).
    - `session_interface.save_session(...)` runs unless the session is a null session (lines 1418–1419).
    - Back in `finalize_request`, the `request_finished` signal is sent (line 1045).
12. If an exception escapes step 7, `wsgi_app` catches it and calls **`Flask.handle_exception`** (`app.py:900`, called at line 1603). That path also ends in `finalize_request(..., from_error_handler=True)`.
13. `wsgi_app` calls `response(environ, start_response)` (`app.py:1607`), which hands the response to the WSGI server.

### 5. Teardown (`finally` block)
14. If the environ contains `werkzeug.debug.preserve_context`, it is called (lines 1609–1610). Then `should_ignore_error` is checked, which is deprecated (lines 1612–1617).
15. **`AppContext.pop(error)`**, `src/flask/ctx.py:446`, called at `app.py:1619`. Cleanup only runs once the push count reaches 0 (lines 483–484). It then calls:
    - **`Flask.do_teardown_request`**, `src/flask/app.py:1423` (called at `ctx.py:490`). Teardown functions run innermost blueprint first, app last, each list in reverse order (lines 1445–1449). Then the `request_tearing_down` signal is sent (line 1452).
    - `request.close()` (`ctx.py:493`).
    - **`Flask.do_teardown_appcontext`**, `src/flask/app.py:1456` (called at `ctx.py:496`). It runs `teardown_appcontext_funcs` in reverse (line 1475), then sends the `appcontext_tearing_down` signal.
    - `_cv_app.reset(token)` (`ctx.py:498`), then the `appcontext_popped` signal (`ctx.py:502`).
    - Errors from all these teardown steps are collected with `_CollectErrors` and raised together at the end (`ctx.py:504`, `app.py:1454`).

### Condensed call chain
```
__call__ → wsgi_app
  → request_context → AppContext.from_environ → AppContext.__init__ → create_url_adapter
  → AppContext.push → _get_session (open_session) → match_request (url_adapter.match)
  → full_dispatch_request
      → [request_started]
      → preprocess_request (url_value_preprocessors, before_request_funcs)
      → dispatch_request → view function (→ View.dispatch_request)
      → (on error) handle_user_exception
      → finalize_request → make_response → process_response (after_request, save_session) → [request_finished]
  → (on unhandled error) handle_exception
  → response(environ, start_response)
  → finally: AppContext.pop → do_teardown_request → request.close → do_teardown_appcontext → [appcontext_popped]
```