Here's a complete map of every place `DEFAULT_AUTO_FIELD` is referenced in the codebase:

## Setting Definition & Default
- **django/conf/global_settings.py:451** — Default value set to `"django.db.models.BigAutoField"`

## Reading the Setting

### Global/App-level reading:
- **django/apps/config.py:65** — Cached property that returns `settings.DEFAULT_AUTO_FIELD`

### With app config override logic:
- **django/db/models/options.py:265** — Reads using `getattr(self.app_config, "default_auto_field", settings.DEFAULT_AUTO_FIELD)`
- **django/db/models/options.py:267** — Checks if app config override exists via `_is_default_auto_field_overridden`
- **django/db/models/options.py:274** — Sets source string to `"DEFAULT_AUTO_FIELD"` when not overridden

## Validation & Error Handling
All in **django/db/models/options.py:261-290** (`_get_default_pk_class` method):
- **Line 275-276** — Validates it's not empty; raises `ImproperlyConfigured: "{source} must not be empty."`
- **Line 278-284** — Validates it can be imported; raises `ImproperlyConfigured` if ImportError
- **Line 285-289** — Validates it's a subclass of `AutoField`; raises `ValueError` if not

## Usage (Instantiation)
- **django/db/models/options.py:332** — Creates auto-generated pk field via `pk_class = self._get_default_pk_class()`

## Tests
**tests/model_options/test_default_pk.py:**
- Lines 21, 45, 68, 88, 96, 105, 113, 122 — `@override_settings(DEFAULT_AUTO_FIELD=...)`
- Tests cover: nonexistent module, non-AutoField subclass, None value, valid custom subclass, app config override priority

**tests/apps/tests.py:**
- Lines 509, 521 — `@override_settings(DEFAULT_AUTO_FIELD=...)`
- Tests for app-level override detection vs global setting