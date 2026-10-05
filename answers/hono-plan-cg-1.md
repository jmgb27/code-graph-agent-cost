I've read the core dispatch, route types and all the adapters, so I have enough for the plan.

# Plan: per-route `timeout` option returning 504

**Summary:** only core files need to change. Every adapter already sends requests through `app.fetch` and then `#dispatch`, and `setTimeout` works in every runtime Hono supports. So if the timeout lives in core, it works in all adapters with no adapter code changes. Adapters only need tests.

## Proposed API

```ts
app.get('/slow', { timeout: 3000 }, handler)
app.post('/slow', { timeout: 3000, exception: (c) => new HTTPException(504, ...) }, mw, handler)
app.on('GET', '/slow', { timeout: 3000 }, handler)
```

- The options object goes directly after the path.
- At runtime it's easy to tell apart: it's a plain object, while handlers are functions.
- **How it works:** it becomes a timeout middleware added in front of the handlers from that call.
  - It goes through `compose()`, so the thrown 504 `HTTPException` reaches the user's `onError` or the default `errorHandler` (`src/hono-base.ts:35-42`, `getResponse()` → 504 "Gateway Timeout").

## Files and functions to change

### 1. `src/middleware/timeout/index.ts`: reuse the existing logic
- `timeout()` (`:38-58`) already races `next()` against a timer that rejects with a 504 `HTTPException` (`defaultTimeoutException`, `:12-14`). The per-route option should reuse it rather than copy it.
- Export `defaultTimeoutException`, or add a tiny exported helper, so core and the middleware share one code path.
- **Bundle size:** importing this into `hono-base.ts` adds a few hundred bytes to every preset (`hono/tiny`, `hono/quick`). If that's a concern, move the core of `timeout()` into `src/utils/timeout.ts` and have both import it.

### 2. `src/types.ts`: types
- **New type:** add `RouteOptions` near `RouterRoute` (`:57-62`):
  ```ts
  export type RouteOptions<E extends Env = any> = {
    timeout?: number
    exception?: HTTPException | ((c: Context<E>) => HTTPException)
  }
  ```
- **Optional:** add `timeout?: number` to `RouterRoute` (`:57`) so `app.routes` and `showRoutes` can show it.
- **`HandlerInterface` (`:127`):** add a `(path, options, ...handlers)` version of every path-first overload:
  - `:167` path, handler
  - `:212` x2, `:274` x3, `:349` x4, `:440` x5, `:541` x6, `:652` x7, `:773` x8, `:904` x9, `:971` x10
  - `:1052` `(path, ...handlers[])`
  - Each copy is identical to the original except for the extra `options: RouteOptions<E>` parameter, so schema inference is unchanged.
  - Don't add options to the handler-only forms (`:134` … `:1043`) or to `(path)` (`:1063`).
- **`OnHandlerInterface` (`:1457`):** do the same for its path-first overloads (the `app.on(method, path, handler…)` family).
- **Leave alone:** `MiddlewareHandlerInterface` (`:1080`, `app.use`). Timeouts for `use` are already covered by `timeout()` middleware.

### 3. `src/hono-base.ts`: runtime
- **Constructor method loop (`:130-143`, `this[method] = (args1, ...args) =>`):**
  - After the path is set (`:133-134`), check whether `args[0]` is a non-null, non-function object.
  - If it is, shift it off and call a new private `#wrapWithOptions(options)`.
  - If `options.timeout` is set, register `timeout(options.timeout, options.exception)` as the first handler for `methodName` and `this.#path` before the loop at `:138-140`.
- **`this.on` (`:146-157`):** same check on `handlers[0]`. Add the timeout handler once per `(p, m)` pair inside the loops at `:147-155`.
- **Validation:** throw at registration time if `timeout` isn't a positive finite number.
- **`#addRoute` (`:388-399`):** optionally accept the `timeout` value and copy it into the `RouterRoute` object `r`.
- **No changes needed:**
  - `#dispatch` (`:408-468`): a route with a timeout always has 2 or more handlers, so it skips the single-handler fast path (`:432-450`) and uses `compose()` (`:452-467`), which already routes errors to `errorHandler`.
  - `route()` (`:221-234`): the timeout handler is an ordinary entry in `app.routes`, so it carries over when an app is mounted, including sub-app `onError`.
  - `mount()` (`:375-384`).

