Perfect! Now I have the complete picture. Here are all the places where `editor.formatOnSave` and `editor.formatOnSaveMode` settings are registered, read, or change behavior:

## Setting Registration

- **src/vs/workbench/contrib/files/browser/files.contribution.ts:391** — `editor.formatOnSave` registered (boolean type, language overridable)
- **src/vs/workbench/contrib/files/browser/files.contribution.ts:396** — `editor.formatOnSaveMode` registered (string enum: 'file', 'modifications', 'modificationsIfAvailable', default: 'file', language overridable)

## Setting Read/Usage

- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:248** — Reads `editor.formatOnSave` boolean value to check if formatting is enabled
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:254** — Reads `editor.formatOnSaveMode` to determine formatting scope

## Behavior Changes

- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:256-268** — FormatOnSaveParticipant implements behavior:
  - Line 256-257: If mode is 'file', formats entire document
  - Line 259-268: If mode is 'modifications' or 'modificationsIfAvailable', formats only modified ranges (with fallback to full file if SCM unavailable in 'modificationsIfAvailable' mode)

## UI References

- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:243** — Creates link to settings for `editor.formatOnSave` in formatter progress message
- **src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33** — Listed in `COMMONLY_USED_SETTINGS` array for settings UI
- **src/vs/workbench/services/preferences/browser/preferencesService.ts:577** — Listed in `getMostCommonlyUsedSettings()` method
- **src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113** — Mentioned in welcome walkthrough documentation