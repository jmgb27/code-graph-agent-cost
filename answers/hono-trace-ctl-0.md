Here's the full path from `app.fetch` to the returned Response. One thing up front: nothing in this path is Workers-specific. The Workers module passes the request to `app.fetch`, and the `hono/cloudflare-workers` adapter (`src/adapter/cloudflare-workers/index.ts:10-12`, marked deprecated) only re-exports `serveStatic`, `upgradeWebSocket` and `getConnInfo`.

## 1. Entry: `app.fetch`
- **`src/hono-base.ts:481-486`**: `fetch(request, env, executionCtx)` calls `this.#dispatch(request, rest[1], rest[0], request.method)`. On Workers, `rest[0]` is `env` (the bindings) and `rest[1]` is the `ExecutionContext`.
- The alternative entry for the older Service Worker format is `app.fire()` (`hono-base.ts:541-542`), which calls the same `#dispatch`.

## 2. Default router
- **`src/hono.ts:28-32`**: unless you pass `options.router`, the router is `new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`.
- **Registering routes:** `app.get/post/...` (`hono-base.ts:136-152`) and `app.use` (`hono-base.ts:159-168`, stored under `METHOD_NAME_ALL`) both call `#addRoute` (`hono-base.ts:388-399`). That calls `this.router.add(method, path, [handler, routeMeta])`, so middleware and handlers are stored side by side in the same router.

## 3. How SmartRouter picks a router (`src/router/smart-router/router.ts`)
- **`add` (`:13-19`)** doesn't route anything yet. It just saves `[method, path, handler]` in `#routes`.
- **The first `match` (`:21-61`)** chooses the router:
  - It tries each candidate in order: RegExpRouter first, then TrieRouter (`:32`).
  - For each one, it replays every saved route into it (`:35-37`) and calls `router.match` (`:38`).
  - If the candidate throws `UnsupportedPathError`, it moves on to the next one (`:39-42`). Any other error is re-thrown.
  - RegExpRouter throws this error when a path can't go into its single-regex trie (`src/router/reg-exp-router/router.ts:60-65`, which turns `PATH_ERROR` into `UnsupportedPathError`).
- **After a router succeeds, SmartRouter locks it in:**
  - `this.match = router.match.bind(router)` (`:46`), so later requests skip SmartRouter entirely.
  - `#routers = [router]` and `#routes = undefined` (`:47-48`). From then on, `add` throws `MESSAGE_MATCHER_IS_ALREADY_BUILT` (`:14-15`).
  - It renames itself `"SmartRouter + RegExpRouter"` (or `+ TrieRouter`) (`:58`).
  - If no router accepts the routes, it throws `Fatal error` (`:52-54`).
- **RegExpRouter's own lazy build:** its first `match` builds all matchers and replaces its `match` with a closure (`src/router/reg-exp-router/matcher.ts:10-32`). That closure checks for a static path hit first (`:17-20`), then runs the combined regex (`:22-28`). With no match it returns `[[], emptyParam]`.

## 4. `#dispatch` (`src/hono-base.ts:408-468`)
1. **HEAD requests** (`:415-418`) are dispatched again as GET, and the result is wrapped as `new Response(null, getResponse)`.
2. **Path and match:** `getPath(request, { env })` (`:420`), then `this.router.match(method, path)` (`:421`). The match result is `[[ [handler, routeMeta], params ]..., paramStash]`.
3. **Context:** a new `Context` is built with `path`, `matchResult`, `env`, `executionCtx` and `notFoundHandler` (`:423-429`).
4. **Fast path, exactly one matched handler** (`:432-450`): the handler is called directly, with no `compose`.
   - Its `next` sets `c.res = await this.#notFoundHandler(c)` (`:435-437`).
   - If it throws synchronously, the error goes to `#handleError` (`:438-439`).
   - If it returns a Promise: `.then(resolved || (c.finalized ? c.res : notFound))` and `.catch(#handleError)` (`:442-448`).
   - If it returns a plain value: `res ?? this.#notFoundHandler(c)` (`:449`).
5. **General case** (`:452-467`): `compose(matchResult[0], this.errorHandler, this.#notFoundHandler)`.
   - It awaits the composed chain. If the context still isn't finalized, it throws "Context is not finalized…" (`:457-461`).
   - It returns `context.res` (`:463`). Any error thrown is passed to `#handleError` (`:464-466`).

## 5. Middleware composition (`src/compose.ts`)
It follows the Koa model:
- **`dispatch(i)`** (`:32-71`) rejects repeat calls with `next() called multiple times` (`:33-36`).
- It picks `middleware[i][0][0]` and records `c.req.routeIndex = i` (`:42-44`). Past the end of the array, it uses the outer `next`, if one exists (`:46`).
- It runs `await handler(context, () => dispatch(i + 1))` (`:51`). That is the onion: code after `await next()` runs as the chain unwinds.
- A handler's return value is written to `context.res` only if the context isn't finalized yet, or the value came from `onError` (`:67-69`).
- The `c.res` setter (`src/context.ts:414-434`) merges headers from the earlier response into the new one (keeping all `set-cookie` values, skipping `content-type`) and sets `finalized = true`.

## 6. Where 404 runs
- **Default handler:** `c.text('404 Not Found', 404)` (`hono-base.ts:31-33`). `app.notFound(h)` replaces it (`hono-base.ts:294-295`).
- **It runs in these places:**
  - **`compose.ts:61-64`:** when the chain runs past the last middleware and no outer `next` exists, and `context.finalized === false`. This covers "no route matched" (an empty array, so `dispatch(0)` goes straight here) and "the last middleware called `next()`".
  - **The fast path in `#dispatch`:** in the handler's `next` (`:436`), or when the single handler returns nothing (`:446`, `:449`).
  - **Explicitly**, through `c.notFound()` (`src/context.ts:793-795`).

## 7. Where the error handler runs
- **Default handler** (`hono-base.ts:35-42`): if the error has `getResponse` (an `HTTPException`), it returns that response. Otherwise it logs the error and returns `500 Internal Server Error`. `app.onError(h)` replaces it (`hono-base.ts:274-275`).
- **It runs at two levels:**
  1. **Per step, inside `compose`** (`compose.ts:52-56`): a thrown `Error` sets `context.error`, calls `onError`, and forces its result into `c.res` (`isError`). Outer middleware still unwinds normally, so it sees the error response.
  2. **As a backstop in `#dispatch`**, through `#handleError` (`hono-base.ts:401-406`): this catches errors from the single-handler fast path (`:438-439`, `:448`) and anything that escapes `compose` (`:464-466`), including the "not finalized" error.
  - Values thrown that are not `Error` objects are re-thrown by both levels (`compose.ts:57-58`, `hono-base.ts:405`) and reach the Workers runtime.
- **Mounted sub-apps:** with `app.route()`, a sub-app that has a custom `errorHandler` gets each of its handlers wrapped in its own `compose([], app.errorHandler)` (`hono-base.ts:224-228`), so its own `onError` applies to its routes.

## 8. Return
`#dispatch` returns a `Response`, or a `Promise<Response>`, straight from `app.fetch` to the Workers runtime. The HEAD wrapper from step 1 is the only extra layer, and it removes the body.