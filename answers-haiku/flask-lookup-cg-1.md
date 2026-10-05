Here are all the places where `MAX_CONTENT_LENGTH` is defaulted, read, or enforced:

## Source Code

**Default value:**
- `src/flask/app.py:227` — Default initialized to `None`

**Reading/Accessing the config:**
- `src/flask/wrappers.py:86` — Property getter reads `current_app.config["MAX_CONTENT_LENGTH"]`

**Documentation:**
- `src/flask/wrappers.py:69` — Docstring mentions the default behavior

**Property definition:**
- `src/flask/wrappers.py:60` — `max_content_length` property definition
- `src/flask/wrappers.py:88-90` — Property setter for per-request override

## Tests

**Setting the config value:**
- `tests/test_request.py:10` — `test_max_content_length()` sets `app.config["MAX_CONTENT_LENGTH"] = 50`
- `tests/test_request.py:26` — `test_limit_config()` sets `app.config["MAX_CONTENT_LENGTH"] = 100`

**Reading and testing behavior:**
- `tests/test_request.py:32` — Reads `r.max_content_length` (expects `None` outside app context)
- `tests/test_request.py:38` — Reads `r.max_content_length` in app context (expects configured value)
- `tests/test_request.py:43` — Sets per-request override: `r.max_content_length = 90`
- `tests/test_request.py:47, 52` — Reads overridden value to verify per-request override works