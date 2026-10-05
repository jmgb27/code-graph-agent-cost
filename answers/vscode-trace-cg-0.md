The Format Document flow runs in five stages. It starts at an editor action, picks one provider, crosses one RPC to the extension host, calls the extension's provider, and applies the edits back on the renderer side.

## 1. Command registration

**`src/vs/editor/contrib/format/browser/formatActions.ts`**
- **Action class:** `FormatDocumentAction` is defined at `formatActions.ts:212`.
  - Its id is `editor.action.formatDocument` (`:216`).
  - It is only enabled when the editor is writable and `EditorContextKeys.hasDocumentFormattingProvider` is true (`:218`).
  - The keybinding is Shift+Alt+F, or Ctrl+Shift+I on Linux (`:221-222`).
  - It also appears in the context menu under `1_modification` (`:225`).
- **Registration:** `registerEditorAction(FormatDocumentAction)` at `formatActions.ts:287`.
- **`run()` (`:231-240`):** calls `formatDocumentWithSelectedProvider(editor, FormattingMode.Explicit, …, userGesture=true)` inside `IEditorProgressService.showWhile(…, 250)`.

"Format Document With…" is a separate action, `FormatDocumentMultipleAction`, at `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:360`.

## 2. Choosing the formatter provider

**`src/vs/editor/contrib/format/browser/format.ts`**
- **`formatDocumentWithSelectedProvider`** (`format.ts:290-308`) does three things:
  1. It builds the candidate list with `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35-72`):
     - First, every registered document formatter from `languageFeaturesService.documentFormattingEditProvider.ordered(model)` (`:48`). `ordered()` lives at `src/vs/editor/common/languageFeatureRegistry.ts:126`.
     - Then every range formatter, wrapped as a document formatter that formats `model.getFullModelRange()` (`:56-69`). An extension is skipped here if it already contributed a document formatter.
  2. It calls `FormattingConflicts.select(provider, model, mode, FormattingKind.File)` (`:303`).
  3. It passes the chosen provider to `formatDocumentWithProvider` (`:306`).
- **`FormattingConflicts`** (`format.ts:86-105`) keeps a list of selector functions. `select()` returns `undefined` when there are no providers; otherwise it asks the most recently registered selector (`:99-101`).

Two selectors are registered:
- **Workbench:** `DefaultFormatter` in `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:39`. It registers its selector at `:63` and is itself registered as a workbench contribution at `:271`.
  - `_analyzeFormatter` (`:138-174`) reads the `editor.defaultFormatter` setting for the document's resource and language (`:139-142`).
    - If that extension's provider is in the list, it is used (`:146-149`).
    - If the extension is enabled but can't format this file, you get an explanatory message (`:153-160`).
    - If no default is set and there is exactly one provider, that one is used (`:163-165`).
    - Otherwise you get a "multiple formatters" or "not available" message (`:168-173`).
  - `_selectFormatter` (`:176-203`) handles the message case.
    - In `Explicit` mode, which is what Format Document uses, it shows a "Configure Default Formatter" dialog.
    - If you confirm, `_pickAndPersistDefaultFormatter` (`:205`) shows a quick pick and saves your choice.
    - In `Silent` mode it only shows a silent notification (`:194-200`).
- **Standalone Monaco:** `src/vs/editor/editor.api.ts:21` always takes `formatter[0]`.

## 3. Renderer → extension host RPC

**Registration (extension host → renderer):**
- An extension calls `vscode.languages.registerDocumentFormattingEditProvider`, defined at `src/vs/workbench/api/common/extHost.api.impl.ts:733-734`.
- That goes to `ExtHostLanguageFeatures.registerDocumentFormattingEditProvider` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488-2492`), which:
  - wraps the provider in a `DocumentFormattingAdapter`,
  - gets a numeric `handle` from `_addNewAdapter` (`:2254`),
  - calls `this._proxy.$registerDocumentFormattingSupport(handle, selector, extensionId, displayName)`.
- The protocol declaration is at `src/vs/workbench/api/common/extHost.protocol.ts:545`.

**Renderer-side stub:**
- `MainThreadLanguageFeatures.$registerDocumentFormattingSupport` (`src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460`) registers a proxy provider with `languageFeaturesService.documentFormattingEditProvider`.
- That proxy carries `extensionId` and `displayName`, which is what the default-formatter matching in stage 2 uses.
- Its `provideDocumentFormattingEdits` makes the RPC: `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (`:457`).
- The protocol declaration is at `extHost.protocol.ts:2978`.

