I found every place `DEFAULT_AUTO_FIELD` is handled. Most of it runs through one method, `Options._get_default_pk_class`. The `models.W042` warning no longer exists in the code; only the docs mention it.

## Default value
- `django/conf/global_settings.py:451`: `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`. This is the only default. Nothing under `django/conf/` sets it, so the project and app templates don't either.

## Where it is read, and the per-app override
- `django/apps/config.py:61-65`: `AppConfig.default_auto_field` is a `cached_property` that returns `settings.DEFAULT_AUTO_FIELD`.
- `django/apps/config.py:67-69`: `_is_default_auto_field_overridden` returns True when a subclass replaces the class attribute (`self.__class__.default_auto_field is not AppConfig.default_auto_field`).
- `django/db/models/options.py:261-290`: `Options._get_default_pk_class()` does the resolving and checking:
  - **Lines 262-266:** reads `app_config.default_auto_field`, falling back to `settings.DEFAULT_AUTO_FIELD` when there is no app config.
  - **Lines 267-274:** picks the name used in error messages: `"<module>.<AppConfig qualname>.default_auto_field"` if the app overrides it, otherwise `"DEFAULT_AUTO_FIELD"`.
- `django/db/models/options.py:331-334`: `_prepare()` is the only caller. When a model has no primary key and no parent link, it builds `pk_class(verbose_name="ID", primary_key=True, auto_created=True)` and adds it as `id`. Auto-created M2M through models get their primary key this way too, which the tests confirm.

## Validation (these raise errors; none are system checks)
All in `django/db/models/options.py`:
- **Line 275-276:** an empty value raises `ImproperlyConfigured(f"{source} must not be empty.")`.
- **Lines 277-284:** if `import_string` fails, it raises `ImproperlyConfigured("{source} refers to the module '…' that could not be imported.")`.
- **Lines 285-289:** if the class doesn't subclass `AutoField`, it raises `ValueError("Primary key '…' referred by {source} must subclass AutoField.")`.

## Built-in per-app overrides
These contrib apps pin `default_auto_field = "django.db.models.AutoField"` so their migrations stay stable:
- `django/contrib/admin/apps.py:10`
- `django/contrib/auth/apps.py:14`
- `django/contrib/contenttypes/apps.py:14`
- `django/contrib/flatpages/apps.py:6`
- `django/contrib/gis/apps.py:7`
- `django/contrib/redirects/apps.py:6`
- `django/contrib/sitemaps/apps.py:6`
- `django/contrib/sites/apps.py:11`

## System checks and warnings
- **No active check.** Searching the repo for `W042`, "Auto-created primary key" and `_check_default_pk` finds nothing outside the docs.
- `docs/ref/checks.txt:456-458` lists **models.W042** ("Auto-created primary key used when not defining a primary key type…") as appearing only in Django 3.2 - 5.2. It was removed when the default became `BigAutoField` (`docs/releases/6.0.txt:429-454`).

## Tests
- `tests/model_options/apps.py:10,15,20,25`: test app configs that override with `SmallAutoField`, `TextField` (not an auto field), `None` and a nonexistent path.
- `tests/model_options/test_default_pk.py:13-123`: covers the default value, each error path for both the setting and the app override, subclasses of `BigAutoField`, and M2M through models.
- `tests/apps/apps.py:38` and `tests/apps/tests.py:509-529`: test `AppConfig.default_auto_field` and `_is_default_auto_field_overridden`.

## Docs
- `docs/ref/settings.txt:1278-1296`
- `docs/ref/applications.txt:228-242`
- `docs/topics/db/models.txt:286-288`
- `docs/ref/models/fields.txt:545-546`
- `docs/intro/reusable-apps.txt:147-158`
- `docs/releases/3.2.txt:63-103`
- `docs/releases/3.2.1.txt:24`

Code that uses `_meta.auto_field` (for example `fields/__init__.py:2913-2919` and admin) tracks a model's actual auto field instance, not this setting, so I left it out.