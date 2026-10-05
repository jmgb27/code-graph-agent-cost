# Plan: per-route `timeout` option returning 504

## Main finding

Hono already has 504 timeout logic in `src/middleware/timeout/index.ts:38-58`. It races `next()` against a timer and rejects with `HTTPException(504)`. All nine adapters go through `app.fetch` → `#dispatch`:

- `src/adapter/aws-lambda/handler.ts:178,294`
- `src/adapter/lambda-edge/handler.ts:146`
- `src/adapter/vercel/handler.ts:10`
- `src/adapter/netlify/handler.ts:11`
- `src/adapter/cloudflare-pages/handler.ts:43`
- `src/adapter/service-worker/handler.ts:33`
- Bun, Deno and Cloudflare Workers call `app.fetch` directly.
- The deprecated `fire()` goes straight into `#dispatch` (`src/hono-base.ts:538-543`).

So the feature can live entirely in route registration in the core. **No adapter files need to change.** Each runtime only needs `setTimeout`/`clearTimeout`, and all of them have both.

## Proposed API

```ts
app.get('/slow', { timeout: 5000 }, handler)
app.post('/slow', { timeout: 5000, onTimeout: (c) => new HTTPException(504, …) }, mw, handler)
app.on(['GET','POST'], '/slow', { timeout: 5000 }, handler)
```

- The options object comes **right after the path**. It must be a plain object, not a function, so the runtime can tell it apart from handlers without any ambiguity.
- `app.use` is left out: `timeout()` middleware already covers that case.
- At runtime, one timeout middleware is registered for that method and path, **before** the route's handlers. One timer then covers the whole handler chain for that route; wrapping each handler separately would give each one its own timer.
- Middleware registered earlier with `app.use` runs outside the timer. The option measures "the handler exceeds it", not the whole request.

## Files and functions to change

| # | File:line | Change |
|---|---|---|
| 1 | **new** `src/utils/timeout.ts` | Move the race logic out of `timeout()` into `createTimeoutHandler(duration, exception)`, which returns a `MiddlewareHandler` named `timeout`. The core then doesn't import a middleware module, and `hono/tiny` and `hono/quick` get the same code. |
| 2 | `src/middleware/timeout/index.ts:38-58` | Make `timeout()` a thin wrapper around `createTimeoutHandler`. Move `defaultTimeoutException` (`:11-13`) into the util and re-export it. The public API stays the same. |
| 3 | `src/types.ts:57-62` (near `RouterRoute`) | Add `export interface RouteOptions<E extends Env = any> { timeout?: number; onTimeout?: HTTPException \| ((c: Context<E>) => HTTPException) }`. |
| 4 | `src/types.ts:127-1072` `HandlerInterface` | Add a `(path, options: RouteOptions<E>, ...handlers)` overload for each path-based overload: `:167` (x1), `:212`, `:274`, `:349`, `:440`, `:541`, `:652`, `:773`, `:904`, `:971` (x10), and the rest form at `:1052`. Each one copies the matching overload's generics and return type, so the `ToSchema` output and RPC inference (`hc`) stay the same. |
| 5 | `src/types.ts:1457+` `OnHandlerInterface` | Same idea for `(method, path, options, ...handlers)`: mirror the overloads starting at `:1462`, `:1481`, `:1505`, `:1537`, … plus the rest form. |
| 6 | `src/hono-base.ts:129-143` (method closure in `constructor`) | After `this.#path = args1`, if `isRouteOptions(args[0])`, call `args.shift()`. If `options.timeout` is set, call `this.#addRoute(methodName, this.#path, createTimeoutHandler(...))` before the `args.forEach`. Change the closure signature to `(args1: string \| H, ...args: (H \| RouteOptions)[])`. |
| 7 | `src/hono-base.ts:146-157` `this.on` | Same detection on `handlers[0]`, and register the timeout handler once for each `(p, m)` pair. |
| 8 | `src/hono-base.ts` (module scope, near `:31`) | Add `const isRouteOptions = (v: unknown): v is RouteOptions => typeof v === 'object' && v !== null`. Also validate `timeout`: it must be a finite number > 0, otherwise throw at registration time. |
| 9 | `src/index.ts:22` | Add `RouteOptions` to the exported types. |
| 10 | `src/hono-base.ts:388-399` `#addRoute`, `:218-235` `route()`, `:408-470` `#dispatch` | **No change, but check these.** The timeout handler is a normal route entry, so `route()` copies it into sub-apps and wraps it with the sub-app's `onError`. The fast path at `:432` for a route with one handler is skipped automatically because the route now has two handlers. `HEAD` → `GET` (`:415-418`) inherits the timeout. The `HTTPException` becomes a 504 through `errorHandler` (`:35-42`) or the user's `onError`. |
| 11 | `src/helper/dev/index.ts:24-34` | **No change.** The handler is named `timeout` and has arity 2, so `isMiddleware` (`src/utils/handler.ts:8`) marks it as middleware, and `inspectRoutes` hides it unless `verbose` is set. |
| 12 | `package.json` / `jsr.json` | **No change.** `./timeout` stays exported (`package.json:221`, `jsr.json:45`), and the new util is internal. |

