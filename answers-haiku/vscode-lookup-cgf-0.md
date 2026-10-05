## Summary: editor.formatOnSave and editor.formatOnSaveMode Settings

Found **8 locations** where these settings are registered, read, or change behavior (excluding extensions/copilot and test fixtures):

### Registration (Configuration Schema)
- **src/vs/workbench/contrib/files/browser/files.contribution.ts:391** — `editor.formatOnSave` registration
- **src/vs/workbench/contrib/files/browser/files.contribution.ts:396** — `editor.formatOnSaveMode` registration
- **src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197** — `notebook.formatOnSave.enabled` registration

### Configuration Definition
- **src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973** — `NotebookSetting.formatOnSave` constant (`'notebook.formatOnSave.enabled'`)

### Behavior Change (Reading Configuration)
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:248** — reads `editor.formatOnSave` to determine if formatting is enabled
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:254** — reads `editor.formatOnSaveMode` to determine formatting scope ('file' vs 'modifications')
- **src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80** — reads `notebook.formatOnSave.enabled` for notebook formatting

### UI/Settings Visibility
- **src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33** — `editor.formatOnSave` listed in `COMMONLY_USED_SETTINGS`
- **src/vs/workbench/services/preferences/browser/preferencesService.ts:577** — `editor.formatOnSave` in `getMostCommonlyUsedSettings()`

### Documentation
- **src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113** — reference in welcome walkthrough