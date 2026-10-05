I've read the request wrapper, the blueprint classes and the existing size-limit tests, so here is the plan.

## Plan: per-blueprint `max_content_length`

**How it would work:** a `Blueprint(..., max_content_length=N)` sets the byte limit for requests routed to that blueprint's endpoints. The value is looked up when the request body is read, and URL matching has already happened by then (`src/flask/ctx.py:441-444` calls `match_request` during `push`). So `request.blueprints` is filled in and no extra hook is needed.

**Which value wins, highest first:**
1. A value set on the request itself (`request.max_content_length = …`, which already exists).
2. The innermost blueprint that sets a value, then its parent blueprints in order.
3. `app.config["MAX_CONTENT_LENGTH"]`.
4. Werkzeug's default when there is no app context.

`None` on a blueprint means "not set, inherit from the parent". The downside is that a blueprint can't turn the limit off when the app sets one. A separate "no limit" value could be added later if that's needed.

### Code changes

**1. `src/flask/sansio/blueprints.py`**
- `Blueprint.__init__` (`:174-211`): add a keyword `max_content_length: int | None = None` after `cli_group` and store it with `self.max_content_length = max_content_length` next to the other attributes (`:201-211`). Putting it last keeps existing positional calls working.
- `Blueprint` docstring (`:120-169`): add a `:param max_content_length:` entry and a `.. versionadded:: 3.2` note.
- `register` (`:273-377`): no change needed. The lookup uses the dotted name, and `app.blueprints[name] = self` (`:319`) already maps nested and renamed registrations back to the blueprint object.
- Optional follow-up: let `register_blueprint(bp, max_content_length=…)` override the value per registration. That needs per-name storage on the app (for example next to `self.blueprints` at `src/flask/sansio/app.py:374`), filled in `register` via `options.get("max_content_length", self.max_content_length)`. I'd leave it out of the first version.

**2. `src/flask/blueprints.py`**
- `Blueprint.__init__` (`:18-42`): add the same `max_content_length` parameter and pass it through to `super().__init__` (the call at `:32-42` passes arguments by position, so add it after `cli_group`).

**3. `src/flask/wrappers.py`**
- `Request.max_content_length` getter (`:59-86`): after the request-level check (`:80-81`) and the `if not current_app` fallback (`:83-84`), check blueprints before the config:
  ```python
  for name in self.blueprints:  # innermost → outermost (_split_blueprint_path, helpers.py:645)
      bp = current_app.blueprints.get(name)
      if bp is not None and bp.max_content_length is not None:
          return bp.max_content_length
  return current_app.config["MAX_CONTENT_LENGTH"]
  ```
  `self.blueprints` (`:180-195`) comes from `self.endpoint`. If routing failed or the endpoint is at app level, the list is empty, so the config value is used.
- Update the docstring (`:61-78`) with the new order and a `.. versionchanged:: 3.2`.
- The setter (`:88-90`) stays as it is.

**4. Docs and changelog**
- `docs/config.rst:320-334` (`MAX_CONTENT_LENGTH`): mention the per-blueprint override.
- `docs/blueprints.rst`: add a short section with an example.
- `docs/web-security.rst:25`: add the blueprint option to the list of ways to control the limit.
- `CHANGES.rst` under 3.2.0 Unreleased (`:1-15`): add an entry.

### Tests to add

**`tests/test_request.py`** (next to `test_max_content_length` at `:9` and `test_limit_config` at `:25`):
- `test_blueprint_max_content_length_overrides_config`: set the config to 1000 and the blueprint to 50, then POST about 150 bytes to a blueprint route. The 413 handler should run. The same body sent to an app-level route should succeed.
- `test_blueprint_max_content_length_larger_than_config`: set the config to 50 and the blueprint to 1000. The large body should pass on the blueprint route and get a 413 on an app route.
- `test_blueprint_max_content_length_none_inherits_config`: with no blueprint value, the config applies.
- `test_request_override_beats_blueprint`: inside the view (or a `before_request`), set `request.max_content_length` smaller than the blueprint value and check that it is the one enforced.
- `test_limit_config`: add a check inside `app.test_request_context("/bp/…")` that `request.max_content_length` equals the blueprint value, and one with an unmatched URL (404) that falls back to the config.

**`tests/test_blueprints.py`** (near the nesting tests, `:1022-1086`):
- `test_nested_blueprint_max_content_length`: the parent sets 100 and the child sets nothing, so the child inherits 100. When the child sets 20, 20 wins.
- `test_blueprint_max_content_length_renamed`: register the same blueprint twice with `name=` and check that both registrations apply the limit (this covers the lookup through `app.blueprints[name]`).
- If the optional per-registration override is built, also add `test_register_blueprint_max_content_length_option`, where the option wins over the blueprint's own value.

**Typing:** run mypy/pyright over `src/flask/wrappers.py`, because `current_app.blueprints` values are the sansio `Blueprint` type, which will now have the attribute.