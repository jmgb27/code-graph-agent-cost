Based on my exploration of the codebase, here's a comprehensive plan for adding per-route request timeout functionality:

## Plan: Per-Route Request Timeout Option

### Core Changes

#### 1. **Type Definitions** (`src/types.ts`)
- **Line 57-62 (RouterRoute interface)**: Add optional `timeout?: number` field to store milliseconds timeout for each route
- **Line 127-220 (HandlerInterface)**: Extend all overloads to accept a timeout option parameter in route definitions (e.g., `app.get({ timeout: 5000 }, handler)`)

#### 2. **Route Registration** (`src/hono-base.ts`)
- **Lines 131-142 (constructor HTTP method setup)**: Update dynamic method generation to parse timeout option from first parameter if it's an object with timeout property
- **Lines 388-399 (#addRoute method)**: Accept and store timeout in RouterRoute object
- **Lines 408-468 (#dispatch method)**: Wrap handler execution with timeout logic that:
  - Creates a Promise.race between the handler and a timeout promise
  - Returns 504 Gateway Timeout when timeout is exceeded
  - Properly handles cleanup if timeout occurs

#### 3. **Middleware Composition** (`src/compose.ts`)
- **Lines 15-72 (compose function)**: Option to receive route timeout metadata and apply it around handler execution at line 51 where `await handler(context, () => dispatch(i + 1))` is called

#### 4. **Context/Request** 
- **`src/context.ts`**: May need to track whether a timeout occurred for middleware awareness
- **`src/request.ts`**: Track which route's timeout (if any) applies to current request

### Runtime Adapters

Each adapter's handler needs to ensure routes with timeout metadata are properly preserved:

#### Adapters in `/adapters/`:
1. **aws-lambda/src/handler.ts** (line 243): `handle` function
2. **bun/src/handler.ts**: Handler wrapper
3. **cloudflare-workers/src/handler.ts**: Handler wrapper  
4. **deno/src/handler.ts**: Handler wrapper
5. **lambda-edge/src/handler.ts** (line 115): `handle` function
6. **netlify/src/handler.ts** (line 4): `handle` function
7. **service-worker/src/handler.ts** (line 18): `handle` function
8. **vercel/src/handler.ts** (line 5): `handle` function

#### Deprecated Adapters in `/src/adapter/`:
1. **aws-lambda/handler.ts** (line 265): `handle` function
2. **bun/handler.ts**: Handler wrapper
3. **cloudflare-pages/handler.ts** (line 38-51): `handle` function
4. **cloudflare-workers/handler.ts**: Handler wrapper
5. **deno/handler.ts**: Handler wrapper
6. **lambda-edge/handler.ts** (line 133): `handle` function
7. **netlify/handler.ts** (line 7): `handle` function
8. **service-worker/handler.ts** (line 22): `handle` function
9. **vercel/handler.ts** (line 8): `handle` function

### Test Files to Add

1. **`src/hono.test.ts`**: Add tests for per-route timeout behavior
2. **`src/compose.test.ts`**: Add tests for timeout handling in middleware chain
3. **Runtime adapter tests**:
   - `adapters/aws-lambda/test/index.test.ts`: Timeout behavior in Lambda
   - `adapters/bun/test/index.test.ts`: Timeout behavior in Bun
   - `adapters/cloudflare-workers/test/index.test.ts`: Timeout in Workers
   - `adapters/deno/test/index.test.ts`: Timeout in Deno
   - `adapters/netlify/test/index.test.ts`: Timeout in Netlify
   - `adapters/vercel/test/handler.test.ts`: Timeout in Vercel
   - `adapters/service-worker/test/index.test.ts`: Timeout in Service Worker

### Integration Points

- **Router**: No changes needed; routes flow through existing router
- **HTTP Exception**: Consider if `HTTPException` should support 504 or create specialized timeout exception
- **Error Handler**: Timeout errors should be catchable by `app.onError()`
- **Not Found Handler**: Ensure timeout doesn't interfere with 404 handling

### API Design

```typescript
// Usage examples that need to work:
app.get({ timeout: 5000 }, '/endpoint', handler)
app.post({ timeout: 10000 }, handler)
app.put('/path', { timeout: 3000 }, handler)
app.delete('/path', handler, middleware) // no timeout
```

### Files Summary

**Total files to modify: 18** (2 core + 8 public adapters + 8 deprecated adapters)
**Total test files to add/update: 10+** (core + per-runtime tests)
**Type definition changes: 2** (RouterRoute, HandlerInterface overloads)