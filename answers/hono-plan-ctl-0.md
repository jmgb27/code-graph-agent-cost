Short version: you mostly don't need adapter changes. Per-route 504s already work with the existing middleware (`app.get('/x', timeout(5000), handler)`, `src/middleware/timeout/index.ts:38`). Every adapter goes through `app.fetch` → `#dispatch`, so if the new option turns into that same middleware at registration time, it works in every runtime for free. The real work is the registration code and the type overloads.

## Proposed API

```ts
app.get('/slow', { timeout: 5000 }, handler)
app.on(['GET', 'POST'], '/slow', { timeout: 5000, exception: (c) => new HTTPException(504, …) }, mw, handler)
```

The options object always comes right after the path. It can't be confused with a handler, because handlers are always functions.

## Files and functions to change

### 1. `src/utils/timeout.ts` (new): shared timeout logic
- Move the body of `timeout()` here (`src/middleware/timeout/index.ts:38-58`), along with `defaultTimeoutException` (`:12`) and the `HTTPExceptionFunction` type.
- Export `createTimeoutHandler(duration, exception?)`.
- **Why:** `hono-base.ts` shouldn't import from `middleware/`. It would also bloat `hono/tiny` (`src/preset/tiny.ts`), which extends `HonoBase`.

### 2. `src/middleware/timeout/index.ts`
- `timeout()` (`:38`) becomes a thin wrapper over `createTimeoutHandler`. Its public API and name stay the same, so it still shows up as "timeout" in `inspectRoutes`.

### 3. `src/types.ts`
- **Add `RouteOptions`** near `RouterRoute` (`:57`): `{ timeout?: number; exception?: HTTPException | ((c: Context) => HTTPException) }`.
- **Optionally add `options?: RouteOptions` to `RouterRoute`** (`:57-62`), so `app.routes` and `hono/dev` can see it.
- **`HandlerInterface` (`:127`):** add a `(path, options, ...handlers)` twin for each path overload: `:167`, `:212`, `:274`, `:349`, `:440`, `:541`, `:652`, `:773`, `:904`, `:971`, `:1052` (`app.get(path, ...handlers[])`). The generics and return type stay the same; only the extra `options: RouteOptions` parameter is new. The handler-only overloads (`:134`, `:149`, …) are left alone, because there's no path to attach options to.
- **`OnHandlerInterface` (`:1457`):** the same twin for `:1462`, `:1481`, `:1505`, `:1537`, `:1580`, `:1628`, `:1681`, `:1739`, `:1802`, `:1870`, `:1943`, the `method[]` set `:1960`–`:2441`, and `:2458`.
- **Leave `MiddlewareHandlerInterface` (`:1080`) alone.** `app.use` doesn't get the option.
- **Trade-off:** this roughly doubles about 35 overloads. It's mechanical, but consider generating them. The cheaper alternative is to add only the variadic overloads (`:1052`, `:1943`, `:2441`, `:2458`). That loses RPC schema inference for routes that use options.

### 4. `src/hono-base.ts`
- **Method implementations in the constructor (`:128-143`):** after `this.#path = args1`, check whether `args[0]` is a non-function object. If so, `shift()` it off as `options`. If `options.timeout` is set, register `createTimeoutHandler(options.timeout, options.exception)` first with `this.#addRoute(methodName, this.#path, …, undefined, options)`, then the user handlers.
- **`this.on` (`:146-157`):** the same extraction from `handlers[0]`, and prepend once for each path × method pair.
- **`#addRoute` (`:388-399`):** accept an optional `options` and store it on `r`.
- **`route()` (`:220-234`):** no logic change needed. The injected timeout handler is an ordinary route entry, so it gets copied into the parent app. If you add `RouterRoute.options`, pass `r.options` through at `:232`.
- **`#dispatch` (`:408-468`):** no change needed, but it's worth documenting why it works:
  - A route with a timeout always has at least 2 handlers, so it skips the single-handler fast path (`:432-450`) and goes through `compose` (`:452`).
  - The rejection is caught in `compose.ts:50-56`, which sends it to `errorHandler`. `HTTPException.getResponse()` then produces the 504 (`hono-base.ts:35`).
  - When the handler finishes late, its result is dropped, because `context.finalized` is already true (`compose.ts:67`, `context.ts:433`).

