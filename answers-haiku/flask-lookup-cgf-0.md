Based on the codebase analysis, here are all the places where `MAX_CONTENT_LENGTH` config value is defaulted, read, or enforced:

## Default Definition
- **src/flask/app.py:227** — Default value set to `None` in the `default_config` class dictionary

## Property Definition & Reading
- **src/flask/wrappers.py:60-86** — `Request.max_content_length` property that reads from config
  - Line 60: Property definition starts
  - Line 69: Docstring references `:data:`MAX_CONTENT_LENGTH` config`
  - Line 86: Returns `current_app.config["MAX_CONTENT_LENGTH"]`

## Test Enforcement
- **tests/test_request.py:10** — `test_max_content_length()` sets `MAX_CONTENT_LENGTH` to 50
- **tests/test_request.py:26** — `test_limit_config()` sets `MAX_CONTENT_LENGTH` to 100

## Documentation References
- **docs/config.rst:320** — Config documentation for MAX_CONTENT_LENGTH
- **docs/config.rst:404** — Another config reference
- **docs/web-security.rst:25** — Security documentation references MAX_CONTENT_LENGTH
- **docs/patterns/fileuploads.rst:138, 144** — File upload pattern examples