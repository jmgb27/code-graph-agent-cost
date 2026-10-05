# Plan: per-route request timeout (`504 Gateway Timeout`)

## The main point: no adapter code needs to change

Every runtime adapter hands requests to `app.fetch`, and `app.fetch` calls `#dispatch`:

- `src/hono-base.ts:485-486`: `fetch` → `#dispatch`
- aws-lambda: `src/adapter/aws-lambda/handler.ts:178` (`streamHandle`) and `:294` (`handle`)
- cloudflare-pages: `src/adapter/cloudflare-pages/handler.ts:43`
- lambda-edge: `src/adapter/lambda-edge/handler.ts:146`
- netlify: `src/adapter/netlify/handler.ts:11`
- service-worker: `src/adapter/service-worker/handler.ts:33`
- vercel: `src/adapter/vercel/handler.ts:10`
- Bun, Deno, Cloudflare Workers, Node and Fastly pass `app.fetch` to the runtime directly. The standalone packages in `adapters/*` do the same (e.g. `adapters/lambda-edge/src/handler.ts:128`).

If the timeout is built into the route handler when the route is registered, it works in every runtime, the presets (`hono/quick`, `hono/tiny`) and every router. The only runtime API it needs is `setTimeout`/`clearTimeout`, which all targets have. Clearing the timer in a `finally` block matters on Lambda: it stops a pending timer from keeping the event loop alive (`callbackWaitsForEmptyEventLoop`, `src/adapter/aws-lambda/types.ts:49`).

## Proposed API

```ts
app.get('/slow', { timeout: 5000 }, handler)
app.post('/slow', { timeout: { duration: 5000, exception: (c) => new HTTPException(504, {...}) } }, mw, handler)
app.on(['GET','POST'], '/slow', { timeout: 5000 }, handler)
```

The options object always comes right after `path`. A plain object that isn't a function can't be confused with a handler, so the check at runtime is simple.

## Files and functions to change

### 1. `src/middleware/timeout/index.ts`: shared timeout helper
- Move the logic in `timeout` (`:38-58`) into an exported helper, e.g. `raceWithTimeout(promise, duration, exception, c)`. It should start the timer, run `Promise.race`, and `clearTimeout` in `finally` (same as `:43-56`).
- Change `timeout()` to call that helper with `next()`, so its behaviour stays the same.
- Export `defaultTimeoutException` (`:12`) and `HTTPExceptionFunction` (`:10`) so core code can reuse them.
- Another option is a new `src/utils/timeout.ts` that both the middleware and `hono-base.ts` import. That keeps core from depending on the middleware module. I recommend this one.

### 2. `src/types.ts`: types
- Add `export type RouteOptions = { timeout?: number | { duration: number; exception?: HTTPException | ((c: Context) => HTTPException) } }`.
- `RouterRoute` (`:57-62`): add `options?: RouteOptions` so `inspectRoutes`/`showRoutes` can show it later.
- `HandlerInterface` (`:127-1079`): add overloads with `options: RouteOptions` after `path`. Copy the path-based ones:
  - `path, handler` (`:167`)
  - `path, handler x2…x10` (`:212, 274, 349, 440, 541, 652, 773, 904, 971`)
  - the variadic `path, ...handlers[]` (`:1052`)
  - These are about 10 hand-written overloads. If that's too much, the minimum is `(path, options, handler)` plus the variadic one, but longer chains then lose middleware type inference.
- `OnHandlerInterface` (`:1457`): the same kind of overloads for `app.on(method, path, options, ...handlers)`.
- Leave `MiddlewareHandlerInterface` (`:1080`) alone. `app.use` already has the `timeout()` middleware.

### 3. `src/hono-base.ts`: runtime behaviour
- **Method loop in the constructor** (`:130-143`): when `args1` is a string, check whether `args[0]` is a plain object and not a function. If it is, `shift()` it off as `options`, then pass it to each `#addRoute(methodName, this.#path, handler, undefined, options)` call (`:136`, `:139`). `app.all` is covered too, because `METHOD_NAME_ALL_LOWERCASE` is part of `allMethods` (`:129`).
- **`this.on`** (`:146-157`): same check on `handlers[0]`, then pass `options` to `#addRoute` at `:152`.
- **`#addRoute`** (`:388-399`):
  - Add an `options?: RouteOptions` parameter.
  - If `options?.timeout` is set, wrap the handler: `wrapped = (c, next) => raceWithTimeout(Promise.resolve(handler(c, next)), duration, exception ?? defaultTimeoutException, c)`.
  - Set `(wrapped as any)[COMPOSED_HANDLER] = handler` (the same pattern as `:229`) so `findTargetHandler` (`src/utils/handler.ts:11-13`) and `inspectRoutes` (`src/helper/dev/index.ts:27-37`) still report the original handler's name and whether it's middleware.
  - Store the wrapped handler in the router and in `r.handler`, and store `options` on `r`.
