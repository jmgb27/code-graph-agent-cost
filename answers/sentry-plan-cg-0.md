# Plan: per-project hourly cap on new issue creation

The plan adds one project option. The API validates and saves it, the project settings page gets a field for it, and ingestion enforces it right before a new `Group` would be created. Events over the cap are dropped the same way load-shedding drops them today: the quota is refunded and a FILTERED outcome is recorded. Events that match an existing issue are never affected.

I suggest calling the setting `newIssueHourlyCap` in the API and frontend and `sentry:new_issue_hourly_cap` as the stored option. A value of `0` or null means no cap.

---

## 1. Option registration

| File | Change |
|---|---|
| `src/sentry/projectoptions/defaults.py:268` | After `sentry:scm_source_context_enabled`, add `register(key="sentry:new_issue_hourly_cap", default=0)` with a one-line comment. |
| `src/sentry/models/options/project_option.py:20-93` (`OPTION_KEYS`) | Add `"sentry:new_issue_hourly_cap"`. Without it, `DetailedProjectSerializer.get_attrs` (`src/sentry/api/serializers/models/project.py:1047`) won't load the value. |
| `src/sentry/features/temporary.py` | Register a flag such as `projects:new-issue-hourly-cap` (ProjectFeature, `api_expose=True`) so the UI and the enforcement can be rolled out gradually (see the `feature-flags` skill). |
| `src/sentry/options/defaults.py` (optional) | A global kill switch or max value, e.g. `issues.new-issue-hourly-cap.max`, used as the serializer's `max_value` and as an off switch for enforcement. |

## 2. API serializer and endpoint (`src/sentry/core/endpoints/project_details.py`)

- **`ProjectAdminSerializer` field** (next to `resolveAge`, `:251-255`): add `newIssueHourlyCap = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=..., help_text="Maximum number of new issues created per hour for this project. 0 or null disables the cap.")`. Putting it on the admin serializer means only users with `project:write` or `project:admin` can change it. The permission check at `:789-795` covers it automatically.
- **`validate_newIssueHourlyCap`** (next to `validate_tempestFetchScreenshots`, `:614-620`): reject the value if the feature flag is off (`features.has("projects:new-issue-hourly-cap", project, actor=request.user)`). Convert `None` to `0`.
- **`ProjectDetailsEndpoint.put`** (`:737`): add a block that follows the `resolveAge` pattern at `:910-916`:
  ```python
  if "newIssueHourlyCap" in result:
      if project.update_option("sentry:new_issue_hourly_cap", result["newIssueHourlyCap"] or 0):
          changed_proj_settings["sentry:new_issue_hourly_cap"] = result["newIssueHourlyCap"]
  ```
  This change then shows up in the `PROJECT_EDIT` audit entry at `:1325-1329`, which is built from `changed_proj_settings`.

## 3. Response serializer (`src/sentry/api/serializers/models/project.py`)

- **`DetailedProjectResponse`** (`:995-1040`): add `newIssueHourlyCap: NotRequired[int]`.
- **`DetailedProjectSerializer.serialize`** (`:1192-1194`): add `"newIssueHourlyCap": self.get_value_with_default(attrs, "sentry:new_issue_hourly_cap")`. `get_value_with_default` (`:1307`) falls back to the registered default.

## 4. Enforcement in the event pipeline

The path for new error groups is `EventManager.save_error_events` (`src/sentry/event_manager.py:521`) → `assign_event_to_group` (`:1318`) → `create_group_with_grouphashes` (`:1478`) when no primary, secondary or Seer match is found (`:1359`) → `_create_group` (`:1549`).

