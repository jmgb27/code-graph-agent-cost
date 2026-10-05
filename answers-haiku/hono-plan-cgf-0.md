Based on my CodeGraph exploration, here's the comprehensive plan for adding per-route request timeout functionality:

## Plan: Per-Route Request Timeout Feature

### Core Changes Required

#### 1. **Type Definitions** (`src/types.ts`)
- **Add**: `RouteOptions` type with `timeout?: number` field
- **Modify**: `RouterRoute` interface to include `timeout?: number` field
- **Modify**: `HandlerInterface` overloads to accept optional timeout parameter

#### 2. **Route Registration** (`src/hono-base.ts`)
- **Line 388-399**: Modify `#addRoute()` method signature to accept `timeout?: number` parameter
  - Store timeout in `RouterRoute` object (line 390-396)
- **Line 128-176**: Update handler registration logic in constructor
  - Support both `app.get(handler)` and `app.get(path, timeout, handler)` patterns
  - Or add new overloads for timeout support
- **Add new methods**: Optional convenience methods like:
  - `#applyTimeout()` - wraps handler execution with AbortController
  - Or inline timeout logic directly in `#dispatch()`

#### 3. **Request Dispatch** (`src/hono-base.ts`)
- **Line 408-468**: Modify `#dispatch()` method
  - Extract timeout from matched route
  - Wrap handler execution with timeout enforcement using `Promise.race()` + `AbortController`
  - Return 504 status when timeout is exceeded
  - Ensure timeout applies to both single-handler and composed-handler flows (lines 432-450 and 452-467)

#### 4. **Router Types** (`src/router/trie-router/node.ts`, `src/router.ts`)
- No changes needed - timeout is stored in `RouterRoute`, not in the router itself

#### 5. **Adapter Handlers** - Verify No Changes Needed
- `src/adapter/aws-lambda/handler.ts:265-302` - calls `app.fetch()`, timeout handled centrally
- `src/adapter/lambda-edge/handler.ts:133-165` - calls `app.fetch()`, timeout handled centrally
- `src/adapter/service-worker/handler.ts:22-41` - calls `app.fetch()`, timeout handled centrally
- `src/adapter/cloudflare-pages/handler.ts:39-52` - calls `app.fetch()`, timeout handled centrally
- `src/adapter/netlify/handler.ts:7-12` - calls `app.fetch()`, timeout handled centrally
- `src/adapter/vercel/handler.ts:8` - calls `app.fetch()`, timeout handled centrally
- Modern adapters: `adapters/aws-lambda/src/handler.ts`, `adapters/lambda-edge/src/handler.ts`, `adapters/vercel/src/handler.ts`, `adapters/netlify/src/handler.ts`

### Test Files to Create/Modify

#### 1. **Core Timeout Tests** (`src/hono.test.ts` or new `src/timeout.test.ts`)
- Test single handler with timeout (exceeds timeout)
- Test single handler with timeout (completes before timeout)
- Test route without timeout (no behavior change)
- Test multiple handlers with timeout
- Test timeout with middleware
- Test timeout returns 504 status
- Test timeout with different response types (text, json, stream)
- Test timeout with async operations
- Test error handling during timeout

#### 2. **Adapter-Specific Tests**
- `src/adapter/aws-lambda/handler.test.ts` - verify timeout works with Lambda
- `src/adapter/lambda-edge/handler.test.ts` - verify timeout works with Lambda@Edge
- `src/adapter/cloudflare-pages/handler.test.ts` - verify timeout works with Cloudflare Pages
- `src/adapter/service-worker/handler.test.ts` - verify timeout works with Service Workers
- `src/adapter/netlify/handler.test.ts` - verify timeout works with Netlify
- `src/adapter/vercel/handler.test.ts` - verify timeout works with Vercel
- Corresponding tests in `adapters/*/src/handler.test.ts` for modern adapters

#### 3. **Edge Cases**
- Test timeout with route parameters
- Test timeout with multiple matching routes
- Test timeout with error handlers
- Test timeout with NOT_FOUND handlers
- Test timeout cancellation of pending operations
- Test nested app.route() with timeout

### Implementation Strategy

1. Create abstract timeout wrapper function that:
   - Uses `AbortController` to signal cancellation
   - Uses `Promise.race()` to enforce timeout
   - Cleans up resources on timeout
   - Returns 504 response

2. Two approaches for route timeout API:
   - **Option A**: `app.get('/path', { timeout: 5000 }, handler)`
   - **Option B**: Extend `HandlerInterface` with timeout parameter overloads
   - **Option C**: Add helper like `app.get('/path', withTimeout(5000, handler))`

3. Integration points:
   - Store timeout in `RouterRoute` during registration
   - Apply timeout at handler execution in `#dispatch()` method
   - Applies to both single-handler and middleware composition flows

### Files Summary

**Files to modify** (7):
- `src/types.ts` - Add types
- `src/hono-base.ts` - Add timeout logic to routing and dispatch
- `src/router.ts` - Update RouterRoute type (if needed)

**Test files to add/modify** (9+):
- `src/hono.test.ts` or new `src/timeout.test.ts`
- `src/adapter/*/handler.test.ts` (6 files)
- `adapters/*/src/handler.test.ts` (4+ files)

**Functions to add/modify**:
- `#addRoute()` - accept timeout parameter
- `#dispatch()` - implement timeout wrapping
- Handler registration in constructor - support timeout in all overloads
- New utility: timeout wrapper function (could be inline or extracted)