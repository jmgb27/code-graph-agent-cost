Based on my exploration, here are all the places where `editor.formatOnSave` and `editor.formatOnSaveMode` settings are registered, read, or referenced (excluding test fixtures and extensions/copilot):

## Registration
- **src/vs/workbench/contrib/files/browser/files.contribution.ts:391-411**
  - `editor.formatOnSave` registered at line 391
  - `editor.formatOnSaveMode` registered at line 396

## Reading/Changing Behavior
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:248** — `editor.formatOnSave` setting is read to determine if formatting on save is enabled
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:254** — `editor.formatOnSaveMode` setting is read to determine the formatting mode (file/modifications/modificationsIfAvailable)
- **src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:243** — `editor.formatOnSave` is referenced in a progress message command URI

## UI References
- **src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33** — `editor.formatOnSave` listed in commonly used settings
- **src/vs/workbench/services/preferences/browser/preferencesService.ts:577** — `editor.formatOnSave` listed in most commonly used settings
- **src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113** — `editor.formatOnSave` mentioned in walkthrough documentation