- **`route()`** (`:211-235`): no logic change. It re-registers `r.handler`, which is already wrapped, so sub-app timeouts carry over. Verify that the `COMPOSED_HANDLER` chain still resolves when the sub-app also has a custom `onError`.
- **`#dispatch`** (`:408-468`): no change expected. Verify both paths turn the rejection into a 504:
  - Single handler (`:432-450`): the wrapped handler returns a Promise that rejects with an `HTTPException`. `.catch` → `#handleError` (`:401`) → `errorHandler` (`:35-38`) → `getResponse()` → 504.
  - Multiple handlers: `compose` catches the error and calls `onError` (`src/compose.ts:48-58`).
  - HEAD requests reuse the GET path (`:415-418`), so they get the timeout automatically.

### 4. Docs and exports
- Add JSDoc for the new overloads, plus an example in `HonoOptions`/README if you want one. No new package export is needed unless you choose `src/utils/timeout.ts` and want it public. If you do, add it to `package.json` exports next to `./timeout` (`:221`) and to `jsr.json`.

## Tests to add

**`src/hono.test.ts`**: a new `describe('Route options: timeout')` next to `Routing` (`:406`) or `Multiple handler - async` (`:2268`). Use `vi.useFakeTimers()`.
1. `app.get(path, { timeout: 100 }, slowHandler)` → 504, body `Gateway Timeout` (single-handler path).
2. A handler that finishes within the limit → 200, and the timer is cleared (`vi.getTimerCount() === 0`).
3. Several handlers in one call (`mw, handler`) where the final handler is slow → 504 (compose path).
4. A custom `exception` object and a custom exception function → the custom status/message.
5. A custom `app.onError` receives the `HTTPException` with status 504.
6. `app.post`, `app.all` and `app.on(['GET','POST'], path, { timeout }, h)` all honour it.
7. HEAD on a timed-out GET route → status 504 with no body.
8. `app.route('/api', sub)` and `basePath()` keep the timeout; also a sub-app with its own `onError` (`:224-230` branch).
9. Routes without options behave exactly as before, and a handler that throws synchronously still gets a 500.
10. Run it against every router: RegExpRouter, TrieRouter, LinearRouter, PatternRouter and `hono/quick`. Follow the existing router-parametrised tests.

**`src/types.test.ts`**: type tests that `app.get('/x', { timeout: 1 }, (c) => c.json({ ok: true }))` keeps its schema and client inference. Use `@ts-expect-error` for bad options (e.g. `timeout: '1'`).

**`src/middleware/timeout/index.test.ts`** (`describe('Timeout API')`, `:7`): regression tests showing `timeout()` behaves the same after the refactor.

**`src/helper/dev/index.test.ts`**: `inspectRoutes` shows the original handler name for a route with a timeout.

**Adapter tests** that check the 504 comes back through each adapter's response mapping:
- `src/adapter/aws-lambda/handler.test.ts`: `statusCode: 504` for `handle`, and a `streamHandle` case.
- `src/adapter/lambda-edge/handler.test.ts`: `status: '504'`.
- `src/adapter/cloudflare-pages/handler.test.ts`, `src/adapter/vercel/handler.test.ts`, `src/adapter/service-worker/handler.test.ts`.
- Matching tests under `adapters/*/src/*.test.ts` (e.g. `adapters/vercel/src/handler.test.ts`).

**Runtime tests**, one real-timer case each (e.g. 50 ms timeout against a 200 ms handler), to check timer behaviour in each runtime:
- `runtime-tests/node/index.test.ts`
- `runtime-tests/bun/index.test.tsx`
- `runtime-tests/deno/hono.test.ts`
- `runtime-tests/workerd/index.test.ts` (plus a route in `runtime-tests/workerd/index.ts`)
- `runtime-tests/fastly/index.test.ts`

## Caveat to decide on

Like the existing `timeout()` middleware, this only stops *waiting* for the handler. The handler itself keeps running. If you want work to actually be cancelled, add an `AbortSignal` (e.g. `c.var.timeoutSignal`) in the helper as a follow-up.