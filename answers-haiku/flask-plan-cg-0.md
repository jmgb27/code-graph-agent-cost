Based on my exploration, here's the complete plan to add per-blueprint `max_content_length` override:

## Implementation Plan

### Files to Modify

**1. `src/flask/sansio/blueprints.py` — Blueprint class**
- **Line 207 (Blueprint.__init__)**: Add `max_content_length: int | None = None` parameter
- **Line 211** (after `self._blueprints`): Add `self.max_content_length = max_content_length` to store blueprint-specific limit

**2. `src/flask/blueprints.py` — Blueprint class**
- **Line 19 (Blueprint.__init__)**: Add `max_content_length: int | None = None` parameter 
- **Line 43** (super().__init__ call): Pass `max_content_length=max_content_length` to parent

**3. `src/flask/wrappers.py` — Request.max_content_length property**
- **Lines 60-86** (max_content_length getter): Modify resolution order:
  1. Return `self._max_content_length` if set (per-request override)
  2. Check if current blueprint has `max_content_length` via `current_app.blueprints[self.blueprint]` 
  3. Fall back to `current_app.config["MAX_CONTENT_LENGTH"]`

**4. `src/flask/sansio/app.py` — App class**
- **register_blueprint method (line 570)**: Store blueprint's `max_content_length` when registering (if provided)
  - When blueprint is registered, check if `blueprint.max_content_length` is set and store it in app.blueprints

### Tests to Add

**In `tests/test_request.py`:**
1. `test_blueprint_max_content_length` — Blueprint override is used for routes in that blueprint
2. `test_blueprint_max_content_length_priority` — Per-request override > blueprint override > app config
3. `test_blueprint_max_content_length_fallback` — App config used when no blueprint override

**In `tests/test_blueprints.py`:**
1. `test_blueprint_max_content_length_attribute` — Blueprint accepts and stores max_content_length
2. `test_nested_blueprint_max_content_length` — Nested blueprints can have own limits (walk `request.blueprints`)

### Implementation Sequence

1. **Blueprint attribute** — Add `max_content_length` parameter/attribute to Blueprint classes
2. **Request property** — Update `Request.max_content_length` getter to check blueprint override
3. **App registration** — Ensure blueprint's max_content_length is accessible via app.blueprints
4. **Tests** — Add comprehensive test coverage for all scenarios

### Key Code Locations

- **Current max_content_length resolution**: `src/flask/wrappers.py:60-86`
- **Blueprint initialization**: `src/flask/sansio/blueprints.py:184-210` and `src/flask/blueprints.py:19-43`
- **Blueprint registration**: `src/flask/sansio/app.py:570-595`
- **Request blueprint access**: `src/flask/wrappers.py:162-195` (blueprint & blueprints properties)
- **Existing tests**: `tests/test_request.py` (test_limit_config), `tests/test_blueprints.py`