Based on my search of the codebase, here are all the places where `MAX_CONTENT_LENGTH` is defaulted, read, or enforced:

## **Defaulted (set to default value):**
- **src/flask/app.py:227** — Default configuration value set to `None` in `default_config` dict

## **Read (accessed/used):**
- **src/flask/wrappers.py:86** — Read from `current_app.config["MAX_CONTENT_LENGTH"]` in the `max_content_length` property getter
- **tests/test_request.py:10** — Test sets config value (`app.config["MAX_CONTENT_LENGTH"] = 50`)
- **tests/test_request.py:26** — Test sets config value (`app.config["MAX_CONTENT_LENGTH"] = 100`)
- **tests/test_request.py:38** — Test reads the value via property getter (assertion: `assert r.max_content_length == 100`)

## **Documentation/References:**
- **src/flask/wrappers.py:69** — Docstring mentions `MAX_CONTENT_LENGTH` config
- **docs/config.rst:320** — Configuration documentation entry
- **docs/config.rst:404** — Version history note (versionadded: 0.6)
- **docs/web-security.rst:25** — Security documentation reference
- **docs/patterns/fileuploads.rst:138** — Example usage in file upload patterns
- **docs/patterns/fileuploads.rst:144** — Example setting the config
- **CHANGES.rst:84** — Changelog entry about per-request configuration capability
- **CHANGES.rst:1536** — Changelog entry about initial introduction of the config

**Note:** The actual enforcement of the limit happens in Werkzeug, not in Flask's source code. Flask only provides the configuration option and the property to access it.