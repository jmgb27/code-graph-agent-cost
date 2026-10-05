# Plan: per-language `editor.formatOnSaveTimeout`

**How it works:** the setting is read in `FormatOnSaveParticipant` using the language override. The participant creates a child `CancellationTokenSource` and cancels it when the timeout fires. That child token already reaches the extension host through the existing formatting path, so the RPC protocol needs no changes. The settings UI picks the setting up automatically; at most one optional edit is needed there.

## 1. Setting registration
**`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`**: add the new setting to the `editorConfigurationBaseNode` block, next to `editor.formatOnSave` (`:391`) and `editor.formatOnSaveMode` (`:396`):
```ts
'editor.formatOnSaveTimeout': {
  type: 'number', default: 0 /* or e.g. 1500 */, minimum: 0,
  markdownDescription: nls.localize('formatOnSaveTimeout', "Timeout in milliseconds after which format on save is cancelled. `0` means no timeout. Only applies when `#editor.formatOnSave#` is enabled."),
  scope: ConfigurationScope.LANGUAGE_OVERRIDABLE,
},
```
- Use `LANGUAGE_OVERRIDABLE`, matching `:394` and `:410`. This scope is what makes `"[python]": { "editor.formatOnSaveTimeout": … }` work, and it makes the settings editor show the language filter.
- A default of `0` keeps today's behaviour unchanged.
- Existing precedent for the shape: `files.participants.timeout` at `:380-384`, read at `workingCopyFileOperationParticipant.ts:32`.
- A leftover `codeActionsOnSaveTimeout?: number` sits in `src/vs/editor/common/config/editorOptions.ts:689` (also in `src/vs/monaco.d.ts:3844`), and nothing uses it. Don't put the new option into `IEditorOptions`. Keep it as a workbench setting, like `formatOnSave`.

## 2. Save participant (the core change)
**`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`**, `FormatOnSaveParticipant.participate` (`:226-270`):
- **Export the class** (`:216`) so tests can build it. Today only `TrimWhitespace`, `FinalNewLine` and `TrimFinalNewLines` are exported (see the test import at `saveParticipant.test.ts:8`).
- After the `enabled` check (`:248-251`), read the timeout with the same `overrides` (`:235`):
  `const timeout = this.configurationService.getValue<number>('editor.formatOnSaveTimeout', overrides);`
- Create `const cts = new CancellationTokenSource(token)` (it's already imported at `:6`). If `timeout > 0`, arm a `setTimeout(() => cts.cancel(), timeout)` or a `TimeoutTimer`/`disposableTimeout` from `base/common/async`.
- Pass `cts.token` instead of `token` in all three calls:
  - `:257`: `formatDocumentWithSelectedProvider` (mode `'file'`)
  - `:263`: `formatDocumentWithSelectedProvider` (fallback for `modificationsIfAvailable`)
  - `:267`: `formatDocumentRangesWithSelectedProvider`
- Wrap the body in `try/finally` to clear the timer and call `cts.dispose()`.
- **Timeout behaviour:** the save must still go ahead, so swallow the timeout rather than rethrowing. There are two reasons:
  - `TextFileSaveParticipant.participate` (`src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:66-77`) treats a `CancellationError` whose outer token was *not* cancelled as "the participant wants the save cancelled" (`bubbleCancel = true`). A timeout must not trigger that.
  - Wrap the three awaits with `raceCancellation(promise, cts.token)` so a provider that ignores the token can't block.
- Optionally report through `progress`/`ILogService` that formatting was skipped after N ms. The existing "Running '{0}' Formatter" message (`:237-246`) could also link to the new setting.

**Framework code: no change needed, but check it.**
- `textFileSaveParticipant.ts:34-92` (`TextFileSaveParticipant.participate`) keeps its user-cancellable "Skip" notification (`:48-82`). The per-participant timeout is layered underneath it.
- `saveParticipants.ts:455-461` (`registerSaveParticipants`) needs no change.

## 3. Cancellation to the extension host
The token path is already complete, so the job here is to confirm it, not to add plumbing:
1. **`src/vs/editor/contrib/format/browser/format.ts`**:
   - `formatDocumentWithSelectedProvider` (`:290`) → `formatDocumentWithProvider` (`:310`) wraps the token in `EditorStateCancellationTokenSource`/`TextModelCancellationTokenSource` with `token` as parent (`:325`, `:328`) and passes `cts.token` to `provider.provideDocumentFormattingEdits` (`:333-337`).
   - `formatDocumentRangesWithSelectedProvider` (`:107`) → `formatDocumentRangesWithProvider` (`:128`, token wrapping at `:144`/`:147`) passes it at `:164-169` and `:201-206`.
   - **Optional hardening:** `formatDocumentWithProvider` checks `cts.token.isCancellationRequested` only *after* `computeMoreMinimalEdits` (`:339-343`). Adding a check right after `provideDocumentFormattingEdits` returns avoids wasted worker time after a timeout.
2. **`src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460`**: `$registerDocumentFormattingSupport` forwards `token` into `this._proxy.$provideDocumentFormattingEdits(...)`. The range variants start at `:462`. RPC turns cancelling that token into a cancel message to the extension host.
3. **`src/vs/workbench/api/common/extHostLanguageFeatures.ts`**:
   - `$provideDocumentFormattingEdits` (`:2494`), `$provideDocumentRangeFormattingEdits` (`:2505`) and `$provideDocumentRangesFormattingEdits` (`:2509`) pass `token` both to the adapter (and so to the extension's provider) and as `tokenToRaceAgainst`.
   - `_withAdapter` (`:2214-2252`) then calls `raceCancellationError` (`:2248-2249`), so the extension-host promise rejects right away even if the extension ignores the token.
   - No change is required here. At most, add a trace log for cancellations in `_withAdapter`.

## 4. Settings UI
- **Nothing is required.** The "Formatting" TOC node in `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:95-97` uses the glob `settings: ['editor.format*']`, so the new key shows up there automatically. It renders as a number input, and the language filter appears because of `LANGUAGE_OVERRIDABLE`.
- **Optional:** add the key to the commonly-used lists. They are duplicated in two places and should stay in sync:
  - `settingsLayout.ts:31-45` (`COMMONLY_USED_SETTINGS`)
  - `src/vs/workbench/services/preferences/browser/preferencesService.ts:574-589` (`getMostCommonlyUsedSettings`)
- **Optional:** in the `formatOnSave` description (`files.contribution.ts:393`), cross-link the new setting with `` `#editor.formatOnSaveTimeout#` ``.

