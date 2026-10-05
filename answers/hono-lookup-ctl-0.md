The `strict` option is only read in one place: the `HonoBase` constructor. From there it has one effect, which is to choose the `getPath` function. No router looks at `strict`. Its effect reaches routing only through `this.getPath`.

## Declared and documented
- `src/hono-base.ts:46-54`: `HonoOptions.strict?: boolean`, with JSDoc `@default true` at line 52.

## Read and defaulted (the only place)
- `src/hono-base.ts:173`: `const { strict, ...optionsWithoutStrict } = options`. `strict` is pulled out so that `Object.assign(this, optionsWithoutStrict)` at line 174 doesn't copy it onto the instance. The instance never stores `strict`.
- `src/hono-base.ts:175`: `this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict`
  - The default is `true`, applied by `?? true`.
  - With `strict: true` or unset, the app uses the user's `getPath` if one was given, otherwise `getPath` from `src/utils/url.ts:106`. That one keeps the trailing slash, so `/a` and `/a/` are different paths.
  - With `strict: false`, the app always uses `getPathNoStrict`. **A user-supplied `options.getPath` is silently ignored in this case.**

## The non-strict behaviour itself
- `src/utils/url.ts:154-159`: `getPathNoStrict` calls `getPath` and then removes one trailing `/` if the path is longer than 1 character (comment at line 157). The root `/` is left alone.

## Where the choice changes routing
- `src/hono-base.ts:420-421`: in `#dispatch`, `const path = this.getPath(request, { env })` feeds `this.router.match(method, path)`. This is the main effect: the normalised path goes to the router, and it also becomes `Context`'s `path` (line 424), which is what `c.req.path` returns.
- `src/hono-base.ts:367-372`: `mount()`'s default `replaceRequest` uses `this.getPath(request).slice(pathPrefixLength)` to rewrite the URL passed to the mounted app. With non-strict, the trailing slash is already gone before the prefix is removed.
- `src/hono-base.ts:178-182`: `#clone()`, used by `basePath()`, passes `getPath: this.getPath` into a new `Hono` without `strict`. The new app therefore defaults to strict, but it receives the already-chosen function, so non-strict behaviour carries over to clones.

## Places the option is passed through (no logic of their own)
These all hand the options object to `super(options)` / `HonoBase`:
- `src/hono.ts:26-27`
- `src/preset/tiny.ts:16-17`
- `src/preset/quick.ts:18-19`
- `src/helper/factory/index.ts:334-345`: `Factory` keeps `defaultAppOptions`, including `strict`, and `createApp` spreads the caller's options over them. A per-call `strict` therefore overrides the factory default.

The `strict` hits in cookie, proxy, jsx, secure-headers and ip-restriction are other features that happen to use the word and have nothing to do with this option.