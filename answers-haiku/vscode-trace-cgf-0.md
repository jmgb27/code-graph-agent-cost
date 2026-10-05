Based on my exploration, here's the complete trace of the Format Document command from registration to applying edits:

## 1. **Command Registration**
**File: `src/vs/editor/contrib/format/browser/formatActions.ts:212-242`**

The `FormatDocumentAction` class registers the command:
- **ID**: `editor.action.formatDocument` (line 216)
- **Label**: "Format Document"
- **Keybinding**: Shift+Alt+F (or Ctrl+Shift+I on Linux)
- **Precondition**: Editor is writable and has a formatting provider
- **Handler**: `run()` method calls `formatDocumentWithSelectedProvider` (line 237)

## 2. **Formatter Provider Selection**
**File: `src/vs/editor/contrib/format/browser/format.ts:290-308`**

`formatDocumentWithSelectedProvider()` function:
- **Line 300**: Gets `ILanguageFeaturesService` from accessor
- **Line 302**: Calls `getRealAndSyntheticDocumentFormattersOrdered()` to retrieve all registered document formatting providers for the model
- **Line 303**: Calls `FormattingConflicts.select()` to resolve which formatter to use (handles multiple formatters, user selection)
- **Line 306**: Invokes `formatDocumentWithProvider()` with the selected provider

## 3. **Provider Invocation (RPC to Extension Host)**
**File: `src/vs/editor/contrib/format/browser/format.ts:310-337`**

`formatDocumentWithProvider()` function:
- **Line 333-337**: Calls the provider's `provideDocumentFormattingEdits()` method
  - This is an RPC call to the extension host (the provider was registered by an extension)
  - The actual implementation is a proxy that communicates with the extension process

**The provider chain:**
- Extensions register via `registerDocumentFormattingEditProvider()` in `src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488`
- An adapter (`DocumentFormattingAdapter`) wraps the extension's provider
- This is exposed through `ILanguageFeaturesService.documentFormattingEditProvider` registry

## 4. **Edit Application**
**File: `src/vs/editor/contrib/format/browser/format.ts:353-379`**

After receiving edits from the provider:
- **Line 339**: Minimizes edits via `workerService.computeMoreMinimalEdits()`
- **Line 355**: Applies edits to the editor using `FormattingEdit.execute()`

**File: `src/vs/editor/contrib/format/browser/formattingEdit.ts:13-35`**

`FormattingEdit.execute()`:
- Handles EOL changes separately (line 15-35)
- **Line 30**: Applies new EOL via `editor.getModel().pushEOL()`
- **Line 29-31**: Returns ISingleEditOperation array for text edits
- The edits are applied to the model via `editor` methods

## Summary Flow:
```
Command: editor.action.formatDocument (FormatDocumentAction)
   ↓
formatDocumentWithSelectedProvider()
   ├─ Get ILanguageFeaturesService
   ├─ getRealAndSyntheticDocumentFormattersOrdered() → providers array
   └─ FormattingConflicts.select() → choose provider
   ↓
formatDocumentWithProvider(selectedProvider)
   ├─ provider.provideDocumentFormattingEdits() → RPC to extension host
   ├─ workerService.computeMoreMinimalEdits()
   ↓
FormattingEdit.execute()
   ├─ Handle EOL changes
   └─ Apply text edits to model via editor.executeEdits()
```