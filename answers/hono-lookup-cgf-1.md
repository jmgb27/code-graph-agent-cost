`strict` is read in exactly one place: the `HonoOptions` constructor, where it picks the path extractor. After that nothing reads `strict` again. Its only effect on routing is which function turns the request URL into the path that gets matched.

### Declared and documented default
- `src/hono-base.ts:46-54`: `HonoOptions.strict?: boolean`, documented as `@default true` (line 52). The doc says it controls "whether to distinguish whether the last path is a directory or not".

### Passed through unchanged (subclass constructors)
- `src/hono.ts:26-27`: `Hono` constructor does `super(options)`.
- `src/preset/quick.ts:18-19` and `src/preset/tiny.ts:16-17`: same for the `hono/quick` and `hono/tiny` presets.

### Where it is read and defaulted (the only place)
- `src/hono-base.ts:173`: `const { strict, ...optionsWithoutStrict } = options`. `strict` is pulled out so the `Object.assign(this, optionsWithoutStrict)` on line 174 never stores it on the instance.
- `src/hono-base.ts:175`: `this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict`
  - The runtime default comes from `?? true`.
  - With strict on (the default), it uses your custom `getPath` if you passed one, otherwise `getPath` from `src/utils/url.ts:106`.
  - With `strict: false`, it always uses `getPathNoStrict`. **A custom `getPath` option is silently ignored in that case.**
- `src/hono-base.ts:120`: `readonly getPath: GetPath<E>` is the field that stores the result.

### Where the behaviour change actually happens
- `src/utils/url.ts:154-159`, `getPathNoStrict`: calls the normal `getPath` and then removes one trailing `/` when the path is longer than 1 character (line 158). So `/hello/` and `/hello` become the same path. The root `/` is left alone. Nothing changes when routes are registered (`#addRoute`, `src/hono-base.ts:388-399`), and the routers get no strict flag. Only the path extracted from the incoming request is changed.

### Where the chosen `getPath` is used
- `src/hono-base.ts:420-421`, `#dispatch`: `const path = this.getPath(request, { env })`, then `this.router.match(method, path)`. This is where strict vs non-strict decides which route matches.
- `src/hono-base.ts:423-424`: that same path is passed to `new Context(...)`, so `c.req.path` also has the trailing slash removed in non-strict mode.
- `src/hono-base.ts:370`, the default `replaceRequest` in `mount()`: `url.pathname = this.getPath(request).slice(pathPrefixLength) || '/'`. With `strict: false`, the mounted app receives a request URL with the trailing slash removed.

### How it carries over to `basePath()` / `route()`
- `src/hono-base.ts:178-182`, `#clone()` (called by `basePath()` at line 253, which `route()` uses at line 221): builds `new Hono({ router: this.router, getPath: this.getPath })` with no `strict`. The clone's `strict` is `undefined`, so it defaults to `true` and takes `options.getPath`, which is the parent's `getPath`. If the parent is non-strict, that is `getPathNoStrict`, so sub-apps keep the parent's behaviour even though `strict` isn't passed to them.

In `src/`, `strict` appears nowhere else outside tests. The other matches are unrelated names such as `strictConnectionProcessing` and `strictTransportSecurity`, and no router (`src/router/*`) reads it.