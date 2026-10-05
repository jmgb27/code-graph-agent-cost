Perfect! Now I have the complete picture. Here are all the places where `editor.formatOnSave` and `editor.formatOnSaveMode` settings are registered, read, or change behavior:

## Setting Registration:

**src/vs/workbench/contrib/files/browser/files.contribution.ts:391-409**
- Registration of `editor.formatOnSave` (line 391-394)
- Registration of `editor.formatOnSaveMode` (line 396-409)

## Reading/Using Settings:

**src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts**
- Line 248: Reads `editor.formatOnSave` configuration value
- Line 254: Reads `editor.formatOnSaveMode` configuration value
- Line 243: References setting in help link

**src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80**
- Reads notebook version `NotebookSetting.formatOnSave`

## Related Notebook Settings:

**src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973**
- Defines `notebook.formatOnSave.enabled` setting name

**src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197-1198**
- Registers notebook `formatOnSave` setting

## UI Display:

**src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33**
- Included in "Commonly Used" settings list

**src/vs/workbench/services/preferences/browser/preferencesService.ts:577**
- Reference in preferences service

## Documentation:

**src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113**
- Mentioned in welcome walkthrough as example of configurable setting

## Tests:

**src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798, 802-803**
- Tests for `formatOnSave` configuration handling