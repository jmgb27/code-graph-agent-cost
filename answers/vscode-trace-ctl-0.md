Format Document runs in five steps: the editor action, choosing a formatter, an RPC to the extension, cleaning up the returned edits, and applying them to the model.

## 1. Command registration and action

- **`src/vs/editor/contrib/format/browser/formatActions.ts:212`** declares `class FormatDocumentAction extends EditorAction`.
  - Its id is `editor.action.formatDocument` and its label is "Format Document" (lines 216–217).
  - The precondition is not in a composite editor, the editor is writable, and `hasDocumentFormattingProvider` is true (line 218).
  - The keybinding is Shift+Alt+F, or Ctrl+Shift+I on Linux (lines 219–224). It also appears in the context menu under group `1_modification` (lines 225–228).
- **`formatActions.ts:287`**: `registerEditorAction(FormatDocumentAction)` registers it.
- **`formatActions.ts:232-241`**: `run()` calls `formatDocumentWithSelectedProvider(editor, FormattingMode.Explicit, Progress.None, CancellationToken.None, true)`. The call is wrapped in `IEditorProgressService.showWhile(..., 250)`, so a progress indicator appears if formatting takes longer than 250 ms.

## 2. Choosing the formatter provider

**`src/vs/editor/contrib/format/browser/format.ts:290-308`**, `formatDocumentWithSelectedProvider`:

1. **Candidate list** (`format.ts:302`) comes from `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35-70`):
   - First, every `DocumentFormattingEditProvider` that matches the model, in score order from `LanguageFeatureRegistry.ordered(model)` (lines 44–50).
   - Then every range formatter from an extension that didn't already contribute a document formatter. Each is wrapped as a synthetic document formatter that calls `provideDocumentRangeFormattingEdits(model, model.getFullModelRange(), …)` (lines 53–67).
2. **Selection** (`format.ts:303`): `FormattingConflicts.select(provider, model, mode, FormattingKind.File)` (`format.ts:95-104`) hands the list to the first registered selector.
   - In the workbench, that selector is installed by the `DefaultFormatter` contribution at `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts:63` (the contribution is registered at around line 272).
   - `_selectFormatter` (`formatActionsMultiple.ts:176`) calls `_analyzeFormatter` (lines 138–174):
     - If the `editor.defaultFormatter` setting (scoped to the resource and language) names a formatter in the list, that formatter is used (lines 139–150).
     - Otherwise, if there is exactly one candidate, it is used (lines 163–165).
     - Otherwise it returns an error message.
   - For an error message in Explicit mode, a "Configure Default Formatter" dialog appears (lines 182–192). If the user confirms, `_pickAndPersistDefaultFormatter` shows a quick pick and writes the choice to settings (lines 205–223).
   - In Silent mode it shows a quiet notification instead (lines 194–201).
   - Standalone Monaco has no workbench, so it installs a trivial "take the first one" selector at `src/vs/editor/editor.api.ts:21`.
3. **Run it** (`format.ts:304-306`): `progress.report(selected)`, then `formatDocumentWithProvider(selected, …)`.

## 3. RPC to the extension host

`formatDocumentWithProvider` (`format.ts:310`) creates an `EditorStateCancellationTokenSource`. The request is cancelled if the editor's value or cursor position changes (line 325). It then calls `provider.provideDocumentFormattingEdits(model, model.getFormattingOptions(), cts.token)` (`format.ts:333-337`).

For a formatter contributed by an extension, the provider object is a main-thread proxy.

**Registration path (extension → main thread):**
- `vscode.languages.registerDocumentFormattingEditProvider` is defined at `src/vs/workbench/api/common/extHost.api.impl.ts:733-734`.
- It calls `ExtHostLanguageFeatures.registerDocumentFormattingEditProvider` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488-2492`). That wraps the extension's provider in a `DocumentFormattingAdapter`, allocates a handle, and calls `$registerDocumentFormattingSupport` over RPC.
- The protocol definition is at `src/vs/workbench/api/common/extHost.protocol.ts:545`.
- **`src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460`** registers a provider in `ILanguageFeaturesService.documentFormattingEditProvider` with the extension's `extensionId` and `displayName`. Its `provideDocumentFormattingEdits` simply forwards `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (line 457).

**Invocation path (main thread → extension host):**
- The protocol definition is at `extHost.protocol.ts:2978`.
- **`extHostLanguageFeatures.ts:2494-2496`**: `$provideDocumentFormattingEdits` revives the URI and uses `_withAdapter(handle, DocumentFormattingAdapter, …)` to find the adapter.
- **`extHostLanguageFeatures.ts:703-721`**: `DocumentFormattingAdapter.provideDocumentFormattingEdits` looks up the `ExtHostDocument` (line 712) and calls the extension's `vscode.DocumentFormattingEditProvider.provideDocumentFormattingEdits(document, options, token)` (line 715). It converts the resulting `vscode.TextEdit[]` with `typeConvert.TextEdit.from` (line 717) before the result is sent back over RPC.

## 4. Post-processing the edits

- **`format.ts:339`**: the raw edits go through `IEditorWorkerService.computeMoreMinimalEdits(model.uri, rawEdits)`, implemented at `src/vs/editor/browser/services/editorWorkerService.ts:153`. The editor web worker (`$computeMoreMinimalEdits`, line 159) diffs the edits into smaller ones so that cursors and markers are disturbed less.
- **`format.ts:341-350`**: if the token was cancelled by then, it returns without applying. If there are no edits, it returns `false`.

## 5. Applying the edits to the model

**With an editor** (the Format Document case): `FormattingEdit.execute(editor, edits, mode !== Silent)` at `format.ts:355`, implemented in `src/vs/editor/contrib/format/browser/formattingEdit.ts:47-63`:
- In Explicit mode it pushes an undo stop before and after the edits (lines 48–50 and 59–61).
- It captures the scroll position with `StableEditorScrollState.capture` (line 51) and restores it afterwards (line 62).
- `_handleEolEdits` (lines 15–35) applies any end-of-line changes through `model.pushEOL()` and keeps only the ordinary range/text edits.
- If a single edit replaces the whole model, it applies it with `editor.executeEdits('formatEditsCommand', EditOperation.replace(...))` (line 55). Otherwise it uses `EditOperation.replaceMove(...)` (line 57).
- Back in `format.ts:357-359`, the cursor is scrolled into view with `revealPositionInCenterIfOutsideViewport`.

**Model only** (no editor, e.g. format on save of a model): `model.pushEditOperations(...)` with `forceMoveMarkers: true` and an undo-selection computer (`format.ts:361-379`).

Finally, the accessibility "format" signal plays (`format.ts:380`).

---

**Summary flow:**
`FormatDocumentAction.run` (formatActions.ts:232) → `formatDocumentWithSelectedProvider` (format.ts:290) → `getRealAndSyntheticDocumentFormattersOrdered` (format.ts:35) → `FormattingConflicts.select` (format.ts:95) → `DefaultFormatter._selectFormatter` (formatActionsMultiple.ts:176) → `formatDocumentWithProvider` (format.ts:310) → main-thread proxy (mainThreadLanguageFeatures.ts:457) → RPC `$provideDocumentFormattingEdits` (extHostLanguageFeatures.ts:2494) → `DocumentFormattingAdapter` (extHostLanguageFeatures.ts:710) → the extension's provider → `computeMoreMinimalEdits` (format.ts:339) → `FormattingEdit.execute` → `editor.executeEdits` (formattingEdit.ts:47-57).