Here's the complete trace of the Format Document command from registration to application:

## 1. Command Registration
**src/vs/editor/contrib/format/browser/formatActions.ts:212-230**
- `FormatDocumentAction` class registered with ID `'editor.action.formatDocument'`
- Preconditions verify `EditorContextKeys.hasDocumentFormattingProvider`
- Keybinding: Shift+Alt+F (or Ctrl+Shift+I on Linux)

## 2. Command Execution
**src/vs/editor/contrib/format/browser/formatActions.ts:232-241**
- `run()` method calls `formatDocumentWithSelectedProvider` from format.ts
- Wrapped with `progressService.showWhile()` for UI feedback

## 3. Formatter Provider Selection
**src/vs/editor/contrib/format/browser/format.ts:290-308**
- `formatDocumentWithSelectedProvider()` gets available formatters
- Calls `getRealAndSyntheticDocumentFormattersOrdered()` to combine document + range formatters

**src/vs/editor/contrib/format/browser/format.ts:35-70**
- Gets formatters from `languageFeaturesService.documentFormattingEditProvider`
- Gets range formatters from `languageFeaturesService.documentRangeFormattingEditProvider`
- Wraps range formatters as document formatters

**src/vs/editor/contrib/format/browser/format.ts:95-105**
- `FormattingConflicts.select()` chooses which formatter to use (handles conflicts)

## 4. Call Formatter Provider
**src/vs/editor/contrib/format/browser/format.ts:310-382**
- `formatDocumentWithProvider()` calls `provider.provideDocumentFormattingEdits()` (line 333)
- This is where the RPC call to extension host occurs
- Returns `TextEdit[]` array from the formatter

## 5. Main Thread Registration (when extension registers formatter)
**src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460**
- `$registerDocumentFormattingSupport()` registers formatter in main thread
- Calls `languageFeaturesService.documentFormattingEditProvider.register()` (line 453)
- Creates provider with `provideDocumentFormattingEdits()` that calls RPC: `this._proxy.$provideDocumentFormattingEdits()` (line 457)

## 6. Extension Host Adapter
**src/vs/workbench/api/common/extHostLanguageFeatures.ts:703-721**
- `DocumentFormattingAdapter` wraps the extension's formatter provider
- `provideDocumentFormattingEdits()` gets the document (line 712)
- Calls extension's actual `provideDocumentFormattingEdits()` (line 715)
- Converts results via `typeConvert.TextEdit.from()` (line 717)

## 7. RPC Entry Point (Extension Host side)
**src/vs/workbench/api/common/extHostLanguageFeatures.ts:2494-2496**
- `$provideDocumentFormattingEdits()` is the RPC method called from main thread
- Uses `this._withAdapter()` to dispatch to the appropriate adapter

## 8. Apply Edits to Editor
**src/vs/editor/contrib/format/browser/format.ts:353-359**
- After receiving edits, calls `FormattingEdit.execute()` with the edits
- Or uses `model.pushEditOperations()` if working directly with model (lines 365-378)

## 9. Formatting Edit Execution
**src/vs/editor/contrib/format/browser/formattingEdit.ts:47-64**
- `FormattingEdit.execute()` processes EOL edits (line 52)
- Calls `editor.executeEdits()` with `'formatEditsCommand'` source (lines 55-57)
- Uses `EditOperation.replace()` or `EditOperation.replaceMove()` based on edit type

## 10. Execute Edits in Code Editor
**src/vs/editor/browser/widget/codeEditor/codeEditorWidget.ts:1282-1314**
- `executeEdits()` validates editor is writable (line 1286)
- Delegates to `this._modelData.viewModel.executeEdits()` (line 1312)
- Fires `onBeforeExecuteEdit` event (line 1311)

## 11. Apply to Text Model
**src/vs/editor/common/model.ts:1258-1262**
- `pushEditOperations()` applies edits to underlying `ITextModel`
- Manages undo/redo stack and cursor position updates

## 12. Provider Interface Definition
**src/vs/editor/common/languages.ts:1813-1826**
- `DocumentFormattingEditProvider` interface
- Method: `provideDocumentFormattingEdits(model: ITextModel, options: FormattingOptions, token: CancellationToken): ProviderResult<TextEdit[]>`