## 5. Tests
1. **`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`**, in `suite('Save Participants')` (`:20`):
   - Import the newly exported `FormatOnSaveParticipant` (`:8`).
   - Register a slow `DocumentFormattingEditProvider` through `ILanguageFeaturesService` that awaits its token.
   - Set `editor.formatOnSave: true` and `editor.formatOnSaveTimeout: 50` in `TestConfigurationService`. Wrap the test in `runWithFakedTimers`.
   - Assert that `participate` resolves (does not throw), the provider saw `token.isCancellationRequested`, and the model is unchanged.
   - Add a per-language case: `[plaintext]` override vs. default.
   - Add a `0` case meaning no timeout, where formatting completes.
   - Add a case where the timeout does *not* bubble as a save cancellation. Run it through `TextFileSaveParticipant` via `accessor.textFileService.files.addSaveParticipant` and check the save still completes.
2. **`src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts`**: add a formatting test that cancels the token passed to `$provideDocumentFormattingEdits` and asserts the provider's token is cancelled and the call rejects or returns undefined. This confirms `_withAdapter` races the token.
3. Optionally, a unit test in the format contrib: there's no existing `src/vs/editor/contrib/format/test/`, so it would be a new file. It would check that `formatDocumentWithProvider` returns without applying edits when the parent token is cancelled mid-provide.

## 6. Optional: notebooks
Notebook format-on-save lives in `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:71-122` (`FormatOnSaveParticipant.participate`, which uses `NotebookSetting.formatOnSave`). To give notebooks the same limit:
- read the timeout per cell language;
- wrap `token` in a timed `CancellationTokenSource` before `checkAndRunFormatCodeAction` (`:87`) and `getDocumentFormattingEditsWithSelectedProvider` (`:98-104`, `format.ts:421`).

Otherwise, state in the setting's description that it applies to text editors only.

## Files and functions to change
| File | Function / symbol | Required? |
|---|---|---|
| `workbench/contrib/files/browser/files.contribution.ts:388-413` | editor config registration | yes |
| `workbench/contrib/codeEditor/browser/saveParticipants.ts:216-270` | `FormatOnSaveParticipant` (export, `participate`) | yes |
| `workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts` | new tests | yes |
| `workbench/api/test/browser/extHostLanguageFeatures.test.ts` | cancellation test | yes |
| `editor/contrib/format/browser/format.ts:310-343` | `formatDocumentWithProvider` early-cancel check | optional |
| `workbench/contrib/preferences/browser/settingsLayout.ts:31` + `workbench/services/preferences/browser/preferencesService.ts:574` | commonly-used lists | optional |
| `workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:71` | notebook `FormatOnSaveParticipant.participate` | optional |
| `mainThreadLanguageFeatures.ts:452`, `extHostLanguageFeatures.ts:2494-2510`, `:2214` | cancellation path to the extension host | already works; no change |