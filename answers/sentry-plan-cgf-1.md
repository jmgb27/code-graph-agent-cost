I didn't edit anything. Nothing below has been run or tested yet.

**Design:** add a project option `sentry:max_new_issues_per_hour` (an integer; 0 means no cap), exposed on the API as `maxNewIssuesPerHour`. Enforce it at the point where a new error group is about to be created. Relay can't do this check because it doesn't know whether an event will create a new issue — only grouping in the event manager knows. The load-shed killswitch already stops group creation at that spot, and its existing error path discards the event and refunds quota, so the cap reuses that path. Gate the whole thing behind a feature flag.

## 1. Option registration
| File | Change |
|---|---|
| `src/sentry/projectoptions/defaults.py:268` (end of file) | `register(key="sentry:max_new_issues_per_hour", default=0)` |
| `src/sentry/models/options/project_option.py:20` `OPTION_KEYS` | Add `"sentry:max_new_issues_per_hour"` so it loads with the project's other options and the serializer can read it. |
| `src/sentry/features/temporary.py` (near `:521`) | `manager.add("projects:new-issue-rate-cap", ProjectFeature, FeatureHandlerStrategy.FLAGPOLE, api_expose=True)` so the frontend can check it. |
| `src/sentry/options/defaults.py` (near `:1133`, next to the `issues.severity.seer-project-rate-limit` option) | Optional global setting `issues.new-issue-cap.max-per-hour` (an upper bound for the per-project value), using `FLAG_AUTOMATOR_MODIFIABLE`. |

## 2. API serializer and endpoint validation
`src/sentry/core/endpoints/project_details.py`:
- **`ProjectAdminSerializer` (`:217`), field:** add `maxNewIssuesPerHour = EmptyIntegerField(required=False, allow_null=True, min_value=0, help_text=...)` next to `resolveAge` (`:251`). `EmptyIntegerField` is in `src/sentry/api/fields/empty_integer.py:5`.
- **Field validator:** add `validate_maxNewIssuesPerHour(self, value)` next to the other `validate_*` methods (`:446`–`:622`). It should:
  - reject the field if the feature flag is off for `self.context["project"]`;
  - enforce the global upper bound;
  - turn `None` into `0`.
- **`ProjectDetailsEndpoint.put` (`:737`), write:** next to the `resolveAge` block (`:910`–`:916`), add `if "maxNewIssuesPerHour" in result: if project.update_option("sentry:max_new_issues_per_hour", ...): changed_proj_settings[...] = ...`. Recording it in `changed_proj_settings` puts the change in the audit log.
- **Superuser `options` path:** in the elevated-scopes block (`:1143`–`:1146`), add `if "sentry:max_new_issues_per_hour" in options: project.update_option(..., int(...))`.

`src/sentry/api/serializers/models/project.py`:
- `DetailedProjectResponse` (`:995`): add `maxNewIssuesPerHour: int`, next to `resolveAge` (`:1002`).
- `DetailedProjectSerializer.serialize` (`:1126`): add `"maxNewIssuesPerHour": int(attrs["options"].get("sentry:max_new_issues_per_hour", 0))`.

`src/sentry/apidocs/examples/project_examples.py:139` and `:165`: add the option key and the response field to the API doc examples.

## 3. Enforcement in the event pipeline
The new error group is created along this call chain: `save_error_events` (`src/sentry/event_manager.py:521`) → `assign_event_to_group` (`:1318`) → `create_group_with_grouphashes` (`:1478`) → `_create_group` (`:1549`).

- **`src/sentry/grouping/ingest/utils.py`, new function:** add `check_for_new_issue_rate_cap(project, event)` next to `check_for_group_creation_load_shed` (`:37`). It should:
  - do nothing if the flag is off or the cap is 0 (read the cap with `project.get_option("sentry:max_new_issues_per_hour")`);
  - otherwise call `ratelimits.backend.is_limited(f"issues:new-issue-cap:{project.id}", limit=cap, window=3600)`, the same way `_get_severity_metadata_for_group` does at `event_manager.py:2061`–`2096`;
  - when the project is over the cap, emit `metrics.incr("grouping.new_issue_cap.dropped")` and raise `HashDiscarded("New issue cap reached", reason="new_issue_cap")`.
