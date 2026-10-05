Here's the request path, starting from Cloudflare's call into `app.fetch`.

## 0. Entry point on Workers

With module syntax (`export default app`), the Workers runtime calls `app.fetch(request, env, ctx)` itself. Hono needs no adapter for this.

- `fetch` is defined at `src/hono-base.ts:481-487`. It calls `this.#dispatch(request, rest[1], rest[0], request.method)`, so `env` comes from `rest[0]` and `ctx` from `rest[1]`.
- For the older service-worker syntax, `app.fire()` (`src/hono-base.ts:538-544`) registers `addEventListener('fetch', …)`. It passes the `FetchEvent` as the execution context and leaves `env` undefined.

## 1. Default router

- `new Hono()` from `src/hono.ts:26-33` uses `options.router` if you pass one. Otherwise it builds `new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`.
- The base class leaves `router` unset (`src/hono-base.ts:115-119`). Any `options.router` is also copied onto the instance by `Object.assign` (`src/hono-base.ts:173-174`).
- The other presets use different routers:
  - `hono/quick`: SmartRouter over `[LinearRouter, TrieRouter]` (`src/preset/quick.ts:20-22`).
  - `hono/tiny`: `PatternRouter` only (`src/preset/tiny.ts:18`).

## 2. Registering routes and middleware

- `app.get/post/...`, `app.on` and `app.use` all end up in `#addRoute` (`src/hono-base.ts:127-171`).
- `use` registers under `METHOD_NAME_ALL`, with path `'*'` when you don't give one (`:160-171`).
- `#addRoute` (`src/hono-base.ts:388-399`) calls `this.router.add(method, path, [handler, routeMeta])`.
- Middleware and handlers are stored the same way. Their order in the match result is what makes one run before the other.
- Until the first request, `SmartRouter.add` only buffers routes in `#routes` (`src/router/smart-router/router.ts:13-19`).

## 3. How SmartRouter picks a router (first request only)

`SmartRouter.match` is at `src/router/smart-router/router.ts:21-61`:

1. It tries each candidate in order. The default order is RegExpRouter, then TrieRouter.
2. For each candidate, it replays every buffered route with `router.add(...)` and then calls `router.match(method, path)` (`:32-38`).
3. If the candidate throws `UnsupportedPathError`, it moves on to the next one (`:39-42`). Any other error is re-thrown.
   - RegExpRouter throws this from `#insertPath` when its trie hits a path it can't turn into one regex (`src/router/reg-exp-router/router.ts:60-66`). The error class is defined at `src/router.ts:103`.
4. The first router that succeeds is kept for good (`:46-49`):
   - `this.match = router.match.bind(router)`, so later requests skip SmartRouter entirely.
   - `#routes = undefined`, so any later `add` throws `MESSAGE_MATCHER_IS_ALREADY_BUILT` (`:14-16`).
5. `name` becomes e.g. `"SmartRouter + RegExpRouter"` (`:58`). If no router succeeds, it throws `'Fatal error'` (`:52-55`).

RegExpRouter also compiles lazily:
- Its first `match` runs `buildAllMatchers()`, which builds one regex per method and frees the build data (`src/router/reg-exp-router/router.ts:131-143`).
- It then replaces `this.match` with a closure (`src/router/reg-exp-router/matcher.ts:10-32`). That closure checks a static-path map first, then the regex, and returns `[[], emptyParam]` when nothing matches (`:17-25`).

## 4. `#dispatch`: from match to Context (`src/hono-base.ts:408-468`)

1. **HEAD**: it dispatches again as `GET` and returns `new Response(null, getResponse)`, i.e. the GET response with no body (`:415-418`).
2. `path = this.getPath(request, { env })` (`:420`). This is strict or non-strict depending on the option set at `:175`.
3. `matchResult = this.router.match(method, path)` (`:421`). `matchResult[0]` is the ordered list of `[[handler, routeMeta], params]`, middleware and handlers together.
4. It builds `new Context(request, { path, matchResult, env, executionCtx, notFoundHandler })` (`:423-429`). The constructor is at `src/context.ts:352-361`, and `c.executionCtx` is Cloudflare's `ctx`.

## 5. Middleware composition

