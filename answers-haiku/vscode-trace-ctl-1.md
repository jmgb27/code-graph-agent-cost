Based on my analysis of the VS Code codebase, here's the complete trace of the Format Document command:

## Command Registration
- **formatActions.ts:216** - `'editor.action.formatDocument'` command is registered as an EditorAction
- **formatActions.ts:232-241** - `FormatDocumentAction.run()` invokes `formatDocumentWithSelectedProvider`

## Provider Selection
- **format.ts:290-308** - `formatDocumentWithSelectedProvider` retrieves and selects a formatter:
  - **format.ts:302** - Gets all formatters via `getRealAndSyntheticDocumentFormattersOrdered()`
  - **format.ts:35-70** - `getRealAndSyntheticDocumentFormattersOrdered` combines document and range formatters from the registry
  - **format.ts:303** - Uses `FormattingConflicts.select()` to choose the provider based on user preference/mode

## RPC to Extension Host
- **format.ts:310-382** - `formatDocumentWithProvider` calls the chosen provider:
  - **format.ts:333** - `provider.provideDocumentFormattingEdits(model, options, token)` is called

## Extension Host Registration (Main Thread Side)
- **mainThreadLanguageFeatures.ts:452-460** - `$registerDocumentFormattingSupport` registers the provider with the language features service:
  - **mainThreadLanguageFeatures.ts:456-458** - The `provideDocumentFormattingEdits` callback makes an RPC call back to the extension host: `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)`

## RPC Protocol Definition
- **extHost.protocol.ts:545** - `$registerDocumentFormattingSupport` interface (main thread receives)
- **extHost.protocol.ts:2978** - `$provideDocumentFormattingEdits` interface (extension host receives)

## Extension Host Provider Implementation
- **extHostLanguageFeatures.ts:703-721** - `DocumentFormattingAdapter` wraps the extension's provider:
  - **extHostLanguageFeatures.ts:710-720** - `provideDocumentFormattingEdits` calls the actual extension provider and converts results
- **extHostLanguageFeatures.ts:2488-2492** - `registerDocumentFormattingEditProvider` registers and sends `$registerDocumentFormattingSupport` to main thread
- **extHostLanguageFeatures.ts:2494-2496** - `$provideDocumentFormattingEdits` RPC handler invokes the adapter

## Edits Application
- **format.ts:355** - `FormattingEdit.execute()` applies the returned edits to the model
- **formattingEdit.ts:47-63** - `FormattingEdit.execute()` handles EOL edits and calls:
  - **formattingEdit.ts:55** - `editor.executeEdits('formatEditsCommand', ...)` with mapped `EditOperation.replace()` or `EditOperation.replaceMove()` operations
  - **formattingEdit.ts:49,60** - Adds undo stops before/after execution
  - **formattingEdit.ts:62** - Restores editor scroll position