- **Where to call it — `create_group_with_grouphashes` (`event_manager.py:1478`):** do **not** put the check before the lock, next to `check_for_group_creation_load_shed` (`:1491`). Put it inside the `if existing_grouphash is None:` branch (`:1530`), before `record_new_group_metrics` and `_create_group` (`:1533`–`1535`). That way:
  - events that lose the race to create the same group don't use up the budget;
  - the exception rolls back the `atomic()` block, so no group row is left behind.
- **`save_error_events` (`:552`–`555`):** the `except HashDiscarded` already calls `discard_event`, which refunds quota and emits a FILTERED outcome. Pass `e.reason` through, i.e. `discard_event(job, attachments, reason=e.reason)`.
- **`discard_event` (`event_manager.py:2257`):** add a `reason` parameter. When it is `"new_issue_cap"`, use the new filter reason in both `track_outcome` calls (`:2283`, `:2298`) and tag the `events.discarded` metric (`:2315`).
- **`src/sentry/ingest/inbound_filters.py:23` `FilterStatKeys`:** add `NEW_ISSUE_CAP = "new-issue-cap"` next to `DISCARDED_HASH` (`:38`), so the stats page shows these drops separately.
- **Issue platform (optional):** `save_issue_from_occurrence` in `src/sentry/issues/ingest.py:197` has its own group-creation path, which runs after `should_create_group` (`:223`). Apply the same check there if the cap should also cover performance and other non-error issues.

**Behavior to note:** an event dropped by the cap has no group, so the next event with the same fingerprint will try to create the group again. After the hour window resets, it will succeed. This is intended — the issue appears once there's budget.

## 4. Frontend settings form
- **`static/app/types/project.tsx:109`:** add `maxNewIssuesPerHour: number;` to the project type, next to `resolveAge`.
- **`static/app/views/settings/projectGeneralSettings/index.tsx`:**
  - Add a zod schema next to `resolveAgeSchema` (`:193`): `z.object({maxNewIssuesPerHour: z.number().int().min(0)})`.
  - Add a new `NewIssueCapForm({project, disabled})` component copied from `AutoResolveForm` (`:323`–`410`). It should:
    - use `useScrapsForm` and `useUpdateProjectMutationOptions(project)`;
    - submit `{maxNewIssuesPerHour}`;
    - show an input or number field (`field.Input` / number) with a hint like "0 = unlimited";
    - reuse the `requestErrorToFieldErrors` error handling.
  - Render it in `ProjectGeneralSettings` (`:554`), inside the "Event Settings" `FieldGroup` (`:751`–`784`), and only when `organization.features.includes('...')` / `project.features.includes('new-issue-rate-cap')` is true.
- **`static/app/views/settings/fieldRegistry.generated.ts:166`:** this file is generated by `scripts/extractFormFields.ts` — regenerate it, don't edit by hand, so an entry for `project-general-settings.maxNewIssuesPerHour` appears.

## 5. Tests
- **`tests/sentry/core/endpoints/test_project_details.py`:** check that PUT saves the option and writes the audit entry; that negative values and flag-off requests are rejected; and that GET returns the field.
- **`tests/sentry/api/serializers/test_project.py`:** check that the field is serialized.
- **`tests/sentry/event_manager/grouping/test_group_creation_lock.py`, or a new test next to it:**
  - with the cap at N, the (N+1)th new fingerprint in an hour is dropped with the new outcome reason and no `Group` row is created;
  - new events for existing groups are still accepted.
- **`static/app/views/settings/projectGeneralSettings/index.spec.tsx`:** add a save test modeled on the resolveAge one (`:455`–`470`).

**PR split (per `AGENTS.md`):** sections 1–3 and the backend tests go in a backend PR, which lands first. Section 4 and the spec test go in a separate frontend PR.