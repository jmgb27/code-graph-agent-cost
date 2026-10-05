## Tracing a Workers request from `app.fetch` to the returned `Response`

### 0. How Workers reaches `app.fetch`
In module syntax (`export default app`), the Workers runtime calls `app.fetch(request, env, ctx)`. Hono doesn't need a special adapter for this.

- `fetch` is an arrow property at `src/hono-base.ts:481-487`. It calls `this.#dispatch(request, rest[1] /* ctx */, rest[0] /* env */, request.method)`.
- For the older service-worker syntax, `fire()` at `src/hono-base.ts:538-544` registers `addEventListener('fetch', …)`. It calls `#dispatch` with the event as the execution context and `env = undefined`.

### 1. The default router
`src/hono.ts:26-33`: the `Hono` constructor calls `super(options)`. It then sets `this.router = options.router ?? new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`. So the default is **SmartRouter**, which tries RegExpRouter first and falls back to TrieRouter.

- `HonoBase` has no router of its own; see the comment at `src/hono-base.ts:115-119`.
- For comparison, `hono/quick` uses `[LinearRouter, TrieRouter]` (`src/preset/quick.ts:20-22`).

Routes are registered by `get`/`post`/`on`/`use` (`src/hono-base.ts:129-171`), which all go through `#addRoute` (`src/hono-base.ts:388-399`). That calls `this.router.add(method, path, [handler, routeMeta])`. `use()` registers under `METHOD_NAME_ALL` (ALL) with path `'*'` if you don't give one (`:160-170`). So middleware and handlers are stored in the router side by side, in registration order.

### 2. `#dispatch` (`src/hono-base.ts:408-468`)
1. **HEAD requests** (`:415-418`) are re-dispatched as GET, and the body is dropped: `new Response(null, getResponse)`.
2. **Path**: `this.getPath(request, { env })` (`:420`). By default this is `getPath`, or `getPathNoStrict` when `strict: false` (`:175`).
3. **Route matching**: `this.router.match(method, path)` (`:421`). The result is an ordered list of `[handler, routeMeta]` entries (middleware plus handlers) and their params.
4. **Context**: a `new Context(...)` is built with `path`, `matchResult`, `env`, `executionCtx` and `notFoundHandler` (`:423-429`; constructor at `src/context.ts:352-361`).

### 3. How SmartRouter picks a router (`src/router/smart-router/router.ts`)
- **`add`** (`:13-19`) only stores `[method, path, handler]` in `#routes`. Nothing is built yet.
- **The first `match`** (`:21-61`) does the selection:
  1. It tries each candidate router in order. For each one it replays every stored route into it with `router.add(...)`, then calls `router.match(method, path)` (`:32-38`).
  2. If that router throws `UnsupportedPathError`, it moves on to the next one (`:40-41`). Any other error is re-thrown.
  3. On success it takes itself out of the path:
     - `this.match = router.match.bind(router)` (`:46`), so later requests call the chosen router directly.
     - It keeps only the winner in `#routers` and sets `#routes = undefined` (`:47-48`). Any later `add` then throws `MESSAGE_MATCHER_IS_ALREADY_BUILT` (`:14-15`).
  4. It renames itself, e.g. `"SmartRouter + RegExpRouter"` (`:58`). If no router works, it throws `'Fatal error'` (`:52-54`).
- **When RegExpRouter gives up**: `#insertPath` turns the trie's `PATH_ERROR` into `UnsupportedPathError` (`src/router/reg-exp-router/router.ts:60-66`). This happens for route patterns RegExpRouter can't compile, and TrieRouter then takes over.
- **RegExpRouter is also lazy**:
  - Its `match` is the shared `match` from `src/router/reg-exp-router/matcher.ts:10-33`.
  - The first call runs `buildAllMatchers()` (`router.ts:131-143`), which calls `#buildMatcher` for each method (`:145-173`) and frees the build caches.
  - It then replaces `this.match` with a closure (`matcher.ts:31`). That closure checks a static-path map first (`:17-20`), then runs one combined regex (`:22-28`). On a miss it returns `[[], emptyParam]` (`:24`).

