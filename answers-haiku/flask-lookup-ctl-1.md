Here are all the references to `MAX_CONTENT_LENGTH` in source and tests:

**Source code:**
- `src/flask/app.py:227` — Default value set to None
- `src/flask/wrappers.py:69` — Documentation comment mentioning default behavior
- `src/flask/wrappers.py:86` — Reading/retrieving the config value from current_app.config

**Tests:**
- `tests/test_request.py:10` — Config value set to 50
- `tests/test_request.py:26` — Config value set to 100

The documentation references (CHANGES.rst, docs/config.rst, docs/web-security.rst, docs/patterns/fileuploads.rst) describe the feature but don't contain active enforcement code.