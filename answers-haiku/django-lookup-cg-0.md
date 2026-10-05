Based on my exploration, here's a comprehensive list of every place where `DEFAULT_AUTO_FIELD` is defaulted, read, overridden, or validated:

## **DEFAULT_AUTO_FIELD Locations**

### **1. Default Setting Definition**
- **django/conf/global_settings.py:451** — Defines `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`

### **2. App Configuration**
- **django/apps/config.py:62-65** — `AppConfig.default_auto_field` (cached property) reads `settings.DEFAULT_AUTO_FIELD`
- **django/apps/config.py:68-69** — `AppConfig._is_default_auto_field_overridden` property checks if the class-level attribute overrides the base implementation

### **3. Model Primary Key Resolution**
- **django/db/models/options.py:261-290** — `Options._get_default_pk_class()` method:
  - **Line 262-266:** Reads from `app_config.default_auto_field` (if app overrides it) or `settings.DEFAULT_AUTO_FIELD`
  - **Line 267-274:** Determines the source (app config or settings)
  - **Line 275-276:** **Validation:** Checks that the value is not empty
  - **Line 277-284:** **Validation:** Attempts to import the class, raises `ImproperlyConfigured` if import fails
  - **Line 285-289:** **Validation:** Verifies the class is a subclass of `AutoField`, raises `ValueError` if not

### **4. Tests**
- **tests/model_options/test_default_pk.py:**
  - Line 21-26: `test_default_auto_field_setting_nonexistent()` — tests import error handling
  - Line 45-50: `test_default_auto_field_setting_non_auto()` — tests AutoField subclass validation
  - Line 68-71: `test_default_auto_field_setting_none()` — tests empty value check
  - Line 89: `test_default_auto_field_setting()` — override settings test
  - Line 96, 105, 113, 122: Various tests with different `DEFAULT_AUTO_FIELD` values

- **tests/apps/tests.py:**
  - Line 508-509: Tests with `DEFAULT_AUTO_FIELD="django.db.models.SmallAutoField"`
  - Line 521: Tests with `DEFAULT_AUTO_FIELD="django.db.models.SmallAutoField"`

### **Summary**

**Defaulting:**
- django/conf/global_settings.py:451

**Reading/Getting:**
- django/apps/config.py:65 (via cached_property)
- django/db/models/options.py:265

**Overriding (per app):**
- django/apps/config.py:62 (class attribute on AppConfig subclasses)
- django/apps/config.py:68-69 (detection mechanism)

**Validation:**
- django/db/models/options.py:275-289 (empty check, import check, AutoField subclass check)