# Plan: a `max_content_length` setting for each blueprint

## Precedence
From highest to lowest:
1. A value set on the request itself (`request.max_content_length = ...`). This already exists.
2. **New:** the matched blueprint's `max_content_length`. With nested blueprints, the innermost blueprint that sets a value wins.
3. The app-wide `MAX_CONTENT_LENGTH` config.
4. Werkzeug's default, used when there is no app context.

This works because the limit is read lazily. Routing runs inside `AppContext.push` (`src/flask/ctx.py:443-444`, calling `match_request` at `src/flask/ctx.py:405`), and that happens before the view touches `request.form` or `request.data`. So `request.blueprints` is already filled in when the limit is read.

## Source changes

### 1. `src/flask/sansio/blueprints.py` — `Blueprint.__init__` (`:174-211`)
- Add a keyword argument `max_content_length: int | None = None` after `cli_group` (`:185`), so existing positional calls keep working.
- Store it with `self.max_content_length = max_content_length` near `:201-210`.
- Document the new `:param max_content_length:` in the class docstring (`:135-170`) and add a `.. versionadded:: 3.2` note.
- `None` means "inherit from the parent blueprint or the app config", which matches how `_max_content_length` already treats `None` (`src/flask/wrappers.py:80`).

### 2. `src/flask/blueprints.py` — `Blueprint.__init__` (`:19-43`)
- This subclass lists every argument explicitly, so it needs the same `max_content_length` argument added to its signature (`:19-31`). It also has to pass the value on in the `super().__init__(...)` call (`:32-43`), otherwise it will be silently dropped.

### 3. `src/flask/wrappers.py` — `Request.max_content_length` getter (`:59-86`)
Insert a blueprint lookup between the per-request check and the config fallback:
```python
if self._max_content_length is not None:
    return self._max_content_length

if not current_app:
    return super().max_content_length

for name in self.blueprints:            # innermost first, see helpers.py:645
    bp = current_app.blueprints.get(name)
    if bp is not None and bp.max_content_length is not None:
        return bp.max_content_length

return current_app.config["MAX_CONTENT_LENGTH"]
```
- `self.blueprints` (`src/flask/wrappers.py:180-195`) uses `_split_blueprint_path` (`src/flask/helpers.py:645-651`). It returns the dotted registered names, innermost first, and those names are the same keys stored in `app.blueprints` by `Blueprint.register` (`src/flask/sansio/blueprints.py:304,319`, dict declared at `src/flask/sansio/app.py:374`). Blueprints registered under a different `name=` and nested blueprints therefore resolve correctly.
- Update the docstring (`:69-79`) to describe the new precedence and add a `.. versionchanged:: 3.2` note.
- The setter (`:88-90`) stays as it is.

### Optional (not recommended for this first version)
You could also allow a `register_blueprint(bp, max_content_length=...)` option for each registration. `app.blueprints` maps names to the shared blueprint object, so that option would need a separate `name -> limit` dict on `App` (`src/flask/sansio/app.py:~374`), filled in inside `Blueprint.register` (`:302-321`) from `options`. I'd leave this out unless someone asks for it.

### Known limitation to document
Because `None` means "inherit", a blueprint cannot turn the limit off when the app sets one. It can only raise it to a large number. The alternative is a sentinel-based design (`_sentinel` is in `src/flask/sansio/scaffold.py`), which I'd avoid because it doesn't match the request-level API.

## Docs
- `docs/config.rst:329-332` (`MAX_CONTENT_LENGTH`): say that a blueprint's `max_content_length` overrides this config.
- `docs/web-security.rst:25`: mention the blueprint-level setting alongside the config and the request attribute.
- `docs/patterns/fileuploads.rst:138-144`: add a short example of a larger limit on an uploads blueprint.
- `docs/blueprints.rst`: optionally add a short paragraph.
- `CHANGES.rst:4-…` (the unreleased 3.2.0 section): add an entry.

## Tests

### `tests/test_request.py` (next to `test_max_content_length` `:9` and `test_limit_config` `:25`)
1. **`test_blueprint_max_content_length_overrides_config`**: set the app config to `MAX_CONTENT_LENGTH = 1000` and the blueprint to `max_content_length=50`. Posting `"foo" * 50` to the blueprint route returns 413; posting the same data to an app route returns 200.
2. **`test_blueprint_max_content_length_larger_than_config`**: set the config to 50 and the blueprint to 1000. A large post to the blueprint route succeeds, and the same post to an app route returns 413.
3. **`test_blueprint_max_content_length_none_inherits`**: a blueprint with no value uses the config value (check it with `request.max_content_length` inside the view).
4. **`test_request_override_beats_blueprint`**: in a `before_request`, or in the view before reading the form, set `request.max_content_length = 10` while the blueprint says 1000. Expect 413.
5. **`test_nested_blueprint_max_content_length`**: the parent blueprint sets 50 and the child sets 1000, registered via `parent.register_blueprint(child)`. The child route uses 1000. A second child with no value inherits the parent's 50. The parent's own routes use 50.
6. **`test_blueprint_max_content_length_renamed_registration`**: register the same blueprint under `name="other"` and check that the lookup works through the renamed dotted key.
7. **`test_blueprint_max_content_length_unmatched_route`**: a 404 request (`url_rule is None`, so `request.blueprints == []`) falls back to the config.
8. Extend **`test_limit_config`** (`:25-54`): a bare `Request({})` with no URL rule still returns the config value and the Werkzeug default, as before (a regression guard).

### `tests/test_blueprints.py`
9. **`test_blueprint_max_content_length_attribute`**: `Blueprint("bp", __name__, max_content_length=123).max_content_length == 123`, and it defaults to `None`. This checks that the value survives being passed through `flask.blueprints.Blueprint.__init__`.

Run `pytest tests/test_request.py tests/test_blueprints.py` and `mypy`. The new `bp.max_content_length` access in `wrappers.py` needs `Blueprint` typed properly; `app.blueprints` is already typed as `dict[str, Blueprint]`.