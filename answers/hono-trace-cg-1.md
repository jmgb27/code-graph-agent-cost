Here's the path a request takes, starting from `export default app` in a Worker and ending with the Response it returns.

## 1. Entry: `app.fetch`
- On Workers (module syntax) the runtime calls `app.fetch(request, env, ctx)`. `fetch` is defined at `src/hono-base.ts:481-487` and calls `this.#dispatch(request, rest[1], rest[0], request.method)`. So `env` becomes the bindings and `ctx` becomes `executionCtx`.
- The older service-worker syntax uses `app.fire()` instead, which registers `addEventListener('fetch', …)` and calls `#dispatch` with the event as the execution context (`src/hono-base.ts:541-542`).
- `src/adapter/cloudflare-workers/index.ts` only re-exports helpers (`serveStatic`, `upgradeWebSocket`, `getConnInfo`) and is deprecated. It plays no part in dispatch.

## 2. Default router
- `src/hono.ts:28-32`: if `options.router` isn't given, the app uses `new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`.
- Registering a route (`app.get`, `app.use`, etc.) goes through `#addRoute` (`src/hono-base.ts:388-399`), which calls `this.router.add(method, path, [handler, routeMeta])`.

## 3. How SmartRouter picks a router (`src/router/smart-router/router.ts`)
- `add()` (`:13-19`) only buffers `[method, path, handler]` into `#routes`. No router is built yet.
- The first `match()` call (`:21-61`) tries each candidate in order:
  - It replays every buffered route into that router (`:35-37`), then calls `router.match` (`:38`).
  - If the router throws `UnsupportedPathError`, it moves on to the next one (`:39-43`). RegExpRouter throws this when a path can't go into its trie (`src/router/reg-exp-router/router.ts:64`). Any other error is re-thrown.
  - On the first success, it replaces its own `match` with the winner's bound `match` (`:46`), keeps only that router (`:47`), and sets `#routes = undefined` (`:48`).
- In practice RegExpRouter wins unless a path is unsupported, in which case TrieRouter is used.
- From then on, `match` calls go straight to the chosen router. Any later `add()` throws `MESSAGE_MATCHER_IS_ALREADY_BUILT` (`:14-16`).
- `name` becomes e.g. `"SmartRouter + RegExpRouter"` (`:58`), and `activeRouter` exposes the winner (`:63-69`).

## 4. `#dispatch` (`src/hono-base.ts:408-466`)
1. **HEAD requests** are dispatched as GET, and the result is returned with a null body (`:415-418`).
2. **Path:** `this.getPath(request, { env })` (`:420`). The default is `getPath` in `src/utils/url.ts:106`, or `getPathNoStrict` when `strict: false` (`src/hono-base.ts:175`).
3. **Match:** `this.router.match(method, path)` (`:421`). The first request triggers SmartRouter's selection from section 3.
4. **Context:** `new Context(request, { path, matchResult, env, executionCtx, notFoundHandler })` (`:423-429`).
5. **Fast path, exactly one matched handler** (`:432-450`): the handler is called directly, with no `compose`.
   - Its `next` sets `c.res` to the not-found handler's result (`:435-437`).
   - A sync throw goes to `#handleError` (`:438-440`).
   - For a Promise result: if it resolves to `undefined`, the code returns `c.res` if the context is finalized, otherwise the not-found handler runs (`:446`). A rejection goes to `#handleError` (`:448`).
   - For a sync `undefined` result, the not-found handler runs (`:449`).
6. **General path, 0 or 2+ handlers** (`:452-465`):
   - Builds `compose(matchResult[0], this.errorHandler, this.#notFoundHandler)` and awaits it.
   - If the context still isn't finalized, it throws "Context is not finalized. Did you forget to return a Response object or `await next()`?" (`:457-461`).
   - Otherwise it returns `context.res` (`:463`). The surrounding `catch` sends errors to `#handleError` (`:464-465`).

## 5. How middleware is composed (`src/compose.ts`)
It's the koa-compose pattern. `dispatch(i)` (`:32-71`) works like this:
- Calling `next()` twice from the same middleware throws "next() called multiple times" (`:33-36`).
- It takes `middleware[i][0][0]` as the handler and sets `c.req.routeIndex = i` (`:42-44`).
- It calls `handler(context, () => dispatch(i + 1))` (`:51`). Each middleware's `await next()` runs the rest of the chain, then control comes back to it (the "onion" model).
- If a handler returns a value, it's written to `context.res` only when the context isn't finalized yet, or when the value came from the error handler (`:67-69`).
- The `c.res` setter (`src/context.ts:414-434`) copies headers already set on the previous response (Set-Cookie is carried over separately; Content-Type is not copied) and sets `finalized = true`.

## 6. Where the 404 handler runs
The default handler is `c.text('404 Not Found', 404)` (`src/hono-base.ts:31-33`), and `app.notFound()` replaces it (`:295`). It runs in these places:
- **Nothing matched, or the chain ran past the last handler** without a response: `compose.ts:61-64` calls `onNotFound` if `context.finalized === false`. With zero matches `matchResult[0]` is empty, so `dispatch(0)` goes straight to this branch.
- **Fast path:** at `hono-base.ts:436` (`next()` called from a single handler), `:446` (Promise resolved to `undefined` and not finalized) and `:449` (sync `undefined`).
- **Explicitly:** `c.notFound()` at `src/context.ts:793-796`.

## 7. Where the error handler runs
The default handler returns `err.getResponse()` for errors that have it (e.g. `HTTPException`); otherwise it logs with `console.error` and returns a 500 (`src/hono-base.ts:35-43`). `app.onError()` replaces it (`:275`). It runs in two places:
- **Inside the chain:** `compose.ts:52-56`. If a middleware throws an `Error`, it sets `c.error`, calls `onError`, and marks `isError` so the error response overwrites any `c.res` that was already set. Because each `dispatch` level catches its own errors, an outer middleware sees `next()` resolve normally and can then inspect `c.error`/`c.res`. Non-`Error` throws are re-thrown (`:57-59`).
- **Outside the chain:** `#handleError` (`hono-base.ts:401-406`) calls `this.errorHandler` for `Error` instances and re-throws anything else. It's used on the fast path (`:439`, `:448`), for the "not finalized" error, and for anything that escapes `compose` (`:464-465`).

For mounted sub-apps that keep the default error handler, `route()` wraps each of their handlers in a `compose([], app.errorHandler)` call (`hono-base.ts:224-228`), so their errors are handled by the parent's handler.

## Summary
`fetch` → `#dispatch` → `getPath` → `SmartRouter.match` (on the first call it locks in RegExpRouter, or TrieRouter if RegExpRouter can't handle a path) → `new Context`. Then either the single handler is called directly, or the handlers go through `compose`, with 404 and error handling applied at the points above. The result is `context.res`, or the handler's return value on the fast path.