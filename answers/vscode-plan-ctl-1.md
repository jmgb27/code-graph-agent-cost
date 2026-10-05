# Plan: `editor.formatOnSaveTimeout` (per-language)

**One thing to watch out for.** A timeout that cancels a token will abort the whole save unless the participant catches the resulting error. Here is the path:

1. The main thread sends a `$cancel` for the formatting request (`src/vs/workbench/services/extensions/common/rpcProtocol.ts:482-486`).
2. The extension host's `_withAdapter` then rejects via `raceCancellationError` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2248-2249`).
3. That `CancellationError` comes back through `formatDocumentWithProvider`, which has only a `finally` and no `catch` (`src/vs/editor/contrib/format/browser/format.ts:332-347`).
4. `TextFileSaveParticipant.participate` sees a cancellation error while its own token is not cancelled. It reads that as "this participant wants the save cancelled" (`src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:70-76`) and throws, so **the file is not saved**.

So `FormatOnSaveParticipant` must catch cancellation errors caused by its own timeout. Only errors from the outer token should be re-thrown.

## 1. Setting registration
**`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`**: add the setting to the `registerConfiguration({...editorConfigurationBaseNode, ...})` block, next to `editor.formatOnSaveMode` (lines 396-411):
```ts
'editor.formatOnSaveTimeout': {
  type: 'number',
  default: 0,          // 0 = no limit (keeps today's behavior)
  minimum: 0,
  markdownDescription: nls.localize('formatOnSaveTimeout', "Timeout in milliseconds after which format on save is cancelled and the file is saved unformatted. Use `0` for no limit. Only applies when `#editor.formatOnSave#` is enabled."),
  scope: ConfigurationScope.LANGUAGE_OVERRIDABLE,
},
```
`LANGUAGE_OVERRIDABLE` is what allows `"[typescript]": { "editor.formatOnSaveTimeout": 500 }`. A default of `0` keeps current behavior. `files.participants.timeout` at lines 380-384 already uses the same "`0` = special" convention.

## 2. Save participant
**`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`**, `FormatOnSaveParticipant.participate` (`:226-270`):
- After the `enabled` check (`:248-251`), read `this.configurationService.getValue<number>('editor.formatOnSaveTimeout', overrides)`. `overrides` at `:235` already carries `overrideIdentifier` and `resource`, so the per-language value resolves for free.
- If the value is `> 0`, create `const cts = new CancellationTokenSource(token)` (already imported at `:6`) and set a timer that calls `cts.cancel()` and records `timedOut = true`.
- Pass `cts.token` instead of `token` to the three format calls at `:257`, `:263` and `:267`. `getModifiedRanges` at `:260` has no token parameter, but the whole body should still sit inside the timed region.
- Wrap the formatting in `raceCancellation(promise, cts.token)` from `base/common/async.ts:95`. This stops a provider that ignores the token from blocking the save. Without it, `format.ts:333` awaits the provider indefinitely.
- In `catch (err)`: if `isCancellationError(err) && timedOut && !token.isCancellationRequested`, swallow it and optionally call `progress.report(...)` or log "Formatting timed out after {0}ms". Otherwise re-throw.
- In `finally`: `clearTimeout(handle); cts.dispose()`.
- Add imports for `raceCancellation` (`base/common/async.js`) and `isCancellationError` (`base/common/errors.js`). You may also want to inject `ILogService` for the timeout log line.

Two things need no change:
- In `format.ts`, both `formatDocumentWithProvider` (`:310-382`) and `formatDocumentRangesWithProvider` (`:128-288`) already chain the passed token into `EditorStateCancellationTokenSource`/`TextModelCancellationTokenSource` (`:144-147`, `:325-328`). They also already drop edits when the token is cancelled (`:212`, `:220`, `:242`, `:251`, `:341`).
- `CodeActionOnSaveParticipant` (`saveParticipants.ts:273+`) is out of scope. Mention it in the setting description if you want the scope to be explicit.

## 3. Cancellation to the extension host (verify only, no protocol change)
The token already travels over RPC:
- `mainThreadLanguageFeatures.ts:457`, `:467` and `:472`: `$provideDocument{,Range,Ranges}FormattingEdits(..., token)`.
- `extHost.protocol.ts:2978-2980`: the signatures already end in `CancellationToken`.
- `rpcProtocol.ts:465-486` (sends `$cancel` when the token fires) and `:358-400` (the receiver creates a `CancellationTokenSource` and cancels it).
- `extHostLanguageFeatures.ts:2494-2511`: forwards the token to `_withAdapter`. `DocumentFormattingAdapter.provideDocumentFormattingEdits` (`:710-720`) and `RangeFormattingAdapter` (`:723+`) hand it to the extension's provider.

Don't touch the separate hardcoded `onWillSaveTextDocument` budgets: `mainThreadSaveParticipant.ts:36` (1750ms) and `extHostDocumentSaveParticipant.ts:31` (1500ms). They are a different mechanism.

Optional, for parity: the notebook `FormatOnSaveParticipant` at `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61-123` reads `NotebookSetting.formatOnSave` (`:80`). Use `editor.formatOnSaveTimeout` there with each cell's language override only if you want notebooks covered too.

## 4. Settings UI
- No code change is needed for it to appear. The settings editor TOC entry `editor/format` matches `'editor.format*'` (`src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:95-97`), so the new setting lands under **Text Editor › Formatting**. Language-override editing works because of `LANGUAGE_OVERRIDABLE`.
- Leave the commonly-used lists alone: `settingsLayout.ts:31-45` (`COMMONLY_USED_SETTINGS`) and `preferencesService.ts:574-588` (`getMostCommonlyUsedSettings`).
- Optional: add a "configure timeout" hint in the progress message at `saveParticipants.ts:237-246`, which currently links to `editor.formatOnSave` at `:243`. It could link to `editor.formatOnSaveTimeout` so users hitting slow formatters can find the new setting.

## 5. Tests
**`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`** (suite at `:20`, `ensureNoDisposablesAreLeakedInTestSuite` at `:178`):
- Export `FormatOnSaveParticipant` from `saveParticipants.ts:216`, which is currently module-private, and import it at `:8`.
- Register a fake `DocumentFormattingEditProvider` through `ILanguageFeaturesService` on the instantiation service. It should return a promise that never resolves and record whether its token was cancelled. Use `runWithFakedTimers` from `base/test/common/timeTravelScheduler.js` for the tests below.
  1. timeout `0` with a fast provider → edits applied (regression check).
  2. timeout `100` with a hanging provider → `participate` resolves (does **not** reject), the provider's token `isCancellationRequested === true`, and the model is unchanged.
  3. a provider that rejects with `CancellationError` after the timeout → `participate` does not throw. This covers the save-abort path described at the top.
  4. outer token cancelled (user clicks "Skip") → behavior unchanged, and no error is swallowed that shouldn't be.
  5. per-language: `TestConfigurationService` with `editor.formatOnSaveTimeout` only under `[plaintext]` → applied to plaintext and not to other languages.
- Optional end-to-end test through `TextFileSaveParticipant` (`services/textfile/test/...`): a timed-out formatter still results in a saved, non-dirty model.
- **`src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts`** (optional): a test that `$provideDocumentFormattingEdits` rejects with a cancellation error and that the extension's token fires once the main-thread token is cancelled.

## Files touched (summary)
| File | Change |
|---|---|
| `workbench/contrib/files/browser/files.contribution.ts:391-411` | register the setting |
| `workbench/contrib/codeEditor/browser/saveParticipants.ts:216-270` | timeout, CTS, race, swallow self-inflicted cancel, export the class |
| `workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts` | new tests |
| `workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61-123` | optional notebook parity |
| `workbench/api/test/browser/extHostLanguageFeatures.test.ts` | optional RPC-cancel test |
| `editor/contrib/format/browser/format.ts`, `mainThreadLanguageFeatures.ts`, `extHost.protocol.ts`, `extHostLanguageFeatures.ts`, `settingsLayout.ts` | no change (verified that the token and TOC pattern already cover them) |