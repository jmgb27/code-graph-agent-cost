Based on my exploration of the codebase, here's a comprehensive plan for adding per-blueprint `max_content_length` override support:

## Plan: Per-Blueprint max_content_length Override

### Overview
The feature will allow blueprints to specify their own `max_content_length` limit that overrides the app-wide `MAX_CONTENT_LENGTH` config. The precedence will be: per-request override > per-blueprint limit > app-wide config.

### Files to Modify

#### 1. **src/flask/sansio/blueprints.py** — Blueprint class
- **Line 174-210**: `Blueprint.__init__` — add `max_content_length: int | None = None` parameter, store as `self.max_content_length`
- **Line 246-253**: `make_setup_state` — pass `max_content_length` to `BlueprintSetupState` initialization (already inherits from options)
- **Line 273-335**: `Blueprint.register` method — after line 320, store blueprint max_content_length in app's blueprint limits dict

#### 2. **src/flask/blueprints.py** — Flask Blueprint subclass  
- **Line 19-43**: `Blueprint.__init__` — add `max_content_length` parameter and pass to `super().__init__`

#### 3. **src/flask/sansio/app.py** — App class
- **Line 374**: Add new dict attribute after `self.blueprints`: `self.blueprint_request_limits: dict[str, int | None] = {}`
- **Line 570-595**: `register_blueprint` docstring — document that `max_content_length` can be passed as an option to override blueprint default

#### 4. **src/flask/wrappers.py** — Request class
- **Line 60-86**: `max_content_length` property — modify the getter to check for blueprint-level limit:
  1. Check `self._max_content_length` (per-request override) — highest priority
  2. Check if current endpoint belongs to a blueprint and if blueprint has a limit in `current_app.blueprint_request_limits` — second priority
  3. Fall back to `current_app.config["MAX_CONTENT_LENGTH"]` — lowest priority

#### 5. **tests/test_request.py** — Add test coverage
- **New test: `test_blueprint_max_content_length`** — test that blueprint limit overrides app config
- **New test: `test_blueprint_max_content_length_with_register_option`** — test passing `max_content_length` to `register_blueprint()`
- **New test: `test_request_override_wins`** — verify per-request override beats blueprint limit
- **Extend `test_limit_config`** — add blueprint context test case (optional)

### Implementation Details

**Lookup logic in Request.max_content_length property**:
```
1. If self._max_content_length is set → return it
2. If not current_app → return super().max_content_length
3. If self.blueprint exists:
   - Lookup self.blueprint in current_app.blueprint_request_limits
   - If found → return it
4. Return current_app.config["MAX_CONTENT_LENGTH"]
```

**Storage in app.register_blueprint flow**:
- When `blueprint.register(app, options)` is called
- Extract `max_content_length` from options or blueprint's `self.max_content_length`
- Store as `app.blueprint_request_limits[blueprint_name] = value`
- Handle multiple registrations of same blueprint with different limits

### Tests to Add

1. **test_blueprint_max_content_length**: Create blueprint with `max_content_length=100`, register it, verify POST requests with >100 bytes are rejected
2. **test_blueprint_register_option_override**: Pass `max_content_length=200` to `app.register_blueprint()`, verify it overrides blueprint's value
3. **test_per_request_wins_over_blueprint**: Set blueprint limit to 100, then set `request.max_content_length = 50` in view, verify 50 is enforced
4. **test_blueprint_none_value**: Set blueprint `max_content_length=None` to explicitly allow unlimited for that blueprint
5. **test_multiple_blueprint_limits**: Register multiple blueprints with different limits, verify each is enforced independently

### Edge Cases to Consider

- Blueprint registered multiple times with different limits
- Nested blueprints (blueprint-on-blueprint) — should use the innermost blueprint's limit
- None values (explicitly no limit for a blueprint)
- Blueprint registered via `register_blueprint()` vs added as deferred function

---

All changes use existing Flask patterns:
- Similar to how `url_prefix`, `subdomain`, and `url_defaults` are handled
- Follows the per-request override pattern already in `max_content_length` property
- Integrates with `BlueprintSetupState.options` dict