Based on my comprehensive exploration of the VS Code codebase, here's the complete plan for adding a per-language `editor.formatOnSaveTimeout` setting:

## Plan: Add `editor.formatOnSaveTimeout` Per-Language Setting

### Overview
This setting will bound the maximum time (in milliseconds) that format-on-save operations can take before being automatically cancelled. It supports per-language configuration via the `[languageId]` override pattern.

### Files and Functions to Change

#### 1. **EditorOption Registration**
**File:** `src/vs/editor/common/config/editorOptions.ts`
- Add new `EditorOption.formatOnSaveTimeout` enum value (after `formatOnSave`)
- Create new `EditorIntOption` instance for `formatOnSaveTimeout` with:
  - Default value: `1500` (milliseconds)
  - Minimum: `100`
  - Maximum: `30000`
  - Add schema definition

#### 2. **Configuration Schema**
**File:** `src/vs/editor/common/config/editorConfigurationSchema.ts`
- Schema is auto-generated from `editorOptionsRegistry` in editorOptions.ts
- No manual changes needed—the schema definition in step 1 creates it

#### 3. **Format-on-Save Participant (Text Files)**
**File:** `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216-271`
- Modify `FormatOnSaveParticipant.participate()` method:
  - Read the timeout setting per language using `overrideIdentifier`
  - Wrap the formatting call with a timeout mechanism using `CancellationTokenSource`
  - Cancel after the configured timeout expires

#### 4. **Format-on-Save Participant (Notebooks)**
**File:** `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:61-342`
- Modify `FormatOnSaveParticipant.participate()` method (notebook version)
- Apply same timeout wrapping logic as text files

#### 5. **Extension Host Save Participant**
**File:** `src/vs/workbench/api/browser/mainThreadSaveParticipant.ts:17-49`
- Current hardcoded timeout: `1750ms` (line 36)
- Make it configurable by reading `editor.formatOnSaveTimeout` from settings
- Use `CancellationTokenSource` with timeout and pass cancellation to extension host

#### 6. **Text File Save Participant (Infrastructure)**
**File:** `src/vs/workbench/services/textfile/common/textFileSaveParticipant.ts:34-92`
- No changes needed—already supports cancellation tokens; timeout is handled by participants

#### 7. **Working Copy Save Participant (Infrastructure)**
**File:** `src/vs/workbench/services/workingCopy/common/storedFileWorkingCopySaveParticipant.ts:37-82`
- No changes needed—already supports cancellation tokens; timeout is handled by participants

#### 8. **Settings UI**
**File:** `src/vs/workbench/contrib/preferences/browser/settingsEditor2.ts`
- No changes needed—automatically discovers settings from the configuration registry

#### 9. **Settings Layout (Commonly Used)**
**File:** `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:31-45`
- Optionally add `editor.formatOnSaveTimeout` to `COMMONLY_USED_SETTINGS` if desired

### Test Files to Update/Create

#### Existing Test Files
- **`src/vs/workbench/services/workingCopy/test/browser/storedFileWorkingCopy.test.ts`** — Add tests for save participant timeout
- **`src/vs/workbench/contrib/format/test/browser/format.test.ts`** — Add tests for format-on-save timeout
- **`src/vs/workbench/services/textfile/test/browser/textFileEditorModel.test.ts`** — Add tests for text file format-on-save timeout

#### New Test Structure
Create tests for:
1. **Timeout behavior**: Verify formatting cancels when exceeding timeout
2. **Per-language configuration**: Test that `[typescript]` and `[python]` can have different timeout values
3. **Fallback to default**: Verify default timeout applies when language-specific value not set
4. **Format completion before timeout**: Verify successful completion when format finishes within timeout
5. **Cancellation propagation**: Verify cancellation token is properly passed through the call chain

### Configuration Schema Example

```json
"editor.formatOnSaveTimeout": {
  "type": "integer",
  "default": 1500,
  "minimum": 100,
  "maximum": 30000,
  "scope": "language-overridable",
  "description": "Timeout in milliseconds for format-on-save operations. When exceeded, the format operation is cancelled."
}
```

### Usage Example

Users would configure it like:
```json
{
  "editor.formatOnSave": true,
  "editor.formatOnSaveTimeout": 2000,
  "[python]": {
    "editor.formatOnSaveTimeout": 5000
  },
  "[typescript]": {
    "editor.formatOnSaveTimeout": 1000
  }
}
```

### Implementation Details

**Key Pattern for Reading Setting:**
```typescript
const overrides = { overrideIdentifier: textEditorModel.getLanguageId(), resource: textEditorModel.uri };
const timeout = this.configurationService.getValue<number>('editor.formatOnSaveTimeout', overrides);
```

**Cancellation Pattern:**
```typescript
const cts = new CancellationTokenSource(token);
const timeoutHandle = setTimeout(() => cts.cancel(), timeout);
try {
  await formatOperation(cts.token);
} finally {
  clearTimeout(timeoutHandle);
  cts.dispose();
}
```

### Integration Points
1. **ConfigurationService** — reads per-language overrides
2. **CancellationTokenSource** — enforces timeout via cancellation
3. **FormatDocumentWithSelectedProvider** — receives cancellation token
4. **ExtensionHost** — extension formatters receive cancellation signals

### Backwards Compatibility
- Default 1500ms is larger than current implicit behavior (formatting runs to completion)
- Existing users not affected unless they explicitly set the timeout
- Can be set to very high values (e.g., 30000ms) to maintain current behavior

This plan touches 7 core files and optionally 2 layout/cosmetic files, with test coverage across 3 existing test suites and specific timeout/cancellation scenarios.