The path goes from a keybinding to a registry lookup, then a policy hook that picks the formatter, then one RPC to the extension host. The edits come back, get shrunk by the editor worker, and are applied as a single undoable edit.

## 1. Command registration and invocation

- **`src/vs/editor/contrib/format/browser/formatActions.ts:212`** defines `class FormatDocumentAction extends EditorAction`:
  - id `editor.action.formatDocument`, label "Format Document" (lines 216–217).
  - Precondition: not in a composite editor, editor is writable, and `EditorContextKeys.hasDocumentFormattingProvider` (line 218).
  - Keybinding is Shift+Alt+F, or Ctrl+Shift+I on Linux (lines 221–222). It also has a context-menu entry (lines 225–228).
- **`formatActions.ts:287`** calls `registerEditorAction(FormatDocumentAction)`, which registers it as a command and keybinding.
- `EditorAction.runEditorCommand` (**`src/vs/editor/browser/editorExtensions.ts:403`**) logs telemetry and then calls `run`.
- **`formatActions.ts:232-241`**: `run()` calls `formatDocumentWithSelectedProvider(editor, FormattingMode.Explicit, Progress.None, CancellationToken.None, true)` through `instaService.invokeFunction`, wrapped in `IEditorProgressService.showWhile(..., 250)`.

## 2. Choosing the formatter provider

**`src/vs/editor/contrib/format/browser/format.ts:290`**, `formatDocumentWithSelectedProvider`:

1. **Collect candidates** (`format.ts:302`) with `getRealAndSyntheticDocumentFormattersOrdered` (`format.ts:35-70`):
   - It first adds every provider from `documentFormattingEditProvider.ordered(model)` (line 44). `LanguageFeatureRegistry.ordered` (`src/vs/editor/common/languageFeatureRegistry.ts:126`) sorts them by selector match score.
   - It then adds each range formatter as a synthetic document formatter, which formats `model.getFullModelRange()` (lines 53–67). This is skipped when the same extension already supplied a document formatter.
2. **Resolve conflicts** (`format.ts:303`) with `FormattingConflicts.select(...)` (`format.ts:95-104`). This calls the first selector registered through `FormattingConflicts.setFormatterSelector` (`format.ts:90`).
3. **The workbench selector**: `DefaultFormatter` in `src/vs/workbench/contrib/format/browser/formatActionsMultiple.ts` is registered as a workbench contribution (lines 271–273). Its constructor installs the selector at line 63.
   - `_selectFormatter` (line 176) calls `_analyzeFormatter` (line 138), which reads `editor.defaultFormatter`, scoped to the file's resource and language:
     - If that setting names an extension, the matching provider is used (lines 144–150).
     - If nothing is configured and there is exactly one candidate, that candidate is used (lines 163–165).
     - Otherwise it returns an error message (lines 168–173).
   - With an error message and `Explicit` mode, it shows the "Configure Default Formatter" dialog, which leads to `_pickAndPersistDefaultFormatter` (lines 182–190). In `Silent` mode it shows a notification instead (lines 195–200).
4. If a provider was selected, `progress.report(selected)` runs and then `formatDocumentWithProvider` is called (`format.ts:304-306`).

## 3. RPC to the extension host

**How the provider gets registered (ext host → main thread):**
- An extension calls `vscode.languages.registerDocumentFormattingEditProvider`, implemented at `src/vs/workbench/api/common/extHost.api.impl.ts:733-734`.
- That calls `ExtHostLanguageFeatures.registerDocumentFormattingEditProvider` (`src/vs/workbench/api/common/extHostLanguageFeatures.ts:2488`). It wraps the extension's provider in a `DocumentFormattingAdapter` stored under a numeric handle (line 2489), then calls `this._proxy.$registerDocumentFormattingSupport(handle, selector, extensionId, displayName)` (line 2490).
- The RPC shape is declared in `src/vs/workbench/api/common/extHost.protocol.ts:545`.
- `MainThreadLanguageFeatures.$registerDocumentFormattingSupport` (`src/vs/workbench/api/browser/mainThreadLanguageFeatures.ts:452-460`) registers a stand-in provider in `ILanguageFeaturesService.documentFormattingEditProvider`. Its `provideDocumentFormattingEdits` forwards to `this._proxy.$provideDocumentFormattingEdits(handle, model.uri, options, token)` (line 457). This stand-in is what step 2 selects.