**Fast path: exactly one matched handler** (`src/hono-base.ts:431-450`). `compose` is skipped and the handler is called directly.
- Its `next` sets `c.res` to the not-found response (`:435-437`).
- If the handler returns nothing:
  - async handler: returns `c.res` if the context is finalized, otherwise the not-found handler (`:446`);
  - sync handler: not-found handler (`:449`).
- Errors thrown synchronously are caught at `:438-439`, and rejected promises at `:448`. Both go to `#handleError`.

**General path** (`:452-467`). It calls `compose(matchResult[0], this.errorHandler, this.#notFoundHandler)`, which is koa-style (`src/compose.ts:15-73`). Inside `dispatch(i)` (`src/compose.ts:32-71`):
- Calling `next()` twice throws `'next() called multiple times'` (`:33-35`).
- It sets `c.req.routeIndex = i` and calls `handler(c, () => dispatch(i + 1))` (`:42-51`).
- A returned `Response` is written to `context.res` only if the context isn't finalized yet, or if it came from the error handler (`:67-69`).
- Setting `c.res` merges headers that middleware set earlier (except `content-type`) and marks the context finalized (`src/context.ts:414-434`).

After `composed(c)` finishes:
- If the context still isn't finalized, `#dispatch` throws `"Context is not finalized. Did you forget to return a Response object or await next()?"` (`src/hono-base.ts:457-461`). That error then goes to the error handler.
- Otherwise it returns `context.res` (`:463`).

## 6. Where the 404 handler runs

- **Default**: `c.text('404 Not Found', 404)` (`src/hono-base.ts:31-33`), stored in `#notFoundHandler` (`:189`). `app.notFound(h)` replaces it (`:294-297`).
- **When it runs**:
  - In `compose`, when the chain runs out (no handler at index `i`, no outer `next`) and the context isn't finalized (`src/compose.ts:61-64`). This covers both "no route matched" (empty list) and "every middleware called `next()`".
  - On the single-handler fast path (`src/hono-base.ts:436`, `:446`, `:449`).
  - Via `c.notFound()`, which uses the handler passed into the Context. Without one it falls back to an empty `Response` (`src/context.ts:793-796`).

## 7. Where the error handler runs

- **Default** (`src/hono-base.ts:35-42`):
  - If the error has `getResponse()` (e.g. `HTTPException`), it returns that response via `c.newResponse`.
  - Otherwise it runs `console.error` and returns `500 Internal Server Error`.
  - `app.onError(h)` replaces it (`:274-277`). It's stored in `errorHandler` (`:191`).
- **Layer 1, inside `compose`**: every handler call is wrapped in try/catch. On an `Error` it sets `context.error = err` and calls `onError(err, c)`. The result overrides `c.res` even if the context was already finalized (`src/compose.ts:52-60`, `:67`). An outer middleware that awaited `next()` then sees that error response.
- **Layer 2, in `#dispatch`**: whatever escapes goes to `#handleError` (`src/hono-base.ts:401-406`, called at `:439`, `:448`, `:465`). This covers the fast path, the "not finalized" error, and errors thrown by `onError` itself. `Error` instances go to `this.errorHandler`; anything else is re-thrown to the Workers runtime.
- **Sub-apps**: when a sub-app mounted with `app.route()` has its own `onError`, its handlers are wrapped in `compose([], app.errorHandler)` (`src/hono-base.ts:224-230`). Its errors are therefore handled by the sub-app's handler before the parent's.

## Summary

```
Workers runtime → app.fetch(req, env, ctx)            hono-base.ts:481
  → #dispatch (HEAD→GET)                              hono-base.ts:408
    → getPath → router.match                          hono-base.ts:420-421
        SmartRouter: try RegExpRouter → TrieRouter,   smart-router/router.ts:21
        keep the first router that doesn't throw
        UnsupportedPathError
    → new Context(...)                                hono-base.ts:423
    → 1 handler: call directly | else compose(...)    hono-base.ts:432 / compose.ts:15
        chain runs out & not finalized → notFound     compose.ts:62
        handler throws → onError                      compose.ts:52
    → escaped errors → #handleError → errorHandler    hono-base.ts:401
  → Response returned to Workers
```