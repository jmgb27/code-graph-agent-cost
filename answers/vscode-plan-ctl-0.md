# Plan: add a per-language `editor.formatOnSaveTimeout` setting

Here is the path a save takes today. `TextFileSaveParticipant.participate` runs each participant with a shared token. `FormatOnSaveParticipant` calls `formatDocument*WithSelectedProvider`. That goes through `mainThreadLanguageFeatures`, then `rpcProtocol._remoteCall`, then `extHostLanguageFeatures._withAdapter`. The token is already passed along this whole path. So the change is mostly local to the save participant, plus the setting registration and tests.

## 1. Register the setting

**`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`**: add a third property next to `editor.formatOnSave` (`:391`) and `editor.formatOnSaveMode` (`:396`), in the same `editorConfigurationBaseNode` block:
```ts
'editor.formatOnSaveTimeout': {
	type: 'number',
	default: 0,           // 0 = no limit (current behavior)
	minimum: 0,
	markdownDescription: nls.localize('formatOnSaveTimeout', "Timeout in milliseconds after which format on save is cancelled and the file is saved unformatted. `0` disables the timeout. Only applies when `#editor.formatOnSave#` is enabled."),
	scope: ConfigurationScope.LANGUAGE_OVERRIDABLE,
},
```
- `LANGUAGE_OVERRIDABLE` makes `"[typescript]": { "editor.formatOnSaveTimeout": 2000 }` work.
- Don't copy the `codeActionsOnSaveTimeout?: number` field in `IEditorOptions` (`src/vs/editor/common/config/editorOptions.ts:689`, also in `src/vs/monaco.d.ts:3844`). Nothing reads it, and the save participant is workbench-level, so the setting belongs here like its siblings.

## 2. The save participant (the main change)

**`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`**, `FormatOnSaveParticipant.participate` (`:226-270`):

1. Next to `enabled` and `mode` (`:248`, `:254`), read the timeout using the same `overrides` object (`:235`), so the per-language value applies:
   `const timeout = this.configurationService.getValue<number>('editor.formatOnSaveTimeout', overrides);`
2. If `timeout > 0`, create `const cts = new CancellationTokenSource(token)`. `CancellationTokenSource` is already imported at `:6`. Start a timer that calls `cts.cancel()` (e.g. `disposableTimeout` from `base/common/async.js`). Then pass `cts.token` instead of `token` to the three format calls at `:257`, `:263` and `:267`. `getModifiedRanges` at `:260` takes no token, so wrap it in `raceCancellation` too, or start the timer after it runs.
3. Wrap the format calls in `raceCancellation(..., cts.token)`. This covers a hung extension host whose event loop never processes the cancel message.
4. **Catch the cancellation caused by the timeout.** This step matters most. In `src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:69-77`, a `CancellationError` thrown while the outer token is *not* cancelled is read as "the participant wants the save aborted", so it sets `bubbleCancel` and throws at `:89-91`. A timeout that escapes as `CancellationError` would therefore **abort the save** instead of saving the file unformatted. So:
   - catch `isCancellationError(err)` when `cts.token.isCancellationRequested && !token.isCancellationRequested`;
   - report or log it (e.g. `progress.report` or `ILogService.info`, "Formatting timed out after {0}ms ([configure](...))"), and return normally;
   - still rethrow when the outer `token` was cancelled (the user clicked "Skip" or the save was cancelled).
5. Dispose the timer and `cts` in `finally`.
6. Add `@ILogService` to the constructor (`:218-224`) if you log.

You don't need to change `textFileSaveParticipant.ts` itself. The per-participant token composes with its outer `cts` (`:35`) and its "Skip" notification (`:48-82`).

**No change needed in `src/vs/editor/contrib/format/browser/format.ts`.** `formatDocumentWithProvider` (`:310`) and `formatDocumentRangesWithProvider` (`:128`) already chain the incoming token into `EditorStateCancellationTokenSource`/`TextModelCancellationTokenSource` (`:144/147`, `:325/328`) and pass `cts.token` to the provider (`:164`, `:201`, `:333`). Both functions also have an `isCancellationRequested` check before applying edits (`:251`, `:341`), so late results are dropped rather than applied after the timeout.

## 3. Cancellation to the extension host (already works, verify only)

- `src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:456-473`: `$registerDocumentFormattingSupport` / `$registerRangeFormattingSupport` pass `token` as the last argument to `$provideDocument(Range|Ranges)FormattingEdits`.
- `src/vs/workbench/services/extensions/common/rpcProtocol.ts:461-488`: `_remoteCall` takes a trailing `CancellationToken` and sends `MessageType.Cancel` (`:484`, `:946`) when it fires. The receiving side handles it in `_receiveCancel` (`:395`).
- `src/vs/workbench/api/common/extHostLanguageFeatures.ts:2494-2511`: the `$provide…FormattingEdits` methods pass the token to the `DocumentFormattingAdapter` (`:703-715`) / `RangeFormattingAdapter` and to `_withAdapter` (`:2214`). `_withAdapter` rejects straight away through `raceCancellationError` (`:2248-2249`), so the main thread gets a `CancellationError` back. That is the error step 2.4 has to catch.
- No changes are needed in `extHost.protocol.ts` (`:2978-2980`) or `vscode.d.ts`. Extensions already get a cancelled `CancellationToken`.

## 4. Settings UI

No code change is needed:
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:94-98`: the `editor/format` TOC entry matches `editor.format*`, so the setting shows under Text Editor › Formatting.
- Language filtering (`@lang:typescript`) and `[lang]` overrides come from the `LANGUAGE_OVERRIDABLE` scope.
- Optional: leave `COMMONLY_USED_SETTINGS` (`settingsLayout.ts:31-45`) and `getMostCommonlyUsedSettings` (`src/vs/workbench/services/preferences/browser/preferencesService.ts:574-589`) alone. It's a niche setting.
- Optional: point the "configure" link at `:243` to the new setting when the timeout message is shown.

