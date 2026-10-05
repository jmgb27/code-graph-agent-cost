Both settings are registered in one place and read in one place. Only `FormatOnSaveParticipant` changes save behaviour; the other references are UI lists and docs.

### Registration
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`: both settings are registered in one `configurationRegistry.registerConfiguration` call under `editorConfigurationBaseNode`.
  - `:391`: `editor.formatOnSave` is a boolean with no explicit default, so it is off. Its scope is `LANGUAGE_OVERRIDABLE` (`:394`).
  - `:396`: `editor.formatOnSaveMode` is an enum of `file`, `modifications` and `modificationsIfAvailable`. It defaults to `file` (`:398`) and is also `LANGUAGE_OVERRIDABLE` (`:410`). Its description (`:409`) says it only applies when `editor.formatOnSave` is on.

### Where they are read and change behaviour
All of this is in `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`, in the `FormatOnSaveParticipant` class (`:216`):
- `:230`: saves with `SaveReason.AUTO` return early. So auto-save with `afterDelay` never formats, and the check happens before the setting is read.
- `:235`: per-language/per-resource overrides are built from the model's language ID and URI.
- `:248`: reads `editor.formatOnSave` with those overrides. If it is false, the method returns at `:249-251`.
- `:254`: reads `editor.formatOnSaveMode` with the same overrides. The branches are:
  - `:256-257`: `file` formats the whole document with `formatDocumentWithSelectedProvider`.
  - `:260`: the other two modes get the changed ranges from source control via `getModifiedRanges` (`src/vs/workbench/contrib/format/browser/formatModified.ts:51`).
  - `:261-263`: with `modificationsIfAvailable`, if there is no source control (`ranges === null`), it falls back to formatting the whole file.
  - `:265-267`: otherwise it formats only the modified ranges with `formatDocumentRangesWithSelectedProvider`.
- `:243`: the "Running '…' Formatter ([configure])" progress message links to the `editor.formatOnSave` setting.
- `:458`: the participant is registered as a text-file save participant, after `CodeActionOnSaveParticipant` and before the final-newline participants.

### Other references (no behaviour change)
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577`: in `getMostCommonlyUsedSettings()`.
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33`: in the Settings editor's `COMMONLY_USED_SETTINGS` list.
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113`: a walkthrough tip that mentions `editor.formatOnSave`.
- `.vscode/settings.json:24, :27, :31`, plus `.vscode/extensions/vscode-selfhost-test-provider/.vscode/settings.json:2` and `.vscode/extensions/vscode-selfhost-import-aid/.vscode/settings.json:2`: the repo's own workspace config turns the setting on.

### Separate setting, not a match
Notebooks use their own setting, `notebook.formatOnSave.enabled`, and never read `editor.formatOnSave`:
- `src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973`: the setting key is defined.
- `src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197`: it is registered.
- `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80`: it is read.

No extension outside `extensions/copilot` references either setting. Two tests mention it and are excluded: `src/vs/base/test/common/filters.test.ts:354` and `src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798-803`.