### 4. Adapters: no code changes (verified)
Each one ends up calling `app.fetch`:

| Adapter | Call site |
|---|---|
| aws-lambda | `src/adapter/aws-lambda/handler.ts:178`, `:294` |
| lambda-edge | `src/adapter/lambda-edge/handler.ts:146` (`handle` at `:133`) |
| cloudflare-pages | `src/adapter/cloudflare-pages/handler.ts:43` |
| vercel | `src/adapter/vercel/handler.ts:10` |
| netlify | `src/adapter/netlify/handler.ts:11` |
| service-worker | `src/adapter/service-worker/handler.ts:33` (`handle` at `:22`) |

Cloudflare Workers, Bun and Deno pass `app.fetch` directly.

### 5. Docs
- JSDoc on `RouteOptions` and on the `app.get` overloads.
- Note two limits:
  - The timeout only covers handlers registered in that call. Earlier `app.use` middleware runs outside it.
  - The handler isn't cancelled; it only loses the race. A streaming body that has already been returned isn't timed.

## Tests to add

**`src/hono.test.ts`** (new `describe('Route options - timeout')`):
- `app.get(path, { timeout: 50 }, slowHandler)` returns 504 with body `Gateway Timeout`.
- A fast handler with a timeout returns 200, and the timer is cleared (use `vi.useFakeTimers()` and check `vi.getTimerCount() === 0`).
- It works with multiple handlers: `app.post(path, { timeout }, mw, handler)`.
- A custom `exception` function returns a custom status and message.
- `app.onError` receives the 504 `HTTPException`.
- `app.on(['GET','POST'], ['/a','/b'], { timeout }, h)` applies to every method/path pair.
- `app.route('/api', sub)` where `sub` has a timed route: still returns 504, and the sub-app's `onError` is respected.
- A HEAD request to a timed GET route returns 504 with no body (goes through `#dispatch` `:415-418`).
- Routes without options behave as before, including the single-handler fast path.
- An invalid `timeout` (`-1`, `NaN`, `'1000'`) throws at registration.
- If `app.routes` gets the field: `app.routes[i].timeout` is set.

**`src/types.test.ts`:**
- `app.get('/x', { timeout: 1 }, (c) => c.json({ ok: true }))` still infers the schema, and `hc` client types still work.
- The same with a validator middleware (`validator('query', …)`) before the handler, so input types still flow through.
- `@ts-expect-error` on `{ timeout: 'x' }` and on options placed after a handler.

**`src/middleware/timeout/index.test.ts`:**
- Regression tests for `timeout()` after the shared-helper refactor.

**Adapter unit tests** (one 504 case each, using a `{ timeout: 10 }` route with a slow handler):
- `src/adapter/aws-lambda/handler.test.ts`: `statusCode: 504` for v1, v2 and ALB events.
- `src/adapter/lambda-edge/handler.test.ts`
- `src/adapter/cloudflare-pages/handler.test.ts`
- `src/adapter/service-worker/handler.test.ts`
- `src/adapter/vercel/handler.test.ts` and `src/adapter/netlify/handler.test.ts`
- Bun, Deno and Workers adapter tests, if present under `src/adapter/*`.

**Runtime tests** (check that real timers work in each runtime):
- `runtime-tests/node/index.test.ts`
- `runtime-tests/bun/index.test.tsx`
- `runtime-tests/deno/hono.test.ts`
- `runtime-tests/workerd/index.ts` (add the route) plus `runtime-tests/workerd/index.test.ts`
- `runtime-tests/fastly/index.test.ts`

Each gets one "returns 504 on timeout" case and one "returns 200 when fast" case.

## Recommendation
Build this in core as a middleware added in front of the route's handlers, reusing the existing `timeout()` logic. Don't add timers inside `#dispatch` or the adapters. That keeps the change to three source files (`src/types.ts`, `src/hono-base.ts`, `src/middleware/timeout/index.ts`, or the new `src/utils/timeout.ts`). The biggest effort is the roughly 11 + N duplicated overloads in `src/types.ts`.