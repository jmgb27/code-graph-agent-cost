Here's the plan: every file and function to change, anchored to current `master` (1c7d16d5). I haven't edited anything.

**Design, in short:**
- A new project option, `sentry:new_issue_hourly_limit`. A value of `0` means no limit.
- The check happens only on the path where a new error group would be created. Events for existing groups are never affected.
- An event over the cap is dropped using the same exception (`HashDiscarded`) the existing load-shed killswitch uses. It's refunded and recorded as a FILTERED outcome with a new reason.

---

## 1. Option registration

| File | Change |
|---|---|
| `src/sentry/projectoptions/defaults.py:~166` (next to `sentry:enable_auto_release_creation`) | `register(key="sentry:new_issue_hourly_limit", default=0)` with a comment explaining that 0 means disabled. No epoch bump is needed. |
| `src/sentry/models/options/project_option.py:25` (`OPTION_KEYS`) | Add `"sentry:new_issue_hourly_limit"`. This is required for `DetailedProjectSerializer.get_attrs` (`api/serializers/models/project.py:1047`) to load the option. |
| `src/sentry/features/temporary.py` (the `projects:*` block, around line 521) | `manager.add("projects:new-issue-hourly-limit", ProjectFeature, FeatureHandlerStrategy.FLAGPOLE, api_expose=True)`. It gates the API field and the UI. |
| `src/sentry/conf/server.py:3249` | Add `SENTRY_NEW_ISSUE_RATE_LIMITER_OPTIONS: dict[str, str] = {}` next to `SENTRY_ISSUE_PLATFORM_RATE_LIMITER_OPTIONS`, so ops can point it at a Redis cluster. |

## 2. API: serializer and endpoint

**`src/sentry/core/endpoints/project_details.py`**
- **`ProjectAdminSerializer` (starts at :217; add near `resolveAge` at :251):**
  - Add `newIssueHourlyLimit = EmptyIntegerField(required=False, allow_null=True, min_value=0, max_value=<sane cap, e.g. 1_000_000>, help_text="Maximum number of new issues created per hour for this project. Set to 0 to disable.")`.
  - Admin-only, so member-scope requests get the existing 403 from the check at :786-792.
- **New `validate_newIssueHourlyLimit(self, value)`** (next to `validate_targetSampleRate` at :596 and `validate_tempestFetchScreenshots` at :614, which already do flag checks):
  - Raise `ValidationError` unless `features.has("projects:new-issue-hourly-limit", self.context["project"], actor=self.context["request"].user)`.
  - Convert `None` to `0`.
- **`ProjectDetailsEndpoint.put` (:737):** after the `resolveAge` block at :910-916, add:
  ```python
  if "newIssueHourlyLimit" in result:
      if project.update_option("sentry:new_issue_hourly_limit", int(result["newIssueHourlyLimit"] or 0)):
          changed_proj_settings["sentry:new_issue_hourly_limit"] = result["newIssueHourlyLimit"]
  ```
  Adding it to `changed_proj_settings` puts the change in the audit log for free.
- **Optional:** mention the field in the `put` docstring at :745-755. It's admin-only, so no change is needed there.

**`src/sentry/api/serializers/models/project.py`**
- `DetailedProjectResponse` (:995): add `newIssueHourlyLimit: int` after `resolveAge` (:1002).
- `DetailedProjectSerializer.serialize` (:1078): add `"newIssueHourlyLimit": int(attrs["options"].get("sentry:new_issue_hourly_limit", 0))` after :1126.

**API docs**
- `src/sentry/apidocs/examples/project_examples.py:139` and `:165`: add the option and field to the examples.
- `api-docs/components/schemas/project.json:252` and `:495`: add the property next to `resolveAge`.

## 3. Enforcement in the event pipeline

**Why this point:** error events create groups only in `assign_event_to_group` (`src/sentry/event_manager.py:1318`), and only in the "no match" branch, which calls `create_group_with_grouphashes` (:1359 → :1478).

**`src/sentry/grouping/ingest/utils.py`**, next to `check_for_group_creation_load_shed` (:37):
```python
new_issue_rate_limiter = RedisSlidingWindowRateLimiter(**settings.SENTRY_NEW_ISSUE_RATE_LIMITER_OPTIONS)

def check_for_new_issue_rate_limit(project: Project, event: Event) -> None:
    limit = project.get_option("sentry:new_issue_hourly_limit")
    if not limit:
        return
    granted = new_issue_rate_limiter.check_and_use_quotas(
        [RequestedQuota(f"new-issues:{project.id}", 1, [Quota(3600, 60, limit)])]
    )[0]
    if not granted.granted:
        metrics.incr("grouping.new_issue_rate_limit.dropped", tags={"platform": event.platform or "unknown"})
        raise HashDiscarded("New issue hourly limit exceeded", reason="new_issue_limit")
```
- This copies the existing issue-platform pattern at `src/sentry/issues/ingest.py:45-47` and `:230-243`.
- `Quota` and `RequestedQuota` come from `sentry.ratelimits.sliding_windows`.
- `project.get_option` is cached, so this adds no DB query.

