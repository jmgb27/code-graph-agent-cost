The timeout fits into one layer, `HonoBase#addRoute` / `#dispatch`, and every adapter already goes through that. So the runtime change is confined to `src/hono-base.ts` plus a small shared helper, and no adapter source files need to change. Most of the work is in the type overloads.

## Proposed API

```ts
app.get('/slow', { timeout: 5000 }, handler)            // path, then options, then handlers
app.on(['GET', 'POST'], '/slow', { timeout: 5000 }, mw, handler)
```

- Only the "path first" forms get options. The pathless form `app.get(handler)` reuses the last path, and adding options there would double the overloads for little benefit.
- When the timeout fires, it throws `new HTTPException(504, { message: 'Gateway Timeout' })`. The default error handler turns that into a 504 (`src/hono-base.ts:35-38`), and a custom `onError` receives it like any other `HTTPException`.

## How it works at runtime

- **Existing machinery to reuse:** `compose` already turns a thrown error into `onError` output (`src/compose.ts:50-59`). The single-handler fast path already sends rejections to `#handleError` (`src/hono-base.ts:442-448`). So wrapping the handler in a "race against a timer" function is enough; neither `compose.ts` nor `#dispatch` needs to change.
- **Only the first handler of each registration is wrapped.** Middleware in the same call runs inside it through `next()`, so one timer covers the whole chain for that call.
- **The route table keeps the original handler.** Only the function passed to `router.add` is wrapped. This matters because `method-not-allowed` compares `route.handler === methodNotAllowed` (`src/middleware/method-not-allowed/index.ts:106`), and `route()` re-registers `r.handler` (`src/hono-base.ts:222-233`).

## Files and functions to change

### 1. `src/types.ts`
- **Near `RouterRoute` (`:57-62`):** add `export type RouteOptions = { timeout?: number }` and an optional `options?: RouteOptions` field on `RouterRoute`. Sub-app mounting uses this field to carry the timeout over.
- **`HandlerInterface` (`:127-1078`):** add a parallel overload for each "path" form, taking `(path: P, options: RouteOptions, ...handlers)`. The forms to mirror are at `:167` (1 handler), `:212` (2), `:274` (3), `:349` (4), `:440` (5), `:541` (6), `:652` (7), `:773` (8), `:904` (9), `:971` (10) and `:1052` (`...handlers[]`). The generics and return types stay identical, so schema and `hc` client inference are unchanged.
- **`OnHandlerInterface` (`:1457+`):** the same for the `app.on(method, path, …)` overloads at `:1462`, `:1481`, `:1505`, `:1537`, `:1580`, `:1628`, `:1681`, `:1739`, `:1802` and `:1870`, plus its `...handlers[]` variant.
- `MiddlewareHandlerInterface` (`:1080`) does not change, because `app.use` has no timeout option.

### 2. New `src/utils/timeout.ts`
Add `withTimeout(handler: H, ms: number, exception?: HTTPException | ((c) => HTTPException)): MiddlewareHandler`. It should:
- Be declared as `async (c, next)` so it has arity 2, and set `wrapped[COMPOSED_HANDLER] = handler`. This lets `findTargetHandler` (`src/utils/handler.ts:9-15`) keep `inspectRoutes`/`showRoutes` (`src/helper/dev/index.ts:29-34`) and SSG (`src/helper/ssg/utils.ts:70-71`) reporting the real handler.
- Run `Promise.race([Promise.resolve().then(() => handler(c, guardedNext)), timer])` and return the handler's resolved value. The fast path needs that value (`src/hono-base.ts:445-446`).
- Call `clearTimeout` in `finally`. A leaked timer can keep Lambda's event loop open (`callbackWaitsForEmptyEventLoop`) and holds Workers/Deno resources. Use the same `as unknown as number` cast as the existing middleware (`src/middleware/timeout/index.ts:44-48`) to cover the Node, Bun and Deno timer typings.
- Pass a guarded `next`: once the timeout has fired, calling `next()` does nothing. Otherwise a slow handler that calls `next()` later would still run downstream handlers after the 504 was sent (`compose`'s `i <= index` check at `src/compose.ts:33` doesn't prevent this).

### 3. `src/middleware/timeout/index.ts:38-62` (optional but recommended)
Rewrite `timeout()` to use the shared race-and-clear logic from `utils/timeout.ts`, so there is one implementation. Its public behaviour stays the same.

