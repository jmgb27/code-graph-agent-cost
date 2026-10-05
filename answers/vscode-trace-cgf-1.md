Here is the Format Document path from the keybinding to the edits landing in the model.

## 1. Command / action registration
- **`src/vs/editor/contrib/format/browser/formatActions.ts:212`**: `FormatDocumentAction extends EditorAction`.
  - Its id is `editor.action.formatDocument` (`:216`), with the label "Format Document".
  - Precondition (`:218`): `notInCompositeEditor && writable && hasDocumentFormattingProvider`.
  - Keybinding (`:221-222`): Shift+Alt+F, or Ctrl+Shift+I on Linux. It also appears in the editor context menu in group `1_modification` (`:225-228`).
- **`formatActions.ts:287`**: `registerEditorAction(FormatDocumentAction)`.
- **`src/vs/editor/browser/editorExtensions.ts:403-405`**: `EditorAction.runEditorCommand` logs `editorActionInvoked` telemetry, then calls `run()`.
- **`formatActions.ts:232-241`**: `run()` wraps the call in `IEditorProgressService.showWhile(..., 250)` and calls `invokeFunction(formatDocumentWithSelectedProvider, editor, FormattingMode.Explicit, Progress.None, CancellationToken.None, true)`.

## 2. Choosing the formatter provider
- **`src/vs/editor/contrib/format/browser/format.ts:290-308`**: `formatDocumentWithSelectedProvider`.
  - `:302` builds the candidate list with `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35-70`):
    1. It adds every `documentFormattingEditProvider.ordered(model)` (`:44`) and records each provider's extension id.
    2. It adds each range formatter from an extension that isn't already in the list, wrapped as a synthetic document formatter that formats `model.getFullModelRange()` (`:53-67`).
  - `LanguageFeatureRegistry.ordered` (`src/vs/editor/common/languageFeatureRegistry.ts:126`) sorts providers by how well their selector matches the model.
  - `:303` calls `FormattingConflicts.select(provider, model, mode, FormattingKind.File)` (`format.ts:95-104`). This asks the first selector registered through `setFormatterSelector` (`:90-93`). If there are no formatters, or no selector is registered, it returns `undefined`.
- **The workbench selector**: `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:39` `DefaultFormatter` (a workbench contribution; registration near `:272`) installs it at `:63`.
  - `_selectFormatter` (`:176-203`) calls `_analyzeFormatter` (`:138-173`):
    - It reads `editor.defaultFormatter`, scoped to the resource and language (`:139-142`), and picks the provider whose `extensionId` matches (`:146-150`).
    - If nothing is configured and there is exactly one formatter, it uses that one (`:162-164`).
    - Otherwise it returns an error message: the configured extension can't format this file, there are multiple formatters, or the configured one isn't available (`:153-172`).
  - In Explicit mode, a message leads to a "Configure Default Formatter" dialog (`:182-192`). Choosing Configure opens a quick pick in `_pickAndPersistDefaultFormatter` (`:205-219`), which saves the choice to `editor.defaultFormatter` and returns the picked provider.
- Back in `format.ts:304-306`, the chosen provider is reported to `progress`, then `formatDocumentWithProvider` runs.

## 3. Calling the provider, which does the RPC
- **`format.ts:310-347`**: `formatDocumentWithProvider`.
  - It creates an `EditorStateCancellationTokenSource` that cancels if the editor's value or cursor position changes (`:323-325`). A plain model gets `TextModelCancellationTokenSource` instead (`:327-328`).
  - `:333` calls `provider.provideDocumentFormattingEdits(model, model.getFormattingOptions(), cts.token)`.