- **New helper** `check_for_new_issue_cap(project, event)` in `src/sentry/grouping/ingest/utils.py`, next to `check_for_group_creation_load_shed` (`:37-47`):
  - Read `project.get_option("sentry:new_issue_hourly_cap")` and return early if it's 0 or the feature flag is off.
  - Call `ratelimits.backend.is_limited(key="new-issue-hourly-cap", limit=cap, project=project, window=3600)` (signature at `src/sentry/ratelimits/base.py:16`). This is the same pattern as the Seer rate limits at `event_manager.py:2061-2090`.
  - If the limit is hit, record `metrics.incr("grouping.new_issue_cap.hit")` and `raise HashDiscarded("New issue hourly cap reached", reason="new_issue_cap")`.
- **Where to call it:** in `create_group_with_grouphashes`, inside the `if existing_grouphash is None:` branch (`event_manager.py:1528`) and before `_create_group`. Don't put it at the load-shed check (`:1491`). Placing it after the double-checked lock means only events that would really create a group count against the limit, so an event that loses the creation race to an identical event isn't counted. Raising inside `transaction.atomic` rolls back cleanly. The grouphash stays without a group, so the same fingerprint gets a new issue once the window resets.
- **Existing error handling:** `save_error_events` already catches `HashDiscarded` (`:552-555`) and calls `discard_event` (`:2257`), which refunds the quota and emits `Outcome.FILTERED` with `FilterStatKeys.DISCARDED_HASH`.
  - Optional but recommended: add a `reason` parameter to `discard_event` and a new `FilterStatKeys` value in `src/sentry/constants.py`, so these drops can be told apart from tombstone drops in stats.
  - `increment_group_tombstone_hit_counter(getattr(e, "tombstone_id", None), ...)` is passed `None` for this case. Check that it does nothing with `None`.
- **Issue platform (optional scope):** `save_issue_from_occurrence` (`src/sentry/issues/ingest.py:197`) creates groups through `save_grouphash_and_group` (`:257`). If the cap should also cover performance and other occurrence-based issues, call the same helper before that (e.g. alongside `should_create_group` at `:223`). Otherwise, document that the cap only applies to errors.

## 5. Frontend (separate PR, merged after the backend)

| File | Change |
|---|---|
| `static/app/types/project.tsx:148` | Add `newIssueHourlyCap?: number;` to `DetailedProject`/`Project`. |
| `static/app/views/settings/projectGeneralSettings/index.tsx:205-216` (`projectSettingsSchema`) | Add `newIssueHourlyCap: z.number().int().min(0)`. |
| same file, `FieldGroup title="Event Settings"` (`:751-784`) | After the `enableAutoReleaseCreation` `AutoSaveForm` (`:753-783`), add an `AutoSaveForm name="newIssueHourlyCap"` with `initialValue={project.newIssueHourlyCap ?? 0}` and `mutationOptions={projectMutationOptions}`. Render a number input in `field.Layout.Row` labeled "New issue hourly cap", with a hint that 0 means unlimited. Wrap it in `project.features.includes('new-issue-hourly-cap')` and use the existing `disabled` prop. |
| `static/app/views/settings/fieldRegistry.generated.ts` | Regenerate with `scripts/extractFormFields.ts` (the file must not be edited by hand) so the field appears in settings search. |

## 6. Tests

- `tests/sentry/core/endpoints/test_project_details.py`: the field saves correctly; it's rejected without the flag, for negative values and for values above the max; a member without write access gets 403; the value appears in the GET response.
- `tests/sentry/event_manager/` (grouping tests): with a cap of N, events N+1 and later with new fingerprints raise `HashDiscarded` and emit the outcome; events for existing groups still save; a cap of 0 means unlimited.
- `static/app/views/settings/projectGeneralSettings/index.spec.tsx`: the field renders when the flag is on and sends a PUT with `newIssueHourlyCap`.

**Notes:**
- The Redis rate limiter counts in fixed one-hour windows, not a true sliding hour.
- `project.get_option` is cached, so reading it on every new-group event is cheap.
- Before `save_error_events` is reached, Relay has already accepted the event and charged quota. That's why the refund in `discard_event` matters.