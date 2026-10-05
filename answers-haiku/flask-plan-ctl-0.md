Now I have a clear picture of the codebase. Here's the complete plan for adding per-blueprint max_content_length override:

## Plan: Per-Blueprint max_content_length Override

### Files to Modify:

**1. src/flask/sansio/blueprints.py**
- Line 174-186: Add `max_content_length: int | None = None` parameter to `Blueprint.__init__()`
- Line 210: Add `self.max_content_length = max_content_length` attribute assignment
- Line 273-336: In `Blueprint.register()` method, store the blueprint's max_content_length in the app's override registry (need to create this registry first)

**2. src/flask/blueprints.py**
- Line 19-43: Add `max_content_length: int | None = None` parameter to `Blueprint.__init__()`
- Line 32-43: Pass it to `super().__init__()`

**3. src/flask/sansio/app.py**
- Line 410: Add new dict initialization: `self.blueprint_max_content_length: dict[str, int | None] = {}`
- Line 273-336 in `Blueprint.register()`: When registering a blueprint, add the max_content_length to this registry using the blueprint name as key

**4. src/flask/app.py**
- No direct changes needed (inherits from Flask which inherits from sansio/app.py)

**5. src/flask/wrappers.py**
- Line 59-86: Modify `max_content_length` property getter to add blueprint override check:
  - Check `self._max_content_length` (instance override) first
  - Check blueprint override from `current_app.blueprint_max_content_length` using the blueprint name from `self.blueprint`
  - Fall back to `current_app.config["MAX_CONTENT_LENGTH"]`
  - Fall back to werkzeug default

### Tests to Add:

**tests/test_request.py**
- `test_blueprint_max_content_length()`: Verify blueprint override wins over app config
- `test_blueprint_max_content_length_with_request_override()`: Verify request-level override has priority
- `test_nested_blueprint_max_content_length()`: Test nested blueprints
- `test_blueprint_max_content_length_none()`: Test when blueprint sets it to None (no override)

**tests/test_blueprints.py** (alternatively)
- Same tests could go here if blueprints are tested separately

### Precedence Order:
1. Per-request override (`request.max_content_length = value`)
2. Per-blueprint override (set in Blueprint constructor)
3. App-wide config (`app.config["MAX_CONTENT_LENGTH"]`)
4. Werkzeug default (None)

### Key Implementation Details:
- Blueprint name lookup uses `request.blueprint` property (line 162-178 in wrappers.py)
- Blueprint names can be dotted for nested blueprints, so need to check exact match in the registry
- When a blueprint is registered multiple times with different names, each name gets its own entry in the registry
- The max_content_length value is immutable per blueprint (set at blueprint creation time, not at registration time)