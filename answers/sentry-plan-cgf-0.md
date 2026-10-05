# Plan: per-project hourly cap on new issues, enforced at ingestion

I didn't edit any files. The design copies two existing patterns:
- **Settings:** handle the new setting the same way as `resolveAge`, from the project option through the serializer, endpoint and settings form.
- **Enforcement:** raise `HashDiscarded` in the new-group branch of the error pipeline, the same way the load-shed killswitch does. The pipeline already catches that exception, refunds quota, records an outcome and cleans up.

**Names I'm proposing:**
- Project option: `sentry:new_issue_hourly_limit`. `0` or unset means no cap.
- API field: `newIssueHourlyLimit`.
- Feature flag: `projects:new-issue-hourly-limit`.

---

## 1. Registering the option and flag

| File | Change |
|---|---|
| `src/sentry/projectoptions/defaults.py:268` (after the last `register(...)`) | `register(key="sentry:new_issue_hourly_limit", default=0)` |
| `src/sentry/models/options/project_option.py:20-103` (`OPTION_KEYS`) | Add `"sentry:new_issue_hourly_limit"` so `DetailedProjectSerializer.get_attrs` (`src/sentry/api/serializers/models/project.py:1047`) preloads it. |
| `src/sentry/options/defaults.py:~1606` (next to `store.load-shed-group-creation-projects`) | Global options: `issues.new-issue-hourly-limit.max` (the server-side ceiling for validation) and `issues.new-issue-hourly-limit.enabled` (a killswitch for enforcement), both `FLAG_AUTOMATOR_MODIFIABLE`. |
| `src/sentry/features/temporary.py` | Register `projects:new-issue-hourly-limit` as a `ProjectFeature` with `api_expose=True`, so the frontend can gate the form. |

## 2. API serializer and endpoint validation

**`src/sentry/core/endpoints/project_details.py`**
- **`ProjectAdminSerializer` (`:217`):** add a field next to `resolveAge` (`:251`):
  `newIssueHourlyLimit = EmptyIntegerField(required=False, allow_null=True, min_value=0, help_text=...)`
  Because it's an admin-only field, the non-admin permission loop at `:787-792` rejects it for members automatically.
- **New `validate_newIssueHourlyLimit(self, value)`** next to `validate_debugFilesRole` (`:622`):
  - Return 400 if the feature is off for `self.context["project"]`.
  - Return 400 if `value > options.get("issues.new-issue-hourly-limit.max")`.
  - Normalize `None` to `0`.
- **`ProjectDetailsEndpoint.put` (`:737`):** next to the `resolveAge` block (`:910-916`), add:
  ```python
  if "newIssueHourlyLimit" in result:
      if project.update_option("sentry:new_issue_hourly_limit", result["newIssueHourlyLimit"] or 0):
          changed_proj_settings["sentry:new_issue_hourly_limit"] = result["newIssueHourlyLimit"]
  ```
  The existing `PROJECT_EDIT` audit entry at `:1325-1331` picks this up.
- **Optional, for the legacy `options` dict path (`:1140-1146`):** handle `"sentry:new_issue_hourly_limit"` the same way as `sentry:resolve_age`.
- **Docstring of `put` (`:745-755`):** no change needed, since this isn't a `project:read` field.

**`src/sentry/api/serializers/models/project.py`**
- **`DetailedProjectResponse` (`:995`, near `resolveAge: int` at `:1002`):** add `newIssueHourlyLimit: int`.
- **`DetailedProjectSerializer.serialize` (`:1078`, near `:1126`):** add `"newIssueHourlyLimit": int(attrs["options"].get("sentry:new_issue_hourly_limit", 0))`.

## 3. Frontend settings form (separate PR, merged after the backend)

- **`static/app/types/project.tsx:109`:** add `newIssueHourlyLimit: number;` to `DetailedProject`.
- **`static/app/views/settings/projectGeneralSettings/index.tsx`:**
  - `projectSettingsSchema` (`:205`): add `newIssueHourlyLimit: z.number().int().min(0)`.
  - In the "Event Settings" `FieldGroup` (`:750-784`), after `<AutoResolveForm>` (`:751`), add an `<AutoSaveForm name="newIssueHourlyLimit" schema={projectSettingsSchema} initialValue={project.newIssueHourlyLimit ?? 0} mutationOptions={projectMutationOptions}>`.
    - It renders `field.Layout.Row` with a number input, a label like "New issue limit (per hour)", and a hint that 0 means unlimited and that events which would create more issues are dropped.
    - Use `disabled={disabled}`.
    - Wrap it in `organization.features.includes('new-issue-hourly-limit')` (or check `project.features`).
  - Backend 400s already reach the field through the existing `requestErrorToFieldErrors` pattern (`:340-346`).
