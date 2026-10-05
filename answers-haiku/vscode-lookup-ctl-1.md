Here are all the places where `editor.formatOnSave` and `editor.formatOnSaveMode` settings are registered, read, or change behavior:

**Registrations/Definitions:**
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:391-409` — Registers `editor.formatOnSave` and `editor.formatOnSaveMode` with descriptions
- `src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197-1198` — Registers notebook-specific `formatOnSave` setting

**Reading/Usage (Changed Behavior):**
- `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:243` — Creates command URI for `editor.formatOnSave`
- `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:248` — Reads `editor.formatOnSave` to determine if formatting should occur
- `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:254` — Reads `editor.formatOnSaveMode` to determine formatting scope ('file' | 'modifications' | 'modificationsIfAvailable')
- `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80` — Reads notebook's `formatOnSave` setting to enable/disable formatting

**Settings Layout/Search:**
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33` — Includes setting in layout for settings UI
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577` — References setting in preferences service

**Documentation Reference:**
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113` — Mentions `editor.formatOnSave` in welcome walkthrough documentation

**Setting Mapping:**
- `src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973` — Maps notebook-specific `formatOnSave` setting name