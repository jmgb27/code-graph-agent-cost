# Plan: per-language `editor.formatOnSaveTimeout`

Most of the work is in one place: the save participant. The token already travels from `FormatOnSaveParticipant` to the extension through the formatter chain and over RPC, so the extension-host protocol doesn't need to change. The settings UI also picks up the new setting without code changes. The one thing to get right is what happens when the timeout fires, because of how the outer save-participant runner treats cancellation errors (see step 2).

## 1. Setting registration

**`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`**: add a third property to the same `registerConfiguration({...editorConfigurationBaseNode, ...})` block, next to `editor.formatOnSave` (`:391`) and `editor.formatOnSaveMode` (`:396`):
```ts
'editor.formatOnSaveTimeout': {
  type: 'number', default: 0, minimum: 0,
  markdownDescription: nls.localize('formatOnSaveTimeout', "Timeout in milliseconds after which format on save is cancelled and the file is saved unformatted. Use `0` for no limit. Only applies when `#editor.formatOnSave#` is enabled."),
  scope: ConfigurationScope.LANGUAGE_OVERRIDABLE,
},
```
- `LANGUAGE_OVERRIDABLE` is what makes `"[python]": { "editor.formatOnSaveTimeout": 2000 }` work.
- A default of `0` keeps today's behaviour. It follows the style of `files.participants.timeout` at `:380-384`, which uses 60000 as its default and `0` to disable participants.

## 2. Save participant (the main change)

**`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`**, `FormatOnSaveParticipant.participate` (`:226-270`):
1. After the `enabled` check (`:248-251`), read the value with the existing per-language `overrides` from `:235`:
   `const timeout = this.configurationService.getValue<number>('editor.formatOnSaveTimeout', overrides);`
2. Create a child source: `const cts = new CancellationTokenSource(token)`. `CancellationTokenSource` is already imported at `:6`. If `timeout > 0`, start `setTimeout(() => { timedOut = true; cts.cancel(); }, timeout)`.
3. Pass `cts.token` instead of `token` at the three call sites: `:257` and `:263` (`formatDocumentWithSelectedProvider`) and `:267` (`formatDocumentRangesWithSelectedProvider`). Wrap the branch in `raceCancellation(..., cts.token)` so a formatter that ignores its token still can't block the save.
4. **Catch and swallow the cancellation error when `timedOut` is true**, then `clearTimeout` and `cts.dispose()` in a `finally`.
   - Why this matters: `TextFileSaveParticipant.participate` (`src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:69-77`) reads a `CancellationError` thrown while its own token is *not* cancelled as "this participant wants the save aborted". It then sets `bubbleCancel` and throws at `:89-91`.
   - The error will reach it: the ext-host side rejects with `raceCancellationError` (`extHostLanguageFeatures.ts:2248-2249`), and `formatDocumentWithProvider` has only a `finally` around the provider call (`format.ts:332-347`).
   - So without the catch, a timeout would *cancel the save* instead of saving unformatted.
   - Optionally, `progress.report` or log a message such as "Formatter '{0}' timed out after {1}ms".
5. Optionally, also point the "configure" link at `:243` to the new setting.

**Registration**: nothing to change. The participant is already added at `saveParticipants.ts:458`. Export the class (`:216`) so tests can instantiate it directly.

**Notebooks (optional, for parity)**: `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts`, `FormatOnSaveParticipant.participate` (`:71-122`). Apply the same child-CTS and timeout wrapping to the token passed to `CodeActionParticipantUtils.checkAndRunFormatCodeAction` (`:87`) and `getDocumentFormattingEditsWithSelectedProvider` (`:98-104`). Read the timeout per cell with `overrideIdentifier: model.getLanguageId()`.

## 3. Cancellation to the extension host (already wired; verify only)

This is the path the child token already takes; none of it needs changing:
- `format.ts:290` `formatDocumentWithSelectedProvider` → `:310` `formatDocumentWithProvider` wraps the token in `EditorStateCancellationTokenSource` / `TextModelCancellationTokenSource` (`:325`, `:328`) → `provider.provideDocumentFormattingEdits(..., cts.token)` at `:333`.
  - Range mode has the same shape: `format.ts:107` → `:128`, wrapped at `:144` / `:147`.
- `src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:456-458` (and `:466-472` for ranges) passes `token` as the last argument of `this._proxy.$provideDocumentFormattingEdits`.
- `src/vs/workbench/services/extensions/common/rpcProtocol.ts:465-487` (`_remoteCall`) takes the trailing token off the arguments and sends a cancel message when it fires.
- `src/vs/workbench/api/common/extHostLanguageFeatures.ts:2494` `$provideDocumentFormattingEdits` (and `:2505` / `:2509` for ranges) → `_withAdapter` (`:2214`) races with `raceCancellationError` (`:2248`). `DocumentFormattingAdapter.provideDocumentFormattingEdits` (`:710-720`) hands the cancelled token to the extension's provider.

No changes are needed in `extHost.protocol.ts` or the `vscode.d.ts` API. For contrast, `ExtHostDocumentSaveParticipant` (`extHostDocumentSaveParticipant.ts:31`, 1500ms) has its own fixed timeout for `onWillSaveTextDocument`. That's a separate mechanism and is left alone.

## 4. Settings UI

- **TOC**: `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:95-98` has `editor/format` matching `settings: ['editor.format*']`, so the new key lands under *Text Editor › Formatting* automatically. No change.
- **Rendering**: a `type: 'number'` setting uses the generic number renderer, and `LANGUAGE_OVERRIDABLE` makes it show up under the `@lang:` filter. No renderer change.
- **Optional**: don't add it to the "commonly used" lists (`settingsLayout.ts:31-44`, `preferencesService.ts:574-589`); it's too niche.

## 5. Tests

- **`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`** (suite at `:20`; follow the `TestConfigurationService` pattern at `:40-41`). Register a formatter through `ILanguageFeaturesService.documentFormattingEditProvider` and use `runWithFakedTimers`. Add:
  1. A formatter that never resolves plus `editor.formatOnSaveTimeout: 100`: `participate` resolves, the provider's token `isCancellationRequested === true`, no error is thrown, and the model text is unchanged.
  2. The same setup wrapped in `TextFileSaveParticipant.participate`: it does **not** throw `CancellationError` (this is the regression guard for the `bubbleCancel` problem).
  3. A language override (`[lang]` value) wins over the global value.
  4. `0` means no timeout: a formatter that resolves after a delay still applies its edits.
  5. A fast formatter's edits are applied and the timer is cleared (no leaks under `ensureNoDisposablesAreLeakedInTestSuite`).
- **`src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts`** (next to "Format Doc, evil provider" at `:1147`): cancelling the token passed to `getDocumentFormattingEditsUntilResult` / `$provideDocumentFormattingEdits` cancels the extension provider's token, and the call rejects or resolves promptly even when the provider ignores the token.
- **Optional**: in `src/vs/workbench/contrib/preferences/test/browser/settingsTreeModels.test.ts`, check that `editor.formatOnSaveTimeout` resolves into the `editor/format` group.
- **Optional (notebooks)**: a notebook save-participant test mirroring test 1.

## Files to change

| File | Function / location |
|---|---|
| `src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413` | new config property |
| `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216-270` | `FormatOnSaveParticipant` (export it) and `participate` |
| `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:71-122` | `FormatOnSaveParticipant.participate` (optional parity) |
| `src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts` | new tests |
| `src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts` | new cancellation test |
| No change needed: `format.ts`, `mainThreadLanguageFeatures.ts`, `rpcProtocol.ts`, `extHostLanguageFeatures.ts`, `settingsLayout.ts` | covered in steps 3 and 4 |