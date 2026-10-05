Based on my exploration of the codebase, here's my complete plan for adding a per-blueprint `max_content_length` override:

## Files to Change

### 1. **src/flask/sansio/blueprints.py** — Blueprint class definition
- **Line 174-186**: Add `max_content_length: int | None = None` parameter to `Blueprint.__init__()`
- **After line 209**: Store as `self.max_content_length = max_content_length`
- **Line 41-86**: Update `BlueprintSetupState.__init__()` to extract `max_content_length` from options and blueprint (similar to how it handles `subdomain`, `url_prefix`)
- **After line 56**: Store in setup state as `self.max_content_length`

### 2. **src/flask/blueprints.py** — Flask-specific Blueprint wrapper
- **Line 19-43**: Update `Blueprint.__init__()` signature to accept and pass through `max_content_length` parameter to `super().__init__()`

### 3. **src/flask/wrappers.py** — Request.max_content_length property
- **Line 60-86**: Update `max_content_length` property getter to:
  1. Check `self._max_content_length` (request-level override) ✓ already done
  2. Check if request has a blueprint and if that blueprint has `max_content_length` set → look up in `current_app.blueprints[self.blueprint].max_content_length`
  3. Fall back to `current_app.config["MAX_CONTENT_LENGTH"]` ✓ already done

### 4. **src/flask/sansio/app.py** — register_blueprint docstring
- **Line 570-595**: Update docstring to document the `max_content_length` option that can be passed during registration

## Tests to Add

Create tests in **tests/test_request.py** or **tests/test_blueprints.py**:

1. **Test blueprint max_content_length override wins over app config**
   - Create blueprint with `max_content_length=1000`
   - Register it on app with `MAX_CONTENT_LENGTH=2000`
   - Request to blueprint route should respect `1000` limit

2. **Test request-level override wins over blueprint override**
   - Set blueprint `max_content_length=1000`
   - Set request-level override to `500`
   - Request should use `500`

3. **Test blueprint parameter passed at registration time**
   - Register blueprint with `max_content_length=800` in `register_blueprint()` call
   - Should override blueprint's default

4. **Test request without blueprint uses app config**
   - Request to non-blueprint route with `MAX_CONTENT_LENGTH=2000`
   - Should use app config value

5. **Test None values (no override)**
   - Blueprint with `max_content_length=None`
   - Should fall back to app config

6. **Test nested blueprint max_content_length**
   - Child blueprint with different limit
   - Should respect child blueprint's limit when request is to child blueprint route

## Reference Points

- Current max_content_length property: **src/flask/wrappers.py:60-86**
- Blueprint registration flow: **src/flask/sansio/blueprints.py:273-335** (register method) and **src/flask/sansio/app.py:570-595** (register_blueprint method)
- Blueprints stored in: **src/flask/sansio/blueprints.py:319** (`app.blueprints[name] = self`)
- Blueprint name from request: **src/flask/wrappers.py:162-178** (`blueprint` property)
- BlueprintSetupState config extraction: **src/flask/sansio/blueprints.py:41-86** (pattern to follow for subdomain, url_prefix, etc.)