`strict` is only consumed in one place, `src/hono-base.ts:175`. It never reaches the routers. All it does is choose which path-extraction function the app uses, and the rest of the effect follows from that choice.

**Declared and documented as defaulting to true**
- `src/hono-base.ts:47-54`: `HonoOptions.strict?: boolean`, with the JSDoc tag `@default true`.

**Read and defaulted (the only real logic)**
- `src/hono-base.ts:173`: `const { strict, ...optionsWithoutStrict } = options`. `strict` is pulled out so the next line, `Object.assign(this, optionsWithoutStrict)` (`:174`), never copies it onto the instance.
- `src/hono-base.ts:175`: `this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict`
  - This is where the runtime default of `true` is applied.
  - When `strict` is true or unset, the app uses the user's `getPath` if one was given, otherwise the built-in `getPath` from `src/utils/url.ts:106-134`.
  - When `strict` is false, the app always uses `getPathNoStrict`, **and any custom `options.getPath` is silently dropped**. Only `strict: false` discards it.

**What non-strict mode does**
- `src/utils/url.ts:154-159`: `getPathNoStrict` calls `getPath`, then removes one trailing `/` if the path is longer than 1 character. So `/hello/` becomes `/hello`, and `/` stays `/`.

**Where the chosen `getPath` changes routing**
- `src/hono-base.ts:420-421`: `#dispatch` computes `const path = this.getPath(request, { env })` and passes it to `this.router.match(method, path)`. It also stores it as the context `path` at `:423-425`, so `c.req.path` shows the normalised value.
- `src/hono-base.ts:370`: the default `replaceRequest` in `mount()` builds the mounted app's URL from `this.getPath(request).slice(pathPrefixLength)`. With `strict: false`, the mounted app also receives the path without its trailing slash.

**Carried over to derived apps**
- `src/hono-base.ts:178-182`: `#clone()` builds a new `Hono` with `getPath: this.getPath` and no `strict`, so the new app keeps the parent's already-chosen function. `basePath()` uses `#clone()` (`src/hono-base.ts:253`), so a `basePath` sub-app keeps the parent's strictness.
- `src/hono.ts:26-27`, `src/preset/tiny.ts:17` and `src/preset/quick.ts:19` pass `options` straight to `super(options)`, which is the base constructor above.
- `src/helper/factory/index.ts:342-345`: `createApp()` merges `{ ...defaultAppOptions, ...options }`. A `strict` value passed to `createApp` overrides the factory default, and the factory default applies when `createApp` gets none.

**Tests that exercise it**
- `src/hono.test.ts:310-381`: strict true (with and without a trailing slash), strict false, and strict false combined with `getPath`.
- `src/hono.test.ts:383-388`: checks that the options object passed in is not mutated.
- `src/helper/factory/index.test.ts:411,419`: the factory's default-versus-override precedence.
- `src/middleware/trailing-slash/index.test.ts:6,158,260`: these use `strict: true`, which the trailing-slash middleware needs.

One gap in that coverage: the "strict is false with `getPath`" test (`src/hono.test.ts:362`) passes in the built-in `getPath` itself. It therefore can't show that a custom `getPath` is ignored when `strict: false`, which `:175` does.