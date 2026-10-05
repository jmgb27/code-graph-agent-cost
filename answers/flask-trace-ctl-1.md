Here is the call order for one request. This repo is on the Flask 3.2 design, where a single `AppContext` covers both the app and the request (the old `RequestContext` was merged into it). One consequence is that URL matching happens while the context is being pushed, not during dispatch.

## Call order

**0. Entry point**
- `Flask.__call__` (`src/flask/app.py:1621`) → `self.wsgi_app(environ, start_response)` (`src/flask/app.py:1628`)

**1. Build the context** (`wsgi_app`, `src/flask/app.py:1569`)
- `Flask.request_context(environ)` (`src/flask/app.py:1595` → `src/flask/app.py:1504`)
  - `AppContext.from_environ` (`src/flask/ctx.py:340`) creates `app.request_class(environ)` and sets `request.json_module`.
  - `AppContext.__init__` (`src/flask/ctx.py:300`) creates `g` from `app.app_ctx_globals_class()` (`src/flask/ctx.py:312`).
    - `Flask.create_url_adapter(request)` (`src/flask/ctx.py:326` → `src/flask/app.py:510`) applies `TRUSTED_HOSTS` and `get_host`, then calls `url_map.bind_to_environ(...)` (`src/flask/app.py:549`). If this raises an `HTTPException`, the exception is stored on `request.routing_exception` (`src/flask/ctx.py:327-329`).

**2. Push the context and match the URL**
- `AppContext.push()` (`src/flask/app.py:1599` → `src/flask/ctx.py:416`)
  - `_cv_app.set(self)` (`src/flask/ctx.py:433`) makes `current_app`, `g`, `request` and `session` available.
  - `appcontext_pushed.send(...)` signal (`src/flask/ctx.py:434`)
  - `AppContext._get_session()` (`src/flask/ctx.py:439` → `src/flask/ctx.py:381`) calls `session_interface.open_session`, falling back to `make_null_session` (`src/flask/ctx.py:388-391`).
  - `AppContext.match_request()` (`src/flask/ctx.py:444` → `src/flask/ctx.py:405`) calls `url_adapter.match(return_rule=True)` (`src/flask/ctx.py:410`).
    - On success it sets `request.url_rule` and `request.view_args` (`src/flask/ctx.py:414`).
    - If `match` raises an `HTTPException`, the exception is stored in `request.routing_exception` rather than raised (`src/flask/ctx.py:412`).

**3. Dispatch**
- `Flask.full_dispatch_request(ctx)` (`src/flask/app.py:1600` → `src/flask/app.py:995`)
  - Warns if the deprecated `should_ignore_error` is set, then sets `_got_first_request = True` (`src/flask/app.py:1002-1013`).
  - `request_started.send(...)` signal (`src/flask/app.py:1016`)
  - **before_request stage:** `Flask.preprocess_request(ctx)` (`src/flask/app.py:1017` → `src/flask/app.py:1369`)
    1. Runs the `url_value_preprocessors`: the app's first (`None`), then blueprints in the order of `reversed(req.blueprints)` (`src/flask/app.py:1380-1385`).
    2. Runs the `before_request_funcs` in the same order, each wrapped in `ensure_sync` (`src/flask/app.py:1387-1390`).
    3. If any hook returns something other than `None`, the chain stops and the view is skipped (`src/flask/app.py:1392-1393`, `src/flask/app.py:1018`).
  - **View:** `Flask.dispatch_request(ctx)` (`src/flask/app.py:1019` → `src/flask/app.py:969`)
    - If `req.routing_exception` is set, calls `raise_routing_exception(req)` (`src/flask/app.py:981-982` → `src/flask/app.py:563`). This is where a 404 or 405 from step 2 is actually raised.
    - For an automatic `OPTIONS` request, returns `make_default_options_response(ctx)` (`src/flask/app.py:990` → `src/flask/app.py:1056`).
    - Otherwise calls `self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)` (`src/flask/app.py:993`).
  - If a hook or the view raises: `handle_user_exception(ctx, e)` (`src/flask/app.py:1021` → `src/flask/app.py:868`)
    - An `HTTPException` goes to `handle_http_exception` (`src/flask/app.py:891` → `src/flask/app.py:833`), which uses `_find_error_handler` to pick the registered handler.
    - Any other exception uses `_find_error_handler` (`src/flask/app.py:893`). If no handler is found, it re-raises (`src/flask/app.py:896`).

