Perfect! Now I have a complete understanding. Here's the plan for implementing per-blueprint `max_content_length` override:

## Files to Modify and Functions to Change:

### 1. **src/flask/sansio/blueprints.py**
- **Line 174-186** — `Blueprint.__init__()`: Add `max_content_length` parameter (optional, default `None`)
- **After line 210** — Add instance attribute: `self.max_content_length = max_content_length`

### 2. **src/flask/blueprints.py**
- **Line 19-31** — `Blueprint.__init__()`: Add `max_content_length` parameter (optional, default `None`)
- **Line 32-43** — Pass `max_content_length` to `super().__init__()`

### 3. **src/flask/wrappers.py**
- **Line 59-86** — Modify `max_content_length` property getter:
  - After checking `self._max_content_length`, add logic to check blueprint-specific override
  - Extract blueprint name from `self.blueprint` property
  - Look up the blueprint in `current_app.blueprints` 
  - Return blueprint's `max_content_length` if set, before falling back to app config

### 4. **tests/test_request.py** (or new test file)
Add tests:
- **test_blueprint_max_content_length()** — Blueprint override wins over app config
- **test_blueprint_max_content_length_multiple()** — Different blueprints have different limits
- **test_blueprint_max_content_length_with_override()** — Per-request override wins over blueprint override
- **test_nested_blueprint_max_content_length()** — Nested blueprints inherit/override correctly
- **test_blueprint_max_content_length_no_routing_exception()** — Works when routing fails

### 5. **tests/test_blueprints.py** (optional integration test)
- Add test showing blueprint max_content_length behavior in full request cycle

## Feature Behavior:

**Priority order** (highest to lowest):
1. Per-request override: `request.max_content_length = X`
2. Blueprint-specific override: `Blueprint(..., max_content_length=X)`
3. App-wide config: `app.config['MAX_CONTENT_LENGTH']`
4. Werkzeug default: `None`

**Key Points:**
- Blueprint override is looked up from `current_app.blueprints[blueprint_name]`
- Lookup happens when the property is accessed, after routing is complete
- Works with nested blueprints (top-level blueprint's override applies)
- Falls back gracefully if blueprint not found or doesn't have override
- No breaking changes to existing code