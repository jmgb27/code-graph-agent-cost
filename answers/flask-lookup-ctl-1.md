Flask only sets the default and reads `MAX_CONTENT_LENGTH`. The 413 limit is enforced by Werkzeug, which calls the overridden property when it reads the request body or parses form data. No other file in `src/` or `tests/` mentions it.

## Source

**Default**
- `src/flask/app.py:227`: `"MAX_CONTENT_LENGTH": None` is set in `Flask.default_config`.

**Read** (in `src/flask/wrappers.py`, the `Request` subclass)
- `src/flask/wrappers.py:55`: `_max_content_length: int | None = None` holds a per-request override.
- `src/flask/wrappers.py:59-86`: the `max_content_length` property returns the first of these that applies:
  1. `:80-81`: the per-request override, if it's set.
  2. `:83-84`: Werkzeug's default (`super().max_content_length`) when there's no app context.
  3. `:86`: `current_app.config["MAX_CONTENT_LENGTH"]`.
- `src/flask/wrappers.py:88-90`: the setter, which lets a view set the limit for one request.

**Enforced**
- Nothing in Flask's code raises the 413 itself. Werkzeug's base `Request` checks `self.max_content_length` when it reads the body stream or parses form data, and raises `RequestEntityTooLarge` (413) if the limit is exceeded. Because Flask overrides the property, Werkzeug picks up the config value. The docstring at `src/flask/wrappers.py:61-67` describes this.

## Tests

- `tests/test_request.py:9-22` (`test_max_content_length`): the limit is enforced end to end.
  - `:10` sets the config to 50.
  - `:14` reads `request.form`, which triggers parsing.
  - `:17-19` a 413 handler catches the error.
  - `:21-22` a 150-byte post returns the handler's `b"42"`, confirming the 413 fired.
- `tests/test_request.py:25-54` (`test_limit_config`): how the value is resolved.
  - `:26` sets the config to 100.
  - `:32` with no app context, the value is Werkzeug's default of `None`.
  - `:38` inside an app context, it's the config value, 100.
  - `:43` sets a per-request override of 90.
  - `:47` and `:52` the override wins both outside and inside an app context.

## Docs and changelog (not code)

- `docs/config.rst:320` and `:330` define the setting and point to the per-request override.
- `docs/config.rst:404` is a later mention of the setting.
- `docs/web-security.rst:25`
- `docs/patterns/fileuploads.rst:138` and `:144` include the example `app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000`.
- `CHANGES.rst:83-84` covers the per-request override added in 3.1.
- `CHANGES.rst:1536` is the original addition of the setting.