**4. Finalize (after_request stage)**
- `Flask.finalize_request(ctx, rv)` (`src/flask/app.py:1022` → `src/flask/app.py:1024`)
  - `Flask.make_response(rv)` (`src/flask/app.py:1042` → `src/flask/app.py:1227`) converts the view's return value into a `Response`.
  - `Flask.process_response(ctx, response)` (`src/flask/app.py:1044` → `src/flask/app.py:1397`)
    1. Runs `ctx._after_request_functions`, which come from `after_this_request` (`src/flask/app.py:1410-1411`).
    2. Runs `after_request_funcs` for the blueprints and then the app (`None`), each list in reverse registration order (`src/flask/app.py:1413-1416`).
    3. If the session is not a null session, calls `session_interface.save_session(...)` (`src/flask/app.py:1418-1419`).
  - `request_finished.send(...)` signal (`src/flask/app.py:1045`)

**5. Unhandled-exception path** (only when step 2, 3 or 4 raised)
- `Flask.handle_exception(ctx, e)` (`src/flask/app.py:1603` → `src/flask/app.py:900`)
  - Sends `got_request_exception` (`src/flask/app.py:929`).
  - If exceptions are set to propagate, it re-raises (`src/flask/app.py:935-941`). `PROPAGATE_EXCEPTIONS` defaults to on when testing or debugging.
  - Otherwise: `log_exception` (`src/flask/app.py:943`) → wraps the error in `InternalServerError` → calls the 500 handler if one is registered → `finalize_request(..., from_error_handler=True)` (`src/flask/app.py:951`).

**6. Send the response**
- `response(environ, start_response)` (`src/flask/app.py:1607`) is the Werkzeug `Response` acting as a WSGI app.

**7. Teardown** (in the `finally` block of `wsgi_app`, so it always runs)
- The debugger's `werkzeug.debug.preserve_context` hook runs if present (`src/flask/app.py:1609-1610`).
- The error is cleared if `should_ignore_error(error)` is true (`src/flask/app.py:1612-1617`).
- `AppContext.pop(error)` (`src/flask/app.py:1619` → `src/flask/ctx.py:446`)
  - Checks that this context is the active one, and returns early while nested pushes remain (`src/flask/ctx.py:465-484`).
  - `Flask.do_teardown_request(ctx, exc)` (`src/flask/ctx.py:490` → `src/flask/app.py:1423`)
    - Runs `teardown_request_funcs` for the blueprints and then the app, in reverse order (`src/flask/app.py:1445-1449`).
    - Sends `request_tearing_down` (`src/flask/app.py:1452`).
  - `request.close()` (`src/flask/ctx.py:493`)
  - `Flask.do_teardown_appcontext(ctx, exc)` (`src/flask/ctx.py:496` → `src/flask/app.py:1456`)
    - Runs `teardown_appcontext_funcs` in reverse order (`src/flask/app.py:1475-1477`).
    - Sends `appcontext_tearing_down` (`src/flask/app.py:1480`).
  - `_cv_app.reset(token)` (`src/flask/ctx.py:498`) deactivates the context.
  - `appcontext_popped.send(...)` signal (`src/flask/ctx.py:502`)
  - `collect_errors.raise_any(...)` (`src/flask/ctx.py:504`)
    - Each teardown step runs inside `_CollectErrors`, so one failing callback doesn't stop the rest.
    - The collected errors are raised together at the end.

## Short version
```
__call__ → wsgi_app
  → request_context → AppContext.from_environ → AppContext.__init__ → create_url_adapter
  → AppContext.push → _get_session (open_session) → match_request (url_adapter.match)
  → full_dispatch_request
      → preprocess_request (url_value_preprocessors, before_request_funcs)
      → dispatch_request (raise_routing_exception? → view_functions[endpoint])
      [→ handle_user_exception / handle_http_exception on error]
      → finalize_request → make_response → process_response (after_this_request, after_request_funcs, save_session)
  [→ handle_exception → finalize_request on unhandled error]
  → response(environ, start_response)
  → AppContext.pop → do_teardown_request → request.close → do_teardown_appcontext → appcontext_popped
```