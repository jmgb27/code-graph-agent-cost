Based on my exploration of the codebase, here's the complete trace of the Format Document command flow:

## Format Document Command Trace

### 1. **Command Registration & Action Definition**
- **Command ID**: `editor.action.formatDocument` (formatActions.ts:216)
- **Action Class**: `FormatDocumentAction` extends `EditorAction` (formatActions.ts:212-242)
- **Registration**: `registerEditorAction(FormatDocumentAction)` (formatActions.ts:287)
- **Keybinding**: Shift+Alt+F (Windows/Mac) or Ctrl+Shift+I (Linux) (formatActions.ts:219-223)
- **Precondition**: Writable editor with formatting provider available (formatActions.ts:218)

### 2. **Action Execution Entry Point**
- **Run Method**: FormatDocumentAction.run() (formatActions.ts:232-241)
  - Gets `IInstantiationService` and `IEditorProgressService`
  - Calls `formatDocumentWithSelectedProvider()` via `instaService.invokeFunction()`

### 3. **Provider Selection**
- **Function**: `formatDocumentWithSelectedProvider()` (format.ts:290-308)
  - Gets `ILanguageFeaturesService` from accessor
  - Retrieves formatters via `getRealAndSyntheticDocumentFormattersOrdered()` (format.ts:302)
  - Source: `languageFeaturesService.documentFormattingEditProvider` (format.ts:300)
  - Calls `FormattingConflicts.select()` to resolve multiple providers (format.ts:303)

### 4. **Formatter Provider Invocation**
- **Function**: `formatDocumentWithProvider()` (format.ts:310-366)
  - Gets `IEditorWorkerService` and `IAccessibilitySignalService`
  - Calls **RPC to extension host**: `provider.provideDocumentFormattingEdits()` (format.ts:333-337)
    - Returns raw edits array
  - Computes minimal edits via `workerService.computeMoreMinimalEdits()` (format.ts:339)
  - Applies edits via `FormattingEdit.execute()` (format.ts:355)

### 5. **Provider Interface Definition**
- **Interface**: `DocumentFormattingEditProvider` (languages.ts:1813-1826)
  - Method: `provideDocumentFormattingEdits(model: ITextModel, options: FormattingOptions, token: CancellationToken): ProviderResult<TextEdit[]>`
  - Optional: `extensionId` and `displayName` properties

### 6. **Extension Host RPC Registration (Incoming)**
- **Extension API**: `registerDocumentFormattingEditProvider()` (extHostLanguageFeatures.ts:2488-2492)
  - Creates `DocumentFormattingAdapter` (line 2489)
  - Sends RPC: `this._proxy.$registerDocumentFormattingSupport()` (line 2490)

- **Adapter Class**: `DocumentFormattingAdapter` (extHostLanguageFeatures.ts:703-721)
  - Method: `provideDocumentFormattingEdits()` wraps extension provider

### 7. **Main Process RPC Handler (Outgoing)**
- **Handler**: `$registerDocumentFormattingSupport()` (mainThreadLanguageFeatures.ts:452-460)
  - Registers provider wrapper in `documentFormattingEditProvider` registry
  - Creates callback that calls back to extension host: `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (line 457)

### 8. **Edit Application to Model**
- **Class**: `FormattingEdit` (formattingEdit.ts:13-64)
- **Method**: `FormattingEdit.execute()` (formattingEdit.ts:47-63)
  - Separates EOL edits via `_handleEolEdits()` (line 52)
  - Applies EOL changes to model via `model.pushEOL()` (line 30)
  - Applies text edits via `editor.executeEdits('formatEditsCommand', edits)` (lines 55-57)
  - Uses `EditOperation.replace()` for full-document replace or `EditOperation.replaceMove()` for partial edits
  - Preserves cursor position via `StableEditorScrollState` (line 51, 62)

### Key Data Structures
- **FormattingOptions**: `tabSize`, `insertSpaces` (languages.ts:1800-1808)
- **TextEdit**: Range + text replacement (edit operations)
- **LanguageFeaturesService**: Central registry for all language feature providers (languageFeaturesService.ts:28)