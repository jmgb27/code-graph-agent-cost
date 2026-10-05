The `models.W042` system check (for a model relying on an auto-created primary key) no longer exists in this checkout. Settings that point to an invalid `DEFAULT_AUTO_FIELD` value are now caught by exceptions raised when a model class is built, not by a system check.

## Global default
- `django/conf/global_settings.py:451`: `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`. The release notes say the default became `BigAutoField` in 6.0 and that the matching lines were removed from the project and app templates (`docs/releases/6.0.txt:429-455`).

## Per-app default and override detection (`AppConfig`)
- `django/apps/config.py:61-65`: `AppConfig.default_auto_field` is a `cached_property` that returns `settings.DEFAULT_AUTO_FIELD`. This is the fallback when an app doesn't override it.
- `django/apps/config.py:67-69`: `_is_default_auto_field_overridden` checks whether a subclass has redefined the attribute (`self.__class__.default_auto_field is not AppConfig.default_auto_field`). It is only used to name the source in error messages.

## Where it's read and validated
- `django/db/models/options.py:261-290`: `Options._get_default_pk_class()` does all of the reading and validation.
  - **Lines 262-266:** reads `app_config.default_auto_field`, falling back to `settings.DEFAULT_AUTO_FIELD` when there's no app config.
  - **Lines 267-274:** builds the name used in error messages: either `"<module>.<ConfigClass>.default_auto_field"` or `"DEFAULT_AUTO_FIELD"`.
  - **Lines 275-276:** an empty or `None` value raises `ImproperlyConfigured("... must not be empty.")`.
  - **Lines 277-284:** an import failure raises `ImproperlyConfigured("... refers to the module '...' that could not be imported.")`.
  - **Lines 285-289:** a class that isn't an `AutoField` subclass raises `ValueError("Primary key '...' referred by ... must subclass AutoField.")`. `BigAutoField` and `SmallAutoField` pass because of `AutoFieldMeta.__subclasscheck__` (`django/db/models/fields/__init__.py:2925-2957`).
- `django/db/models/options.py:331-334`: the only caller. `Options._prepare()` calls it when a model has no primary key and no parent link, then adds `id = pk_class(verbose_name="ID", primary_key=True, auto_created=True)`. Auto-created M2M through models go through the same path.

## Contrib apps that override it
Each of these sets `default_auto_field = "django.db.models.AutoField"` to keep its existing migrations stable:
- `django/contrib/admin/apps.py:10`
- `django/contrib/auth/apps.py:14`
- `django/contrib/contenttypes/apps.py:14`
- `django/contrib/flatpages/apps.py:6`
- `django/contrib/gis/apps.py:7`
- `django/contrib/redirects/apps.py:6`
- `django/contrib/sitemaps/apps.py:6`
- `django/contrib/sites/apps.py:11`

## System checks and warnings
- **`models.W042`:** not in the code any more. `docs/ref/checks.txt:456-458` lists it as "This check appeared in Django 3.2 - 5.2", and `docs/releases/6.0.txt:448-450` explains why it was dropped.
- **Nothing else checks the setting.** No other system check references `DEFAULT_AUTO_FIELD` or `default_auto_field`.

## Tests
- `tests/model_options/apps.py:10,15,20,25`: per-app overrides set to `SmallAutoField`, `TextField` (not an auto field), `None` and a nonexistent class.
- `tests/model_options/test_default_pk.py:13-123`: covers the default value, the nonexistent/non-auto/`None` cases for both the setting and the app attribute, a `BigAutoField` subclass, and M2M through models.
- `tests/apps/apps.py:38` and `tests/apps/tests.py:509-529`: the `AppConfig` property and `_is_default_auto_field_overridden`.

## Docs
- `docs/ref/settings.txt:1278-1296` (the setting)
- `docs/ref/applications.txt:228-242` (the `AppConfig` attribute)
- `docs/topics/db/models.txt:286-288`
- `docs/ref/models/fields.txt:545-546`
- `docs/intro/reusable-apps.txt:147-158`
- `docs/releases/3.2.txt:63-103`
- `docs/releases/3.2.1.txt:24`