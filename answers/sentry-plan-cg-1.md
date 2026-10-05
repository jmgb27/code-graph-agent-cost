# Plan: per-project cap on new issues per hour

**Approach:** add a project option, `sentry:max_new_issues_per_hour` (an integer; `0` means no cap). The API exposes it as `maxNewIssuesPerHour` and it's edited from "Project Settings → Event Settings". Ingestion enforces it at the one place error groups are created, using the existing load-shedding path (`HashDiscarded`). Put it behind a FlagPole flag. Backend and frontend go in **separate PRs**, backend first.

## 1. Option registration (backend)

| File | Change |
|---|---|
| `src/sentry/projectoptions/defaults.py:28` (next to the other `sentry:` registrations) | `register(key="sentry:max_new_issues_per_hour", default=0)` |
| `src/sentry/models/options/project_option.py:20` (`OPTION_KEYS`) | Add `"sentry:max_new_issues_per_hour"`. Without it, `DetailedProjectSerializer.get_attrs` (`src/sentry/api/serializers/models/project.py:1047`) won't load the option. |
| `src/sentry/features/temporary.py` | Register `projects:new-issue-rate-limit` (a `ProjectFeature`, `api_expose=True`). Use the **`feature-flags`** skill. |
| `src/sentry/options/defaults.py` (near `issues.client_error_sampling.project_allowlist`, `:4006`) | Optional global controls: `issues.new-issue-rate-limit.enabled` (a killswitch) and `issues.new-issue-rate-limit.max-value` (an upper bound for validation). |

## 2. API serializer and endpoint validation

`src/sentry/core/endpoints/project_details.py`:
- **`ProjectAdminSerializer`** (`:217`): add the field next to `resolveAge` (`:251`):
  `maxNewIssuesPerHour = serializers.IntegerField(required=False, allow_null=True, min_value=0, help_text=...)`
- **New `validate_maxNewIssuesPerHour`**, placed with the other validators, for example after `validate_tempestFetchScreenshots` (`:614`):
  - Reject if `features.has("projects:new-issue-rate-limit", self.context["project"])` is false. This copies the feature check in `validate_tempestFetchScreenshots`.
  - Normalise `None` to `0`, and enforce the optional `max-value` bound.
- **`ProjectDetailsEndpoint.put`** (`:737`): after the `resolveAge` block (`:911-916`), add:
  ```python
  if "maxNewIssuesPerHour" in result:
      if project.update_option("sentry:max_new_issues_per_hour", result["maxNewIssuesPerHour"] or 0):
          changed_proj_settings["sentry:max_new_issues_per_hour"] = result["maxNewIssuesPerHour"]
  ```
  Adding the key to `changed_proj_settings` makes the existing `create_audit_entry` call (`:1325`) record the change.
- **Legacy `options` dict writer** (`:1139-1146`): add an `int(...)` branch like the one for `sentry:resolve_age`, or leave it out on purpose so the only way to write the setting is the validated field.

`src/sentry/api/serializers/models/project.py`:
- `DetailedProjectResponse` (`:995`): add `maxNewIssuesPerHour: int` next to `resolveAge` (`:1002`).
- `DetailedProjectSerializer.serialize` (`:1126`): add `"maxNewIssuesPerHour": int(attrs["options"].get("sentry:max_new_issues_per_hour", 0))`.

`src/sentry/apidocs/examples/project_examples.py:139`: add `"sentry:max_new_issues_per_hour": 0` and the camelCase field to the example response.

## 3. Enforcement in the event pipeline

The call path is `save_event` (`src/sentry/tasks/store.py`) → `EventManager.save_error_events` (`src/sentry/event_manager.py:521`) → `assign_event_to_group` (`:1318`) → `create_group_with_grouphashes` (`:1478`) → `_create_group` (`:1549`).

- **`src/sentry/grouping/ingest/utils.py`**: add `check_for_new_issue_rate_limit(project, event)` next to `check_for_group_creation_load_shed` (`:37`):
  - Read `limit = project.get_option("sentry:max_new_issues_per_hour")`. Return early if the limit is `0`, the flag is off, or the killswitch is off.
  - Call `ratelimiter.is_limited(f"new-issues:{project.id}", limit=limit, project=project, window=3600)`. The API is `src/sentry/ratelimits/base.py:16`, and the Redis backend's `is_limited_with_value` is at `ratelimits/redis.py:93`. It uses time-bucketed Redis keys that expire, so it complies with the Redis TTL rule.
  - If limited, emit `metrics.incr("grouping.new_issue_rate_limited", tags={"platform": ...})` and `raise HashDiscarded("New issue rate limit", reason="new_issue_limit")`.