- **Tests:** `static/app/views/settings/projectGeneralSettings/index.spec.tsx`. Assert that the PUT sends `{newIssueHourlyLimit: N}` and that the field is hidden without the flag.

## 4. Enforcement in the event pipeline

Here is the error path as it stands:
1. `EventManager.save_error_events` (`src/sentry/event_manager.py:521`) calls `assign_event_to_group` (`:1318`).
2. When no grouphash matches and Seer finds nothing, that calls `create_group_with_grouphashes` (`:1478`, reached at `:1359`).
3. That calls `_create_group` (`:1549`).

The load-shed check already sits at `:1491` and raises `HashDiscarded`. `save_error_events` catches it at `:552-555` and calls `discard_event`. `tasks/store.py:635-642` then cleans up the cache and attachments.

**`src/sentry/grouping/ingest/utils.py`**
- **New `check_for_new_issue_rate_limit(project, event) -> None`**, next to `check_for_group_creation_load_shed` (`:37`):
  - Read `project.get_option("sentry:new_issue_hourly_limit")` (cached through `ProjectOption`). Return early if it's `0`, the killswitch option is off, or `features.has("projects:new-issue-hourly-limit", project)` is false.
  - Call `ratelimiter.backend.is_limited(f"new-issue-hourly-limit:{project.id}", limit=cap, window=3600)`. The interface is at `src/sentry/ratelimits/base.py:16` and the Redis version at `src/sentry/ratelimits/redis.py:93`.
  - If limited, call `metrics.incr("grouping.new_issue_rate_limited")` and `raise HashDiscarded("New issue rate limit", reason="new_issue_rate_limit")` (`HashDiscarded` is defined at `src/sentry/exceptions.py:87`).

**`src/sentry/event_manager.py`**
- **Import** the new helper next to `check_for_group_creation_load_shed` (`:79`).
- **Call it in `create_group_with_grouphashes` (`:1478`)** inside the `if existing_grouphash is None:` branch (`:1530`), before `record_new_group_metrics` and `_create_group` (`:1533-1535`).
  - In that position, only real new-group creations use up the budget. Events that lose the creation race still attach to the other worker's group.
  - Raising inside the `transaction.atomic` rolls back cleanly, the same as the `:1706` timeout case.
- **`discard_event` (`:2257`)** hardcodes `FilterStatKeys.DISCARDED_HASH` (`:2283`, and again for attachments). Add a `reason` parameter:
  - Pass `getattr(e, "reason", None)` from `save_error_events` (`:552-554`).
  - Map `"new_issue_rate_limit"` to a new filter key.
  - Without this, the dropped events are counted as "discarded hash" in the stats.
- **`src/sentry/ingest/inbound_filters.py:23-40` (`FilterStatKeys`):** add `NEW_ISSUE_RATE_LIMITED = "new-issue-rate-limited"  # Not replicated in Relay`, plus its TSDB mapping near `:53` (reuse `TSDBModel.project_total_received_discarded`, `src/sentry/tsdb/base.py:102`).
- **`save_error_events` `:553`:** `increment_group_tombstone_hit_counter` already no-ops when `tombstone_id` is `None`, so nothing else changes there.

**Issue-platform path (decide the scope):** `save_issue_from_occurrence` (`src/sentry/issues/ingest.py:197`) creates groups through `save_grouphash_and_group` (`src/sentry/event_manager.py:2811`, called at `ingest.py:257`), which bypasses `create_group_with_grouphashes`. If performance, feedback and uptime issues should count too, call the same helper before `_create_group` at `event_manager.py:2821`. Otherwise, document the cap as errors-only. I recommend errors-only for v1.

## 5. Tests

- **`tests/sentry/core/endpoints/test_project_details.py`:** the admin PUT saves the option and writes the audit entry; a member gets 403; negative values and values above the ceiling get 400; missing flag gets 400; GET returns `newIssueHourlyLimit`.
- **`tests/sentry/grouping/ingest/`** (new `test_utils.py` or an existing one): the helper does nothing when the cap is `0`, the flag is off or the killswitch is off, and raises once the cap is exceeded.
- **`tests/sentry/event_manager/test_event_manager.py`:** with the cap set to `N`, `N+1` distinct fingerprints create `N` groups. The extra event is discarded with the new outcome reason and its quota is refunded. Events for existing groups still go through when over the cap.
- **`tests/sentry/event_manager/grouping/test_group_creation_lock.py`:** check that a creation race doesn't double-count.

**PR split** (per `AGENTS.md`): PR 1 is backend (sections 1, 2, 4 and backend tests). PR 2 is frontend (section 3).