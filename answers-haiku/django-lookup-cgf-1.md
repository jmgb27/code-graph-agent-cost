## Summary: DEFAULT_AUTO_FIELD Usage

Here are all the places where `DEFAULT_AUTO_FIELD` is defaulted, read, overridden per app, or validated:

### Default Definition
- **django/conf/global_settings.py:451** — `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"` (global default)

### Reading / Accessing
- **django/apps/config.py:65** — `return settings.DEFAULT_AUTO_FIELD` (in `default_auto_field` cached property)
- **django/db/models/options.py:265** — `settings.DEFAULT_AUTO_FIELD` (fallback in `_get_default_pk_class()`)

### Per-App Overrides (Contrib Apps)
- **django/contrib/admin/apps.py:10** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/auth/apps.py:14** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/contenttypes/apps.py:14** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/flatpages/apps.py:6** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/gis/apps.py:7** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/redirects/apps.py:6** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/sites/apps.py:11** — `default_auto_field = "django.db.models.AutoField"`
- **django/contrib/sitemaps/apps.py:6** — `default_auto_field = "django.db.models.AutoField"`

### Override Detection
- **django/apps/config.py:69** — `_is_default_auto_field_overridden` property (checks if an app overrode the default)

### Validation & Error Messages
- **django/db/models/options.py:261-290** — `_get_default_pk_class()` method that:
  - **Line 262-266:** Retrieves app's `default_auto_field` or falls back to `settings.DEFAULT_AUTO_FIELD`
  - **Line 267-274:** Determines the error message source (app-specific or global setting)
  - **Line 275-276:** Validates the setting is not empty
  - **Line 277-284:** Validates the class path can be imported
  - **Line 285-288:** Validates the class is a subclass of `AutoField`

### Primary Key Field Creation
- **django/db/models/options.py:332-334** — Calls `_get_default_pk_class()` to create the default primary key field when a model has no explicit primary key defined