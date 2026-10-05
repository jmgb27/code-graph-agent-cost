I didn't edit anything. The override fits into code that already exists: blueprints already take per-registration options like `url_prefix`, and `Request.max_content_length` already looks up its limit on each access. The plan is to store each blueprint's resolved limit on the app, keyed by the blueprint's registered name. The request then checks its blueprints from the innermost outwards before it uses `MAX_CONTENT_LENGTH`.

**Precedence (highest first):**
1. A value set directly on the request.
2. The innermost blueprint that has a limit.
3. That blueprint's parent blueprints.
4. `MAX_CONTENT_LENGTH`.
5. Werkzeug's default, when there is no app context.

## Source changes

### 1. `src/flask/sansio/blueprints.py`
- **`Blueprint.__init__`** (`:174-211`): add a `max_content_length: int | None = None` parameter after `url_defaults` (`:183`). Store it as `self.max_content_length = max_content_length` next to `self.subdomain` (`:203`). Document it in the class docstring (`:119`+) with a `versionadded`.
- **`BlueprintSetupState.__init__`** (`:41-85`): resolve the value the same way as `subdomain` and `url_prefix` (`:64-77`). Use the registration option if given, otherwise the blueprint's own value, and store it as `self.max_content_length`.
- **`Blueprint.register`** (`:273-377`):
  - After `state` is created (`:321`), record the limit when it isn't `None`: `app.blueprint_max_content_length[name] = state.max_content_length`. Using the dotted registered `name` (`:304`) keeps two registrations of one blueprint (`name=`) and nested blueprints separate.
  - Don't copy the parent's value into the nested-blueprint loop (`:349-377`). Child blueprints inherit at request time instead, which keeps the rule "innermost set value wins" simple.
  - Add a `versionchanged` note to the docstring.

### 2. `src/flask/blueprints.py`
- **`Blueprint.__init__`** (`:19-43`): this subclass lists every parameter explicitly, so add `max_content_length: int | None = None` to the signature and pass it through in the `super().__init__(...)` call (`:32-43`). Pass it by keyword, since the positional order must match the sansio class.

### 3. `src/flask/sansio/app.py`
- **`App.__init__`**: next to `self.blueprints` (`:374`), add
  `self.blueprint_max_content_length: dict[str, int] = {}` with a `#:` doc comment in the same style.
- **`App.register_blueprint`** (`:570-595`): add a `:param max_content_length:` line to the docstring. No code change is needed because options are already forwarded.

### 4. `src/flask/wrappers.py`
- **`Request.max_content_length` getter** (`:59-86`): between the app-context check (`:83-84`) and the config fallback (`:86`), insert:
  ```python
  limits = current_app.blueprint_max_content_length
  for bp in self.blueprints:   # innermost first, via _split_blueprint_path
      if bp in limits:
          return limits[bp]
  ```
  This reuses `Request.blueprints` (`:180-195`), which already returns names from the innermost outwards. Update the docstring (`:61-79`) to describe the precedence and add a `versionchanged:: 3.2`.
- The setter (`:88-90`) stays the same, so a value set on the request still wins.
- `max_form_memory_size` and `max_form_parts` (`:92-144`) are left alone. They could get the same treatment later.

### 5. Docs
- `docs/config.rst:320-334` (`MAX_CONTENT_LENGTH`): say that a blueprint's `max_content_length` overrides this setting.
- `docs/blueprints.rst`: add a short "Request size limits" section.
- `docs/web-security.rst:25`: mention the blueprint-level option.
- `CHANGES.rst`: add an entry under "Version 3.2.0 / Unreleased" (`:1-5`).

## Tests to add (`tests/test_request.py`, after `test_limit_config` at `:25`)

1. **`test_blueprint_max_content_length_overrides_app`**:
   - Set `MAX_CONTENT_LENGTH = 1000` and use `Blueprint("bp", __name__, max_content_length=50)`.
   - Post `"foo" * 50` to a blueprint route and expect 413 (use the `errorhandler(413)` pattern from `:17-22`).
   - Post the same body to an app route and expect 200.
2. **`test_blueprint_max_content_length_raises_limit`**: the app limit is 50 and the blueprint limit is 1000. A large post to the blueprint succeeds, which shows the blueprint override wins in both directions.
3. **`test_blueprint_max_content_length_register_option`**: `app.register_blueprint(bp, max_content_length=50)` overrides the value set in the constructor. Registering the same blueprint again with `name="bp2"` and no option uses the constructor value, so each registration keeps its own limit.
4. **`test_nested_blueprint_max_content_length`**:
   - Case 1: the parent limit is 50 and the child has none. The child route inherits 50.
   - Case 2: the child has its own limit. The child's limit wins over the parent's.
5. **`test_blueprint_max_content_length_request_override`**: in a `before_request`, set `request.max_content_length = 10`. That value wins over the blueprint limit.
6. **`test_blueprint_max_content_length_unmatched`**:
   - Use `app.test_request_context("/nope")`, where routing fails and `request.blueprints == []`, so the limit falls back to the config value.
   - The existing no-app-context case in `test_limit_config` (`:31-34`) should keep returning `None`.

There's also an optional check in `tests/test_blueprints.py`: `BlueprintSetupState(bp, app, {"max_content_length": 5}, True).max_content_length == 5`, plus the fallback to the value on the blueprint.

## Decisions and limits
- **`None` means "inherit"**, matching how `subdomain` and `url_prefix` work. So a blueprint can't set "no limit" when the app has one. If that's needed, use a sentinel default instead of `None` and store `None` values explicitly in the dict.
- **The limit only applies after URL matching.** It works because the body is read after routing. If a hook reads `request.data` before matching, or matching fails, the app limit is used.
- **The request looks up limits in a dict on the app instead of `app.blueprints[name]`.** That's because a limit passed to `register_blueprint` isn't stored on the blueprint object.