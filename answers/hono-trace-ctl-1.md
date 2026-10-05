Here is the full path of a request, from `app.fetch` to the `Response`.

## 1. Entry: `app.fetch`

On Workers you write `export default app`. The runtime then calls `app.fetch(request, env, ctx)`.

- `src/hono-base.ts:481-487`: `fetch` is an arrow function, so it stays bound to the app. It calls `this.#dispatch(request, rest[1] /*ctx*/, rest[0] /*env*/, request.method)`.
- `src/hono-base.ts:541-542`: `app.fire()` is the older Service Worker style. It goes into the same `#dispatch`.
- `src/adapter/cloudflare-workers/index.ts` only exports `serveStatic`, `upgradeWebSocket` and `getConnInfo`. It does not wrap `fetch`, and it is marked deprecated (lines 5-7).

## 2. Default router

- `src/hono.ts:28-32`: if no `options.router` is passed, the router is `new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`.
- When you register routes, `#addRoute` (`src/hono-base.ts:388-399`) calls `this.router.add(method, path, [handler, routeMeta])`. Both route handlers and `app.use` middleware go through this; `use` also calls `#addRoute` (e.g. `:168`).

## 3. How SmartRouter picks a router (`src/router/smart-router/router.ts`)

- `add` (`:13-19`) only stores `[method, path, handler]` tuples in `#routes`. Once a router has been chosen, `#routes` is undefined and any later `add` throws `MESSAGE_MATCHER_IS_ALREADY_BUILT`.
- The first `match` call (`:21-61`) does the selection. It tries each candidate in order, RegExpRouter first, then TrieRouter:
  - It replays every stored route into the candidate with `router.add(...)` (`:35-37`), then calls `router.match(method, path)` (`:38`).
  - If the candidate throws `UnsupportedPathError`, it moves on to the next one (`:40-41`). Any other error is re-thrown.
  - RegExpRouter throws this when its trie cannot represent a path, for example some ambiguous param/regex combinations. The internal `PATH_ERROR` (`src/router/reg-exp-router/node.ts:81-134`) is converted at `src/router/reg-exp-router/router.ts:64`.
  - The first candidate that succeeds is kept for good. `this.match` is replaced with the winner's bound `match` (`:46`), the router list becomes just that one (`:47`), and the stored routes are dropped (`:48`). Later requests skip SmartRouter entirely.
  - If every candidate fails, it throws `'Fatal error'` (`:52-55`).
  - The name is set to e.g. `"SmartRouter + RegExpRouter"` (`:58`), and the winner is available as `activeRouter` (`:63-69`).

## 4. `#dispatch` (`src/hono-base.ts:408-468`)

1. **HEAD** (`:415-418`): runs the request again as GET and returns `new Response(null, getResponse)`, which drops the body.
2. **Path and match** (`:420-421`): `this.getPath(request, { env })`, then `this.router.match(method, path)`. On the first request this is where SmartRouter makes its choice.
3. **Context** (`:423-429`): a `new Context(...)` is built with the path, `matchResult`, `env`, `executionCtx` and the app's `#notFoundHandler`.
4. **Fast path, exactly one matched handler** (`:432-450`): no `compose` call.
   - The handler is called directly. Its `next` sets `c.res = await this.#notFoundHandler(c)` (`:435-437`).
   - A synchronous throw goes to `#handleError` (`:438-439`).
   - For a Promise result, it resolves to the returned value. If there is none, it uses `c.res` when finalized, otherwise `#notFoundHandler(c)` (`:444-447`). A rejection goes to `#handleError` (`:448`).
   - For a sync result, it uses the value or falls back to `#notFoundHandler(c)` (`:449`).
5. **General path** (`:452-467`):
   - `compose(matchResult[0], this.errorHandler, this.#notFoundHandler)` is run on `c`.
   - If the context still isn't finalized afterwards, it throws `"Context is not finalized…"` (`:457-461`).
   - Otherwise it returns `context.res` (`:463`). Anything that escapes goes to `#handleError` (`:464-466`).

## 5. Middleware composition (`src/compose.ts`)

This is koa-compose style onion ordering, with handlers in the order the router matched them (middleware and routes together).

- `dispatch(i)` (`:32-71`) guards against calling `next()` twice (`:33-36`). It takes `middleware[i][0][0]` and sets `c.req.routeIndex = i` (`:42-44`), then calls `handler(context, () => dispatch(i + 1))` (`:51`).
- Past the end of the array, it uses the outer `next` if one was given (`:46`).
- **404:** if there is no handler left and `context.finalized === false`, it runs `onNotFound(context)` (`:61-64`). This happens when the last middleware calls `next()` and no route produced a response.
- **Error:** if a handler throws an `Error`, it sets `context.error = err` and `res = await onError(err, context)`, then marks `isError` (`:52-56`). Non-`Error` throws are re-thrown (`:58`).
- The result is written to `context.res` only if nothing has finalized the context yet, or if the error handler produced it (`:67-69`). Because of this, a middleware that runs after `await next()` sees the error response in `c.res`. This is also why errors are caught per layer, not only at the top.

## 6. The 404 and error handlers

**Defaults:**
- `notFoundHandler` returns `c.text('404 Not Found', 404)` (`src/hono-base.ts:31-33`).
- `errorHandler` returns `err.getResponse()` for `HTTPException`-like errors. Otherwise it logs with `console.error` and returns `500 Internal Server Error` (`:35-42`).

**Overrides:** `app.notFound(h)` (`:294-295`) and `app.onError(h)` (`:274-275`) replace these. The fields are declared at `:189` and `:191`.

**Where the 404 handler runs:**
- In `compose`, when the chain runs out (`compose.ts:61-64`).
- In the one-handler fast path, via `next` or the fallbacks (`hono-base.ts:436`, `:446`, `:449`).
- When user code calls `c.notFound()` (`src/context.ts:793-796`). This uses the handler passed into the Context at `hono-base.ts:428`.

**Where the error handler runs:**
- Inside `compose` for each throwing layer (`compose.ts:53-56`).
- As the outer safety net `#handleError` (`hono-base.ts:401-406`). It calls `this.errorHandler` for `Error` instances and re-throws anything else.
- For sub-apps mounted with `app.route()` that have their own `onError`, the sub-app's handler is wrapped in `compose([], app.errorHandler)` (`hono-base.ts:224-228`). Errors then get that sub-app's handler first.

## Summary

`fetch` → `#dispatch` → HEAD check → `getPath` → `router.match` (SmartRouter chooses RegExpRouter, or TrieRouter if RegExpRouter throws `UnsupportedPathError`, on the first request and then gets out of the way) → `new Context` → either the single-handler fast path or `compose(handlers, errorHandler, notFoundHandler)` → `context.res`. `#handleError` catches anything that escapes. The resulting `Response` is returned directly to the Workers runtime.