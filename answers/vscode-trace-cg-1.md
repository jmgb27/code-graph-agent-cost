Here is the full path of Format Document (`editor.action.formatDocument`), from the keybinding to the extension and back to the text model. Paths are relative to `src/vs/`.

## 0. Setup: the extension registers a provider (extension host → renderer)

1. An extension calls `vscode.languages.registerDocumentFormattingEditProvider`. The API is defined at `workbench/api/common/extHost.api.impl.ts:733-734`.
2. This forwards to `ExtHostLanguageFeatures.registerDocumentFormattingEditProvider` (`workbench/api/common/extHostLanguageFeatures.ts:2488`), which:
   - wraps the provider in a `DocumentFormattingAdapter` (`:703`) and stores it under a numeric handle (`:2489`);
   - calls `this._proxy.$registerDocumentFormattingSupport(handle, selector, extension.identifier, displayName)` over RPC (`:2490`). The protocol is declared at `workbench/api/common/extHost.protocol.ts:545`.
3. On the renderer side, `MainThreadLanguageFeatures.$registerDocumentFormattingSupport` (`workbench/api/browser/mainThreadLanguageFeatures.ts:452-460`) registers a proxy provider into `ILanguageFeaturesService.documentFormattingEditProvider`. The proxy:
   - carries `extensionId` and `displayName`, which the selector uses later;
   - implements `provideDocumentFormattingEdits` as `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (`:457`).

## 1. The command / action

- `FormatDocumentAction` is at `editor/contrib/format/browser/formatActions.ts:212`.
  - id `editor.action.formatDocument`, label "Format Document" (`:216-217`).
  - precondition: `notInCompositeEditor && writable && hasDocumentFormattingProvider` (`:218`). The context key is defined at `editor/common/editorContextKeys.ts:95`.
  - keybinding: Shift+Alt+F, or Ctrl+Shift+I on Linux (`:221-222`). It also appears in the context menu (`:225-228`).
- It is registered with `registerEditorAction(FormatDocumentAction)` (`formatActions.ts:287`).
- `run()` (`:232-241`) calls `formatDocumentWithSelectedProvider(editor, FormattingMode.Explicit, Progress.None, CancellationToken.None, true)` inside `progressService.showWhile(..., 250)`.

## 2. Choosing the formatter provider

`formatDocumentWithSelectedProvider` is at `editor/contrib/format/browser/format.ts:290-308`.

1. **Candidate list:** `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35-70`, called at `:302`).
   - It first adds every document formatter from `documentFormattingEditProvider.ordered(model)` (`:44-50`). `ordered` is `LanguageFeatureRegistry.ordered`, which ranks by selector score (`editor/common/languageFeatureRegistry.ts:126`).
   - It then wraps each range formatter as a synthetic document formatter that formats `model.getFullModelRange()` (`:53-67`). A range formatter is skipped if the same extension already contributed a document formatter.
2. **Selection:** `FormattingConflicts.select(provider, model, mode, FormattingKind.File)` (`format.ts:303`, implemented at `:95-104`) hands the list to the first registered selector. If the list is empty, or no selector is registered, it returns `undefined`.
3. **The selector** is installed by the workbench contribution `DefaultFormatter` (`workbench/contrib/format/browser/formatActionsMultiple.ts:39`).
   - It calls `FormattingConflicts.setFormatterSelector(...)` in its constructor (`:63`).
   - It is registered at `LifecyclePhase.Restored` (`:271-274`).
   - `_selectFormatter` (`:176-203`) relies on `_analyzeFormatter` (`:138-174`), which applies these rules:
     - If `editor.defaultFormatter` is set for this resource/language, it returns the provider whose `extensionId` matches (`:139-150`).
     - If that setting names an extension that is installed but has no formatter for this file, it returns an error message (`:153-161`).
     - If nothing is configured and there is exactly one formatter, it returns that one (`:163-165`).
     - Otherwise it returns a "multiple formatters / configure default" message (`:168-173`).
   - When `_analyzeFormatter` returns a message:
     - In **Explicit** mode (the case here), a "Configure Default Formatter" dialog appears (`:185-192`). If the user confirms, `_pickAndPersistDefaultFormatter` shows a quick pick and writes `editor.defaultFormatter` (`:205-223`).
     - In **Silent** mode it shows a notification instead (`:195-200`).
4. If a provider was selected, it is reported to `progress` (`format.ts:305`) and `formatDocumentWithProvider` is called (`:306`).

## 3. The RPC to the extension host provider

`formatDocumentWithProvider` is at `format.ts:310-382`.

1. It creates a cancellation source (`:323-329`):
   - for an editor, `EditorStateCancellationTokenSource`, which cancels if the editor's value or cursor position changes;
   - for a bare model, `TextModelCancellationTokenSource`.
2. It calls `provider.provideDocumentFormattingEdits(model, model.getFormattingOptions(), cts.token)` (`:333-337`). This is the main-thread proxy from step 0, so it runs `$provideDocumentFormattingEdits` over RPC (`mainThreadLanguageFeatures.ts:457`; protocol at `extHost.protocol.ts:2978`).
3. On the extension host, `ExtHostLanguageFeatures.$provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:2494-2496`) runs `_withAdapter(handle, DocumentFormattingAdapter, …)` (`:2214-2252`), which:
   - looks up the adapter by handle and checks its type (`:2222-2225`);
   - traces and logs, and reports errors to extension telemetry (`:2228-2246`);
   - races the result against the cancellation token (`:2248-2249`).
4. `DocumentFormattingAdapter.provideDocumentFormattingEdits` (`:710-720`):
   - resolves the `vscode.TextDocument` with `_documents.getDocument(resource)`;
   - calls the extension's own `provideDocumentFormattingEdits(document, options, token)` (`:715`);
   - converts each result with `typeConvert.TextEdit.from` (`:717`), which maps `newText`/`newEol`/`range` to `{text, eol, range}` (`workbench/api/common/extHostTypeConverters.ts:619-625`).

## 4. Applying the returned edits

Back in `formatDocumentWithProvider`:

1. **Minimize:** `workerService.computeMoreMinimalEdits(model.uri, rawEdits)` (`format.ts:339`).
   - This goes through `editor/browser/services/editorWorkerService.ts:153-159` to the editor web worker's `$computeMoreMinimalEdits` (`editor/common/services/editorWebWorker.ts:218`), which diffs the edits down to minimal changes.
   - If cancellation was requested (for example, the user typed meanwhile), it returns early (`format.ts:341-343`). If there are no edits, it returns `false` (`:349-351`).
2. **Editor case:** `FormattingEdit.execute(editor, edits, mode !== Silent)` (`format.ts:355`), implemented in `editor/contrib/format/browser/formattingEdit.ts:47-63`:
   - pushes undo stops around the edit when not Silent (`:48-50`, `:59-61`);
   - captures scroll state with `StableEditorScrollState.capture` (`:51`);
   - `_handleEolEdits` pulls out any `eol` change and applies it with `model.pushEOL` (`:15-35`);
   - if there is a single edit covering the whole model, it uses `EditOperation.replace` so markers stay put (`:53-55`); otherwise it uses `EditOperation.replaceMove` (`:57`);
   - both paths go through `editor.executeEdits('formatEditsCommand', …)`;
   - it restores the cursor's relative scroll position (`:62`);
   - finally, in Explicit mode it calls `revealPositionInCenterIfOutsideViewport` (`format.ts:357-359`).
3. **Model-only case** (e.g. save participants and notebooks): `model.pushEditOperations` with `forceMoveMarkers: true` (`format.ts:361-379`). The undo selection is computed from the first edit's range.
4. **Signal:** it plays `AccessibilitySignal.format` (`format.ts:380`) and returns `true`.

## Call chain in one line

`FormatDocumentAction.run` (formatActions.ts:232) → `formatDocumentWithSelectedProvider` (format.ts:290) → `getRealAndSyntheticDocumentFormattersOrdered` (format.ts:35) + `FormattingConflicts.select` (format.ts:95) → `DefaultFormatter._selectFormatter` (formatActionsMultiple.ts:176) → `formatDocumentWithProvider` (format.ts:310) → main-thread proxy (mainThreadLanguageFeatures.ts:456) → RPC `$provideDocumentFormattingEdits` (extHostLanguageFeatures.ts:2494) → `DocumentFormattingAdapter` (extHostLanguageFeatures.ts:710) → the extension's provider → `TextEdit.from` → back to `computeMoreMinimalEdits` (format.ts:339) → `FormattingEdit.execute` (formattingEdit.ts:47) → `editor.executeEdits`.