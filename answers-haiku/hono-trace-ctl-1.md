Here's the trace of a Cloudflare Workers request through Hono:

## Entry Point: app.fetch()

**hono-base.ts:481-487** — The `.fetch()` method is the entry point. It calls the private `#dispatch()` method, passing the request, environment, and execution context.

## Dispatch Flow

**hono-base.ts:408-468** — `#dispatch()` handles the routing:
- Line 420: Extracts the path from the request using `this.getPath()`
- Line 421: Matches the route via `this.router.match(method, path)`
- Line 423-429: Creates a Context object with match results
- Lines 432-450: Single handler fast-path (no composition needed)
- Line 452: Multi-handler path calls `compose()` to chain middleware

## Default Router: SmartRouter

**hono.ts:26-32** — Constructor sets the default router:
```
options.router ?? new SmartRouter({
  routers: [new RegExpRouter(), new TrieRouter()],
})
```

## SmartRouter Route Selection

**smart-router/router.ts:21-61** — `match()` method intelligently picks a router:
- Lines 29-50: Iterates through routers (RegExpRouter first, then TrieRouter)
- Line 36: Attempts to add all routes to each router
- Line 38: Calls `match()` on the current router
- Line 40-42: Catches `UnsupportedPathError` and tries the next router
- Line 46-48: On successful match, replaces SmartRouter's methods with the active router's (sticky selection)

## Middleware Composition

**compose.ts:15-72** — Middleware functions are composed into a chain:
- Lines 32-71: Recursive `dispatch()` function iterates through matched handlers
- Line 51: Each handler is called with context and a `next()` callback to the next middleware
- Line 54-55: If a handler throws, the `onError` handler is invoked
- Line 46, 62-63: After all middleware, the `onNotFound` handler runs if context isn't finalized

Middleware is applied in **hono-base.ts:452** when there are multiple matched routes:
```
compose(matchResult[0], this.errorHandler, this.#notFoundHandler)
```

## 404 Handler

**hono-base.ts:31-32** — Default 404 handler returns "404 Not Found"

**hono-base.ts:189, 294-297** — Customizable via `.notFound()` method. Runs in two places:
- **hono-base.ts:436**: Single-handler path, called if handler's `next()` is invoked
- **hono-base.ts:446, 452, 62-63**: Multi-handler path via compose when no route matches

## Error Handler

**hono-base.ts:35-41** — Default error handler checks for `getResponse()` method or returns "Internal Server Error"

**hono-base.ts:191, 274-277** — Customizable via `.onError()` method. Runs in:
- **compose.ts:53-55**: Within middleware chain when any handler throws an Error
- **hono-base.ts:439, 448, 465**: Wraps entire dispatch in try-catch via `#handleError()` (hono-base.ts:401-406)