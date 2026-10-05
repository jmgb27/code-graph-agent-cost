Here is the full path of `editor.action.formatDocument`, from the keybinding to the edits landing in the model.

## 1. Command / action registration

- **`FormatDocumentAction`** is defined at `src/vs/editor/contrib/format/browser/formatActions.ts:212-242`.
  - id `'editor.action.formatDocument'` (`:216`)
  - The precondition requires `EditorContextKeys.hasDocumentFormattingProvider` (`:218`). That key is set at `src/vs/editor/browser/widget/codeEditor/codeEditorWidget.ts:2418`, and it is true if either a document formatter or a range formatter is registered for the model.
  - Keybinding: Shift+Alt+F, or Ctrl+Shift+I on Linux (`:221-222`).
- It is registered with `registerEditorAction(FormatDocumentAction)` at `formatActions.ts:287`.
- The legacy `editor.action.format` command sends you here when the selection is empty (`formatActions.ts:292-303`).
- If no formatter is registered at all, `src/vs/workbench/contrib/format/browser/formatActionsNone.ts:52` handles the case and then re-dispatches to this command.
- **`run()`** (`formatActions.ts:232-241`) calls `formatDocumentWithSelectedProvider(editor, FormattingMode.Explicit, …, userGesture=true)` through `IInstantiationService.invokeFunction`. The call is wrapped in `IEditorProgressService.showWhile(…, 250)`.

## 2. Choosing the formatter provider

`formatDocumentWithSelectedProvider` is at `src/vs/editor/contrib/format/browser/format.ts:290-308`.

1. **Collect the candidates** with `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35-70`):
   - First it adds every `documentFormattingEditProvider.ordered(model)` (`:44-50`).
   - Then it adds range formatters wrapped as document formatters over `model.getFullModelRange()` (`:53-68`). A range formatter is skipped if the same extension already contributed a document formatter.
   - The ordering comes from `LanguageFeatureRegistry.ordered` → `_updateScores` → `_compareByScoreAndTime` (`src/vs/editor/common/languageFeatureRegistry.ts:126-219`):
     - sorted by selector score first;
     - built-in providers go below extension providers;
     - after that, the newest registration wins.
2. **Pick one** with `FormattingConflicts.select(provider, model, mode, FormattingKind.File)` (`format.ts:95-104`). This calls the first selector registered through `setFormatterSelector` (`:90-93`).
   - **Workbench selector:** `DefaultFormatter` registers `_selectFormatter` at `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:63`.
     - `_analyzeFormatter` (`:138-174`) reads `editor.defaultFormatter`, scoped to the resource and the language override (`:139-142`).
     - If a candidate's `extensionId` matches that setting, it is used (`:146-149`).
     - If nothing is configured and there is exactly one candidate, that one is used (`:163-165`).
     - Any other case produces an error message string instead of a provider.
   - When `_selectFormatter` (`:176-203`) gets a message rather than a provider:
     - In `Explicit` mode (which Format Document uses), it shows a "Configure Default Formatter" dialog. That leads to `_pickAndPersistDefaultFormatter` (`:205+`), which opens a quick pick and writes `editor.defaultFormatter`.
     - In `Silent` mode, it shows a silent notification and returns `undefined`.
   - **Standalone Monaco** registers a trivial selector that always takes the first candidate: `src/vs/editor/editor.api.ts:21`.
3. If a provider was selected, the code reports progress and calls `formatDocumentWithProvider` (`format.ts:304-307`).

## 3. RPC to the extension host

**How registration works (extension host → main thread):**

