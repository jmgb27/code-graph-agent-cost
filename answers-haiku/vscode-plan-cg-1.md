Based on the CodeGraph exploration, here's a comprehensive plan for adding a per-language setting `editor.formatOnSaveTimeout` that bounds how long format-on-save waits:

## Files to Change

### 1. **Settings Registration**
- **`src/vs/editor/common/config/editorOptions.ts:5841+`**
  - Add `formatOnSaveTimeout` to `EditorOption` enum
  - Register the option in `EditorOptions` (after line 6024) with timeout type (number, in milliseconds)

### 2. **Save Participants (Text Files)**
- **`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216`**
  - `FormatOnSaveParticipant.participate()` method - pass timeout from config to the formatting operation
  - Add timeout cancellation logic using `CancellationToken`

- **`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`** (top level)
  - Import/use appropriate timeout wrapper with `CancellationToken`

### 3. **Save Participants (Notebooks)**
- **`src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61`**
  - `FormatOnSaveParticipant.participate()` method - apply timeout to notebook formatting

### 4. **Extension Host (timeout thresholds)**
- **`src/vs/workbench/api/common/extHostDocumentSaveParticipant.ts:31`**
  - Modify `_thresholds` default/configuration to use the new per-language timeout setting

- **`src/vs/workbench/api/browser/mainThreadNotebookSaveParticipant.ts:32-38`**
  - Update timeout value (currently hardcoded to 1750ms) to use per-language setting

- **`src/vs/workbench/api/common/extHost.protocol.ts`**
  - Check if `ExtHostDocumentSaveParticipantShape` or `ExtHostNotebookDocumentSaveParticipantShape` need timeout parameter updates

### 5. **Settings UI/Editor**
- **`src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:31`**
  - Optionally add `editor.formatOnSaveTimeout` to `COMMONLY_USED_SETTINGS` (read-only, no edit required)

### 6. **Configuration Schema**
- **`src/vs/editor/common/config/editorConfigurationSchema.ts:325-336`**
  - Schema is auto-generated from `editorOptionsRegistry`, no direct edit needed

### 7. **Tests**
- **`src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`**
  - Add test cases for timeout enforcement
  - Test per-language override of timeout value
  - Test that format-on-save is cancelled after timeout

### 8. **Notebook Tests** (if exists)
- Search for notebook save participant tests and add timeout coverage

## Summary of Changes by Category

| Category | File | Line Range | Change Type |
|----------|------|-----------|------------|
| **Option Definition** | src/vs/editor/common/config/editorOptions.ts | 5841+, 6024+ | Add enum + registration |
| **Text Format Participant** | src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts | 216-253 | Integrate timeout |
| **Notebook Format Participant** | src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts | 61-122 | Integrate timeout |
| **Extension Host Text** | src/vs/workbench/api/common/extHostDocumentSaveParticipant.ts | 31-32, 51-73 | Use configurable timeout |
| **Extension Host Notebook** | src/vs/workbench/api/browser/mainThreadNotebookSaveParticipant.ts | 32-46 | Use configurable timeout |
| **Tests** | src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts | Full file | Add timeout tests |

The flow works: setting → format participant reads timeout from config → passes `CancellationToken` with timeout to extension host → formatter respects deadline.