### 5. `src/index.ts:22`
- Export the `RouteOptions` type.

### 6. Adapters: no source changes
All of these end up in `HonoBase.fetch` (`hono-base.ts:486`) or `fire` (`:542`):
- aws-lambda (`src/adapter/aws-lambda/handler.ts:178` for streaming, `:294`)
- lambda-edge (`src/adapter/lambda-edge/handler.ts:146`)
- vercel (`src/adapter/vercel/handler.ts:10`)
- netlify (`src/adapter/netlify/handler.ts:11`)
- cloudflare-pages `handle` (`src/adapter/cloudflare-pages/handler.ts:43`)
- service-worker (`src/adapter/service-worker/handler.ts:33`)
- Bun, Deno and Workers, which call `app.fetch` directly

Things to document:
- `handleMiddleware` in cloudflare-pages (`handler.ts:58`) isn't route-based, so the option doesn't apply there.
- For streamed responses (`streamHandle`, `c.stream`), the timeout only covers the time until the `Response` is returned, not the time spent streaming the body.
- On timeout the handler isn't cancelled; it keeps running in the background.

## Tests to add

- **`src/middleware/timeout/index.test.ts` (`:7`):** the existing cases must still pass after the refactor. That's the regression guard for step 2.
- **`src/hono.test.ts`:** a new `describe('Route timeout option')`, next to `'Middleware with app.HTTP_METHOD'` (`:1247`). Cases:
  - `app.get(path, {timeout}, h)`: 504 when slow, 200 when fast.
  - Works for every entry in `METHODS` plus `app.all`.
  - Multiple handlers: `app.get(path, {timeout}, mw, h)`, where time spent in `mw` counts toward the limit.
  - A custom `exception` (object and function forms).
  - A custom `app.onError` sees an `HTTPException` with status 504.
  - `app.on` with a single method, `method[]` and `path[]`.
  - Routes in `app.route()` sub-apps, with and without a custom sub-app `onError` (covers `hono-base.ts:224-229`).
  - `basePath()` routes.
  - HEAD on a timed GET route (`:414-417`).
  - A late-finishing handler doesn't overwrite the 504.
  - Timers are cleared on success (`vi.useFakeTimers()` plus `vi.getTimerCount() === 0`).
  - The timeout doesn't leak to other routes on the same path with a different method.
  - `app.routes` exposes `options`.
- **`src/types.test.ts`:** `app.get('/a', { timeout: 1 }, (c) => c.json({ ok: true }))` still infers the `/a` schema, including the middleware-plus-validator combinations and `app.on`. `@ts-expect-error` for `app.use('/a', { timeout: 1 }, …)` and for an options object with no path.
- **`src/helper/dev/index.test.ts`:** `inspectRoutes` lists the injected handler as middleware named `timeout`.
- **Adapter unit tests:** one 504 case each in `src/adapter/aws-lambda/handler.test.ts` (both `handle` and `streamHandle`), `lambda-edge/handler.test.ts`, `cloudflare-pages/handler.test.ts`, `vercel/handler.test.ts`, `service-worker/handler.test.ts`, and a new `src/adapter/netlify/handler.test.ts`.
- **Real-runtime tests** (these check that `setTimeout`/`clearTimeout` actually work per runtime): add a slow route with `{ timeout: 10 }` expecting 504 and a fast route expecting 200 to:
  - `runtime-tests/bun/index.test.tsx`
  - `runtime-tests/deno/hono.test.ts`
  - `runtime-tests/node/index.test.ts`
  - `runtime-tests/workerd/index.ts` + `index.test.ts`
  - `runtime-tests/fastly/index.test.ts`