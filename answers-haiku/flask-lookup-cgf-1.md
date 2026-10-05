## MAX_CONTENT_LENGTH Configuration References

Based on my search, here are all the places where `MAX_CONTENT_LENGTH` is defaulted, read, or enforced:

### Source Code

**Default Value:**
- `src/flask/app.py:227` — Defaults to `None` in the `default_config` dictionary

**Read/Accessed:**
- `src/flask/wrappers.py:69` — Documented in the `max_content_length` property docstring as "Each request defaults to the :data:`MAX_CONTENT_LENGTH` config, which defaults to ``None``"
- `src/flask/wrappers.py:86` — Read from `current_app.config["MAX_CONTENT_LENGTH"]` in the `max_content_length` property getter

### Tests

**Configuration Used in Tests:**
- `tests/test_request.py:10` — Sets `app.config["MAX_CONTENT_LENGTH"] = 50`
- `tests/test_request.py:26` — Sets `app.config["MAX_CONTENT_LENGTH"] = 100`

The config value has a default of `None` (no limit enforced at Flask level), and is read at request time via the `Request.max_content_length` property which queries the app's config.