Flask sets the default for `MAX_CONTENT_LENGTH` in one place and reads it in one place. It never checks the limit itself. It passes the value to Werkzeug, which enforces it.

## Source

**Default**
- `src/flask/app.py:227`: `"MAX_CONTENT_LENGTH": None,` is set in `Flask.default_config`, so there is no limit by default.

**Read** (the `Request.max_content_length` property in `src/flask/wrappers.py`)
- `src/flask/wrappers.py:55`: the class attribute `_max_content_length: int | None = None` holds a per-request override.
- `src/flask/wrappers.py:59-86`: the property getter checks three things in order:
  - `:80-81`: if the per-request override is set, it returns that.
  - `:83-84`: if there is no app context, it falls back to Werkzeug's `super().max_content_length`, which is `None`.
  - `:86`: otherwise it returns `current_app.config["MAX_CONTENT_LENGTH"]`. This is the only place the config key is read.
- `src/flask/wrappers.py:88-90`: the setter stores the per-request override (new in 3.1).
- `src/flask/wrappers.py:61-72`: the docstring describes the behaviour. Once the limit is exceeded you get a 413 `RequestEntityTooLarge` error.

**Enforcement**
- The Flask code base has no enforcement code of its own. Werkzeug's request base class reads `self.max_content_length` when it builds the input stream and parses form data, and it raises `RequestEntityTooLarge` (413) there. Flask's only part is overriding the property so Werkzeug gets the config value.

## Tests (`tests/test_request.py`)
- `tests/test_request.py:9-22`, `test_max_content_length`: sets the config to 50 (`:10`), posts a body larger than that, and checks that the 413 handler runs (`:17-22`).
- `tests/test_request.py:25-54`, `test_limit_config`:
  - `:26`: sets the config to 100.
  - `:32`: with no app context, the value is `None` (the Werkzeug default).
  - `:38`: inside an app context, the config value (100) is used.
  - `:43`: sets a per-request override of 90.
  - `:47` and `:52`: the override wins both outside and inside an app context.

## Docs and changelog (not code)
- `docs/config.rst:320-330` documents the setting, and `docs/config.rst:404` is a changelog note.
- `docs/patterns/fileuploads.rst:138` and `:144` show an example: `app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000`.
- `docs/web-security.rst:25` mentions it.
- `CHANGES.rst:83-84` covers the 3.1 per-request override, and `CHANGES.rst:1536` covers the original addition in 0.6.

Nothing else in `src/` or `tests/` refers to it. That includes `ConfigAttribute`: there is no `app.max_content_length` attribute.