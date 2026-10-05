`MAX_CONTENT_LENGTH` is defaulted in one place and read in one place in Flask's source. Flask never checks the limit itself: it passes the value to Werkzeug, which raises the 413. Two tests cover it.

## Defaulted
- `src/flask/app.py:227`: `"MAX_CONTENT_LENGTH": None` in the app's default config, so there is no limit unless you set one.

## Read (`src/flask/wrappers.py`)
- `wrappers.py:55`: `_max_content_length: int | None = None` is a slot on `Request` for a per-request override.
- `wrappers.py:59-86`: the `Request.max_content_length` property overrides Werkzeug's version. It picks the value in this order:
  - `:80-81`: the per-request override, if one is set.
  - `:83-84`: with no app context, Werkzeug's default (`super().max_content_length`).
  - `:86`: otherwise, `current_app.config["MAX_CONTENT_LENGTH"]`.
- `wrappers.py:88-90`: a setter, so a view can do `request.max_content_length = N` (added in 3.1).

## Enforced
- The docstring at `wrappers.py:61-63` describes the enforcement, but the 413 `RequestEntityTooLarge` is raised inside Werkzeug's `Request`/form parser. Werkzeug calls `self.max_content_length`, which dispatches to Flask's property above. No Flask source file compares against the limit.

## Tests (`tests/test_request.py`)
- `test_request.py:9-22` (`test_max_content_length`): sets the config to 50 (`:10`), posts a form field of about 150 bytes, and checks that the 413 error handler runs (`:17-22`). This is the end-to-end enforcement test.
- `test_request.py:25-54` (`test_limit_config`):
  - `:26`: sets the config to 100.
  - `:32`: with no app context, the value is `None` (Werkzeug's default).
  - `:38`: inside an app context, the value is `100`, taken from the config.
  - `:43`: sets a per-request override of 90.
  - `:47`, `:52`: the override wins both outside and inside an app context.

## Other (outside source and tests)
- `CHANGES.rst:83-84` and `:1536` are changelog entries.
- I left out `docs/`, which also documents the setting (e.g. the config reference).