In this checkout, `DEFAULT_AUTO_FIELD` is defaulted in one place, read in two, and validated in one. There is no system check or warning for it any more.

## 1. Global default
- `django/conf/global_settings.py:451`: `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`.
- The project and app templates no longer set it. `docs/releases/6.0.txt:444-446` says those lines were removed, and a search of the `*.py-tpl` files found nothing.

## 2. Where it is read
- **`AppConfig.default_auto_field`**, `django/apps/config.py:61-65`: a `cached_property` that returns `settings.DEFAULT_AUTO_FIELD`. This is the per-app hook that subclasses override.
- **`AppConfig._is_default_auto_field_overridden`**, `django/apps/config.py:67-69`: true when the subclass's `default_auto_field` is not the base `AppConfig` property.
- **`Options._get_default_pk_class`**, `django/db/models/options.py:261-290`:
  - `:262-266` reads `app_config.default_auto_field`. If the model has no app config, it falls back to `settings.DEFAULT_AUTO_FIELD`.
  - `:267-274` picks the name used in error messages: `"<module>.<AppConfig>.default_auto_field"` when the app overrides it, otherwise `"DEFAULT_AUTO_FIELD"`.
- **The only caller** is `Options._prepare`, `django/db/models/options.py:332-334`. When a model has no primary key and no parent link, it builds the class with `pk_class(verbose_name="ID", primary_key=True, auto_created=True)` and adds it as `id`. Auto-created M2M through models also go through this path (covered by `tests/model_options/test_default_pk.py:114,123`).

## 3. Per-app overrides in `django.contrib`
All of these pin `default_auto_field = "django.db.models.AutoField"` so their existing migrations stay valid:
- `django/contrib/admin/apps.py:10`
- `django/contrib/auth/apps.py:14`
- `django/contrib/contenttypes/apps.py:14`
- `django/contrib/flatpages/apps.py:6`
- `django/contrib/gis/apps.py:7`
- `django/contrib/redirects/apps.py:6`
- `django/contrib/sitemaps/apps.py:6`
- `django/contrib/sites/apps.py:11`

Test app configs that override it:
- `tests/apps/apps.py:38` (BigAutoField)
- `tests/model_options/apps.py:10` (SmallAutoField), `:15` (TextField, invalid), `:20` (`None`), `:25` (nonexistent path)

## 4. Validation
Validation happens when the model class is built, not in a system check. `Options._get_default_pk_class` raises:
- `ImproperlyConfigured("<source> must not be empty.")` if the value is empty or `None` (`options.py:275-276`).
- `ImproperlyConfigured("<source> refers to the module '...' that could not be imported.")` if `import_string` fails (`options.py:277-284`).
- `ValueError("Primary key '...' referred by <source> must subclass AutoField.")` if the class isn't an `AutoField` subclass (`options.py:285-289`).

Tests for these cases are in `tests/model_options/test_default_pk.py:13-123` and `tests/apps/tests.py:509-529`.

## 5. System checks and warnings
- The **models.W042** warning ("Auto-created primary key used when not defining a primary key type") has been removed. Searching `django/` for `W042` and `_check_default_pk` finds nothing.
- It is only mentioned in docs:
  - `docs/ref/checks.txt:456-458`: "This check appeared in Django 3.2 - 5.2".
  - `docs/releases/6.0.txt:448-455`: explains that the default changed to `BigAutoField` and how to keep `AutoField`.

## Other docs that mention it
- `docs/ref/settings.txt:1278-1296` (the setting)
- `docs/ref/applications.txt:228-242` (`AppConfig.default_auto_field`)
- `docs/ref/models/fields.txt:545-546`
- `docs/topics/db/models.txt:286-288`
- `docs/intro/reusable-apps.txt:147-158`
- `docs/releases/3.2.txt:63-103` (where the setting was introduced)
- `docs/releases/3.2.1.txt:24`