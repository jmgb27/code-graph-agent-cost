`MAX_CONTENT_LENGTH` is defaulted in one place and read in one place in Flask's source. Flask never enforces it itself: it passes the value to Werkzeug, which raises the 413.

## Source

**Default**
- `src/flask/app.py:227`: `"MAX_CONTENT_LENGTH": None` in `Flask.default_config`, so there is no limit by default.

**Read**
- `src/flask/wrappers.py:55`: `_max_content_length: int | None = None` stores a per-request override.
- `src/flask/wrappers.py:59-86`: the `Request.max_content_length` property overrides Werkzeug's. It resolves the value in this order:
  1. `:80-81`: the per-request override `self._max_content_length`, if set.
  2. `:83-84`: with no app context, Werkzeug's default (`super().max_content_length`, which is `None`).
  3. `:86`: otherwise `current_app.config["MAX_CONTENT_LENGTH"]`. This is the only line in the source that reads the config key.
- `src/flask/wrappers.py:88-90`: a setter so a view can set the limit for one request (added in 3.1).

**Enforcement**
- Werkzeug does it. Its request parsing reads `self.max_content_length`, which goes through Flask's override above, and raises `RequestEntityTooLarge` (413) when the body is too big. No Flask source raises or checks 413 directly. The only mention is the docstring at `src/flask/wrappers.py:62`.

## Tests
- `tests/test_request.py:9-22` (`test_max_content_length`) covers enforcement from start to finish:
  - `:10` sets the config to 50.
  - `:14` reads `request.form`, which triggers parsing.
  - `:17-19` registers a 413 error handler.
  - `:21-22` posts 150 bytes and checks that the handler's response comes back.
- `tests/test_request.py:25-54` (`test_limit_config`) covers how the value is resolved:
  - `:26` sets the config to 100.
  - `:32`: with no app context the value is `None`, Werkzeug's default.
  - `:38`: inside an app context the value is 100, from config.
  - `:43`: sets a per-request override of 90.
  - `:47` and `:52`: the override (90) wins both outside and inside an app context.

## Docs and changelog (not code, listed for completeness)
- `docs/config.rst:320` and `:330` define the config key; `:404` lists it under version changes.
- `docs/patterns/fileuploads.rst:138` and `:144` show example usage (`16 * 1000 * 1000`).
- `docs/web-security.rst:25`.
- `CHANGES.rst:83-84` (per-request override) and `CHANGES.rst:1536` (config key introduced in 0.6).