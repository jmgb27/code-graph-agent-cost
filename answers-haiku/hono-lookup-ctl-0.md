Here are all the places where the `strict` option of `new Hono()` is defaulted, read, or changes routing behavior:

## Type Definition & Default
- **src/hono-base.ts:54** — Type definition: `strict?: boolean`
- **src/hono-base.ts:52** — Documentation comment: `@default true`

## Constructor: Default & Read
- **src/hono-base.ts:175** — Reads and defaults `strict`: `this.getPath = (strict ?? true) ? (options.getPath ?? getPath) : getPathNoStrict`
  - Defaults to `true` (via `strict ?? true`)
  - Selects routing function based on `strict` value

## Routing Behavior Implementation
- **src/utils/url.ts:106-134** — `getPath()` function (strict routing: distinguishes `/hello` and `/hello/`)
- **src/utils/url.ts:154-159** — `getPathNoStrict()` function (non-strict routing: treats `/hello` and `/hello/` identically)
- **src/utils/url.ts:157** — Comment explaining behavior: `// if strict routing is false => `/hello/hey/` and `/hello/hey` are treated the same`

## Test Cases Demonstrating Behavior
- **src/hono.test.ts:312** — Test: "strict is true with not slash"
- **src/hono.test.ts:329** — Test: "strict is true with slash"
- **src/hono.test.ts:346** — Test: `new Hono({ strict: false })`
- **src/hono.test.ts:364** — Test: `new Hono({ strict: false, getPath: getPath })`
- **src/helper/factory/index.test.ts:411** — Factory test: `defaultAppOptions: { strict: false }`
- **src/helper/factory/index.test.ts:419** — Factory test: override with `strict: false`
- **src/middleware/trailing-slash/index.test.ts:6** — Test: `new Hono({ strict: true })`
- **src/middleware/trailing-slash/index.test.ts:158** — Test: `new Hono({ strict: true })`
- **src/middleware/trailing-slash/index.test.ts:260** — Test: `new Hono({ strict: true })`