Based on the CodeGraph search and grep results, here are all the places where MAX_CONTENT_LENGTH is defaulted, read, or enforced in source and tests:

**Source Code:**

1. **src/flask/app.py:227** — Default value initialization
   - Sets the default configuration: `"MAX_CONTENT_LENGTH": None`

2. **src/flask/wrappers.py:60** — Property definition (reads the config)
   - `max_content_length` property getter that reads the config value

3. **src/flask/wrappers.py:86** — Reading the config value
   - `return current_app.config["MAX_CONTENT_LENGTH"]`

4. **src/flask/wrappers.py:69** — Reference in docstring
   - Documents that requests default to the `MAX_CONTENT_LENGTH` config

**Tests:**

1. **tests/test_request.py:10** — Sets config in test
   - `app.config["MAX_CONTENT_LENGTH"] = 50`

2. **tests/test_request.py:26** — Sets config in test
   - `app.config["MAX_CONTENT_LENGTH"] = 100`

The enforcement is handled by Werkzeug's underlying `max_content_length` property (accessed via the Flask `Request` wrapper), which raises a 413 error when the limit is exceeded.