Both settings are registered in one place and read in one place. `FormatOnSaveParticipant` is the only code that changes behaviour based on them. Nothing outside `extensions/copilot` reads them, including the other built-in extensions.

## Registration
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413` registers both settings under `editorConfigurationBaseNode`:
  - `editor.formatOnSave` at `:391-395`: boolean with no explicit default, so it is off unless set. Scope is `LANGUAGE_OVERRIDABLE`. Its description says auto-saves with `afterDelay` don't format (`:393`).
  - `editor.formatOnSaveMode` at `:396-411`: enum `file` | `modifications` | `modificationsIfAvailable`, default `'file'` (`:398`). Scope is `LANGUAGE_OVERRIDABLE`. The enum descriptions are at `:404-408`.

## Read and behaviour (the only runtime consumer)
`src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`, class `FormatOnSaveParticipant` (`:216-271`):
- `:230-232`: returns early on `SaveReason.AUTO`, so auto-save never formats, whatever the settings say.
- `:235`: builds the config overrides from the language ID and resource URI, which is what makes per-language `[lang]` overrides work.
- `:243`: the progress message's "configure" link opens settings at `editor.formatOnSave`.
- `:248-251`: reads `editor.formatOnSave` and returns if it is falsy.
- `:254`: reads `editor.formatOnSaveMode`.
- `:256-257`: `file` formats the whole document with `formatDocumentWithSelectedProvider`.
- `:260`: any other mode first gets the SCM-modified ranges with `getModifiedRanges`.
- `:261-263`: `modificationsIfAvailable` with no SCM info (`ranges === null`) falls back to formatting the whole file.
- `:265-267`: if ranges exist, only those ranges are formatted with `formatDocumentRangesWithSelectedProvider`. Under plain `modifications` with no SCM, nothing is formatted.
- `:458`: the participant is registered with `textFileService.files.addSaveParticipant(...)`.

## UI surfacing (only lists the setting, no behaviour)
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577`: in `getMostCommonlyUsedSettings()`.
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33`: in `COMMONLY_USED_SETTINGS` for the Settings editor's "Commonly Used" section.
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113`: a tip in the walkthrough text.

## Related but separate setting
Notebooks have their own setting, `notebook.formatOnSave.enabled`, and don't use `editor.formatOnSave`:
- It is defined at `src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973`.
- It is registered at `src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197`.
- It is read at `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80`.

## Excluded as tests or config
- Tests: `src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798-803` and `src/vs/base/test/common/filters.test.ts:354`.
- The repo's own `.vscode/settings.json` (`:24`, `:27`, `:31`) and the selfhost extensions' `.vscode/settings.json` files.