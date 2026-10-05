I have what I need from the blueprint and request code, so here's the plan. I haven't edited any files.

# Plan: per-blueprint `max_content_length`

## Design
- **Lookup order:** a limit set on the `request` object wins, then the innermost matched blueprint that sets a limit, then its parent blueprints, then `MAX_CONTENT_LENGTH`.
- **Where limits are stored:** the app keeps a dict of limits keyed by each blueprint's *registered* name (the dotted name, e.g. `parent.child`). This means `register_blueprint(bp, max_content_length=...)` can override the value set on the blueprint, and the same blueprint registered twice under different names can have two different limits.
- **Why it works at runtime:** the request has already been matched to a route before the form or body is read. So `request.blueprints` (`src/flask/wrappers.py:181-195`) already lists the blueprint names, innermost first. If routing failed, that list is empty and the app-wide config applies.
- **"No override" marker:** `None` already means "no limit", so it can't also mean "not set". Use Flask's existing `_sentinel` for "not set", so a blueprint can set `None` to remove the limit for its own routes.

## Files and functions to change

**1. `src/flask/sansio/blueprints.py`**
- `Blueprint.__init__` (`:174-211`): add a `max_content_length: int | None = _sentinel` parameter (after `url_defaults` or `cli_group`) and store it as `self.max_content_length`. Add a `:param max_content_length:` entry and a `.. versionadded:: 3.2` note to the class docstring (`:135-170`).
- `BlueprintSetupState.__init__` (`:41-85`): work out the value the same way `subdomain` and `url_prefix` are handled (`:64-77`): `self.options.get("max_content_length", _sentinel)`, falling back to `self.blueprint.max_content_length`. Store it as `self.max_content_length`.
- `Blueprint.register` (`:273-377`): after `state` is created (`:321`), add: if `state.max_content_length is not _sentinel`, set `app.blueprint_max_content_length[name] = state.max_content_length`. Don't copy the value down to nested blueprints in the loop at `:349-377`. The lookup already walks up through parent blueprints, so a child inherits the parent's limit unless it sets its own. Add a `.. versionchanged:: 3.2` note.

**2. `src/flask/blueprints.py`**
- `Blueprint.__init__` (`:19-43`): add the same parameter and pass it through to `super().__init__` (`:32-43`). The arguments there are passed by position, so add it at the end, or switch to keyword arguments.

**3. `src/flask/sansio/app.py`**
- `App.__init__`, next to `self.blueprints` (`:374`): add `self.blueprint_max_content_length: dict[str, int | None] = {}`, with a `#:` doc comment like the neighbouring attributes.
- `App.register_blueprint` docstring (`:570-594`): document the new `:param max_content_length:` keyword argument.

**4. `src/flask/wrappers.py`**
- `Request.max_content_length` getter (`:59-86`): between the per-request check (`:80-81`) and the config fallback (`:86`), add:
  ```python
  limits = current_app.blueprint_max_content_length
  for bp in self.blueprints:
      if bp in limits:
          return limits[bp]
  ```
  Update the docstring (`:61-79`) to describe the new lookup order, with a `.. versionchanged:: 3.2` note. The setter (`:88-90`) doesn't change.
- If you want the same override for `max_form_memory_size` (`:92-113`) and `max_form_parts` (`:119-140`), use the same pattern there. I'd leave them out of scope for now.

**5. Docs and changelog**
- `CHANGES.rst`: add an entry under "Version 3.2.0 / Unreleased" (`:1-4`).
- `docs/config.rst:320-330` (`MAX_CONTENT_LENGTH`): mention the blueprint override.
- Optional: `docs/web-security.rst:25` and `docs/patterns/fileuploads.rst:138-144`, plus a short section in `docs/blueprints.rst`.

## Tests to add
Put these in `tests/test_request.py`, next to `test_max_content_length` (`:9`) and `test_limit_config` (`:25`), or in `tests/test_blueprints.py`:

1. **`test_blueprint_max_content_length_overrides_config`:** app config is 1000, the blueprint sets 50. Posting `"foo" * 50` to a blueprint route returns 413; the same post to an app route succeeds.
2. **`test_blueprint_max_content_length_raises_limit`:** app config is 50, the blueprint sets 1000. A large post to the blueprint route succeeds, which shows the blueprint wins in both directions.
3. **`test_blueprint_max_content_length_none_disables`:** the blueprint sets `None`, the app is 50. A large post to the blueprint route succeeds.
4. **`test_blueprint_max_content_length_register_option`:** `app.register_blueprint(bp, max_content_length=50)` overrides the blueprint's own value. Register the same blueprint twice under different `name=` values with different limits and check each is applied separately.
5. **`test_nested_blueprint_max_content_length`:** a child with no limit inherits its parent's; a child with its own limit overrides the parent's. Check that `request.max_content_length` inside the view equals the expected value.
6. **`test_request_override_beats_blueprint`:** setting `request.max_content_length = 10` in a `before_request` hook on a blueprint with limit 1000 gives 413.
7. **`test_blueprint_limit_unmatched_route`:** a 404 request, or one outside any request context, falls back to config. This extends `test_limit_config` (`:25-54`), where `Request({})` has no blueprints.
8. **Sansio unit test in `tests/test_blueprints.py`:** after registering, `app.blueprint_max_content_length` holds the dotted names (for example `"parent.child"`), and a blueprint with no limit set adds no entry.

Run `pytest tests/test_request.py tests/test_blueprints.py` and `mypy`. The new `_sentinel` default needs the same `# type: ignore[assignment]` that `cli_group` has (`sansio/blueprints.py:185`).