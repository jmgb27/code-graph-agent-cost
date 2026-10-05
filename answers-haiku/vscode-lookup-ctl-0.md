Here are all the locations where `editor.formatOnSave` and `editor.formatOnSaveMode` are registered, read, or change behavior (excluding extensions/copilot and test fixtures):

## Registration
- **src/vs/workbench/contrib/files/browser/files.contribution.ts:391** — registers `editor.formatOnSave`
- **src/vs/workbench/contrib/files/browser/files.contribution.ts:396** — registers `editor.formatOnSaveMode`

## Reading/Using Settings
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:248** — reads `editor.formatOnSave` to determine if formatting is enabled
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:254** — reads `editor.formatOnSaveMode` to determine formatting scope ('file' | 'modifications' | 'modificationsIfAvailable')
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:243** — references `editor.formatOnSave` in an error notification with a link to settings

## Settings UI/Layout
- **src/vs/workbench/services/preferences/browser/preferencesService.ts:577** — includes `editor.formatOnSave` in most commonly used settings list
- **src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33** — includes `editor.formatOnSave` in settings layout
- **src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113** — documents `editor.formatOnSave` in welcome walkthrough

## Related Notebook Settings
- **src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973** — maps `notebook.formatOnSave.enabled` (separate notebook-specific setting)
- **src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197** — registers `notebook.formatOnSave` (separate notebook-specific setting)
- **src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80** — reads `notebook.formatOnSave` (separate notebook-specific setting)