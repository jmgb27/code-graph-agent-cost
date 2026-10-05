In this checkout, `DEFAULT_AUTO_FIELD` is read and validated in one place: `Options._get_default_pk_class()`. There is **no system check or warning** for it any more. The old `models.W042` check was removed in Django 6.0, and nothing in `django/` refers to `W042` now.

### 1. Global default
- `django/conf/global_settings.py:451`: `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`. This became the default in 6.0; before that it was `AutoField` and triggered W042 (see `docs/releases/6.0.txt:429-455`).

### 2. Per-app hook on `AppConfig`
- `django/apps/config.py:61-65`: `AppConfig.default_auto_field` is a `cached_property` that returns `settings.DEFAULT_AUTO_FIELD`.
- `django/apps/config.py:67-69`: `_is_default_auto_field_overridden` is True when a subclass has replaced the class attribute (`self.__class__.default_auto_field is not AppConfig.default_auto_field`). It is used only to choose the wording of error messages.

### 3. Where it is read and validated
`django/db/models/options.py:261-290`, `Options._get_default_pk_class()`:
- **:262-266**: `getattr(self.app_config, "default_auto_field", settings.DEFAULT_AUTO_FIELD)`. If the model has an app config, its value is used (which is the setting unless overridden). If not, the setting is used directly.
- **:267-274**: builds the "source" name used in errors: either `"<module>.<Class>.default_auto_field"` or `"DEFAULT_AUTO_FIELD"`.
- **:275-276**: an empty value or `None` raises `ImproperlyConfigured("... must not be empty.")`.
- **:277-284**: `import_string` failure raises `ImproperlyConfigured("... refers to the module '...' that could not be imported.")`.
- **:285-289**: a class that doesn't subclass `AutoField` raises `ValueError("Primary key '...' referred by ... must subclass AutoField.")`.

These checks run at model-class preparation time (`_prepare`), not as system checks.

**Only caller:** `django/db/models/options.py:331-334`. `_prepare()` calls it when a model has no explicit primary key and no parent link, then adds an auto-created `id` field. Auto-created M2M through models get their pk the same way; the tests at `tests/model_options/test_default_pk.py:114,123` cover this.

### 4. Per-app overrides in contrib (all set to `"django.db.models.AutoField"`)
These keep existing migrations stable now that the global default is `BigAutoField`:
- `django/contrib/admin/apps.py:10`
- `django/contrib/auth/apps.py:14`
- `django/contrib/contenttypes/apps.py:14`
- `django/contrib/flatpages/apps.py:6`
- `django/contrib/gis/apps.py:7`
- `django/contrib/redirects/apps.py:6`
- `django/contrib/sitemaps/apps.py:6`
- `django/contrib/sites/apps.py:11`

### 5. System checks and warnings
- No active check exists. The only W042 mentions are in the docs:
  - `docs/ref/checks.txt:456-458` marks W042 as "appeared in Django 3.2 - 5.2".
  - `docs/releases/6.0.txt:448-455` explains the removal and how to keep `AutoField`.

### 6. Tests
- `tests/model_options/apps.py:10,15,20,25`: test app configs overriding the value with `SmallAutoField`, `TextField` (not an auto field), `None`, and a nonexistent path.
- `tests/model_options/test_default_pk.py:13-123`: covers every validation branch above, for both the setting and the per-app attribute, plus M2M.
- `tests/apps/apps.py:38`: override set to `BigAutoField`.
- `tests/apps/tests.py:509-529`: tests `default_auto_field` resolution and `_is_default_auto_field_overridden` (True/False).

### 7. Other docs
- `docs/ref/settings.txt:1278-1296`
- `docs/ref/applications.txt:228-242`
- `docs/ref/models/fields.txt:545-546`
- `docs/topics/db/models.txt:286-288`
- `docs/intro/reusable-apps.txt:147-158`
- `docs/releases/3.2.txt:63-103`
- `docs/releases/3.2.1.txt:24`

Other `auto_field` matches, such as `Options.auto_field` in `options.py:145` and `fields/__init__.py:2913-2919`, are about the model's actual auto field instance, not this setting.