- **`src/sentry/event_manager.py` `create_group_with_grouphashes`**: call the check **inside the lock, in the `if existing_grouphash is None:` branch (`:1530`)**, before `record_new_group_metrics` (`:1533`).
  - **Why there:** at that point we know a group really will be created. Events that lose the creation race (`:1544-1546`) and events matching existing groups never use up budget.
  - Raising inside `transaction.atomic` is safe because nothing has been written yet.
  - The alternative is next to `check_for_group_creation_load_shed` (`:1491`). That avoids a Redis call while holding row locks, but race losers would count against the cap.
- **Outcomes and quota refund:** `HashDiscarded` is already caught in `save_error_events` (`:552-555`), which calls `discard_event` and re-raises. `tasks/store.py:635` then cleans up the processing store and attachments. Two changes are needed:
  - `src/sentry/ingest/inbound_filters.py:39` (`FilterStatKeys`): add `NEW_ISSUE_LIMIT = "new-issue-limit"  # Not replicated in Relay`. Check whether `FILTER_STAT_KEYS_TO_VALUES` needs an entry; `CRASH_REPORT_LIMIT` is the pattern to copy.
  - `event_manager.py:2257` `discard_event`: add a `reason: str = FilterStatKeys.DISCARDED_HASH` parameter and use it at `:2283` and `:2299`. Then at `:553-554`, pass `FilterStatKeys.NEW_ISSUE_LIMIT` when `e.reason == "new_issue_limit"`, so customers see why events were dropped and aren't billed for them.
- **Behaviour note:** events are dropped (FILTERED outcome, quota refunded), not held. Grouphashes created in `get_hashes_and_grouphashes` (`:1408`) stay without a group, the same as with load-shed. The next event with the same hash after the window resets creates the issue.
- **Scope:** this covers error issues only. Issue-platform groups are created in `src/sentry/issues/ingest.py` (`save_issue_from_occurrence`). Extending the cap there is a separate decision.
- Other code that catches `HashDiscarded` needs no change: `src/sentry/utils/mockdata/core.py:118`.

## 4. Frontend settings form (separate PR)

| File | Change |
|---|---|
| `static/app/types/project.tsx:109` | Add `maxNewIssuesPerHour: number;` to `DetailedProject`. |
| `static/app/views/settings/projectGeneralSettings/index.tsx:205` (`projectSettingsSchema`) | Add `maxNewIssuesPerHour: z.number().int().min(0)`. |
| same file, `ProjectGeneralSettings` "Event Settings" `FieldGroup` (`:751-784`) | Add an `<AutoSaveForm name="maxNewIssuesPerHour" schema={projectSettingsSchema} initialValue={project.maxNewIssuesPerHour ?? 0} mutationOptions={projectMutationOptions}>` after the auto-release form (`:783`). Render a number input in `field.Layout.Row` (label "Max new issues per hour", hint "0 = unlimited; events that would create issues beyond this are dropped"), with `disabled={disabled}`. Show it only when `organization.features.includes('new-issue-rate-limit')`. Use the **`generate-frontend-forms`** skill. |
| `static/app/views/settings/fieldRegistry.generated.ts:166` | Regenerate with `scripts/extractFormFields.ts` so the field appears in settings search. Don't edit this file by hand. |
| Project test fixture (`tests/js/fixtures/project*`) | Add a `maxNewIssuesPerHour: 0` default if the fixture types require it. |

## 5. Tests

- `tests/sentry/core/endpoints/test_project_details.py`: add tests next to `test_resolve_age` (`:958`) for: setting and reading the value, `null` becoming `0`, negative values rejected, rejection when the flag is off, and the audit entry.
- Event-manager and grouping tests (for example under `tests/sentry/event_manager/`): the (N+1)th new hash within the hour raises `HashDiscarded` and emits a `new-issue-limit` outcome. Events on existing groups aren't counted. A limit of `0` means no cap.
- `tests/sentry/api/serializers/test_project.py`: the field appears in the detailed serializer output.
- `static/app/views/settings/projectGeneralSettings/index.spec.tsx`: the field renders behind the flag and saves with a PUT (pattern at `:464`).