- The public API `vscode.languages.registerDocumentFormattingEditProvider` is at `src/vs/workbench/api/common/extHost.api.impl.ts:733-734`.
- It calls `ExtHostLanguageFeatures.registerDocumentFormattingEditProvider` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488-2492`), which:
  - wraps the provider in a `DocumentFormattingAdapter` and stores it under a numeric `handle` (`_addNewAdapter`);
  - sends `$registerDocumentFormattingSupport(handle, selector, extensionId, displayName)` to the main thread. The protocol is declared at `src/vs/workbench/api/common/extHost.protocol.ts:545`.
- `MainThreadLanguageFeatures.$registerDocumentFormattingSupport` (`src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460`) registers a proxy provider in `ILanguageFeaturesService.documentFormattingEditProvider`. That proxy is what shows up as a candidate in step 2.

**How the call works (main thread → extension host):**

- `formatDocumentWithProvider` calls `provider.provideDocumentFormattingEdits(model, model.getFormattingOptions(), cts.token)` (`format.ts:333-337`).
  - The cancellation token comes from `EditorStateCancellationTokenSource`, which cancels if the editor's value or cursor position changes (`:325`).
- For an extension provider, that is the proxy lambda, which calls `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (`mainThreadLanguageFeatures.ts:456-458`). The protocol is declared at `extHost.protocol.ts:2978`.
- On the extension host, `ExtHostLanguageFeatures.$provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:2494-2496`) looks up the adapter by handle with `_withAdapter`.
- `DocumentFormattingAdapter.provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:703-721`):
  - resolves the `vscode.TextDocument` from `ExtHostDocuments` (`:712`);
  - calls the extension's `provideDocumentFormattingEdits(document, options, token)` (`:715`);
  - converts the result with `typeConvert.TextEdit.from` (`:717`, defined in `src/vs/workbench/api/common/extHostTypeConverters.ts:617`) and returns it over RPC.

## 4. Applying the returned edits

Back in `formatDocumentWithProvider` (`format.ts:310-382`):

1. **Minimize the edits.** `workerService.computeMoreMinimalEdits(model.uri, rawEdits)` (`format.ts:339`) diffs the edits in the editor web worker (`src/vs/editor/browser/services/editorWorkerService.ts:153-181`).
2. **Bail out early.** If the token was cancelled it returns (`:341-343`). If there are no edits it returns `false` (`:349-351`).
3. **Editor path** (the one Format Document takes): `FormattingEdit.execute(editor, edits, addUndoStops = mode !== Silent)` (`format.ts:355`), then the cursor is revealed if it's outside the viewport (`:357-359`). `FormattingEdit.execute` is in `src/vs/editor/contrib/format/browser/formattingEdit.ts:47-63`:
   - It pushes an undo stop before and after the edits (`:48-50`, `:59-61`).
   - It captures the scroll position with `StableEditorScrollState` and restores it afterwards (`:51`, `:62`).
   - `_handleEolEdits` (`:15-35`) applies any `eol` change through `model.pushEOL`.
   - It applies the edits with `editor.executeEdits('formatEditsCommand', …)`. A single full-document replacement uses `EditOperation.replace`; anything else uses `EditOperation.replaceMove` (`:53-58`).
4. **Model-only path** (used when there is no editor, e.g. format-on-save with a bare model): `model.pushEditOperations` with `forceMoveMarkers: true` and an undo-selection computer (`format.ts:361-378`).
5. **Accessibility signal.** Finally it plays `AccessibilitySignal.format` (`format.ts:380`).

## Summary

1. Shift+Alt+F runs `FormatDocumentAction.run` (`formatActions.ts:232`).
2. That calls `formatDocumentWithSelectedProvider` (`format.ts:290`).
3. The candidates are collected by `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35`).
4. One provider is picked by `FormattingConflicts.select` (`format.ts:95`) through `DefaultFormatter._selectFormatter` (`formatActionsMultiple.ts:176`).
5. `formatDocumentWithProvider` (`format.ts:310`) calls that provider.
6. For an extension provider, the main-thread proxy (`mainThreadLanguageFeatures.ts:457`) sends `$provideDocumentFormattingEdits`.
7. On the extension host this reaches `ExtHostLanguageFeatures.$provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:2494`), then `DocumentFormattingAdapter` (`:710`), then the extension's provider.
8. The returned edits go through `computeMoreMinimalEdits` (`format.ts:339`).
9. `FormattingEdit.execute` (`formattingEdit.ts:47`) applies them with `editor.executeEdits`.