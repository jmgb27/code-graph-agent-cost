`strict` is read in exactly one place, `src/hono-base.ts:173-175`. It never reaches the router: all it does is choose the `getPath` function once, in the constructor, and the rest of the code only sees that function.

## Defined and defaulted
- `src/hono-base.ts:46-54`: `HonoOptions.strict?: boolean`, documented with `@default true` (line 52).
- `src/hono-base.ts:173`: `const { strict, ...optionsWithoutStrict } = options` pulls `strict` out so that `Object.assign(this, optionsWithoutStrict)` (line 174) doesn't copy it onto the instance.
- `src/hono-base.ts:175`: `this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict`
  - **This is where the default is applied:** if `strict` is `undefined`, it's treated as `true`.
  - If strict is on, a user-supplied `getPath` is used, otherwise the built-in `getPath`.
  - **If `strict: false`, `getPathNoStrict` is used and any user `getPath` is silently ignored** (tested at `src/hono.test.ts:362-365`).

## Options that pass through to that constructor
- `src/hono.ts:26-27`, `src/preset/quick.ts:18-19`, `src/preset/tiny.ts:16-17`: each subclass constructor calls `super(options)` unchanged.
- `src/helper/factory/index.ts:336-345`: `createFactory({ defaultAppOptions })` shallow-merges the defaults with the options given to `createApp()`, so `createApp({ strict })` overrides `defaultAppOptions.strict`. Tested at `src/helper/factory/index.test.ts:411,419`.

## How it changes routing
- `src/utils/url.ts:154-159`: `getPathNoStrict` calls `getPath` and then removes one trailing `/` when the path is longer than 1 character. So `/hello/` becomes `/hello`, and `/` stays `/`.
- `src/utils/url.ts:106-134`: the strict `getPath` returns the pathname exactly as sent, keeping the trailing slash.
- `src/hono-base.ts:420-421`: `#dispatch` calls `this.getPath(request, { env })` and passes the result to `this.router.match(method, path)`. This is where the choice affects which route matches. The same `path` also goes into the `Context` (line 424).
- `src/hono-base.ts:370`: in `mount()`, the default `replaceRequest` builds the sub-request's pathname with `this.getPath(request)`. With `strict: false`, the mounted app therefore gets the path without its trailing slash.

## Derived apps inherit the choice
- `src/hono-base.ts:178-182`: `#clone()` passes `getPath: this.getPath` to the new instance and no `strict` value, so the clone gets the default and keeps the parent's already-chosen function. `basePath()` uses `#clone()` (`src/hono-base.ts:253`).
- `src/hono-base.ts:211-235`: `route()` copies the sub-app's routes into the parent's router (line 232). **Only the parent's `strict` setting matters at dispatch; the sub-app's is ignored.**

## Related but doesn't read `strict`
- The `trailing-slash` middleware is meant for apps using `strict: true` (see `src/middleware/trailing-slash/index.test.ts:6,158,260`), but its source never reads the option.
- No router under `src/router/*` knows about `strict`. They all just match whatever path `getPath` produced.
- Tests of the behaviour: `src/hono.test.ts:346` (`strict: false`) and `:384` (`strict: true`), plus `src/utils/url.test.ts:193-203` for `getPathNoStrict`.