## 4. Extension host side

- `ExtHostLanguageFeatures.$provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:2494-2496`) calls `_withAdapter(handle, DocumentFormattingAdapter, …)`.
- `_withAdapter` (`:2214-2252`):
  - looks up the adapter by handle and checks its type,
  - logs and reports telemetry on errors,
  - races the result against the cancellation token (`:2248-2250`).
- `DocumentFormattingAdapter.provideDocumentFormattingEdits` (`:703-721`):
  - gets the `ExtHostDocument` from `ExtHostDocuments` (`:713`),
  - calls the extension's `vscode.DocumentFormattingEditProvider.provideDocumentFormattingEdits(document, options, token)` (`:716`),
  - converts each returned `vscode.TextEdit` to the wire format with `typeConvert.TextEdit.from` (`:718`).

## 5. Applying the returned edits

Back in `formatDocumentWithProvider` (`format.ts:310-383`):
- **Cancellation:** a cancellation token source is created. For an editor it is `EditorStateCancellationTokenSource`, which cancels if the value or cursor position changes (`:323-328`).
- **Getting edits:** it calls `provider.provideDocumentFormattingEdits(model, model.getFormattingOptions(), cts.token)`, which is the RPC stub above (`:332-336`).
- **Minimising edits:** the raw edits go to `IEditorWorkerService.computeMoreMinimalEdits` (`format.ts:338`). This is a diff computed in the editor web worker, at `src/vs/editor/browser/services/editorWorkerService.ts:153-160`.
- **Early exits:**
  - If cancellation was requested, it returns early (`:340`).
  - If there are no edits, it returns `false` (`:348`).
- **With an editor:** `FormattingEdit.execute(editor, edits, addUndoStops = mode !== Silent)` (`format.ts:353`), in `src/vs/editor/contrib/format/browser/formattingEdit.ts:47-61`:
  - It pushes an undo stop before and after (`:49`, `:60`).
  - `_handleEolEdits` (`:15-35`) applies any end-of-line change with `model.pushEOL` and keeps only the edits that have a range and text.
  - A single edit that replaces the whole model is applied with `editor.executeEdits('formatEditsCommand', …EditOperation.replace…)` (`:53-55`).
  - Otherwise it uses `EditOperation.replaceMove` (`:57`).
  - Afterwards the action calls `revealPositionInCenterIfOutsideViewport` (`format.ts:356`).
- **With only a model (no editor):** it calls `model.pushEditOperations` with `forceMoveMarkers: true` and a cursor-state computer that restores the selection from the undo edits (`format.ts:360-377`).
- **Finally:** it plays `AccessibilitySignal.format` (`:379`).

## Summary chain

`FormatDocumentAction.run` (`formatActions.ts:231`)
→ `formatDocumentWithSelectedProvider` (`format.ts:290`)
→ `getRealAndSyntheticDocumentFormattersOrdered` (`:35`) plus `FormattingConflicts.select` (`:97`)
→ `DefaultFormatter._selectFormatter` (`formatActionsMultiple.ts:176`)
→ `formatDocumentWithProvider` (`format.ts:310`)
→ main-thread proxy (`mainThreadLanguageFeatures.ts:457`)
→ **RPC** `$provideDocumentFormattingEdits`
→ `ExtHostLanguageFeatures` (`extHostLanguageFeatures.ts:2494`)
→ `DocumentFormattingAdapter` (`:710`)
→ the extension's provider
→ back to the renderer, where `computeMoreMinimalEdits` (`format.ts:338`) runs
→ `FormattingEdit.execute` / `editor.executeEdits` (`formattingEdit.ts:47`), or `model.pushEditOperations` (`format.ts:361`) when there is no editor.