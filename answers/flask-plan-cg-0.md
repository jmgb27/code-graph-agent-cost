I've read `wrappers.py`, both `Blueprint` classes and the registration path. This is a small change. The override is looked up when the request asks for its limit, so it needs no new registration state: `app.blueprints` is already keyed by each blueprint's full dotted registered name, which covers nesting and renaming.

## Design

The limit is resolved in this order, highest priority first:
1. An explicit per-request value (`request.max_content_length = …`), which already exists.
2. The innermost matched blueprint's `max_content_length`, then its parent blueprints outward.
3. `app.config["MAX_CONTENT_LENGTH"]`.

On a blueprint, `None` means "inherit from the parent or the app". That keeps it consistent with how the request-level override already works (`wrappers.py:80`).

## Files and functions to change

### 1. `src/flask/sansio/blueprints.py`
- **`Blueprint.__init__`** (`:174-211`): add a keyword argument `max_content_length: int | None = None` after `cli_group` (`:185`). Putting it last means existing positional callers keep working. Store it as `self.max_content_length = max_content_length` next to `self.url_prefix` and `self.subdomain` (`:202-203`).
- **Class docstring** (`:135-170`): add `:param max_content_length:` and a `.. versionadded:: 3.2` note.
- **No change needed in `register`** (`:273-377`). Line `:319` (`app.blueprints[name] = self`) already records the blueprint under its dotted name, including `name_prefix` for nested blueprints (`:304`, `:376`) and `name=` renames (`:303`).

### 2. `src/flask/blueprints.py`
- **`Blueprint.__init__`** (`:19-43`): add the same `max_content_length: int | None = None` parameter to the signature and pass it through in the `super().__init__(...)` call (`:32-43`). That call is positional, so either pass the new argument by keyword or put it last.

### 3. `src/flask/wrappers.py`
- **`Request.max_content_length` getter** (`:59-86`): add a blueprint lookup between the `current_app` check (`:83-84`) and the config fallback (`:86`):
  ```python
  for bp_name in self.blueprints:          # innermost first, via _split_blueprint_path
      bp = current_app.blueprints.get(bp_name)
      if bp is not None and bp.max_content_length is not None:
          return bp.max_content_length
  ```
  - `Request.blueprints` (`:180-195`) returns names from innermost to outermost, because `_split_blueprint_path` (`helpers.py:644-651`) returns `["a.b.c", "a.b", "a"]`.
  - If routing hasn't run or failed (for example a 404 or 405), `url_rule` is `None`, so `blueprints` is `[]` and the app config applies. That's the right fallback.
- **Docstring** (`:61-78`): describe the new order and add `.. versionchanged:: 3.2`.
- The setter (`:88-90`) doesn't change, so a per-request value still wins.

**Timing check:** the body is read lazily, so the lookup sees the matched route. `url_rule` is set in `match_request` (`src/flask/ctx.py:405-414`) when the context is pushed, before any `before_request` handler or view can read `request.form`, `request.data` or `request.stream`.

### 4. Docs
- `docs/config.rst:320-335` (`MAX_CONTENT_LENGTH`): mention the blueprint-level override and the order in which the limit is resolved.
- `docs/blueprints.rst`: add a short section about limiting request size per blueprint, for example after "Nesting Blueprints" (`:123`), including how nested blueprints inherit.
- `docs/web-security.rst:25`: add the blueprint override to the list of size controls.
- `CHANGES.rst`: add an entry under "Version 3.2.0 / Unreleased" (`:1-20`).

## Tests to add

**`tests/test_request.py`**, next to `test_max_content_length` (`:9`) and `test_limit_config` (`:25`):
1. `test_blueprint_max_content_length_overrides_config`: app limit 1000, blueprint limit 50. Posting about 150 bytes to the blueprint route returns 413 (use the `@app.errorhandler(413)` pattern from `:17-19`). The same body posted to an app route returns 200.
2. `test_blueprint_max_content_length_larger_than_config`: app limit 50, blueprint limit 1000. A 150-byte post to the blueprint route succeeds, which shows the blueprint value wins in both directions.
3. `test_blueprint_max_content_length_none_inherits`: a blueprint without a limit uses the app's `MAX_CONTENT_LENGTH`.
4. `test_request_override_beats_blueprint`: a `before_request` sets `request.max_content_length = 10` on a blueprint with a limit of 1000, and the request gets a 413.
5. `test_blueprint_max_content_length_unmatched_route`: a 404 or 405 falls back to the app config. Assert on `request.max_content_length` in an `errorhandler`, or use `app.test_request_context` with a URL that doesn't exist.

**`tests/test_blueprints.py`**, near `test_nesting_subdomains` (`:1022`) and `test_blueprint_renaming` (`:1086`):
6. `test_nested_blueprint_max_content_length`: a parent with a limit of 50 and a child with no limit, so the child route inherits 50. Set the child to 1000 and it overrides the parent. Assert on `request.max_content_length` inside the view.
7. `test_blueprint_max_content_length_renamed`: register the same blueprint twice with `name="alt"` and check that both registrations get the limit. This works because the lookup uses the object in `app.blueprints`.

## Decisions to confirm
- **Overriding the limit per registration** with `app.register_blueprint(bp, max_content_length=…)` isn't covered by this plan. Both registrations of a blueprint point to the same object in `app.blueprints`, so this would need extra per-name storage. The value would come from `options.get("max_content_length", self.max_content_length)` in `Blueprint.register` (`sansio/blueprints.py:273`) and be saved in a new dict on the app (`sansio/app.py:374`). I'd leave it for a follow-up.
- **No "unlimited" setting for a blueprint:** because `None` means "inherit", a blueprint can't remove a limit the app sets. If you need that, use a sentinel default (such as the existing `_sentinel`) for the "inherit" case so that `None` can mean "no limit".
- **Other size limits:** `max_form_memory_size` and `max_form_parts` (`wrappers.py:92-144`) could get the same override. The same pattern would work for both, but the request didn't ask for them.