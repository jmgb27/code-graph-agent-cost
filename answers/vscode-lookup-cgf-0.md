Both settings are declared in one place and read in only one place: the text-file `FormatOnSaveParticipant`. All other hits are UI lists, links or docs. I didn't edit anything.

## Registration (configuration schema)
`src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413`, inside a `configurationRegistry.registerConfiguration({...editorConfigurationBaseNode, ...})` block:
- **`editor.formatOnSave`** (`:391-395`): a `boolean` with scope `LANGUAGE_OVERRIDABLE` and no explicit default, so it is effectively `false`. The description at `:393` says formatting doesn't happen when `files.autoSave` is `afterDelay`.
- **`editor.formatOnSaveMode`** (`:396-411`): a `string` enum of `file` / `modifications` / `modificationsIfAvailable`. The default is `'file'` (`:398`), with enum descriptions at `:404-406`. It is also `LANGUAGE_OVERRIDABLE` (`:410`), and its description (`:409`) says it only applies when `editor.formatOnSave` is on.

## Reads and behaviour
Everything happens in `FormatOnSaveParticipant.participate` in `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts` (class at `:216`):
- `:228-230`: it does nothing when the save reason is `SaveReason.AUTO`. That's why auto-save never formats.
- `:233`: it reads both settings with per-language/per-resource overrides (`overrideIdentifier: languageId, resource: uri`).
- `:243`: the progress message ("Running 'X' Formatter (configure)") links to `workbench.action.openSettings` with `'editor.formatOnSave'`.
- `:248-251`: **reads `editor.formatOnSave`** and returns early if it's off.
- `:254`: **reads `editor.formatOnSaveMode`**. Then it branches on the mode:
  - `'file'` (`:256-257`): formats the whole document with `formatDocumentWithSelectedProvider` (`src/vs/editor/contrib/format/browser/format.ts:290`), silently.
  - Otherwise (`:260`): it gets the changed ranges from source control with `getModifiedRanges` (`src/vs/workbench/contrib/format/browser/formatModified.ts:51`).
  - `'modificationsIfAvailable'` with no source control (`ranges === null`, `:261-263`): falls back to formatting the whole file.
  - Ranges found (`:265-267`): formats only those ranges with `formatDocumentRangesWithSelectedProvider` (`format.ts:107`).
  - `'modifications'` with no source control: nothing is formatted.
- `:458`: the participant is registered in `SaveParticipantsContribution.registerSaveParticipants` (`:455-461`) via `textFileService.files.addSaveParticipant`. It runs after `TrimWhitespace` and `CodeActionOnSave`, and before `FinalNewLine` and `TrimFinalNewLines`.
- `:465`: that contribution is registered at `LifecyclePhase.Restored`.

## Other references (UI and docs only)
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33`: listed in `COMMONLY_USED_SETTINGS`, the Settings editor's "Commonly Used" section.
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577`: listed in `getMostCommonlyUsedSettings()`.
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113`: walkthrough tip text mentioning `editor.formatOnSave`.

## Related but separate setting (notebooks)
Notebooks don't read `editor.formatOnSave`. They have their own setting, `notebook.formatOnSave.enabled`:
- The key is defined at `src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973` (`NotebookSetting.formatOnSave`).
- It is registered at `src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197`.
- It is read at `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80`, inside a notebook `FormatOnSaveParticipant` (`:61`) that also skips `SaveReason.AUTO` (`:76`). That participant is registered at `:661`.
- Nothing in the notebook code reads `formatOnSaveMode`: notebooks always format every cell (or run the format code action).

## Tests (for reference)
- `src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798-803` uses `editor.formatOnSave` to test language-scoped config updates.
- `src/vs/base/test/common/filters.test.ts:354` uses the string for fuzzy-match tests.

No other extension outside `extensions/copilot` contributes or reads either setting.