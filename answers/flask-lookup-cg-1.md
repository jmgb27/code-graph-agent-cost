`MAX_CONTENT_LENGTH` is defaulted in one place and read in one place in Flask's source. Flask never checks the limit itself: Werkzeug does, by reading the `max_content_length` property that Flask overrides.

## Source

**Default**
- `src/flask/app.py:227`: `"MAX_CONTENT_LENGTH": None` is set in the app's `default_config`, so there is no limit by default.

**Read** (`Request.max_content_length` property in `src/flask/wrappers.py`)
- `src/flask/wrappers.py:55`: the per-request override starts as `_max_content_length: int | None = None`.
- `src/flask/wrappers.py:59-86`: the property checks three things in order:
  - `:80-81`: if a per-request override has been set, it is returned.
  - `:83-84`: if there is no app context, it falls back to Werkzeug's own default (`super().max_content_length`).
  - `:86`: otherwise it returns `current_app.config["MAX_CONTENT_LENGTH"]`. **This is the only line in Flask's source that reads the config key.**
- `src/flask/wrappers.py:88-90`: the setter stores a per-request override in `_max_content_length`.

**Enforcement**
- Nothing under `src/flask/` checks the limit or raises the 413 error. Werkzeug's base `Request` does that when it builds the input stream or parses form data: it reads `self.max_content_length`, which resolves to Flask's override above. The docstring at `src/flask/wrappers.py:61-67` describes this behaviour.

## Tests (`tests/test_request.py`)
- `:9-22` `test_max_content_length`: sets the config to 50 at `:10` and posts about 150 bytes. It asserts that the 413 handler at `:17-19` runs (`rv.data == b"42"`, `:22`), which tests enforcement end to end.
- `:25-54` `test_limit_config`:
  - `:26`: sets the config to 100.
  - `:32`: with no app context, the value is `None` (Werkzeug's default).
  - `:38`: inside an app context, the value comes from the config (`100`).
  - `:43`: sets a per-request override of `90`.
  - `:47` and `:52`: the override wins both outside and inside an app context.

## Docs and changelog (not code)
- `docs/config.rst:320` and `:330`: the config value's definition, with a note on the per-request property.
- `docs/config.rst:404`: listed in the config version-history notes.
- `docs/patterns/fileuploads.rst:138` and `:144`: an example setting it to `16 * 1000 * 1000`.
- `docs/web-security.rst:25`: mentioned as a way to limit resource use.
- `CHANGES.rst:83-84`: 3.1 added the per-request override.
- `CHANGES.rst:1536`: the change that first introduced the config value.