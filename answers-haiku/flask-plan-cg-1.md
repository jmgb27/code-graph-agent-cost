Based on the CodeGraph context, here's the complete plan for adding per-blueprint `max_content_length` override:

## Files to Modify

### Core Implementation

1. **`src/flask/wrappers.py:max_content_length` property (lines 59–106)**
   - Modify getter to check blueprint-specific override before falling back to app config
   - Priority order: per-request → blueprint-specific → app-wide config → werkzeug default
   - Use `self.blueprint` property (already exists at line 181) to look up the blueprint name

2. **`src/flask/scaffold.py` or `src/flask/sansio/scaffold.py`** (Blueprint/Scaffold class)
   - Add `max_content_length` attribute to Blueprint class initialization
   - Allow setting via blueprint constructor parameter or attribute assignment
   - Similar pattern already exists for other Flask configurations

3. **`src/flask/app.py` or `src/flask/sansio/app.py`** (Flask app class, `register_blueprint()` method around line 570 in sansio/app.py)
   - Store blueprint-level `max_content_length` values in app config (e.g., under `_blueprint_max_content_length` dict)
   - Extract blueprint's max_content_length during registration and store lookup by blueprint name

### Testing

4. **`tests/test_basic.py`** (extends existing request tests around lines 500–515)
   - Test blueprint max_content_length overrides app-wide config
   - Test per-request override still wins over blueprint config
   - Test multiple blueprints with different limits

5. **`tests/test_helpers.py`** or **new test file** (for blueprint configuration tests)
   - Test setting max_content_length on blueprint definition
   - Test unset blueprint falls back to app config
   - Test behavior with nested blueprints

## Supporting References

- `src/flask/wrappers.py:181–179` — `blueprint` property (read endpoint to extract blueprint name)
- `src/flask/wrappers.py:75–110` — existing `_max_content_length` pattern to follow
- `src/flask/helpers.py:645` — `_split_blueprint_path` helper (already imported at wrappers.py:12)
- `src/flask/sansio/app.py:570` — `register_blueprint()` where registration logic lives