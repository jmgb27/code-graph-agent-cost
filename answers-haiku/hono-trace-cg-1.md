## Request Trace: app.fetch to Response on Cloudflare Workers

Here's the complete flow:

### **Entry Point**
- **src/hono-base.ts:481-487** — `fetch` method (entry point for Cloudflare Workers)
  - Calls `#dispatch(request, executionCtx, env, method)`

### **Default Router Selection**
The default router depends on which Hono preset is imported:

**Main Hono (src/hono.ts:26-33)**
```
SmartRouter with [RegExpRouter, TrieRouter]
```
- Options.router can override; otherwise SmartRouter tries routers in order

**Quick preset (src/preset/quick.ts:18-23)**
```
SmartRouter with [LinearRouter, TrieRouter]
```

**Tiny preset (src/preset/tiny.ts:16-19)**
```
PatternRouter
```

### **SmartRouter Route Selection Logic**
- **src/router/smart-router/router.ts:4-70** — SmartRouter class
  - **Line 21-61** — `match()` method: tries each router sequentially (line 32-50)
  - Once a router succeeds without `UnsupportedPathError`, it replaces itself with that router (line 46-48)
  - Subsequent requests go directly to the active router (cached)

### **Request Dispatch & Matching**
- **src/hono-base.ts:408-468** — `#dispatch()` method
  - **Line 420-421** — Gets path and calls `this.router.match(method, path)`
  - **Line 423-429** — Creates Context with matchResult
  - **Line 432-450** — Single handler fast path (no compose overhead)
  - **Line 452** — Multiple handlers: calls `compose(matchResult[0], this.errorHandler, this.#notFoundHandler)`

### **Middleware Composition**
- **src/compose.ts:15-73** — `compose()` function
  - **Line 32-71** — `dispatch()` nested function chains middleware
  - **Line 43** — Extracts handler: `middleware[i][0][0]`
  - **Line 51** — Calls handler with `() => dispatch(i + 1)` (the `next` function)
  - **Line 62-64** — If no handler and context not finalized, calls `onNotFound()`
  - **Line 53-56** — On error, calls `onError(err, context)` if provided

### **Default Handlers**
- **404 Handler (src/hono-base.ts:31-33)**
  ```typescript
  notFoundHandler: (c) => c.text('404 Not Found', 404)
  ```

- **Error Handler (src/hono-base.ts:35-42)**
  ```typescript
  errorHandler: (err, c) => {
    if ('getResponse' in err) return c.newResponse(res.body, res)
    console.error(err)
    return c.text('Internal Server Error', 500)
  }
  ```

### **Response Return Flow**
- **src/hono-base.ts:442-449** (single handler) or **452-467** (multiple handlers)
  - Handler returns Response or Promise<Response>
  - Error caught at src/hono-base.ts:439 or 464, passed to `#handleError()` (line 401-406)
  - If not finalized, 404 handler returned at line 446 or 449