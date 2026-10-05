I've traced the full path: settings → save participant → `format.ts` → RPC → extension-host adapter. Here is the plan.

# Plan: `editor.formatOnSaveTimeout` (per-language)

## What already exists
- **The save participant already gets a token, but it has no deadline.** `TextFileSaveParticipant.participate` (`src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:34-92`) creates `cts` from the save token. That token is cancelled only when the user clicks "Skip" (`:80-82`).
- **The formatter already forwards that token.** `FormatOnSaveParticipant.participate` (`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:226-270`) passes it to `formatDocumentWithSelectedProvider` (`:257`, `:263`) and `formatDocumentRangesWithSelectedProvider` (`:267`).
- **The format functions chain the token.** `formatDocumentWithProvider` (`src/vs/editor/contrib/format/browser/format.ts:310-347`) and `formatDocumentRangesWithProvider` (`format.ts:128-256`) wrap it in `EditorStateCancellationTokenSource` / `TextModelCancellationTokenSource` (`:144/147`, `:325/328`) and pass `cts.token` to the provider.
- **Cancellation already reaches the extension host, so no protocol change is needed:**
  - The main-thread provider shim passes the token to `$provideDocumentFormattingEdits` / `$provideDocumentRangeFormattingEdits` / `$provideDocumentRangesFormattingEdits` (`src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:456-472`; protocol at `src/vs/workbench/api/common/extHost.protocol.ts:2978-2980`).
  - `RPCProtocol._remoteCall` (`src/vs/workbench/services/extensions/common/rpcProtocol.ts:461-496`) strips the trailing token and sends a `cancel` message when it fires (`:482-487`).
  - The extension host rebuilds the token in `_receiveRequest` (`:358-374`).
  - `ExtHostLanguageFeatures._withAdapter` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2214-2252`) races the provider with `raceCancellationError` (`:2248-2249`), which is the token extensions see at `:710-749`.

## Changes

### 1. Register the setting
**`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`**: add to the `editorConfigurationBaseNode` block next to `editor.formatOnSave` / `editor.formatOnSaveMode`:
```ts
'editor.formatOnSaveTimeout': {
  type: 'number', default: 0, minimum: 0,
  markdownDescription: nls.localize('formatOnSaveTimeout', "Timeout in milliseconds after which format on save is cancelled. Use `0` for no limit. Only applies when `#editor.formatOnSave#` is enabled."),
  scope: ConfigurationScope.LANGUAGE_OVERRIDABLE,
},
```
A default of `0` keeps today's behaviour. `LANGUAGE_OVERRIDABLE` is what makes `"[typescript]": { "editor.formatOnSaveTimeout": … }` work.

### 2. Save participant
**`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`, `FormatOnSaveParticipant.participate` (`:226-270`)**
- After the `enabled` check (`:248-251`), read the timeout with the existing `overrides` (`:235`): `getValue<number>('editor.formatOnSaveTimeout', overrides)`.
- If it's greater than 0:
  - Create `const cts = new CancellationTokenSource(token)` and schedule `cts.cancel()` after the timeout (e.g. `disposableTimeout` from `base/common/async`).
  - Pass `cts.token` instead of `token` at `:257`, `:263` and `:267`.
  - Wrap each `await` in `raceCancellation(…, cts.token)`. The main-side RPC promise only settles when the extension host replies, so without this a hung extension host would still block.
  - Dispose `cts` and the timer in a `finally`.
- **Required: swallow the timeout's cancellation error.** If the timer fired and the outer `token` was not cancelled, catch `isCancellationError(err)` and return normally. Optionally log it or `progress.report` a "Formatting timed out after {0}ms" message.
  - Why: `TextFileSaveParticipant.participate` (`textFileSaveParticipant.ts:69-77`) reads a `CancellationError` whose outer token *wasn't* cancelled as "the participant wants the save cancelled". It then sets `bubbleCancel` and aborts the save.
  - The extension host's `raceCancellationError` (`extHostLanguageFeatures.ts:2249`) produces exactly that error, so without this catch a timeout would silently drop the save.
- Update the imports at `:6` (already imports `CancellationTokenSource`) and add `raceCancellation`, `disposableTimeout` and `isCancellationError`.
- Export `FormatOnSaveParticipant` (`:216`) so tests can instantiate it. `registerSaveParticipants` (`:455-461`) stays unchanged.

### 3. Formatting core (no change needed, check only)
`format.ts:128-256` and `:310-347` already chain the incoming token and check `cts.token.isCancellationRequested` before applying edits (`:241-253`, `:341-343`). A late result is therefore thrown away and never applied.

### 4. Extension host (no change needed)
Nothing to change in `mainThreadLanguageFeatures.ts:456-472`, `extHost.protocol.ts:2978-2980`, `extHostLanguageFeatures.ts:710-749` / `:2494-2510`, or `rpcProtocol.ts`.

Out of scope but worth noting: `MainThreadSaveParticipant.participate` (`src/vs/workbench/api/browser/mainThreadSaveParticipant.ts:25-47`) has its own hard-coded 1750ms for `onWillSaveTextDocument`. That timeout is separate and unrelated to formatting providers.

### 5. Settings UI (no code change required)
- The TOC entry `editor/format` in `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:95-97` matches `'editor.format*'`, so the new setting appears under Text Editor › Formatting automatically.
- A `number` setting renders with the existing number renderer.
- Don't add it to `COMMONLY_USED_SETTINGS` (`settingsLayout.ts:31-45`) or `getMostCommonlyUsedSettings` (`src/vs/workbench/services/preferences/browser/preferencesService.ts:573-588`).
- The `[configure]` link in the progress message (`saveParticipants.ts:243`) could point to `'editor.formatOnSave'` plus the new key, but that's optional.

### 6. Tests
**`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`** (suite at `:20`, uses `workbenchInstantiationService` at `:27`, which stubs a real `LanguageFeaturesService` at `src/vs/workbench/test/browser/workbenchTestServices.ts:319`). Import `FormatOnSaveParticipant` at `:8`, register a `documentFormattingEditProvider` through `ILanguageFeaturesService`, and wrap the timing tests in `runWithFakedTimers`. Add tests for:
1. **Timeout cancels a slow formatter:** the provider waits until its token is cancelled. With `editor.formatOnSaveTimeout: 50`, `participate` resolves, the provider saw `token.isCancellationRequested`, and the model is unchanged.
2. **A hung provider doesn't block:** the provider ignores the token and never resolves; `participate` still resolves after the timeout.
3. **`0` means no limit:** a slow provider's edits are applied.
4. **Per-language override:** a `[lang]` override wins. Check first that `TestConfigurationService.getValue` (`src/vs/platform/configuration/test/common/testConfigurationService.ts:30`) honours `overrideIdentifier`; if it doesn't, stub `getValue` instead.
5. **The outer token still wins:** cancelling the outer token cancels formatting.

**`src/vs/workbench/services/textfile/test/browser/textFileEditorModel.test.ts`** (save-participant tests at `:672-760`): add a regression test that a participant throwing `CancellationError` because of its own timeout does not abort `model.save()`. It should cover the full flow, which depends on the swallowing in step 2.

**Optional:** in `src/vs/workbench/api/test/browser/extHostLanguageFeatures.test.ts` (format tests at `:1129-1230`), add a test that cancelling the token passed to `getDocumentFormattingEditsUntilResult` cancels the extension provider's token.

## Summary of edits
| File | Function / location |
|---|---|
| `contrib/files/browser/files.contribution.ts:388-413` | new `editor.formatOnSaveTimeout` property |
| `contrib/codeEditor/browser/saveParticipants.ts:216-270` | export and change `FormatOnSaveParticipant.participate` |
| `contrib/codeEditor/test/browser/saveParticipant.test.ts` | new timeout tests |
| `services/textfile/test/browser/textFileEditorModel.test.ts` | save isn't aborted by a participant's own timeout |
| `api/test/browser/extHostLanguageFeatures.test.ts` | (optional) cancellation reaches the extension provider |

Everything else in the chain (`format.ts`, `mainThreadLanguageFeatures.ts`, `extHost.protocol.ts`, `extHostLanguageFeatures.ts`, `rpcProtocol.ts`, `settingsLayout.ts`) already handles the token or the new key and needs no change.