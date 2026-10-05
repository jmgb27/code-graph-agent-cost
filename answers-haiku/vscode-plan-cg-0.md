Based on my CodeGraph exploration, here's the comprehensive plan for adding a per-language setting `editor.formatOnSaveTimeout` that bounds how long format-on-save waits:

## Complete Plan: Adding `editor.formatOnSaveTimeout` Setting

### **Files to Modify**

#### 1. **Settings Registration**
- **`src/vs/editor/common/config/editorConfigurationSchema.ts`** — Register the new `editor.formatOnSaveTimeout` setting in the editor configuration schema

#### 2. **Editor Options**
- **`src/vs/editor/common/config/editorOptions.ts:5841`** — Add `EditorOption` enum entry for `formatOnSaveTimeout`
- **`src/vs/editor/common/config/editorOptions.ts:6024+`** — Add corresponding `EditorOptions.formatOnSaveTimeout` registration using `EditorIntOption`

#### 3. **Save Participants (Format on Save)**
- **`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216`** — Modify `FormatOnSaveParticipant.participate()` method to:
  - Read the timeout value from configuration
  - Pass timeout to formatting function
  - Implement cancellation after timeout expires
  
- **`src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61`** — Modify `FormatOnSaveParticipant.participate()` method (notebook version) similarly

#### 4. **Extension Host API**
- **`src/vs/workbench/api/common/extHostDocumentSaveParticipant.ts:22`** — Modify `ExtHostDocumentSaveParticipant`:
  - Update `_thresholds` property (line 31) to read from configuration or accept timeout parameter
  - Modify `$participateInSave()` method (line 51) to use per-language timeout for cancellation

- **`src/vs/workbench/api/common/extHostNotebookDocumentSaveParticipant.ts:24`** — Modify `ExtHostNotebookDocumentSaveParticipant`:
  - Update `_thresholds` property (line 32) similarly
  - Modify `$participateInSave()` method (line 47) to respect per-language timeout

#### 5. **Working Copy Save Participants**
- **`src/vs/workbench/services/workingCopy/common/storedFileWorkingCopySaveParticipant.ts:37`** — Modify `participate()` method to:
  - Accept or derive timeout value
  - Pass timeout to individual save participants
  - Update cancellation token behavior

- **`src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:17`** — Similar modifications for text file save participant

#### 6. **Settings UI**
- **`src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:31`** — Add `'editor.formatOnSaveTimeout'` to `COMMONLY_USED_SETTINGS` array (optional, if we want it visible)

- **`src/vs/workbench/contrib/preferences/browser/settingsEditor2.ts`** — Settings editor will automatically display the new setting via the schema registration

#### 7. **Tests**
- **`src/vs/workbench/api/test/browser/extHostDocumentSaveParticipant.test.ts`** — Add tests for:
  - Default timeout value
  - Per-language timeout override
  - Timeout cancellation behavior

- **`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.test.ts`** (if exists) or create new test file

- **`src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.test.ts`** (if exists)

- **`src/vs/workbench/services/workingCopy/common/storedFileWorkingCopySaveParticipant.test.ts`** (if exists)

### **Key Implementation Points**

1. **Configuration Scope**: Should support language-specific overrides using `@` syntax (e.g., `[python].editor.formatOnSaveTimeout`)
2. **Timeout Handling**: Use `CancellationToken` with `setTimeout()` to enforce the timeout
3. **Default Value**: Recommend starting with a reasonable default (e.g., 5000ms or 10000ms)
4. **Minimum/Maximum Bounds**: Consider enforcing minimum (e.g., 100ms) and maximum (e.g., 60000ms) values
5. **Extension Host Communication**: May need to update the protocol between main and extension host to pass timeout information

### **Related Interfaces & Types**
- `CancellationToken` — Used for timeout enforcement
- `IConfigurationPropertySchema` — Schema definition
- `IEditorOption<K, V>` — Editor option definition
- `IStoredFileWorkingCopySaveParticipant` — Save participant interface

This plan covers setting registration, cancellation implementation in save participants, UI exposure through settings editor, and test coverage for the new feature.