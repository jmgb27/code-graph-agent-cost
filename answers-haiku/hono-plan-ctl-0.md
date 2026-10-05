Now I'll provide a comprehensive plan for implementing per-route request timeouts.

## Plan: Per-Route Request Timeout Implementation

### Core Type Changes

**src/types.ts** - Add timeout option type definitions:
- Create a `RouteOptions` type with `timeout?: number` (milliseconds)
- Update `RouterRoute` interface (line 57-62) to include optional `timeout?: number` field
- Update `HandlerInterface` overloads - all ~30+ overloads (lines 127-600+) need variants that accept options parameter after path/before handlers

### Route Registration Changes

**src/hono-base.ts** - Route registration and execution:
- Line 388-399 `#addRoute()` - Add `options?: RouteOptions` parameter, store timeout in RouterRoute
- Line 129-143 Constructor method assignment - Modify the forEach loop to extract options from args if present
- Line 145-157 `on()` implementation - Add options parameter support
- Line 159-171 `use()` implementation - Add options parameter support  
- Line 408-468 `#dispatch()` - Wrap handler execution with timeout logic at lines 434-449 (single handler) and lines 452-467 (composed handlers)
- Optionally, line 232 in `route()` - Preserve timeout when copying routes from sub-app

### Error Handling

**src/http-exception.ts** - Create timeout exception:
- Add new `RequestTimeoutException` class extending HTTPException with status 504

Or create a new file **src/request-timeout.ts**:
- Export `TimeoutError` class extending Error
- Export error message constant

### Handler Wrapper Logic

**src/compose.ts** or **src/hono-base.ts** - Add timeout wrapper:
- Create helper function `withTimeout(handler, timeoutMs)` that returns a wrapped handler
- Use `Promise.race()` with handler execution and timeout promise
- Throw error if timeout exceeded before handler completes

### Adapter Updates  

All adapters need to ensure compatibility with timeout exceptions:

**src/adapter/aws-lambda/handler.ts** - Line 175-217 (streamHandle), Line 265-320+ (handle):
- Verify 504 responses are properly handled

**src/adapter/cloudflare-workers/index.ts** - Verify timeout handling

**src/adapter/deno/index.ts** - Verify timeout handling

**src/adapter/bun/server.ts** - Verify timeout handling

**src/adapter/vercel/handler.ts** - Verify timeout handling

**src/adapter/netlify/handler.ts** - Verify timeout handling (if exists)

**src/adapter/lambda-edge/handler.ts** - Verify timeout handling

**src/adapter/cloudflare-pages/handler.ts** - Verify timeout handling (if exists)

**src/adapter/service-worker/index.ts** - Verify timeout handling (if exists)

### Test Files to Add

**src/hono.test.ts** (line 111213) - Add timeout tests:
- Test route-specific timeout triggering 504
- Test handler completing within timeout
- Test timeout with multiple handlers/middleware
- Test timeout across different HTTP methods (GET, POST, etc.)
- Test timeout on mounted sub-apps
- Test different timeout values on different routes

**src/adapter/aws-lambda/handler.test.ts** - Add adapter-specific timeout tests

**src/adapter/cloudflare-workers/index.test.ts** (or similar) - Verify timeout works in CF worker context

**src/adapter/bun/server.test.ts** - Verify timeout works in Bun

**src/adapter/deno/index.test.ts** - Verify timeout works in Deno

### Implementation Approach Summary

1. **Extend RouterRoute** with timeout field (optional)
2. **Update HandlerInterface** to accept options containing timeout - creates variants like:
   - `app.get(path, handler)` existing
   - `app.get(path, { timeout: 5000 }, handler)` new
   - `app.get(path, handler1, handler2)` existing  
   - `app.get(path, { timeout: 5000 }, handler1, handler2)` new
3. **Modify #addRoute()** to extract and store timeout
4. **Wrap handler execution** in #dispatch() using Promise.race with AbortController or timeout promise
5. **Return 504** when timeout occurs (via thrown error caught by errorHandler)
6. **Verify all adapters** properly propagate timeout exceptions to 504 responses
7. **Add comprehensive tests** for timeout behavior in all adapter contexts

This approach keeps timeout logic centralized in hono-base.ts while maintaining backward compatibility - all existing code continues working without changes.