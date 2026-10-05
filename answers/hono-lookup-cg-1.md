The `strict` option is read in exactly one place: the `HonoBase` constructor. It works by picking which path-extraction function the app uses. No router reads it; they only ever get the path that function returns.

## Declared and defaulted
- `src/hono-base.ts:47-54`: `HonoOptions.strict?: boolean`, documented as `@default true`.
- `src/hono-base.ts:173-175`: the only runtime read, and the only place the default is applied:
  ```ts
  const { strict, ...optionsWithoutStrict } = options
  Object.assign(this, optionsWithoutStrict)
  this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict
  ```
  - `strict` is pulled out so it never becomes a property on the instance. Everything else, including `router` and `getPath`, is copied onto `this`.
  - If `strict` is `undefined` or `true`, the app uses the user's `getPath` if one was given, otherwise the default `getPath`.
  - If `strict` is `false`, the app always uses `getPathNoStrict`, and **any user-supplied `getPath` is silently ignored**.
- `src/hono.ts:26-27`, `src/preset/tiny.ts:17`, `src/preset/quick.ts:19`: the `Hono` subclasses pass `options` straight to `super(options)` without looking at `strict`.

## Where the behaviour differs
- `src/utils/url.ts:106-134`: `getPath` is the strict version. It returns the raw pathname, so `/hello` and `/hello/` are different paths.
- `src/utils/url.ts:154-159`: `getPathNoStrict` calls `getPath` and then removes one trailing `/`, except when the path is just `/`.
- `src/hono-base.ts:120`: `readonly getPath`, the field that holds whichever function was chosen.

## Where the chosen `getPath` is used
- `src/hono-base.ts:420-421`: in `#dispatch`, `const path = this.getPath(request, { env })` produces the path passed to `this.router.match(method, path)` and to `Context`. This is where routing actually changes.
- `src/hono-base.ts:370`: in `mount()`, the default `replaceRequest` builds the sub-app URL with `this.getPath(request).slice(pathPrefixLength)`. With `strict: false`, a mounted app receives the path without its trailing slash.
- `src/hono-base.ts:178-182`: `#clone()` (used by `route`/`basePath`) creates a new `Hono` with `getPath: this.getPath` and no `strict`. The clone therefore defaults to `strict ?? true` and keeps the parent's chosen function, so non-strict behaviour carries over to it.

## Indirect producer
- `src/helper/factory/index.ts:341-346`: `createFactory({ defaultAppOptions })` merges `{ ...defaultAppOptions, ...options }`, so a `strict` passed to `createApp()` overrides the factory default. This is tested at `src/helper/factory/index.test.ts:411` and `:419`.

## Tests
- `src/hono.test.ts:310-380`: strict true (with and without a slash), strict false, and strict false with `getPath`. The last test passes the default `getPath`, so it doesn't catch that a custom `getPath` is dropped when `strict: false`.
- `src/hono.test.ts:383-388`: checks that the options object is not mutated. The destructuring at `hono-base.ts:173` is what keeps it unchanged.
- `src/utils/url.test.ts:194-205`: unit tests for `getPathNoStrict`.
- `src/middleware/trailing-slash/index.test.ts:6,158,260`: these use `strict: true` explicitly. The trailing-slash middleware itself never reads `strict`.

None of the router implementations (`src/router/**`) read `strict`.