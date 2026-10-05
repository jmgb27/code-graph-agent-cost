`DEFAULT_AUTO_FIELD` is used in only a few places in `django/`, and there is no longer any system check for it. The old `models.W042` warning was removed in Django 6.0. Invalid values are now caught when a model class is prepared, where Django raises `ImproperlyConfigured` or `ValueError`.

## 1. Where the default is set
- `django/conf/global_settings.py:451` sets `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`.
- `docs/releases/6.0.txt:429-455` covers the switch from `AutoField` to `BigAutoField`. It also says the matching lines were removed from the `startproject` and `startapp` templates, so no `*-tpl` file contains the setting any more.

## 2. Where the setting is read (resolution chain)
- `django/apps/config.py:61-65`: `AppConfig.default_auto_field` is a `cached_property` that returns `settings.DEFAULT_AUTO_FIELD`. This is the fallback when an app doesn't set its own value.
- `django/apps/config.py:67-69`: `AppConfig._is_default_auto_field_overridden` checks whether the subclass replaced the base `default_auto_field` with its own value.
- `django/db/models/options.py:261-290`: `Options._get_default_pk_class()`
  - `:262-266` uses `app_config.default_auto_field`, falling back to `settings.DEFAULT_AUTO_FIELD` when the model has no app config.
  - `:267-274` picks the name used in error messages: `"<module>.<AppConfig>.default_auto_field"` if the app overrides it, otherwise `"DEFAULT_AUTO_FIELD"`.
- `django/db/models/options.py:331-334`: the only caller. `Options._prepare()` calls it when a model has no primary key (and no parent link to promote), then adds the auto-created `id` field.

## 3. Per-app overrides (built-in contrib apps all pin `AutoField`)
- `django/contrib/admin/apps.py:10`
- `django/contrib/auth/apps.py:14`
- `django/contrib/contenttypes/apps.py:14`
- `django/contrib/flatpages/apps.py:6`
- `django/contrib/gis/apps.py:7`
- `django/contrib/redirects/apps.py:6`
- `django/contrib/sitemaps/apps.py:6`
- `django/contrib/sites/apps.py:11`

Overrides used by the tests:
- `tests/apps/apps.py:38` sets `BigAutoField`.
- `tests/model_options/apps.py:10`, `:15`, `:20`, `:25` set `SmallAutoField`, `TextField`, `None` and `NonexistentAutoField` respectively.

## 4. Validation (runtime errors, not system checks)
All of this happens in `django/db/models/options.py`:
- `:275-276`: an empty or `None` value raises `ImproperlyConfigured("<source> must not be empty.")`.
- `:277-284`: a path that can't be imported raises `ImproperlyConfigured("<source> refers to the module '...' that could not be imported.")`.
- `:285-289`: a class that isn't an `AutoField` subclass raises `ValueError("Primary key '...' referred by <source> must subclass AutoField.")`. `AutoField` is defined at `django/db/models/fields/__init__.py:2957`.

## 5. System checks and warnings
- No check currently exists: there is no `W042` or `_check_default_pk` in `django/`.
- `docs/ref/checks.txt:456-458` lists **models.W042** ("Auto-created primary key used when not defining a primary key type…") as a historical check, marked "appeared in Django 3.2 - 5.2".
- `docs/releases/6.0.txt:448-450` refers to W042 when explaining how the migration affects existing projects.

## 6. Tests covering this behaviour
- `tests/model_options/test_default_pk.py:13-123` covers the default value, nonexistent, non-auto and `None` values (both as the setting and as an app override), valid overrides, a `BigAutoField` subclass, and M2M through-tables.
- `tests/apps/tests.py:509-529` covers `AppConfig.default_auto_field` and `_is_default_auto_field_overridden`, with and without an app override.

## 7. Other docs mentioning it
`docs/ref/settings.txt`, `docs/ref/applications.txt`, `docs/ref/models/fields.txt`, `docs/topics/db/models.txt`, `docs/intro/reusable-apps.txt`, `docs/releases/3.2.txt`, `docs/releases/3.2.1.txt`.