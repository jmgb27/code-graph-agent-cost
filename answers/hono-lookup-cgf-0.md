`strict` is read in exactly one place: the `HonoBase` constructor turns it into a choice of path extractor, `this.getPath`. No router ever sees the flag. It only changes the path string that gets passed to the router at dispatch time.

### Declaration and default
- `src/hono-base.ts:46-54`: `HonoOptions.strict?: boolean`, documented with `@default true` at line 52.
- The `Hono` constructors in `src/hono.ts:26-27`, `src/preset/quick.ts:18-19` and `src/preset/tiny.ts:16-17` just call `super(options)`. None of them touch `strict`.

### The only read, where the default is applied
- `src/hono-base.ts:173`: `const { strict, ...optionsWithoutStrict } = options` takes `strict` out of the options.
- `src/hono-base.ts:174`: `Object.assign(this, optionsWithoutStrict)` copies the other options onto the instance, so `strict` is never stored.
- `src/hono-base.ts:175`: `this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict`
  - The `?? true` is the actual runtime default.
  - When strict is true (or unset), a custom `options.getPath` is used if given, otherwise `getPath` from `src/utils/url.ts:106`.
  - When `strict: false`, the result is always `getPathNoStrict`. Any custom `getPath` you pass is silently ignored.
- `src/hono-base.ts:29` imports `getPath` and `getPathNoStrict` from `./utils/url`.

### What non-strict does
- `src/utils/url.ts:154-159`: `getPathNoStrict` calls `getPath(request)`, then drops one trailing `/` if the path is longer than 1 (line 158). So `/hello/hey/` becomes `/hello/hey`, while `/` stays `/`.

### Where it affects routing
- `src/hono-base.ts:420`: in `#dispatch`, `const path = this.getPath(request, { env })` and then `this.router.match(method, path)` at line 421. Both `fetch` (line 486) and `fire` (line 542) go through here.
- `src/hono-base.ts:424`: the same normalised `path` is passed into `Context`, so `c.req.path` also has no trailing slash when non-strict.
- `src/hono-base.ts:370`: in `mount()`, the default `replaceRequest` builds the mounted app's pathname from `this.getPath(request)`, so a non-strict app also strips the trailing slash before handing the request to the mounted app.

### How the setting carries over to sub-apps
- `src/hono-base.ts:178-182`: `#clone()` creates a new `Hono` with `{ router, getPath: this.getPath }` and no `strict` key. That means `strict ?? true` is true there, and it keeps the parent's already-chosen `getPath` function (which is `getPathNoStrict` when the parent was non-strict). So the parent's strictness carries over.
- `#clone()` is called by `basePath()` (`src/hono-base.ts:253`), which `route()` uses at line 221.
- A child app passed to `app.route()` keeps only its routes (lines 222-233). Its own `strict` setting is ignored: requests are matched using the parent's `getPath`.

Nothing else in `src/` refers to `strict` or `getPathNoStrict`. The other `strict` matches are unrelated: the proxy's RFC 9110 option, cookie `sameSite`, JSX referrer policies and a comment in `jsx/dom/render.ts`.