**How the call is made (main thread → ext host):**
- `formatDocumentWithProvider` (`format.ts:310`) creates a cancellation source (lines 323–329):
  - With an editor, it uses `EditorStateCancellationTokenSource`, which cancels if the text or cursor position changes.
  - With a bare model, it uses `TextModelCancellationTokenSource`.
- It then calls `provider.provideDocumentFormattingEdits(model, model.getFormattingOptions(), cts.token)` (`format.ts:333-337`). That goes through the stand-in and crosses the RPC boundary.
- The ext host receives it in `ExtHostLanguageFeatures.$provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:2494-2496`, declared at `extHost.protocol.ts:2978`). `_withAdapter` looks up the `DocumentFormattingAdapter` by handle.
- `DocumentFormattingAdapter.provideDocumentFormattingEdits` (`extHostLanguageFeatures.ts:703-721`):
  - Gets the ext-host document with `ExtHostDocuments.getDocument(resource)` (line 712).
  - Calls the extension's `vscode.DocumentFormattingEditProvider.provideDocumentFormattingEdits(document, options, token)` (line 715).
  - Converts the result with `typeConvert.TextEdit.from` into `languages.TextEdit[]` (line 717), which is serialized back over the RPC.

## 4. Applying the returned edits

Still in `formatDocumentWithProvider`:
- **`format.ts:339`**: `workerService.computeMoreMinimalEdits(model.uri, rawEdits)` diffs the edits in the editor web worker, so a full-document replacement becomes small edits. If the token was cancelled meanwhile, nothing is applied (lines 341–343). If there are no edits, it returns `false` (lines 349–351).
- **Editor case** (`format.ts:353-359`): it calls `FormattingEdit.execute(editor, edits, mode !== Silent)`, then reveals the cursor if it is off screen. In `src/vs/editor/contrib/format/browser/formattingEdit.ts:47-63`, `execute`:
  - Adds undo stops before and after when the mode isn't Silent (lines 48–50 and 59–61).
  - Captures the scroll position with `StableEditorScrollState` (line 51).
  - `_handleEolEdits` (lines 15–35) pulls out any `eol` change and applies it with `model.pushEOL`. It keeps only the edits that have a range and text.
  - If one edit covers the whole model, it applies `EditOperation.replace`. Otherwise it applies `EditOperation.replaceMove`. Both go through `editor.executeEdits('formatEditsCommand', ...)` (lines 53–58).
  - It then restores the cursor's position relative to the viewport (line 62).
- **Model-only case** (`format.ts:361-379`, used for example by save participants): it calls `model.pushEditOperations` with `forceMoveMarkers: true`. The cursor state computed for undo is based on the first edit's range.
- **`format.ts:380`** plays the `AccessibilitySignal.format` sound.

## Call chain summary

```
Shift+Alt+F → editor.action.formatDocument
  FormatDocumentAction.run                        formatActions.ts:232
  → formatDocumentWithSelectedProvider            format.ts:290
      getRealAndSyntheticDocumentFormattersOrdered format.ts:35
      FormattingConflicts.select                  format.ts:95
        → DefaultFormatter._selectFormatter        formatActionsMultiple.ts:176 (editor.defaultFormatter)
  → formatDocumentWithProvider                    format.ts:310
      stand-in provider.provideDocumentFormattingEdits   mainThreadLanguageFeatures.ts:456
        ══ RPC $provideDocumentFormattingEdits ══>       extHostLanguageFeatures.ts:2494
          DocumentFormattingAdapter                      extHostLanguageFeatures.ts:710
            extension's provideDocumentFormattingEdits   (line 715) → TextEdit.from (line 717)
      computeMoreMinimalEdits (worker)            format.ts:339
      FormattingEdit.execute → editor.executeEdits formattingEdit.ts:47
```

The "Format Document With…" command, which lets you pick a formatter, is defined in `formatActionsMultiple.ts`. It skips `FormattingConflicts` and calls `formatDocumentWithProvider` directly with the formatter you chose.