The provider object here was created on the main thread when the extension registered its formatter:
- **Extension side**: `vscode.languages.registerDocumentFormattingEditProvider` in `src/vs/workbench/api/common/extHost.api.impl.ts:733-734` calls `ExtHostLanguageFeatures.registerDocumentFormattingEditProvider` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488-2492`). That wraps the extension's provider in a `DocumentFormattingAdapter`, stores it under a `handle`, and calls `this._proxy.$registerDocumentFormattingSupport(handle, selector, extensionId, displayName)`.
- **Protocol**: `src/vs/workbench/api/common/extHost.protocol.ts:545` defines `$registerDocumentFormattingSupport` (main-thread shape) and `:2978` defines `$provideDocumentFormattingEdits` (ext-host shape).
- **Main thread**: `src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460` registers a stub in `documentFormattingEditProvider` that carries `extensionId` and `displayName`. Its `provideDocumentFormattingEdits` calls `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (`:457`), which is the RPC to the extension host.
- **Extension host receives it**: `extHostLanguageFeatures.ts:2494-2496` `$provideDocumentFormattingEdits` uses `_withAdapter(handle, DocumentFormattingAdapter, ...)` to look up the adapter, then calls `URI.revive(resource)`.
- **The adapter**: `extHostLanguageFeatures.ts:703-721` `DocumentFormattingAdapter.provideDocumentFormattingEdits`:
  - It resolves the `vscode.TextDocument` with `_documents.getDocument(resource)` (`:712`).
  - It calls the extension's `vscode.DocumentFormattingEditProvider.provideDocumentFormattingEdits(document, options, token)` (`:715`).
  - It converts the results with `typeConvert.TextEdit.from` (`:717`; the converter namespace is at `src/vs/workbench/api/common/extHostTypeConverters.ts:617`).
  - The resulting `languages.TextEdit[]` goes back over RPC as the resolved promise.

## 4. Applying the returned edits
- **`format.ts:339`**: `workerService.computeMoreMinimalEdits(model.uri, rawEdits)` diffs the raw edits in the editor web worker (`src/vs/editor/browser/services/editorWorkerService.ts:153-160`), usually shrinking one large replace into minimal edits.
- **`format.ts:341-351`**: it returns early if the token was cancelled, or with `false` if there are no edits.
- **Editor case** (`:353-359`): `FormattingEdit.execute(editor, edits, mode !== Silent)`, in `src/vs/editor/contrib/format/browser/formattingEdit.ts:47-63`:
  - It pushes an undo stop before and after the edits (`:48-50`, `:59-61`) so the format is one undo step.
  - It captures the scroll state with `StableEditorScrollState.capture` (`:51`).
  - `_handleEolEdits` (`:15-35`) applies any `eol` change with `model.pushEOL` and keeps only the edits that have a range and text.
  - If there is exactly one edit and it covers the whole model, it uses `EditOperation.replace` (`:53-55`). Otherwise it uses `EditOperation.replaceMove` (`:57`). Both go through `editor.executeEdits('formatEditsCommand', ...)`.
  - It restores the cursor's relative vertical position (`:62`).
  - Back in `format.ts:357-359`, in Explicit mode the editor then calls `revealPositionInCenterIfOutsideViewport`.
- **Model-only case** (`format.ts:361-379`), used when there is no editor, e.g. save participants: `model.pushEditOperations` with `forceMoveMarkers: true`. The cursor-state computer restores a selection that touches the first edit's range.
- **`format.ts:380`**: `accessibilitySignalService.playSignal(AccessibilitySignal.format, { userGesture })`.

## Summary
```
Shift+Alt+F → FormatDocumentAction.run (formatActions.ts:232)
 → formatDocumentWithSelectedProvider (format.ts:290)
   → getRealAndSyntheticDocumentFormattersOrdered (format.ts:35)
   → FormattingConflicts.select → DefaultFormatter._selectFormatter (formatActionsMultiple.ts:176)
 → formatDocumentWithProvider (format.ts:310)
   → [main-thread stub] mainThreadLanguageFeatures.ts:457 ── RPC ──►
       ExtHostLanguageFeatures.$provideDocumentFormattingEdits (extHostLanguageFeatures.ts:2494)
       → DocumentFormattingAdapter (:710) → extension's provider (:715)
   ◄── TextEdit[] ── computeMoreMinimalEdits (format.ts:339)
   → FormattingEdit.execute → editor.executeEdits('formatEditsCommand') (formattingEdit.ts:47)
```