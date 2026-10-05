Based on my exploration of the VS Code codebase, here's a comprehensive plan for adding the per-language `editor.formatOnSaveTimeout` setting:

## Plan: Add `editor.formatOnSaveTimeout` per-language setting

### Summary
This setting will bound how long format-on-save waits before timing out and cancelling formatting operations. It will be configurable per language via language-specific settings overrides.

---

## Files & Functions to Change

### 1. **Setting Registration**
**File:** `src/vs/editor/common/config/editorOptions.ts`

- Register new `EditorOption.formatOnSaveTimeout` enum value
- Add to `editorOptionsRegistry` array with:
  - Default value (suggest 1500ms to match extension timeout threshold)
  - Validation (must be positive number or 0 for no timeout)
  - Type specification
  - Description for settings schema

---

### 2. **Text File Format-on-Save Participant**
**File:** `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`

**Class:** `FormatOnSaveParticipant`

- **Method:** `participate()` (L226)
  - Read `editor.formatOnSaveTimeout` from configuration with language-specific overrides
  - Pass timeout value to the formatting function calls
  - May need to wrap formatting promises with timeout enforcement using `raceCancellation`

- **Method:** Add helper function to apply timeout to formatting operations
  - Wraps promise with `setTimeout` that fires cancellation token if timeout expires

---

### 3. **Notebook Format-on-Save Participant**
**File:** `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts`

**Class:** `FormatOnSaveParticipant`

- **Method:** `participate()` (L71)
  - Read `editor.formatOnSaveTimeout` from configuration
  - Apply timeout to cell formatting operations
  - Handle both bulk edit and individual cell formatting paths

---

### 4. **Formatting Functions**
**File:** `src/vs/editor/contrib/format/browser/format.ts`

- **Function:** `formatDocumentWithSelectedProvider()` (L290)
  - Add `timeout?: number` parameter
  - Pass to `formatDocumentWithProvider()`

- **Function:** `formatDocumentRangesWithSelectedProvider()` (L107)
  - Add `timeout?: number` parameter
  - Pass to `formatDocumentRangesWithProvider()`

- **Function:** `formatDocumentWithProvider()` (L310)
  - Add `timeout?: number` parameter
  - If timeout specified, wrap formatting provider call with cancellation timeout
  - Use `raceCancellation()` to enforce timeout

- **Function:** `formatDocumentRangesWithProvider()` (L128)
  - Add `timeout?: number` parameter
  - Apply timeout similarly

- **Helper function:** Add `withTimeoutCancellation(promise, timeout, token)` utility
  - Returns promise that rejects if timeout expires before completion
  - Triggers cancellation token

---

### 5. **Format Actions (User Gestures)**
**File:** `src/vs/editor/contrib/format/browser/formatActions.ts`

- **Class:** `FormatDocumentAction` 
  - **Method:** `run()` (check line ~232)
  - Read timeout from settings and pass to `formatDocumentWithSelectedProvider()`

- **Class:** `FormatSelectionAction`
  - **Method:** `run()`
  - Pass timeout to `formatDocumentRangesWithSelectedProvider()`

- **Class:** `FormatOnType`
  - Check if it needs timeout handling (probably not, as it's triggered by typing, not save)

- **Class:** `FormatOnPaste`
  - Check if it needs timeout handling (probably not, as it's triggered by paste, not save)

---

### 6. **Cancellation Token Utilities**
**File:** `src/vs/base/common/cancellation.ts` (or `src/vs/base/common/async.ts`)

- **Function:** Add `withTimeoutCancellation()` or enhance `raceCancellation()`
  - Takes promise, timeout value (ms), and optional CancellationToken
  - Creates timeout that triggers cancellation
  - Returns promise that rejects with cancellation error if timeout fires first
  - Example: `await withTimeoutCancellation(formattingPromise, timeout, cts.token)`

---

### 7. **Settings Schema**
**Files:** 
- `src/vs/workbench/contrib/preferences/common/preferencesRegistry.ts` (or equivalent schema registration)
- May also need updates to `package.json` if settings are defined there

Add JSON schema entry for `editor.formatOnSaveTimeout`:
- Type: `number`
- Minimum: `0`
- Default: `1500`
- Description: "Time in milliseconds to wait for format-on-save before timing out"
- Scope: `language-overridable`

---

### 8. **Tests**

**File:** `src/vs/workbench/api/test/browser/extHostDocumentSaveParticipant.test.ts` (existing)
- Add tests for format-on-save timeout enforcement

**Potential new test files:**
- Tests for timeout enforcement in `src/vs/editor/contrib/format/browser/format.ts`
- Tests for configuration reading with language overrides in save participants
- Tests for cancellation token timeout behavior

**Test scenarios:**
1. Formatting completes before timeout → completes successfully
2. Formatting exceeds timeout → cancellation error is raised
3. Timeout can be configured per language
4. Timeout value of 0 disables timeout
5. Cancellation propagates properly to extension host

---

## Execution Flow Diagram

```
Save triggered
  ↓
TextFileSaveParticipant.participate()
  ├→ FormatOnSaveParticipant.participate()
  │   ├→ Read editor.formatOnSaveTimeout (with language override)
  │   ├→ Call formatDocumentWithSelectedProvider(timeout)
  │   │   ├→ formatDocumentWithProvider(timeout)
  │   │   │   ├→ Create cancellation source
  │   │   │   ├→ Set up timeout: if timeout expires, cancel token
  │   │   │   ├→ Run provider.provideDocumentFormattingEdits(token)
  │   │   │   └→ raceCancellation(promise, cts.token)
  │   │   │       → If timeout fires: CancellationError thrown
  │   │   │       → Timeout cleared if operation completes first
  │   │   └→ Apply edits or handle cancellation
  │   └→ Progress reported
  └→ Continue with other participants or complete
```

---

## Summary Table

| Component | File | Function/Class | Change |
|-----------|------|----------------|--------|
| **Registration** | `editorOptions.ts` | `editorOptionsRegistry` | Register `formatOnSaveTimeout` option |
| **Text Format-on-Save** | `saveParticipants.ts` (codeEditor) | `FormatOnSaveParticipant.participate()` | Read & pass timeout |
| **Notebook Format-on-Save** | `saveParticipants.ts` (notebook) | `FormatOnSaveParticipant.participate()` | Read & pass timeout |
| **Format Execution** | `format.ts` | `formatDocumentWithProvider()` | Enforce timeout via cancellation |
| **Format Selection** | `format.ts` | `formatDocumentRangesWithProvider()` | Enforce timeout via cancellation |
| **Cancellation** | `cancellation.ts` | Add `withTimeoutCancellation()` | Helper to enforce timeout |
| **Format Actions** | `formatActions.ts` | Action `run()` methods | Pass timeout to formatters |
| **Settings Schema** | `preferencesRegistry.ts` | Schema definitions | Add formatOnSaveTimeout schema |
| **Tests** | `extHostDocumentSaveParticipant.test.ts` | Test suites | Add timeout enforcement tests |