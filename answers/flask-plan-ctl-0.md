I didn't edit anything. The limit should be resolved when the request is read, in `Request.max_content_length`. That code can use `request.blueprints`, which already gives the matched blueprint names from innermost to outermost, including nested and renamed ones. The only other change is storing each blueprint's limit on the app when it is registered.

## Order of precedence

1. A value set on the request itself (`request.max_content_length = N`). This already exists and should keep winning.
2. The limit of the innermost matched blueprint, then its parent, and so on up the chain.
3. `app.config["MAX_CONTENT_LENGTH"]`.
4. Werkzeug's default, when there's no app context.

A blueprint left at `None` inherits the next level down, so a blueprint can't turn the limit off. If "no limit for this blueprint" is needed, a separate sentinel value would be required.

## Source changes

### 1. `src/flask/sansio/blueprints.py`
- **`Blueprint.__init__`** (`:174-211`): add `max_content_length: int | None = None` as the last parameter, after `cli_group` at `:185`. Store it as `self.max_content_length` next to `self.cli_group = cli_group` at `:210`. Add a `:param max_content_length:` entry and a `.. versionchanged:: 3.2` note to the class docstring (`:135-170`).
- **`Blueprint.register`** (`:273-377`): after `app.blueprints[name] = self` at `:319`, work out the limit the same way `cli_group` is handled at `:337`:
  ```python
  max_len = options.get("max_content_length", self.max_content_length)
  if max_len is not None:
      app.blueprint_max_content_length[name] = max_len
  ```
  Key it by the full dotted `name` from `:304`, not `self.name`. That way `name=` renames and nested registrations each get their own entry. Nested blueprints are registered through the loop at `:349-377`, which sets `name_prefix`, so they get their own full name automatically. Don't copy the parent's limit into `bp_options`; the lookup in step 4 walks up the chain instead.
- **`BlueprintSetupState.__init__`** (`:41-85`), optional: expose the resolved value as `self.max_content_length` for `record()` callbacks, matching how `subdomain` and `url_prefix` are handled at `:64-77`.

### 2. `src/flask/blueprints.py`
- **`Blueprint.__init__`** (`:19-43`): add the same `max_content_length: int | None = None` parameter. The call to `super().__init__` at `:32-43` passes arguments by position, so append `max_content_length` after `cli_group` at `:42`. Putting it anywhere else would shift the other arguments.

### 3. `src/flask/sansio/app.py`
- **`App.__init__`**: add the lookup table right after `self.blueprints` at `:374`:
  ```python
  #: Maps registered (dotted) blueprint names to their max_content_length override.
  self.blueprint_max_content_length: dict[str, int] = {}
  ```
- **`App.register_blueprint`** docstring (`:570-594`): document the new `:param max_content_length:` option alongside `url_prefix`, `subdomain` and `url_defaults` at `:579-582`.

### 4. `src/flask/wrappers.py`
- **`Request.max_content_length` getter** (`:59-86`): keep the per-request check at `:80-81` first and the no-app-context fallback at `:83-84`. Insert the blueprint lookup before the config fallback at `:86`:
  ```python
  overrides = current_app.blueprint_max_content_length
  for bp in self.blueprints:  # innermost first, via _split_blueprint_path
      if bp in overrides:
          return overrides[bp]
  return current_app.config["MAX_CONTENT_LENGTH"]
  ```
  `self.blueprints` (`:180-195`) uses `self.endpoint`, which is set when the URL is matched in `ctx.py:405-414`. That happens during `push()` (`ctx.py:443-444`), before any view reads the body.
- Update the docstring (`:69-79`) to describe the precedence and add `.. versionchanged:: 3.2`.
- Leave the setter (`:88-90`) unchanged.

### 5. Things to be aware of (no code change needed)
- **Session is opened before URL matching** (`ctx.py:439`, before `:444`): if a custom `SessionInterface.open_session` reads the request body, it sees the app-wide limit, not the blueprint's. Document this.
- **Routing failures** (404/405): `url_rule` is `None`, so `blueprints` is empty and the app-wide config applies. That's the correct result.
- **Leave `max_form_memory_size` and `max_form_parts` (`:92-144`) out of this change**, but the same pattern would extend to them later if wanted.

## Docs
- `docs/config.rst:320-332`: under `MAX_CONTENT_LENGTH`, mention that a blueprint can override it.
- `docs/web-security.rst:25`: add the blueprint-level override to the list of ways to limit request size.
- `docs/patterns/fileuploads.rst:138-144`: short example of `Blueprint("uploads", __name__, max_content_length=...)`.
- `docs/blueprints.rst`: short section on per-blueprint limits.
- `CHANGES.rst`: add an entry under "Version 3.2.0" (`:1`), near the existing per-request limit note at `:83-84`.

## Tests

### `tests/test_request.py` (next to `test_max_content_length` `:9` and `test_limit_config` `:25`)
1. **`test_blueprint_max_content_length_overrides_config`**: set app `MAX_CONTENT_LENGTH = 1000` and a blueprint with `max_content_length=50`. A 150-byte POST to the blueprint route returns 413, and the same POST to an app route returns 200.
2. **`test_blueprint_max_content_length_larger_than_config`**: app limit 50, blueprint limit 1000. A 150-byte POST to the blueprint succeeds. This shows the override can loosen the limit as well as tighten it.
3. **`test_blueprint_max_content_length_none_inherits_config`**: a blueprint with no limit falls back to the app config.
4. **`test_request_override_beats_blueprint`**: a `before_request` sets `request.max_content_length = 10` on a blueprint whose limit is 1000, and a small POST returns 413.
5. **`test_blueprint_max_content_length_no_match`**: a 404 request inside a test request context reports the app config value.

### `tests/test_blueprints.py` (next to the nesting and renaming tests at `:862`, `:1063`, `:1086`)
6. **`test_nested_blueprint_max_content_length`**: parent limit 100, child limit 20, grandchild with no limit. Inside `app.test_request_context(path)`, check that `request.max_content_length` is 100 on the parent route, 20 on the child route, and 20 on the grandchild route (inherited from the child).
7. **`test_register_blueprint_max_content_length_option`**: `app.register_blueprint(bp, max_content_length=30)` overrides the constructor value. Registering the same blueprint twice with `name="bp2"` and different limits keeps a separate limit for each name. Also check the `app.blueprint_max_content_length` dict directly.
8. **`test_nested_register_option_max_content_length`**: `parent.register_blueprint(child, max_content_length=5)` is keyed as `"parent.child"`.
9. Optional: if `BlueprintSetupState.max_content_length` is added, check its value from a `bp.record(...)` callback.