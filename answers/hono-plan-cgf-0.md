I have a plan. Nothing was edited.

## Approach

Every adapter ends up calling `app.fetch` → `#dispatch`: aws-lambda `src/adapter/aws-lambda/handler.ts:178,294`, cloudflare-pages `:43`, lambda-edge `:146`, netlify `:11`, service-worker `:33`, vercel `:10`, plus the `adapters/*/src/handler.ts` copies. Bun, Deno and Workers pass `app.fetch` straight through. So the timeout should be applied **when the route is registered**, not in any adapter, and **no adapter file needs to change**. It only relies on `setTimeout`/`clearTimeout`, which every runtime has.

The logic already exists in `timeout()` (`src/middleware/timeout/index.ts:38-58`): it races `next()` against a timer that rejects with `HTTPException(504)`. On the multi-handler path, `compose` catches that error and passes it to `onError` (`src/compose.ts:50-56`). On the single-handler path, `.catch` → `#handleError` does the same (`src/hono-base.ts:448`, `:401`). Both end in the default `errorHandler`, which calls `err.getResponse()` and returns the 504 (`src/hono-base.ts:35-38`).

**Proposed API:** `app.get('/slow', { timeout: 5000 }, handler)` or `{ timeout: { duration, exception } }`, with the options object right after the path.

## Files and functions to change

1. **`src/middleware/timeout/index.ts:38`**: move the race logic into an exported helper, e.g. `withTimeout(handler, duration, exception)`, which returns `(c, next) => Promise.race([handler(c, next), timer])` and clears the timer in `finally`. Keep `timeout()` as a thin wrapper around it so behaviour doesn't change. Set `wrapped[COMPOSED_HANDLER] = handler` (`src/utils/constants.ts:4`) so `inspectRoutes`/`showRoutes` (`src/helper/dev/index.ts:24,34`) still show the original handler's name and middleware flag.
   - Optionally, create an `AbortController`, abort it when the timer fires, and expose it via `c.set('timeoutSignal', …)`. That lets handlers stop their own work. Without it, the handler keeps running after the 504 is sent, because JS can't cancel a promise.

2. **`src/hono-base.ts:130-143`** (the method loop in the constructor that builds `app.get`, `app.post`, …): after the path argument, check whether the next argument is a plain object rather than a function. If it is, treat it as route options and remove it from the handler list. Wrap **only the first handler** of that call with `withTimeout`. Its `next()` leads into the rest of the chain, so one timer covers every handler registered in that call.
   - Wrapping the first handler, rather than inserting a separate middleware route, keeps `app.routes`, `matchedRoutes`, `routePath` (`src/helper/route/index.ts:32,58`) and `c.req.routeIndex`-based params (`src/request.ts:104`) unchanged.
   - It also keeps the single-handler fast path at `src/hono-base.ts:432-449` working: the wrapper still returns a Promise, and a rejection reaches `#handleError`.

3. **`src/hono-base.ts:146-157`** (`this.on = …`): accept the same optional options object before `...handlers`, for consistency.

4. **`src/hono-base.ts:211-235`** (`route()`): no logic change. The wrapped handler is stored in `r.handler`, so a mounted sub-app keeps its timeouts, and a sub-app `onError` still sees the `HTTPException` through the `compose([], app.errorHandler)` wrapper at `:227-228`. This needs a test.

5. **`src/types.ts`**:
   - Add `export type RouteOptions = { timeout?: number | { duration: number; exception?: HTTPException | HTTPExceptionFunction } }` next to `RouterRoute` (`:57`).
   - In `HandlerInterface` (`:127`), add a `(path: P, options: RouteOptions, ...handlers)` overload for each existing `path` overload (`:168` onward, roughly 10 of the ~20 overloads). Adding an optional parameter in the middle isn't possible, so this means duplicating overloads.
   - Do the same in `OnHandlerInterface` (`:1457`).
   - Move `HTTPExceptionFunction` from `src/middleware/timeout/index.ts:10` into a shared place to avoid an import cycle.

6. **`src/hono.ts:16`**, **`src/preset/tiny.ts`** and **`src/preset/quick.ts`**: no change, since they inherit from `HonoBase`. The tests below should confirm this.

7. **Exports**: re-export `RouteOptions` from `src/index.ts` and `hono/types`. `jsr.json:45` and `package.json:221` need no changes, because the `./timeout` entry already exists.

## Tests to add

- **`src/hono.test.ts`**, new `describe('Route options: timeout')` near `describe('Options')` at `:296`:
  - A slow handler returns 504 with body `Gateway Timeout`, and a fast one returns 200.
  - A custom `exception` (instance or function) is used.
  - Works on both paths: a single handler (fast path at `hono-base.ts:432`) and several handlers (the `compose` path).
  - Works with every method (`get`, `post`, `put`, `delete`, `patch`, `options`, `all`, `on`); `HEAD` should also get 504 through the GET reroute at `hono-base.ts:415`.
  - A custom `app.onError` receives the `HTTPException` with status 504.
  - Works after `app.route('/api', sub)` and `basePath()`.
  - Only the route with the option is affected; a middleware registered earlier with `app.use` is not timed.
  - Use fake timers to check the timer is cleared (`vi.getTimerCount() === 0`) after both success and timeout.
  - `routePath(c)`, `c.req.param()` and `showRoutes` output are unchanged.
- **`src/middleware/timeout/index.test.ts`**: add unit tests for `withTimeout`, and keep the existing `timeout()` tests (`:43`, `:57`) passing unchanged as a regression check.
- **`src/types.test.ts`**, under `describe('HandlerInterface')` at `:51`: check that `app.get('/p', { timeout: 1 }, handler)` still infers the `c.req.param()` type, the response type and the schema. Also add a `@ts-expect-error` case for an invalid option.
- **`src/preset/tiny.test.ts`** and **`src/preset/quick.test.ts`**: one 504 case each.
- **Adapter tests**, one slow route each asserting a 504: `src/adapter/aws-lambda/handler.test.ts` (statusCode 504), `lambda-edge/handler.test.ts` (`status: '504'`), `cloudflare-pages/handler.test.ts`, `service-worker/handler.test.ts`, `vercel/handler.test.ts`, `netlify/handler.test.ts`, and the matching `adapters/*/src/handler.test.ts` files.
- **Real-runtime tests**, one case each: `runtime-tests/node/index.test.ts`, `bun/index.test.tsx`, `deno/hono.test.ts`, `workerd/index.test.ts` (plus the route in `workerd/index.ts`), and `fastly/index.test.ts`.

## Caveats to document

- The timeout only covers the time until the handler returns a `Response`. A streaming body (`streamSSE`, etc.) that is still being written afterwards is not limited.
- On timeout, the handler keeps running in the background. The optional abort signal in step 1 lets handlers notice and stop.