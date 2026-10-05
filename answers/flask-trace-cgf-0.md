Here is the path from `Flask.wsgi_app` to the response, in call order. In this version of Flask there is no separate `RequestContext`: a single `AppContext` holds the request, the session and the URL adapter.

### 0. Entry
- `Flask.__call__` → `self.wsgi_app(environ, start_response)` — `src/flask/app.py:1621-1628`
- `Flask.wsgi_app` — `src/flask/app.py:1569`

### 1. Build the context (`wsgi_app`, line 1595)
1. `Flask.request_context(environ)` — `src/flask/app.py:1504` → `AppContext.from_environ(self, environ)` (line 1518)
2. `AppContext.from_environ` — `src/flask/ctx.py:340`. It builds `app.request_class(environ)` and calls `cls(app, request=request)`.
3. `AppContext.__init__` — `src/flask/ctx.py:300`. It creates `g`, then calls `app.create_url_adapter(self._request)` (`ctx.py:326`, defined at `app.py:510`). If binding raises an `HTTPException`, the exception is stored on `request.routing_exception` (`ctx.py:327-329`).

### 2. Push the context and match the URL (`wsgi_app`, line 1599: `ctx.push()`)
4. `AppContext.push` — `src/flask/ctx.py:416`
   - Sets the contextvar `_cv_app.set(self)` (line 433) and sends the `appcontext_pushed` signal (line 434).
   - `AppContext._get_session()` — `ctx.py:381` → `session_interface.open_session(...)`, falling back to `make_null_session` (lines 386-391).
   - `AppContext.match_request()` — `ctx.py:405` → `url_adapter.match(return_rule=True)`. On success it sets `request.url_rule` and `request.view_args`; on `HTTPException` it stores `request.routing_exception` (lines 409-414).

### 3. Full dispatch (`wsgi_app`, line 1600)
5. `Flask.full_dispatch_request(ctx)` — `src/flask/app.py:995`
   - Sets `_got_first_request = True` and sends the `request_started` signal (line 1016).
6. `Flask.preprocess_request(ctx)` — `app.py:1369` (called at line 1017). This is where the before_request hooks run:
   - `url_value_preprocessors` for the app (`None`) and then each blueprint (lines 1382-1385).
   - `before_request_funcs`, each called through `ensure_sync(before_func)()` (lines 1387-1393). If one returns a non-`None` value, that value short-circuits the view.
7. `Flask.dispatch_request(ctx)` — `app.py:969` (line 1019, only if step 6 returned `None`):
   - If `req.routing_exception` is set → `raise_routing_exception(req)` (line 982, defined at `app.py:563`).
   - Automatic OPTIONS → `make_default_options_response(ctx)` (line 990, `app.py:1056`).
   - Otherwise → `ensure_sync(self.view_functions[rule.endpoint])(**view_args)` (line 993; `ensure_sync` is at `app.py:1068`).
   - For class-based views, the registered function is `View.as_view`'s `view` closure (`src/flask/views.py:106` or `:115`). It calls `View.dispatch_request` (`views.py:78`); `MethodView.dispatch_request` (`views.py:182`) picks the method handler by HTTP verb.
   - If steps 6 or 7 raise → `Flask.handle_user_exception(ctx, e)` (`app.py:1021`, defined at `app.py:868`), which goes to `handle_http_exception` (`app.py:833`) for HTTP errors.
8. `Flask.finalize_request(ctx, rv)` — `app.py:1024` (line 1022):
   - `Flask.make_response(rv)` — `app.py:1227` (line 1042) converts the return value into a `Response` (`src/flask/wrappers.py:222`).
9. `Flask.process_response(ctx, response)` — `app.py:1397` (line 1044). This is where the after_request hooks run:
   - Per-request `ctx._after_request_functions` (lines 1410-1411).
   - `after_request_funcs` for the blueprints and then the app, in reverse registration order (lines 1413-1416).
   - `session_interface.save_session(...)` if the session isn't a null session (lines 1418-1419).
   - Back in `finalize_request`, the `request_finished` signal is sent (lines 1045-1047).

   If `full_dispatch_request` itself raises, `wsgi_app` calls `Flask.handle_exception(ctx, e)` (`app.py:1603`, defined at `app.py:900`). That also ends in `finalize_request(..., from_error_handler=True)`.

### 4. Send the response
10. `response(environ, start_response)` — `app.py:1607`. The Werkzeug `Response` WSGI call produces the body iterable.

### 5. Teardown (`finally` block in `wsgi_app`, lines 1608-1619)
- If the debugger set `environ["werkzeug.debug.preserve_context"]`, it is called with `ctx` (line 1610).
- The deprecated `should_ignore_error` hook may clear `error` (lines 1612-1617).
11. `AppContext.pop(error)` — `src/flask/ctx.py:446` (called at `app.py:1619`). It checks that this is the active context, decrements `_push_count`, and runs cleanup only when the count reaches 0 (lines 481-484).
12. `Flask.do_teardown_request(ctx, exc)` — `app.py:1423` (called at `ctx.py:490`):
    - `teardown_request_funcs` for the blueprints and then the app, in reverse order (lines 1445-1449).
    - `request_tearing_down` signal (line 1452).
13. `request.close()` — `ctx.py:493`
14. `Flask.do_teardown_appcontext(ctx, exc)` — `app.py:1456` (called at `ctx.py:496`):
    - `teardown_appcontext_funcs` in reverse order (lines 1475-1477).
    - `appcontext_tearing_down` signal (line 1480).
15. `_cv_app.reset(token)` (`ctx.py:498`), then the `appcontext_popped` signal (`ctx.py:502`).
16. `collect_errors.raise_any(...)` (`ctx.py:504`). Every teardown callback runs even if an earlier one fails; the errors are collected and raised at the end.

### Summary
```
wsgi_app
 ├─ request_context → AppContext.from_environ → AppContext.__init__ → create_url_adapter
 ├─ AppContext.push → _get_session (open_session) → match_request (url_adapter.match)
 ├─ full_dispatch_request
 │   ├─ request_started signal
 │   ├─ preprocess_request   (url_value_preprocessors, before_request_funcs)
 │   ├─ dispatch_request     (raise_routing_exception | OPTIONS | view_functions[endpoint])
 │   ├─ [handle_user_exception on error]
 │   └─ finalize_request → make_response → process_response (after_request, save_session) → request_finished
 ├─ [handle_exception if full_dispatch_request raised]
 ├─ response(environ, start_response)
 └─ finally: AppContext.pop → do_teardown_request → request.close → do_teardown_appcontext → appcontext_popped
```