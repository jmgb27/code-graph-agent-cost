I didn't edit any files. Almost all of the change goes in three places: the setting registration, `FormatOnSaveParticipant`, and one guard in `format.ts`. The extension host and the settings UI need no code changes. One bug has to be avoided, covered in step 2.

## 1. Setting registration
**`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`**: add the setting to the same `editorConfigurationBaseNode` block as `editor.formatOnSave` (`:391`) and `editor.formatOnSaveMode` (`:396`):
```ts
'editor.formatOnSaveTimeout': {
    type: 'number',
    default: 0,              // 0 = no limit (keeps today's behaviour)
    minimum: 0,
    markdownDescription: nls.localize('formatOnSaveTimeout', "Timeout in milliseconds after which format on save is cancelled and the file is saved unformatted. Use `0` for no timeout. Only applies when `#editor.formatOnSave#` is enabled."),
    scope: ConfigurationScope.LANGUAGE_OVERRIDABLE,
},
```
- `LANGUAGE_OVERRIDABLE` is what makes `"[python]": { "editor.formatOnSaveTimeout": 3000 }` work. `files.participants.timeout` (`:380-384`) is the existing example of a millisecond timeout setting.
- Optionally, add a mention of the new setting to the `formatOnSave` description at `:393`.

## 2. Save participant: `FormatOnSaveParticipant.participate`
**`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:226-270`**
- Read the timeout next to `mode` (`:254`): `getValue<number>('editor.formatOnSaveTimeout', overrides)`. The `overrides` at `:235` already carry the language id and resource, so the per-language value resolves for free.
- If the timeout is greater than 0, create `const cts = new CancellationTokenSource(token)` and `setTimeout(() => cts.cancel(), timeout)`. Pass `cts.token` instead of `token` to the three format calls at `:257`, `:263` and `:267`. Clear the timer and `cts.dispose()` in a `finally`.
- Wrap each format call with `raceCancellation(..., cts.token)` from `base/common/async`. This matters when the extension host is busy and never answers (see step 4).
- **Swallow cancellation caused by the timeout.** If you skip this, the timeout aborts the save instead of just skipping formatting. The reason is in `TextFileSaveParticipant.participate` (`src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:66-78`): a `CancellationError` whose outer token was *not* cancelled is read as "participant wants the save cancelled" (`bubbleCancel = true`, rethrown at `:89-91`). So: `catch (e) { if (isCancellationError(e) && cts.token.isCancellationRequested && !token.isCancellationRequested) { log/report "formatting timed out"; return; } throw e; }`
- Optional: add `ILogService` to the constructor (`:218-222`) to log the timeout with the formatter's name, and change the "configure" link at `:243` to point at `editor.formatOnSaveTimeout`.
- Export the class (it's currently module-private at `:216`) so tests can instantiate it. It's registered in `SaveParticipantsContribution.registerSaveParticipants` (`:455-458`); no change is needed there.

## 3. Format pipeline: pass the token through and respect it
**`src/vs/editor/contrib/format/browser/format.ts`**
- `formatDocumentWithSelectedProvider` (`:290-308`) and `formatDocumentRangesWithSelectedProvider` (`:107-126`) already pass `token` on. No change.
- `formatDocumentWithProvider` (`:310-347`): `await provider.provideDocumentFormattingEdits(model, …, cts.token)` at `:333` isn't raced. Wrap it in `raceCancellationError(…, cts.token)` so the edits are dropped if cancellation wins. The existing `isCancellationRequested` check at `:341` already stops stale edits from being applied.
- `formatDocumentRangesWithProvider` (`:128-288`): do the same for `computeEdits` (`:164`) and `provideDocumentRangesFormattingEdits` (`:201`).
- `cts` is built from `EditorStateCancellationTokenSource`/`TextModelCancellationTokenSource(…, token)` (`:144/147`, `:325/328`), so the parent token already cancels it. No change there.

## 4. Cancellation to the extension host (checked; no change needed)
- `src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:456-467` passes `token` into `$provideDocumentFormattingEdits` / `$provideDocumentRangeFormattingEdits`.
- `src/vs/workbench/services/extensions/common/rpcProtocol.ts:465-495` (`_remoteCall`) sends a cancel message when that token fires (`:483-487`). But the main-thread promise stays pending until the extension host replies, which is why step 3's race is needed.
- `src/vs/workbench/api/common/extHostLanguageFeatures.ts:2494-2506` passes the token to the extension's provider (`DocumentFormattingAdapter.provideDocumentFormattingEdits` `:710`, `RangeFormattingAdapter` `:730`). `_withAdapter` (`:2214-2252`) races it with `raceCancellationError` (`:2248-2249`), so the extension sees `token.isCancellationRequested` and the reply comes back quickly.

## 5. Settings UI (no code change needed)
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:94-98`: the `editor/format` table-of-contents entry uses `settings: ['editor.format*']`, so the new setting appears under Text Editor › Formatting automatically. Because it's `LANGUAGE_OVERRIDABLE`, it also shows up under `@lang:` filters. The `number` type gets the number input.
- Leave it out of the "commonly used" lists (`settingsLayout.ts:31-45` and `preferencesService.ts:574-589` `getMostCommonlyUsedSettings`). If you do add it, add it to both.

## 6. Tests
- **`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`** (suite at `:20`, uses `TestConfigurationService`): add `FormatOnSaveParticipant` tests. Register a document formatting provider through `ILanguageFeaturesService` and use `runWithFakedTimers`:
  1. A provider that never resolves, with timeout 100: `participate` resolves (doesn't throw `CancellationError`) and the model is unchanged.
  2. A provider that checks `token.isCancellationRequested`: it becomes true after the timeout.
  3. A fast provider with a timeout: edits are applied.
  4. Timeout `0`: no timer is created (current behaviour).
  5. A per-language override: `[lang]` timeout wins over the default.
  6. Outer token cancelled by the user's "Skip": still propagates as today.
- **`src/vs/workbench/services/textfile/test/browser/textFileEditorModel.test.ts`**: an end-to-end test that `save()` still writes the file when the format participant times out, which guards the `bubbleCancel` issue from step 2.
- **`src/vs/editor/contrib/format/test/browser/`**: add a test that `formatDocumentWithProvider` returns without applying edits when the token is cancelled while the provider hangs (the race from step 3).
- **`src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts`** (formatting tests near `:1129-1160`): add a "Format Doc, cancellation" test where the provider sees the token cancelled and `$provideDocumentFormattingEdits` rejects with a cancellation error.

## 7. Related (optional, same pattern)
Notebook format-on-save, `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61-…`: its `FormatOnSaveParticipant.participate` (`:71`) calls `getDocumentFormattingEditsWithSelectedProvider` (`:98`). It could use the same timeout per cell language, but it has its own setting (`NotebookSetting.formatOnSave`, `:80`). Treat it as a follow-up.

**Resulting behaviour:** the existing "Skip" notification (after a 3–5 s delay, `textFileSaveParticipant.ts:48-53`) still works. The new timeout cancels only formatting, and later participants and the save itself carry on.