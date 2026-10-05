Based on my exploration of the codebase, here's a comprehensive plan for implementing `editor.formatOnSaveTimeout`:

## Setting Registration

**File:** `src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`
- Add new setting `editor.formatOnSaveTimeout` after `editor.formatOnSaveMode` (after line 411)
- Type: `number`
- Scope: `LANGUAGE_OVERRIDABLE`
- Default: `10000` (milliseconds)
- Description: "Timeout in milliseconds after which format-on-save is cancelled"

## FormatOnSaveParticipant Implementation

**File:** `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216-271`

Changes needed in `FormatOnSaveParticipant` class:
- Line 220: Add `@IConfigurationService` to constructor (already present)
- Line 226: In `participate()` method, after line 248, read the timeout setting using `configurationService.getValue<number>('editor.formatOnSaveTimeout', overrides)`
- After reading timeout, create a timeout-bounded CancellationTokenSource (using native `setTimeout` + `CancellationTokenSource.cancel()`)
- Lines 257, 263, 267: Replace `token` parameter with the timeout-bounded token in the three formatting calls

## Format Functions (Read-Only Verification)

**File:** `src/vs/editor/contrib/format/browser/format.ts:107-135, 290-310`
- `formatDocumentRangesWithSelectedProvider()` at line 107 - already accepts `token: CancellationToken`
- `formatDocumentWithSelectedProvider()` at line 290 - already accepts `token: CancellationToken`
- Both functions already propagate cancellation tokens to providers (line 124, etc.)

## Settings UI

**File:** `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:31-35`
- Optional: Add `'editor.formatOnSaveTimeout'` to `COMMONLY_USED_SETTINGS` array if desired to expose in Quick Settings

## Tests

**File:** `src/vs/workbench/contrib/codeEditor/test/browser/saveParticipant.test.ts`

Add new test suite after line 149:
- Test `formatOnSaveTimeout` with timeout expiration (format takes longer than timeout)
- Test `formatOnSaveTimeout` with successful completion (format finishes before timeout)
- Test with timeout value of 0 (disabled)
- Test with different timeout values (100ms, 5000ms, etc.)
- Verify cancellation token is properly passed to format functions

## Extension Host Communication

**File:** `src/vs/editor/contrib/format/browser/format.ts:128-170, 164-169, 201-206`
- Line 168, 205: `cts.token` is passed to `provider.provideDocumentRangeFormattingEdits()` and `provider.provideDocumentRangesFormattingEdits()`
- These already support cancellation - timeout token will automatically cancel the format operation

## Summary of Changes

| Component | File | Lines | Change |
|-----------|------|-------|--------|
| Setting registration | files.contribution.ts | 388-413 | Add `editor.formatOnSaveTimeout` config |
| Save participant | saveParticipants.ts | 220-270 | Read timeout, create timeout-bounded token, pass to format functions |
| Format functions | format.ts | 107-310 | (No changes needed - already support cancellation) |
| Settings UI | settingsLayout.ts | 31-35 | (Optional: add to COMMONLY_USED_SETTINGS) |
| Tests | saveParticipant.test.ts | 149+ | Add timeout-related test cases |