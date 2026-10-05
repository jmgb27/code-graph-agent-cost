Here's a comprehensive list of every place where `DEFAULT_AUTO_FIELD` is defaulted, read, overridden per app, or validated:

## Default Value
- **django/conf/global_settings.py:451** — Sets default to `"django.db.models.BigAutoField"`

## Reading/Retrieval
- **django/apps/config.py:65** — `AppConfig.default_auto_field` cached property reads the setting value
- **django/db/models/options.py:265** — `_get_default_pk_class()` method reads setting as fallback when app config doesn't override it

## App-Level Override Detection
- **django/apps/config.py:68-69** — `_is_default_auto_field_overridden` property detects if an app config class overrides the default

## Validation/Error Handling (django/db/models/options.py:_get_default_pk_class)
- **Line 275-276** — Validates that pk_class_path is not empty; raises `ImproperlyConfigured` if empty
- **Line 278-284** — Validates the class path can be imported; raises `ImproperlyConfigured` if import fails
- **Line 285-289** — Validates the imported class subclasses `AutoField`; raises `ValueError` if not

## Test Coverage
**tests/model_options/test_default_pk.py:**
- **Line 21-31** — Tests nonexistent module reference (ImproperlyConfigured)
- **Line 45-54** — Tests non-AutoField class (ValueError)
- **Line 68-74** — Tests None value (ImproperlyConfigured)
- **Line 88-93** — Tests SmallAutoField setting
- **Line 95-102** — Tests custom BigAutoField subclass
- **Line 105-110** — Tests app-level override
- **Line 113-128** — Tests M2M models respecting the setting

**tests/apps/tests.py:**
- **Line 507-529** — Tests app config override detection vs. setting-based default