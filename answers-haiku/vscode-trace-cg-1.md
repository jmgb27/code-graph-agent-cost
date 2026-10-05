Here's the complete trace of the Format Document command flow:

## 1. **Command Registration**

**File: `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:360`**
- `FormatDocumentMultipleAction` registers the format document action
- Extends `EditorAction` which extends `EditorCommand` and `Command`

## 2. **Formatter Provider Selection**

**File: `src/vs/editor/contrib/format/browser/format.ts:35–70`**
- `getRealAndSyntheticDocumentFormattersOrdered()` retrieves and orders available formatters
- Gets document formatters from `documentFormattingEditProvider.ordered(model)` (line 44)
- Gets range formatters from `documentRangeFormattingEditProvider.ordered(model)` (line 53)
- Wraps range formatters as document formatters (lines 61–67)

**File: `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:375–386`**
- `FormatDocumentMultipleAction.run()` calls `getRealAndSyntheticDocumentFormattersOrdered()` at line 382
- Selects a formatter based on user input or configuration

## 3. **RPC to Extension Host**

**File: `src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488–2492`**
- `registerDocumentFormattingEditProvider()` wraps the extension's provider in `DocumentFormattingAdapter` (line 2489)
- Calls `this._proxy.$registerDocumentFormattingSupport()` (line 2490) — RPC to main thread

**File: `src/vs/workbench/api/common/extHostLanguageFeatures.ts:703–721`**
- `DocumentFormattingAdapter` bridges the extension provider to the main thread
- `provideDocumentFormattingEdits()` method converts the extension's response

**File: `src/vs/editor/common/languages.ts:1813–1826`**
- `DocumentFormattingEditProvider` interface defines the contract

## 4. **Provider Invocation & Edit Collection**

**File: `src/vs/editor/contrib/format/browser/format.ts:310–382`**
- `formatDocumentWithProvider()` orchestrates the formatting:
  - Calls `provider.provideDocumentFormattingEdits()` at line 333
  - Receives `TextEdit[]` array
  - Computes minimal edits at line 339 via `workerService.computeMoreMinimalEdits()`

## 5. **Edit Application to Model**

**File: `src/vs/editor/contrib/format/browser/formattingEdit.ts:47–63`**
- `FormattingEdit.execute()` applies edits to the editor:
  - `pushUndoStop()` at lines 49, 60 — creates undo breakpoints
  - `_handleEolEdits()` at line 52 — processes end-of-line changes
  - `_isFullModelReplaceEdit()` at line 53 — detects full document replacement
  - `editor.executeEdits()` at lines 55, 57 — applies edit operations with appropriate semantics

**File: `src/vs/editor/contrib/format/browser/format.ts:354–379`**
- For `ICodeEditor`: uses `FormattingEdit.execute()` (line 355)
- For bare `ITextModel`: uses `model.pushEditOperations()` (line 365) with `pushEOL()` for EOL changes (line 30)

## Call Path Summary

```
FormatDocumentMultipleAction.run()
  → getRealAndSyntheticDocumentFormattersOrdered()
    → documentFormattingEditProvider.ordered()
  → formatDocumentWithProvider()
    → provider.provideDocumentFormattingEdits()
    → workerService.computeMoreMinimalEdits()
    → FormattingEdit.execute() or model.pushEditOperations()
      → editor.executeEdits() / model.pushEOL()
```