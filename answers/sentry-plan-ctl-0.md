I didn't edit any files. Here's the plan: every change point, plus the existing code each one should copy.

**Names used below:**
- **Project option:** `sentry:new_issue_hourly_limit` (a whole number; `0` means off).
- **API field:** `newIssueHourlyLimit`.
- **Feature flag:** `projects:new-issue-hourly-limit`.

---

## 1. Option registration

| File | Change |
|---|---|
| `src/sentry/projectoptions/defaults.py:268` | Add `register(key="sentry:new_issue_hourly_limit", default=0)` after the `sentry:scm_source_context_enabled` registration. |
| `src/sentry/models/options/project_option.py:20` (`OPTION_KEYS`, e.g. next to `:93`) | Add the key. Without it, the project serializer never loads the option (`project.py:1047` filters on `OPTION_KEYS`). |
| `src/sentry/features/temporary.py` | Register `projects:new-issue-hourly-limit` as a `ProjectFeature` using FlagPole with `api_expose=True`, so the frontend can check it (repo convention, see the `feature-flags` skill). |
| `src/sentry/options/defaults.py` (optional) | Add a global safety option, e.g. `issues.new-issue-hourly-limit.max`, capping the highest value a project may set. It can also serve as a global killswitch. |

## 2. API: serializer, validation, endpoint

`src/sentry/core/endpoints/project_details.py`
- **`ProjectAdminSerializer` (`:217`):** add the field next to `resolveAge` (`:251`), because it's an admin-only setting:
  `newIssueHourlyLimit = EmptyIntegerField(required=False, allow_null=True, min_value=0, help_text=...)`.
  Don't use the legacy `options` dict; the comment at `:414` says not to add more there.
- **New `validate_newIssueHourlyLimit(self, value)`:** follow `validate_tempestFetchScreenshots` (`:614`). It should:
  - reject the request if the feature flag is off for `self.context["project"]`;
  - reject negative values;
  - reject values above the global max, if that option is added;
  - turn `None` into `0`.
- **`ProjectDetailsEndpoint.put` (`:737`):** after the `resolveAge` block (`:910-916`), add
  `if "newIssueHourlyLimit" in result: if project.update_option("sentry:new_issue_hourly_limit", result[...]): changed_proj_settings[...] = ...`
  so the existing audit log picks up the change.

`src/sentry/api/serializers/models/project.py`
- **`DetailedProjectResponse` (`:995`):** add `newIssueHourlyLimit: int`.
- **`DetailedProjectSerializer.serialize` (`~:1126`/`:1192`):** add
  `"newIssueHourlyLimit": int(self.get_value_with_default(attrs, "sentry:new_issue_hourly_limit"))`.
  `get_value_with_default` is at `:1307`.

## 3. Enforcement in the event pipeline

The model to copy is the load-shed killswitch. It raises `HashDiscarded` right before group creation, and existing code already handles that exception from there down the call chain.

- **`src/sentry/grouping/ingest/utils.py:37`:** next to `check_for_group_creation_load_shed`, add `check_for_new_issue_rate_limit(project: Project) -> None`. It should:
  - read `project.get_option("sentry:new_issue_hourly_limit")` and return if the value is `0` or the feature flag is off;
  - call `ratelimits.backend.is_limited_with_value(key="new_issue_hourly_limit", limit=limit, project=project, window=3600)`; the signature is at `src/sentry/ratelimits/base.py:27`, and `event_manager.py:2473-2485` shows a call;
  - if the project is over the limit, record a metric and `raise HashDiscarded("New issue rate limit exceeded", reason="new_issue_rate_limit")`.
- **`src/sentry/event_manager.py:1478` `create_group_with_grouphashes`:** call the new check **inside** the `if existing_grouphash is None:` branch (`:1525`), before `record_new_group_metrics` and `_create_group` (`:1530`).
  - Don't put it next to the load-shed check at `:1491`. There it would count events that lose the lock race and end up joining an existing group.
  - Raising inside `transaction.atomic` only rolls back the row locks. The GroupHash rows stay without a group, so a later event with the same hash can create the issue once the hourly window frees up.
- **`event_manager.py:1318` `assign_event_to_group`:** no change needed. Events matching existing issues (`:1330`, `:1336`) and Seer matches (`:1356`) never reach the check, so only new issues count.
- **`event_manager.py:552` (`save_error_events` `except HashDiscarded`):** already calls `discard_event(job, attachments)` and re-raises.
  - Pass `e.reason` through so the dropped event isn't reported as a discarded hash.
  - For `increment_group_tombstone_hit_counter`, `tombstone_id=None` is already handled; confirm it does nothing.
- **`event_manager.py:2257` `discard_event`:** add an optional `reason` argument. It currently always reports `Outcome.FILTERED` with `FilterStatKeys.DISCARDED_HASH` (`:2278-2287`) and refunds quota (`:2270`).
  - For this cap, use `Outcome.RATE_LIMITED` with reason `"new_issue_rate_limit"`, or add a new `FilterStatKeys` value.
  - Decide whether a rate-limited event should get its quota refunded; I'd suggest yes, matching how discarded hashes are treated.
- **`src/sentry/ingest/inbound_filters.py:23` `FilterStatKeys`:** add a constant here, only if you choose the FILTERED outcome route.
- **`src/sentry/tasks/store.py:635`:** no change. It already cleans up the processing store and attachments on `HashDiscarded`.
- **Out of scope unless you want it:** issue-platform (non-error) groups are created through `src/sentry/issues/ingest.py:197` `save_issue_from_occurrence` / `should_create_group` (`:223`). Covering them would need the same check there.

## 4. Frontend settings form

This goes in a **separate PR**, merged after the backend PR (AGENTS.md rule).

- **`static/app/types/project.tsx:109`:** add `newIssueHourlyLimit: number;` to the detailed project type.
- **`static/app/views/settings/projectGeneralSettings/index.tsx`:**
  - Add `newIssueHourlyLimit: z.number().int().min(0)` to `projectSettingsSchema` (`:205`).
  - In the "Event Settings" `FieldGroup` (`:751-784`), add an `<AutoSaveForm name="newIssueHourlyLimit" schema={projectSettingsSchema} initialValue={project.newIssueHourlyLimit ?? 0} mutationOptions={projectMutationOptions}>` with a number input row. Label it "New issue limit (per hour)" with hint text saying `0` = unlimited.
  - Show it only when `project.features.includes('new-issue-hourly-limit')`, and respect `disabled`.
  - `AutoResolveForm` (`:323`) is the model if you want a custom form instead.
- **`static/app/views/settings/fieldRegistry.generated.ts:166`:** regenerate with `scripts/extractFormFields.ts` (don't hand-edit it). This adds `project-general-settings.newIssueHourlyLimit` to settings search.

## 5. Tests

- **`tests/sentry/core/endpoints/test_project_details.py`:** add tests modelled on `test_resolve_age` (`:958`) covering:
  - a value is saved;
  - a negative value returns 400;
  - the flag being off returns 400;
  - a member without write scope can't set it;
  - the value appears in the GET response.
- **`tests/sentry/event_manager/test_event_manager.py`:** with the option set to N, save N+1 events with different fingerprints and check that:
  - N groups are created, and the extra event raises `HashDiscarded` with the new reason and emits the expected outcome;
  - an event matching an existing group is still accepted while over the cap.
- **`tests/sentry/grouping/ingest/`:** unit test for `check_for_new_issue_rate_limit`.
- **`static/app/views/settings/projectGeneralSettings/index.spec.tsx`:** add `newIssueHourlyLimit` to the fixture (`:32`) and check that the field is shown and sends a PUT.