### 4. `src/hono-base.ts`
- **Imports (`:12-29`):** add `RouteOptions`, `withTimeout` and `HTTPException`.
- **Method closure (`:131-142`):** when `args1` is a string and `args[0]` is a plain object (not a function), `shift()` it off as `options`. Pass `options` to the first `#addRoute` call only. Allow only this position for options, so a later object isn't mistaken for a handler.
- **`this.on` (`:146-157`):** the same detection on `handlers[0]`. For each method × path combination, pass `options` to the first handler's `#addRoute`.
- **`#addRoute` (`:388-399`):** new signature `#addRoute(method, path, handler, baseRoutePath?, options?)`. Store `options` on `r`. Call `this.router.add(method, path, [options?.timeout ? withTimeout(handler, options.timeout) : handler, r])` and leave `r.handler` as the original handler.
- **`route()` (`:222-233`):**
  - Default error handler: pass `r.options` through, i.e. `subApp.#addRoute(r.method, r.path, handler, r.basePath, r.options)`.
  - Custom sub-app `onError`: apply `withTimeout` inside the compose closure, before the handler call on `:228`. That way the 504 goes to the sub-app's `onError`, not the parent's. In this branch, don't pass `r.options` to `#addRoute`, or the route would get two timers.
- **`#clone()` (`:178-187`), `mount()` (`:375-384`) and `#dispatch()` (`:408-468`):** no change. HEAD (`:415-418`) re-dispatches as GET, so it inherits the timeout.

### 5. Adapters: no code changes
Every adapter hands requests to `app.fetch` and from there to `#dispatch`:
- `aws-lambda/handler.ts:178` and `:294`
- `lambda-edge/handler.ts:146`
- `cloudflare-pages/handler.ts:43`
- `netlify/handler.ts:11`
- `vercel/handler.ts:10`
- `service-worker/handler.ts:33`
- Bun, Deno and Workers call `app.fetch` directly

Three limitations to document (JSDoc in `types.ts`):
- **No interruption of CPU-bound code.** The timeout only interrupts awaited async work; a synchronous CPU-bound handler can't be pre-empted on any single-threaded runtime.
- **Platform limits come first.** The Lambda function timeout and the Lambda@Edge/Workers limits kill the request before a longer route timeout would fire.
- **Streaming bodies aren't covered.** The timeout measures time until a `Response` is returned, not time spent streaming the body.

## Tests to add

**`src/hono.test.ts`**: a new `describe('Route timeout option')` near `'Error handle'` (`:1422`), using `vi.useFakeTimers()`. Cases:
- Async handler slower than the timeout → 504 with body `Gateway Timeout`. Faster handler → 200.
- Single-handler fast path and multi-handler path (`mw, handler`) both work.
- Global `app.use` middleware still runs after `next()` and sees `c.res.status === 504`.
- Other routes aren't affected.
- `app.all`, `app.on` with a method array and a path array, and a HEAD request to a GET route that has a timeout.
- Custom `app.onError` receives an `HTTPException` with `status === 504`.
- `vi.getTimerCount() === 0` after success, after the timeout, and after the handler throws (which should still give 500).
- A handler that calls `next()` after the timeout doesn't run downstream handlers.
- `app.routes[i].handler` is the original function.
- `app.route('/api', sub)` keeps the timeout, both with the default error handler and with a sub-app `onError` (which must be the one that handles the 504).
- `basePath()` keeps the timeout.

**Other unit tests:**
- `src/types.test.ts`: `app.get('/x', { timeout: 1 }, (c) => c.json({ ok: true }))` produces the same `ExtractSchema` as without options. Add the same check with validator middleware in front and for `app.on`.
- `src/client/client.test.ts`: `hc` infers response types for a route registered with options.
- `src/helper/dev/index.test.ts`: `inspectRoutes` reports the original handler name and `isMiddleware: false` for a timed handler.
- New `src/utils/timeout.test.ts`: resolve, reject, timeout, `clearTimeout` called, guarded `next`.
- `src/middleware/timeout/index.test.ts`: existing tests must still pass after the refactor.

**Adapter tests** (one "exceeds → 504, under → 200" case each, with real short timers such as a 10 ms timeout against a 50 ms sleep):
- `src/adapter/aws-lambda/handler.test.ts`, covering both `handle` and `streamHandle`
- `src/adapter/lambda-edge/handler.test.ts`
- `src/adapter/cloudflare-pages/handler.test.ts`
- `src/adapter/vercel/handler.test.ts`
- `src/adapter/service-worker/handler.test.ts`
- New `src/adapter/netlify/handler.test.ts` (none exists today)

**Runtime tests:**
- `runtime-tests/node/index.test.ts`
- `runtime-tests/bun/index.test.tsx`
- `runtime-tests/deno/hono.test.ts`
- `runtime-tests/workerd/index.ts` (add the route) and `runtime-tests/workerd/index.test.ts`
- `runtime-tests/fastly/index.test.ts`