In this checkout (Django 6.0 dev), there is no longer any system check or warning for `DEFAULT_AUTO_FIELD`. All validation happens when a model class is built, and a bad value raises an exception.

## Default value
- `django/conf/global_settings.py:451`: `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`. This was `AutoField` before 6.0; see `docs/releases/6.0.txt:429-454`.

## Where the setting is read
- `django/apps/config.py:61-65`: `AppConfig.default_auto_field` is a `cached_property` that returns `settings.DEFAULT_AUTO_FIELD`. This is how an app inherits the project setting.
- `django/apps/config.py:67-69`: `_is_default_auto_field_overridden` returns True when a subclass replaces the base `cached_property` with its own class attribute.
- `django/db/models/options.py:261-266`: `Options._get_default_pk_class()` reads `self.app_config.default_auto_field`. If the model has no app config, it falls back to `settings.DEFAULT_AUTO_FIELD`.
- `django/db/models/options.py:331-333`: `Options._prepare()` is the only caller. When a model has no primary key and no parent link, it instantiates the class as an auto-created `id` field. Auto-created M2M through models get their pk this way too.

## Per-app overrides (all set `"django.db.models.AutoField"` so existing migrations stay valid)
- `django/contrib/admin/apps.py:10`
- `django/contrib/auth/apps.py:14`
- `django/contrib/contenttypes/apps.py:14`
- `django/contrib/flatpages/apps.py:6`
- `django/contrib/gis/apps.py:7`
- `django/contrib/redirects/apps.py:6`
- `django/contrib/sitemaps/apps.py:6`
- `django/contrib/sites/apps.py:11`

## Validation (runtime exceptions, not system checks)
All of this is in `django/db/models/options.py:267-289`:
- **Lines 267-274:** these build the error "source" name. If the app overrides the value, the name is `<module>.<AppConfig>.default_auto_field`; otherwise it is `DEFAULT_AUTO_FIELD`.
- **Lines 275-276:** an empty value or `None` raises `ImproperlyConfigured("... must not be empty.")`.
- **Lines 277-283:** if `import_string` fails, it raises `ImproperlyConfigured("... refers to the module '...' that could not be imported.")`.
- **Lines 284-288:** a class that is not a subclass of `AutoField` raises `ValueError("Primary key '...' referred by ... must subclass AutoField.")`.

## The removed system check
- `docs/ref/checks.txt:456-458`: **models.W042** ("Auto-created primary key used when not defining a primary key type") is documented as "appeared in Django 3.2 - 5.2". It is not in `django/` anymore; grepping for `W042` finds only docs.
- `docs/releases/6.0.txt:444-454` explains why it was removed and how to keep `AutoField`.

## Tests covering this
- `tests/model_options/test_default_pk.py:13-123` tests the default value, and the nonexistent, non-auto and `None` cases for both the setting and the app attribute. It also covers a `BigAutoField` subclass and the M2M through-model pk.
- `tests/model_options/apps.py:10,15,20,25` define the fixture AppConfigs: `SmallAutoField`, `TextField`, `None`, and a nonexistent class.
- `tests/apps/tests.py:507-529` tests `default_auto_field` and `_is_default_auto_field_overridden`, using the fixture config at `tests/apps/apps.py:38`.

## Docs
The setting is also described in `docs/ref/settings.txt`, `docs/ref/applications.txt`, `docs/ref/models/fields.txt`, `docs/topics/db/models.txt`, `docs/intro/reusable-apps.txt`, and `docs/releases/3.2.txt` and `3.2.1.txt`. The app and project templates in `django/conf/` do not set it.