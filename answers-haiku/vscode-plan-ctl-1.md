Based on my analysis of the VS Code codebase, here's a complete plan for adding a per-language `editor.formatOnSaveTimeout` setting:

## **Files and Functions to Change**

### **1. Setting Registration**
**File**: `src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`
- **Function**: Anonymous contribution (configuration registry)
- **Line 412**: Add new property definition for `editor.formatOnSaveTimeout` after `editor.formatOnSaveMode`
  - Type: `number`
  - Default: `60000` (milliseconds)
  - Scope: `ConfigurationScope.LANGUAGE_OVERRIDABLE`
  - Description: "Timeout in milliseconds for format on save"

### **2. Save Participant Modification**
**File**: `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216-271`
- **Class**: `FormatOnSaveParticipant`
- **Method**: `participate()` (line 226-270)
  - Add: Read `editor.formatOnSaveTimeout` setting (line ~248, after reading `editor.formatOnSave`)
  - Add: Apply timeout to cancellation token before calling format functions (line ~256-257)
  - Modify: Pass modified cancellation token to `formatDocumentWithSelectedProvider()` and `formatDocumentRangesWithSelectedProvider()`

### **3. Formatting Functions (Timeout Application)**
**File**: `src/vs/editor/contrib/format/browser/format.ts:107-308`
- **Function**: `formatDocumentRangesWithSelectedProvider()` (line 107-126)
  - Add: Accept optional timeout parameter
  - Add: Wrap cancellation token with timeout before passing to `formatDocumentRangesWithProvider()`
  
- **Function**: `formatDocumentWithSelectedProvider()` (line 290-308)
  - Add: Accept optional timeout parameter
  - Add: Wrap cancellation token with timeout before passing to `formatDocumentWithProvider()`

- **Function**: `formatDocumentRangesWithProvider()` (line 128-288)
  - Line 141-148: Modify CTS creation to incorporate timeout
  
- **Function**: `formatDocumentWithProvider()` (line 310-375)
  - Line 321-329: Modify CTS creation to incorporate timeout

### **4. Cancellation Timeout Mechanism**
**File**: `src/vs/base/common/cancellation.ts` OR `src/vs/editor/contrib/editorState/browser/editorState.ts`
- **New Export**: Create `TimeoutCancellationTokenSource` class
  - Constructor: Accept `timeout: number` and parent `CancellationToken`
  - Mechanism: Use `setTimeout()` to call `cancel()` after timeout
  - Cleanup: Dispose timer when cancelled or disposed

### **5. Extension Host Protocol (Optional - for completeness)**
**File**: `src/vs/workbench/api/common/extHost.protocol.ts:2978-2981`
- Line 2978: `$provideDocumentFormattingEdits()` signature
- Line 2979: `$provideDocumentRangeFormattingEdits()` signature  
- Line 2980: `$provideDocumentRangesFormattingEdits()` signature
- Note: These already accept `CancellationToken` - timeout is enforced on main thread, no protocol changes needed

### **6. Settings UI (Layout)**
**File**: `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:95-98`
- **Section**: `editor/format` (line 95-97)
- **Add**: `'editor.formatOnSaveTimeout'` to settings array
- Note: Pattern matching via `'editor.format*'` will auto-include it

### **7. Tests**
**File**: `src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts:20-179`
- **Suite**: `'Save Participants'`
- **Add test**: Timeout cancellation during format on save
  - Mock a slow formatter
  - Set timeout to small value
  - Verify cancellation token is cancelled before formatter completes
  - Verify format edits are not applied
- **Add test**: Timeout with sufficient duration allows formatting to complete
- **Add test**: Timeout value is read from language-specific overrides

### **Summary of Functions to Add/Modify**

| File | Function/Line | Type | Change |
|------|---|---|---|
| `files.contribution.ts:412` | config registry | Add | New setting definition |
| `saveParticipants.ts:226` | `FormatOnSaveParticipant.participate()` | Modify | Read timeout, create timeout token |
| `format.ts:107` | `formatDocumentRangesWithSelectedProvider()` | Modify | Accept timeout parameter |
| `format.ts:290` | `formatDocumentWithSelectedProvider()` | Modify | Accept timeout parameter |
| `format.ts:128` | `formatDocumentRangesWithProvider()` | Modify | Apply timeout to CTS |
| `format.ts:310` | `formatDocumentWithProvider()` | Modify | Apply timeout to CTS |
| `cancellation.ts` or `editorState.ts` | New class | Add | `TimeoutCancellationTokenSource` |
| `settingsLayout.ts:97` | format section | Modify | Add to settings array |
| `saveParticipant.test.ts:179` | test suite | Add | 2-3 timeout tests |