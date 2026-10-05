Now I'll compile the plan for adding per-route request timeout support to Hono.

## Plan: Per-Route Request Timeout

### Design Overview
Add a `timeout` option to route handlers (e.g., `app.get('/path', { timeout: 5000 }, handler)`) that returns 504 Gateway Timeout when the handler exceeds the specified duration. This works across all runtime adapters by wrapping handlers with timeout logic in the dispatch phase.

---

### Files to Change

#### 1. **Core Types** (`src/types.ts`)
- **Line ~57:** Modify `RouterRoute` interface to include optional `timeout` field
- **New:** Add `RouteOptions` interface with `timeout?: number` property
- **Line ~127-500:** Update `HandlerInterface` type signatures to accept route options as first argument before path (e.g., `app.get({ timeout: 5000 }, path, handler)` and `app.get(path, { timeout: 5000 }, handler)`)

#### 2. **Hono Base** (`src/hono-base.ts`)
- **Line 46:** Update `HonoOptions<E>` type to potentially store default route timeout
- **Line ~131-142:** Modify the route registration logic in constructor to parse route options from handler arguments
- **Line ~388-399:** Update `#addRoute()` method signature to accept `options?: RouteOptions` parameter and store it in `RouterRoute`
- **Line ~408-468:** Modify `#dispatch()` method to:
  - Extract timeout from matched route
  - Wrap single-handler path (line ~432-449) with timeout logic
  - Wrap composed handler path (line ~452-467) with timeout logic
- **New:** Add private `#applyTimeout()` helper method that wraps handler execution with Promise.race() against a timeout promise

#### 3. **New Timeout Handler Utility** (`src/utils/timeout-handler.ts`)
- **New file** with exported function:
  - `applyRouteTimeout(handler: H, timeout: number, c: Context): ReturnType<H>` - Wraps handler with timeout protection
  - Returns 504 when timeout exceeded
  - Clears timeout in finally block to prevent memory leaks

#### 4. **HTTP Exception** (`src/http-exception.ts`)
- No changes needed; reuse existing HTTPException class

#### 5. **Tests** (`src/hono.test.ts`)
- **New test suite:** "Request Timeout"
  - Test timeout on single route with path and options
  - Test timeout on route without path (just handlers)
  - Test multiple routes with different timeouts
  - Test route that completes within timeout
  - Test route that exceeds timeout returns 504
  - Test nested apps with different timeouts (via route())
  - Test timeout in basePath() variants
  - Test interaction with middleware (middleware timeout vs route timeout - route should take precedence)
  - Test custom timeout exception
  - Test that timeout doesn't break other routes

#### 6. **Runtime Adapter Verification** (all adapters below - read-only verification, no code changes needed)
- `adapters/bun/src/server.ts` - Verify fetch() calls route through Hono.fetch()
- `adapters/deno/src/serve-static.ts` - Verify request handling
- `adapters/cloudflare-workers/src/index.ts` - Verify fetch handler
- `adapters/aws-lambda/src/index.ts` - Verify request transformation
- `adapters/netlify/src/index.ts` - Verify event handling
- `adapters/vercel/src/index.ts` - Verify request handling
- `adapters/service-worker/src/index.ts` - Verify fetch event listener
- All should work because timeout is applied in Hono.#dispatch() before returning response

---

### Detailed Changes Summary

**Type System Changes:**
1. Add `RouteOptions` interface to types.ts with `timeout?: number`
2. Extend `RouterRoute` interface to include optional `options?: RouteOptions`
3. Update all `HandlerInterface` overloads to support optional options parameter placement

**Route Registration Changes:**
1. Update constructor's method binding logic to parse and extract options
2. Modify `#addRoute()` to accept and store options in RouterRoute

**Timeout Execution Changes:**
1. Add timeout application in `#dispatch()` for both single and composed handler paths
2. Create utility function to safely apply timeout wrapping with Promise.race()
3. Return HTTPException(504) on timeout
4. Ensure cleanup of timers in finally blocks

**Test Coverage:**
- Basic per-route timeout functionality
- Multiple routes with different timeouts
- Timeout interaction with middleware
- All handler registration patterns (with/without path, multiple handlers)
- Custom exception handling
- basePath() and route() integration
- All runtime adapters (via existing test infrastructure)

---

### Key Implementation Details

**Timeout Logic:**
- Uses `Promise.race()` between handler execution and timeout promise
- Clears timer in finally block to prevent memory leaks
- Returns 504 Gateway Timeout response
- Compatible with both sync and async handlers
- Works with composed middleware chains
- Respects timeout only if handler timeout defined (opt-in per route)

**Backward Compatibility:**
- Routes without timeout option work as before
- Existing middleware timeout functionality unchanged
- No breaking changes to public API

**Runtime Support:**
- Works in all adapters because timeout wrapping happens in core Hono.#dispatch()
- No adapter-specific changes needed
- Timeouts apply consistently across Node, Bun, Deno, Cloudflare Workers, AWS Lambda, etc.