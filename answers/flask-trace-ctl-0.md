This checkout is the Flask 3.2 layout. `RequestContext` has been merged into `AppContext` (`src/flask/ctx.py:286-288`), so a single `AppContext` holds the request, session, `g` and URL adapter.

## Call order

**0. Entry point**
- `Flask.__call__` in `src/flask/app.py:1621` calls `self.wsgi_app(environ, start_response)` (`app.py:1628`).

**1. Build the context (before the push)**
- `Flask.wsgi_app` (`app.py:1569`) first runs `ctx = self.request_context(environ)` (`app.py:1595`).
- `Flask.request_context` (`app.py:1504`) calls `AppContext.from_environ` (`ctx.py:340`).
  - `app.request_class(environ)` creates the `Request` (`ctx.py:346`).
  - `AppContext.__init__` (`ctx.py:300`) creates `g` (`ctx.py:312`) and calls `app.create_url_adapter(request)`.
    - `Flask.create_url_adapter` (`app.py:510`) applies trusted hosts and host checks, then calls `url_map.bind_to_environ(...)` (`app.py:549`).
    - If binding raises an `HTTPException`, it is stored in `request.routing_exception` (`ctx.py:327-329`).

**2. Push the context and match the URL**
- `ctx.push()` (`app.py:1599`) calls `AppContext.push` (`ctx.py:416`), which:
  - sets the contextvar `_cv_app.set(self)` (`ctx.py:433`)
  - sends the `appcontext_pushed` signal (`ctx.py:434`)
  - opens the session with `AppContext._get_session` (`ctx.py:381`), which calls `session_interface.open_session` or falls back to `make_null_session` (`ctx.py:388-391`)
  - matches the URL with `AppContext.match_request` (`ctx.py:405`), which calls `url_adapter.match(return_rule=True)` (`ctx.py:410`). This sets `request.url_rule` and `request.view_args`, or `request.routing_exception` if matching fails.

**3. Dispatch**
- `Flask.full_dispatch_request` (`app.py:995`, called at `app.py:1600`) sets `_got_first_request` (`app.py:1013`), then:
  - sends the `request_started` signal (`app.py:1016`)
  - calls `Flask.preprocess_request` (`app.py:1369`, called at `app.py:1017`):
    - runs `url_value_preprocessors` for the app and then each blueprint (`app.py:1382-1385`)
    - runs `before_request_funcs` through `ensure_sync` (`app.py:1387-1393`). If one returns a value that is not `None`, that value is used as the response and the view is skipped.
  - calls `Flask.dispatch_request` (`app.py:969`, called at `app.py:1019`):
    - if `routing_exception` is set, calls `Flask.raise_routing_exception` (`app.py:563`, called at `app.py:982`), which raises the 404/405/redirect
    - for OPTIONS requests with automatic options, calls `make_default_options_response` (`app.py:1056`, called at `app.py:990`)
    - otherwise runs `self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)`, which calls the view (`app.py:993`)
  - if any of this raises, calls `Flask.handle_user_exception` (`app.py:868`, called at `app.py:1021`). HTTP exceptions go to `handle_http_exception` (`app.py:891`); other exceptions go to the registered error handler, and are re-raised if there is none (`app.py:893-898`).

**4. Finalize the response and run after_request hooks**
- `Flask.finalize_request` (`app.py:1024`, called at `app.py:1022`):
  - calls `Flask.make_response` (`app.py:1227`, called at `app.py:1042`) to turn the return value into a `Response`
  - calls `Flask.process_response` (`app.py:1397`, called at `app.py:1044`):
    - runs the per-request `ctx._after_request_functions` first (from `after_this_request`, `app.py:1410-1411`)
    - runs `after_request_funcs` for each blueprint and then the app, each list in reverse registration order (`app.py:1413-1416`)
    - calls `session_interface.save_session(...)` unless the session is a null session (`app.py:1418-1419`)
  - sends the `request_finished` signal (`app.py:1045`)

**4b. Unhandled-exception path**
- If anything escapes step 3, `Flask.handle_exception` (`app.py:900`, called at `app.py:1603`) runs:
  - sends the `got_request_exception` signal (`app.py:929`)
  - re-raises if propagation is on (`app.py:935-941`)
  - otherwise calls `log_exception` (`app.py:953`), builds an `InternalServerError`, runs any 500 handler, then calls `finalize_request(..., from_error_handler=True)` (`app.py:951`)

**5. Send the response**
- `response(environ, start_response)` is the Werkzeug WSGI response call (`app.py:1607`).

**6. Teardown (in the `finally` block, so it always runs)**
- If the debugger's `preserve_context` hook is present, it is called (`app.py:1609-1610`).
- `should_ignore_error` can clear `error` (`app.py:1612-1617`). It is deprecated (`app.py:1002-1011`).
- `ctx.pop(error)` (`app.py:1619`) calls `AppContext.pop` (`ctx.py:446`). It checks that this is the active context and decrements the push count (`ctx.py:465-484`), then:
  - calls `Flask.do_teardown_request` (`app.py:1423`, called at `ctx.py:490`). This runs `teardown_request_funcs` for each blueprint and then the app, in reverse order (`app.py:1445-1449`), and sends `request_tearing_down` (`app.py:1452`).
  - closes the request with `self._request.close()` (`ctx.py:493`)
  - calls `Flask.do_teardown_appcontext` (`app.py:1456`, called at `ctx.py:496`). This runs `teardown_appcontext_funcs` in reverse (`app.py:1475-1477`) and sends `appcontext_tearing_down` (`app.py:1480`).
  - resets the contextvar with `_cv_app.reset(token)` (`ctx.py:498`)
  - sends the `appcontext_popped` signal (`ctx.py:502`)
  - raises any collected teardown errors together (`ctx.py:504`)

## Condensed chain
```
__call__ → wsgi_app
  → request_context → AppContext.from_environ → AppContext.__init__ → create_url_adapter
  → AppContext.push → _get_session (open_session) → match_request (url_adapter.match)
  → full_dispatch_request
      → [request_started] → preprocess_request (url_value_preprocessors, before_request)
      → dispatch_request (raise_routing_exception? → view_functions[endpoint])
      → (on error) handle_user_exception
      → finalize_request → make_response → process_response (after_this_request, after_request, save_session) → [request_finished]
  → (on unhandled error) handle_exception → log_exception → finalize_request
  → response(environ, start_response)
  → AppContext.pop → do_teardown_request → request.close → do_teardown_appcontext → [appcontext_popped]
```

## Ordering details
- **Session before matching:** the session is opened before URL matching (`ctx.py:437-444`), so custom URL converters can use it.
- **Before-request order:** before-request hooks run app first, then blueprints from outermost to innermost (`names = (None, *reversed(req.blueprints))`, `app.py:1380`).
- **After-request and teardown order:** these run blueprints innermost first, then the app, each list in reverse registration order (`chain(req.blueprints, (None,))`).