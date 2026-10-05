Based on my CodeGraph exploration, here's the complete trace of the Format Document command from registration to edit application:

## 1. Command Registration

**`src/vs/editor/contrib/format/browser/format.ts:360-380`**
- `FormatDocumentAction` class extends `EditorAction`
- Registers the command with ID: `editor.action.formatDocument`
- The `run()` method is called when the user invokes the command

## 2. Formatter Provider Selection

**`src/vs/editor/contrib/format/browser/format.ts:35-50`** — `getRealAndSyntheticDocumentFormattersOrdered()`
- Queries `LanguageFeatureRegistry<DocumentFormattingEditProvider>` 
- Gets providers via `documentFormattingEditProvider.ordered(model)` which scores providers for the current file
- Returns providers in priority order (highest scoring first)

## 3. Getting Formatting Edits

**`src/vs/editor/contrib/format/browser/format.ts:403-419`** — `getDocumentFormattingEditsUntilResult()`
- Iterates through ordered formatters from step 2
- Calls `provider.provideDocumentFormattingEdits(model, options, token)` on each
- Uses first provider that returns edits
- Worker service optimizes edits via `computeMoreMinimalEdits()`

**`src/vs/editor/contrib/format/browser/format.ts:310-337`** — `formatDocumentWithProvider()`
- Gets formatting options from model: `model.getFormattingOptions()`
- Calls formatter: `provider.provideDocumentFormattingEdits(model, options, token)`

## 4. Extension Host RPC

**`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488-2495`** — `registerDocumentFormattingEditProvider()`
- Extension registers provider: `new DocumentFormattingAdapter(this._documents, provider)`
- Sends to main process: `this._proxy.$registerDocumentFormattingSupport()` 
- Returns disposable to unregister
- When formatting requested, calls adapter's `provideDocumentFormattingEdits()` which invokes the extension's provider

## 5. Applying Edits to Model

**`src/vs/editor/contrib/format/browser/format.ts:353-362`** — Editor case
- Uses `FormattingEdit.execute(editorOrModel, edits, mode !== FormattingMode.Silent)`

**`src/vs/editor/contrib/format/browser/formattingEdit.ts:47-54`** — `FormattingEdit.execute()`
- Handles EOL edits: `editor.getModel().pushEOL(newEol)` 
- For full model replace: replaces entire content
- Otherwise: `editor.executeEdits()` applies text edits
- Preserves undo/redo state and scroll position

**`src/vs/editor/contrib/format/browser/format.ts:362-379`** — Model-only case (no editor)
- Uses `model.pushEditOperations()` to batch apply edits
- Maintains selection state via edit operation callbacks

**File references:**
- src/vs/editor/contrib/format/browser/format.ts:35, 310, 403
- src/vs/editor/contrib/format/browser/formattingEdit.ts:47
- src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488