**`src/sentry/event_manager.py`**
- **`create_group_with_grouphashes` (:1478):** call `check_for_new_issue_rate_limit(project, event)` inside the `if existing_grouphash is None:` branch (:1530), before `record_new_group_metrics` and `_create_group` (:1533-1535).
  - Why inside the lock and not next to the load-shed check at :1491: an event that loses the race falls through to `handle_existing_grouphash` (:1546). Checking outside the lock would use up quota for events that never create a group.
  - Raising there rolls back the `transaction.atomic` at :1499. The grouphashes stay without a group, as they do under load shedding, so a later event with the same hash can still create the issue once the window has room.
- **`EventManager.save_error_events` (:552-555):** no change needed. It already catches `HashDiscarded`, calls `discard_event` and re-raises. `tasks/store.py:635` then cleans up the processing store and attachments.
- **`discard_event` (:2257):** it currently hard-codes `FilterStatKeys.DISCARDED_HASH` (:2283, :2299). Add a `reason: str = FilterStatKeys.DISCARDED_HASH` parameter, and at :554 pass `FilterStatKeys.NEW_ISSUE_LIMIT if e.reason == "new_issue_limit" else FilterStatKeys.DISCARDED_HASH`. This keeps these drops separate in the stats pages.

**`src/sentry/ingest/inbound_filters.py:38`**
- Add `NEW_ISSUE_LIMIT = "new-issue-limit"  # Not replicated in Relay` to `FilterStatKeys`, next to `DISCARDED_HASH` and `CRASH_REPORT_LIMIT`.

**Out of scope, but decide explicitly:**
- **Issue-platform issues** (`src/sentry/issues/ingest.py`, `save_issue_from_occurrence` :197): these already have a per-type cap at :230-243. To make the project cap cover all issue types, add a second `RequestedQuota` for the same `new-issues:{project.id}` key in that call and return `None` when it's denied.
- **Performance issues:** `save_grouphash_and_group` (`event_manager.py:2811`) also creates groups and would need the same treatment. I recommend errors-only for v1.

## 4. Frontend

- **`static/app/types/project.tsx:109`:** add `newIssueHourlyLimit: number;` to `DetailedProject`, next to `resolveAge`.
- **`static/app/views/settings/projectGeneralSettings/index.tsx`:**
  - `projectSettingsSchema` (:205): add `newIssueHourlyLimit: z.number().int().min(0)`.
  - In `ProjectGeneralSettings` (:554), inside the "Event Settings" `FieldGroup` (:751-784), add an `AutoSaveForm` after the `enableAutoReleaseCreation` one:
    - Props: `name="newIssueHourlyLimit"`, `schema={projectSettingsSchema}`, `initialValue={project.newIssueHourlyLimit ?? 0}`, `mutationOptions={projectMutationOptions}`.
    - Contents: a `field.Layout.Row` with the label "New issue limit (per hour)" and hint text such as "Events that would create a new issue beyond this limit are dropped. 0 disables the limit."
    - Input: `<field.Number>`, following the number-field example in `static/app/views/settings/project/projectKeys/details/keyRateLimitsForm.tsx:176`.
    - Render it only when `organization.features.includes('projects:new-issue-hourly-limit')`, or the project-level equivalent. This works because the flag has `api_expose=True`.
    - Use the existing `disabled` prop for non-admins.
- **`static/app/views/settings/fieldRegistry.generated.ts`:** don't edit it by hand. Regenerate it with `pnpm run extract-form-fields` (`scripts/extractFormFields.ts`), which will add a `project-general-settings.newIssueHourlyLimit` entry like `resolveAge` at :166.
- **`tests/js/fixtures/project.ts:67`:** add `newIssueHourlyLimit: 0`.
- **Optional:** add the `new-issue-limit` reason to the org/project stats outcome-reason labels. No frontend code currently special-cases `discarded-hash`, so it's not required.

## 5. Tests

- **`tests/sentry/core/endpoints/test_project_details.py`** (next to `test_resolve_age` at :958):
  - Setting the value with the flag on works, and the value appears in the GET response.
  - Without the flag, the request returns 400.
  - A negative value returns 400.
  - A member-scope user gets 403.
  - An audit log entry is created.
- **`tests/sentry/event_manager/test_event_manager.py`** or **`tests/sentry/event_manager/grouping/`**:
  - With the limit at 2, the 3rd distinct fingerprint raises `HashDiscarded` and emits a FILTERED outcome with reason `new-issue-limit`.
  - An event matching an existing group is still accepted while over the cap.
  - A limit of 0 means unlimited.
- **`tests/sentry/grouping/ingest/`:** a unit test for `check_for_new_issue_rate_limit`.
- **`static/app/views/settings/projectGeneralSettings/index.spec.tsx`:** the field renders only behind the flag and PUTs `{newIssueHourlyLimit: N}`. The existing mock around :464 shows the pattern.

Run the backend changes through `.venv/bin/prek run -q` and targeted pytest files. Per `AGENTS.md`, the backend (sections 1–3 and Python tests) and the frontend (section 4) must ship as **separate PRs, backend first**.