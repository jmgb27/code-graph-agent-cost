Based on my exploration of the codebase, here are all the places where `DEFAULT_AUTO_FIELD` is defaulted, read, overridden, or validated:

## Global Default
- **django/conf/global_settings.py:451** — Global setting default: `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`

## AppConfig Integration
- **django/apps/config.py:62-65** — `default_auto_field` cached property that reads from `settings.DEFAULT_AUTO_FIELD`
- **django/apps/config.py:68-69** — `_is_default_auto_field_overridden` property to check if app overrides the global setting

## Model Metadata Resolution & Validation
- **django/db/models/options.py:261-289** — `_get_default_pk_class()` method that:
  - Reads `default_auto_field` from app_config or falls back to `settings.DEFAULT_AUTO_FIELD` (lines 262-266)
  - Determines the source for error messages (lines 267-274)
  - Validates the setting is not empty (lines 275-276)
  - Imports the field class and validates it exists (lines 277-284)
  - Validates it's a subclass of AutoField (lines 285-289)

## Per-App Overrides
- **django/contrib/admin/apps.py:10** — AdminConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/auth/apps.py:14** — AuthConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/contenttypes/apps.py:14** — ContentTypesConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/flatpages/apps.py:6** — FlatPagesConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/gis/apps.py:7** — GISConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/redirects/apps.py:6** — RedirectsConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/sites/apps.py:11** — SitesConfig overrides to `"django.db.models.AutoField"`
- **django/contrib/sitemaps/apps.py:6** — SitemapsConfig overrides to `"django.db.models.AutoField"`

## Test Apps
- **tests/model_options/apps.py:10, 15, 20, 25** — Test app configs with various overrides and edge cases
- **tests/apps/apps.py:38** — Test app override to `"django.db.models.BigAutoField"`

## Tests (Validation Scenarios)
- **tests/model_options/test_default_pk.py:13-128** — Comprehensive tests covering:
  - Default value (line 13)
  - Nonexistent field class (lines 21-43)
  - Non-AutoField subclass (lines 45-66)
  - None/empty value (lines 68-85)
  - Valid custom subclasses (lines 88-102)
  - App-level overrides (lines 104-128)

There are **no explicit system checks** in `django/core/checks/` for DEFAULT_AUTO_FIELD. Validation occurs at the point of use (model creation) in `_get_default_pk_class()`.