### 4. How middleware is composed
**Fast path: exactly one handler matched** (`src/hono-base.ts:432-450`)
- `compose` is skipped. The handler is called directly with a `next` that sets `c.res = await this.#notFoundHandler(c)` (`:435-437`).
- A sync throw goes to `#handleError` (`:438-440`). A rejected promise goes there too, via `.catch` (`:448`).
- If the handler returns nothing, the not-found handler runs. For async handlers: `resolved || (c.finalized ? c.res : notFound(c))` (`:446`). For sync handlers: `res ?? notFound(c)` (`:449`).

**General path: zero or several handlers** (`:452-467`)
- `compose(matchResult[0], this.errorHandler, this.#notFoundHandler)` builds the chain. It is Koa-style onion middleware (`src/compose.ts:15-73`):
  - `dispatch(i)` rejects a second `next()` call (`:33-35`). It sets `context.req.routeIndex = i` and calls `handler(context, () => dispatch(i + 1))` (`:42-51`).
  - When the list runs out, it calls the outer `next` if one was passed; otherwise the handler is `undefined` (`:46`).
  - If a handler returns a value and the context isn't finalized yet (or an error was just handled), it is stored with `context.res = res` (`:67-69`). The `res` setter merges headers set earlier and marks `finalized = true` (`src/context.ts:414-434`).
- After the chain finishes, `#dispatch` checks `context.finalized`. If it's still false, it throws `"Context is not finalized. Did you forget to return a Response object or \`await next()\`?"` (`src/hono-base.ts:457-461`). Otherwise it returns `context.res` (`:463`).

### 5. Where the 404 handler runs
The default is `notFoundHandler` at `src/hono-base.ts:31-33`, which returns `c.text('404 Not Found', 404)`. `app.notFound()` overrides it (`:294-297`). It is invoked in three places:
- **Composed path**: in `compose`, when there's no handler at index `i` and the context isn't finalized (`src/compose.ts:61-64`). This covers both "no routes matched" (an empty list goes straight here) and "the last middleware called `next()` without producing a response".
- **Single-handler path**: through the injected `next` (`src/hono-base.ts:436`), or when the handler returns nothing (`:446`, `:449`).
- **Inside Context**: it is also passed into `Context` (`:428`, stored at `src/context.ts:357`) so that `c.notFound()` can use it.

### 6. Where the error handler runs
The default is `errorHandler` at `src/hono-base.ts:35-42`:
- If the error has `getResponse` (an `HTTPException`), it returns that response via `c.newResponse`.
- Otherwise it calls `console.error` and returns `500 Internal Server Error`.

`app.onError()` overrides it (`:274-277`). It runs at two levels:
1. **Inside `compose`, per handler** (`src/compose.ts:52-57`). If a handler throws an `Error`, it sets `context.error = err` and `res = await onError(err, context)`. It marks `isError`, so the error response replaces any response already set (`:67`). This means outer middleware still sees the error response after its `await next()`.
2. **In `#dispatch`, via `#handleError`** (`src/hono-base.ts:401-406`). This is the final safety net: for the single-handler path (`:439`, `:448`), and around the composed promise (`:464-466`), which includes the "not finalized" error. Values that aren't `Error`s are re-thrown to the runtime (`:405`).

Sub-apps mounted with `app.route()` that have their own `onError` are wrapped in `compose([], app.errorHandler)`. That way the sub-app's handler takes precedence over the parent's for those routes (`src/hono-base.ts:224-230`).

### Summary flow
1. The Workers runtime calls `app.fetch(req, env, ctx)` (`hono-base.ts:481`).
2. `#dispatch` (`:408`) turns HEAD into GET and computes the path with `getPath`.
3. `SmartRouter.match` runs (`smart-router/router.ts:21`). On the first request it picks RegExpRouter, or TrieRouter if a route isn't supported, then hands off to that router's `match` for good.
4. A `new Context(...)` is created (`context.ts:352`).
5. There are two branches:
   - **One handler**: it is called directly. The 404 handler covers an empty result, and `#handleError` covers throws.
   - **Otherwise**: `compose(...)` runs (`compose.ts:15`). `onError` runs per handler, `onNotFound` runs at the end of the chain, then the finalized check happens and `#handleError` is the outer catch.
6. The final `Response` (`c.res`) goes back to Workers.