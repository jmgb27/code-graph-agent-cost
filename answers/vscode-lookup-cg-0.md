Both settings are registered in one place and read in one place: `FormatOnSaveParticipant`. I found no other code in `src/` or in the non-copilot extensions that reads them.

### Registration
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:388-413` registers both settings in one `configurationRegistry.registerConfiguration` call, using `editorConfigurationBaseNode`.
  - **`editor.formatOnSave`** is at `:391-395`. It is a boolean with no explicit default and scope `LANGUAGE_OVERRIDABLE`. Its description (`:393`) says it doesn't apply when `files.autoSave` is `afterDelay`.
  - **`editor.formatOnSaveMode`** is at `:396-411`. It is a string enum: `file` (the default), `modifications` or `modificationsIfAvailable`. Its scope is `LANGUAGE_OVERRIDABLE`, and its description (`:409`) says it only applies when `editor.formatOnSave` is enabled.

### Reads and behaviour
All of this is in `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`:
- `:216` defines the `FormatOnSaveParticipant` class, and `:226` is its `participate()` method.
- `:230-232`: saves with `SaveReason.AUTO` return before either setting is read. This is how the "afterDelay" rule is enforced.
- `:235`: both settings are read with language and resource overrides (`overrideIdentifier: languageId`, `resource: uri`). That is why `[typescript]` blocks and similar per-language settings take effect.
- `:243`: the progress message's "configure" link opens the settings UI at `editor.formatOnSave`.
- `:248-251` reads `editor.formatOnSave`. If it is false or unset, the method returns without formatting.
- `:254` reads `editor.formatOnSaveMode`. What happens next depends on the value:
  - **`file`** (`:256-257`): the whole document is formatted with `formatDocumentWithSelectedProvider`.
  - **Anything else** (`:260`): the changed ranges are fetched from source control with `getModifiedRanges`. Then:
    - With `modificationsIfAvailable` and no source control result (`ranges === null`), it falls back to formatting the whole file (`:261-263`).
    - If ranges are found, only those ranges are formatted with `formatDocumentRangesWithSelectedProvider` (`:265-267`).
    - With `modifications` and no source control, nothing is formatted.
- `:458` adds the participant with `textFileService.files.addSaveParticipant(...)`. It runs after `TrimWhitespace` and `CodeActionOnSave`, and before `FinalNewLine` and `TrimFinalNewLines` (`:456-460`).

### Other references (setting name only, no effect on behaviour)
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33` lists `editor.formatOnSave` in `COMMONLY_USED_SETTINGS` in the Settings editor.
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577` lists `editor.formatOnSave` in `getMostCommonlyUsedSettings()`.
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113` mentions it in the walkthrough tip text.
- `.vscode/settings.json:24,27,31` and `.vscode/extensions/vscode-selfhost-{test-provider,import-aid}/.vscode/settings.json:2` set it to `true` for this repo's own workspace. These are config files, not code.

### Related but separate
Notebooks have their own setting, `notebook.formatOnSave.enabled`, which the editor settings don't control:
- It is defined as `NotebookSetting.formatOnSave` at `src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973`.
- It is registered at `notebook/browser/notebook.contribution.ts:1197`.
- It is read at `notebook/browser/contrib/saveParticipants/saveParticipants.ts:80`.

I left out tests as you asked: `src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798-803` and `src/vs/base/test/common/filters.test.ts:354`.