## 5. Tests

**`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`** (suite at `:20`):
- Export `FormatOnSaveParticipant` from `saveParticipants.ts:216` (today it isn't exported) and add it to the import at `:8`.
- Register a fake `DocumentFormattingEditProvider` on `ILanguageFeaturesService` whose promise never resolves and which records `token.onCancellationRequested`.
- Use `runWithFakedTimers` from `base/test/common/timeTravelScheduler.js`.
- Test cases:
  1. With a timeout of 100, `participate` **resolves** (does not throw `CancellationError`), the provider's token is cancelled, and the model is unchanged.
  2. With the timeout at 0, there is no cancellation. A provider that resolves after a delay still has its edits applied.
  3. A provider that resolves before the timeout has its edits applied, and no cancellation is recorded.
  4. When the outer token is cancelled, it still propagates (the "Skip" behavior is preserved).
  5. Per-language: `TestConfigurationService.getValue` ignores `overrideIdentifier` (`src/vs/platform/configuration/test/common/testConfigurationService.ts:30-43`). Either stub `getValue` to branch on `overrides.overrideIdentifier`, or assert that the key is read with `{ overrideIdentifier: model.getLanguageId() }`.
- Keep `ensureNoDisposablesAreLeakedInTestSuite()` (`:178`) passing by disposing the timer and CTS.

**`src/vs/workbench/services/textfile/test/browser/textFileEditorModel.test.ts`** (optional, end to end): a save with a participant that times out still writes the file and clears the dirty state. This guards against the `bubbleCancel` pitfall.

**`src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts`** (optional): a cancelled token passed to `$provideDocumentFormattingEdits` reaches the extension provider and rejects with a cancellation error. `src/vs/workbench/services/extensions/test/common/rpcProtocol.test.ts` already covers cancellation over RPC.

## Out of scope, worth a follow-up

The notebook `FormatOnSaveParticipant` (`src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61`) has a separate `notebook.formatOnSave.enabled` setting. A matching `notebook.formatOnSaveTimeout` would follow the same pattern.