## Tests to add

**`src/hono.test.ts`**: add a new `describe('Route options: timeout')` block, for example after `'Options'` at `:296`:
- `app.get('/slow', { timeout: 50 }, async c => { await sleep(100); return c.text('x') })` → 504, body `Gateway Timeout`.
- A fast handler under the same option → 200, and the timer is cleared (spy on `clearTimeout` or use `vi.useFakeTimers`).
- A custom `onTimeout` → a custom status and message.
- A custom `app.onError` receives an `HTTPException` with status 504.
- `app.post`, `app.all`, and `app.on(['GET','POST'], path, opts, h)` all apply the timeout; `on` with several paths applies it to every path.
- The timeout covers the whole chain `(path, opts, mw, handler)`: slow middleware also triggers a 504.
- Global `app.use` middleware registered earlier runs outside the timer and still sees `c.res.status === 504` after `next()`.
- The timeout only applies to its own method and path: `GET /slow` has a timeout, `POST /slow` without one doesn't.
- `HEAD /slow` → 504 with a null body.
- Timeout plus sub-app: `sub.get('/x', {timeout}, h); app.route('/api', sub)` → 504; this also checks the sub-app `onError` wrapping at `:224-230`.
- `basePath` plus options → 504.
- Chained calls: `app.get('/a', {timeout:10}, h).get('/b', h2)`, where `/b` has no timeout. This guards against `#path` or state leaking between calls.
- Invalid options (`{ timeout: -1 }`, `NaN`) throw at registration.
- Existing behavior is unchanged: `app.get('/p', h)` still uses the single-handler fast path.

**`src/types.test.ts`**:
- `app.get('/p', { timeout: 1 }, validator(...), h)` gives the same `ToSchema` as the call without options.
- `hc` (RPC) infers the same input and output types.
- `@ts-expect-error` on `{ timeout: 'x' }`.
- `app.on` with options infers correctly.

**`src/middleware/timeout/index.test.ts`**: the existing cases at `:43-64` must still pass after the refactor. Add one case that imports `createTimeoutHandler` directly.

**`src/helper/dev/index.test.ts`**: `inspectRoutes` hides the timeout entry by default and shows it as `timeout` / `isMiddleware: true` with `verbose`.

**Adapter unit tests**: one 504 case in each, to prove the status passes through each adapter's response conversion:
- `src/adapter/aws-lambda/handler.test.ts`
- `src/adapter/lambda-edge/handler.test.ts`
- `src/adapter/service-worker/handler.test.ts`
- `src/adapter/cloudflare-pages/handler.test.ts`
- `src/adapter/vercel/handler.test.ts`
- `src/adapter/netlify/handler.test.ts`
- `src/adapter/bun`, `deno` and `cloudflare-workers` tests, if present

**Runtime tests**: one `app.get('/slow', { timeout: 50 }, …)` → 504 case in each of these, to check real `setTimeout` behavior in each engine:
- `runtime-tests/node/index.test.ts`
- `runtime-tests/bun/index.test.tsx`
- `runtime-tests/deno/hono.test.ts`
- `runtime-tests/workerd/index.test.ts` (with the route in `runtime-tests/workerd/index.ts`)
- `runtime-tests/fastly/index.test.ts`

## Caveats to decide before implementing

1. **The handler isn't cancelled.** As in today's `timeout()`, the handler keeps running after the 504 is sent. A possible follow-up is an `AbortSignal`, for example exposed as `c.var.timeoutSignal`, so handlers can stop early.
2. **Streaming responses.** The timeout covers the time until a `Response` is returned, not the time to stream the body. `streamSSE` and `stream` return right away, so they are never affected.
3. **Size of the overloads.** The typing adds about 11 overloads to `HandlerInterface` and a few to `OnHandlerInterface`. That is the main cost and the main risk for type-check performance, so run `tsc` benchmarks on `src/types.test.ts` before and after.