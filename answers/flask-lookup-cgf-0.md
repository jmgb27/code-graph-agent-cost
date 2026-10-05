Flask sets the default and reads the value, but it never checks the limit itself. Werkzeug enforces it by reading `Request.max_content_length`.

## Default
- `src/flask/app.py:227`: `"MAX_CONTENT_LENGTH": None` sits in `Flask.default_config`, so by default there is no limit.

## Read (source)
Everything is in `src/flask/wrappers.py`, in the `Request` class:
- `:55`: `_max_content_length: int | None = None` holds the per-request override.
- `:59-86`: the `max_content_length` property returns values in this order:
  1. `:80-81`: the per-request override, if one is set.
  2. `:83-84`: with no app context, Werkzeug's own default (`super().max_content_length`, which is `None`).
  3. `:86`: otherwise, `current_app.config["MAX_CONTENT_LENGTH"]`. This is the only line in source that reads the config key.
- `:88-90`: the setter, which stores the per-request override (added in 3.1).

## Enforced
Flask has no enforcement code of its own. Werkzeug's base `Request` checks `self.max_content_length` when it builds the input stream and parses form data. If the body is too large it raises `RequestEntityTooLarge` (HTTP 413), as the docstring at `wrappers.py:61-67` says. Flask's only role is to supply the value through the property override above.

## Tests
- `tests/test_request.py:9-22`, `test_max_content_length`: sets the config to 50 (`:10`), posts a 150-byte form field (`:21`), and checks that the 413 handler at `:17-19` runs (`:22`). This is the end-to-end enforcement test.
- `tests/test_request.py:25-54`, `test_limit_config`:
  - `:26` sets the config to 100.
  - `:32`: with no app context, the value falls back to Werkzeug's `None`.
  - `:38`: inside an app context, the value comes from the config (100).
  - `:43`: sets a per-request override of 90.
  - `:47` and `:52`: the override wins both outside and inside an app context.

## Docs and changelog (not code)
- `docs/config.rst:320` (definition), `:330`, `:404`
- `docs/web-security.rst:25`
- `docs/patterns/fileuploads.rst:138`, `:144` (example: `16 * 1000 * 1000`)
- `CHANGES.rst:83-84` (per-request override in 3.1), `:1536` (config key added in 0.6)