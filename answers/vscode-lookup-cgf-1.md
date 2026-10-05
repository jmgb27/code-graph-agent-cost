Both settings are registered in one place, and only one piece of runtime code reads them: the text-file `FormatOnSaveParticipant`. Other places mention `editor.formatOnSave` only as a string in lists, links and docs. Nothing outside the `.vscode/` settings files references `editor.formatOnSaveMode` except its registration and that one read.

## Registration
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:388` — `configurationRegistry.registerConfiguration({...editorConfigurationBaseNode, ...})`
  - `:391-395` — `'editor.formatOnSave'`: boolean, no default, `ConfigurationScope.LANGUAGE_OVERRIDABLE`.
  - `:396-411` — `'editor.formatOnSaveMode'`: string, default `'file'`, enum `file | modifications | modificationsIfAvailable` (descriptions at `:405-407`, description text at `:409`), `LANGUAGE_OVERRIDABLE`.

## Read / behaviour (the only runtime consumer)
`FormatOnSaveParticipant` in `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts:216`:
- `:230` — returns early when `context.reason === SaveReason.AUTO`. So auto-save never formats, whatever the setting says.
- `:235` — builds language/resource overrides (`overrideIdentifier: languageId, resource: uri`), so both settings are resolved per language and per resource.
- `:243` — the progress message's "configure" link opens settings at `editor.formatOnSave`.
- `:248-251` — **reads `editor.formatOnSave`**; if it isn't true, nothing happens.
- `:254` — **reads `editor.formatOnSaveMode`**, then branches on it:
  - `:256-257` `'file'` → `formatDocumentWithSelectedProvider` (whole document, `FormattingMode.Silent`).
  - `:260` otherwise → `getModifiedRanges` (changed ranges from source control).
  - `:261-263` `'modificationsIfAvailable'` with no source control (`ranges === null`) → falls back to whole-document formatting.
  - `:265-267` ranges available → `formatDocumentRangesWithSelectedProvider`.
  - With `'modifications'` and no source control, nothing is formatted.
- `:458` — the participant is registered through `textFileService.files.addSaveParticipant(...)` in `SaveParticipantsContribution`. That contribution is registered at `:465` (`LifecyclePhase.Restored`).

## Other references (string mentions only)
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33` — in `COMMONLY_USED_SETTINGS`, the "Commonly Used" group in the Settings editor.
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577` — in `getMostCommonlyUsedSettings()`.
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113` — tip text in the walkthrough.
- The repo's own workspace settings set `editor.formatOnSave: true`: `.vscode/settings.json:24,27,31`, `.vscode/extensions/vscode-selfhost-test-provider/.vscode/settings.json:2`, `.vscode/extensions/vscode-selfhost-import-aid/.vscode/settings.json:2`.

## Related, but a different setting
Notebooks use their own setting, `notebook.formatOnSave.enabled`, not `editor.formatOnSave`:
- `src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973` — `NotebookSetting.formatOnSave`.
- Registered at `src/vs/workbench/contrib/notebook/browser/notebook.contribution.ts:1197`.
- Read at `src/vs/workbench/contrib/notebook/browser/contrib/saveParticipants/saveParticipants.ts:80` in the notebook `FormatOnSaveParticipant` (`:61`). It also skips auto-save (`:76`), always formats every cell in full, and ignores `formatOnSaveMode`. It is registered at `:661`.

I left out tests as you asked. For completeness, `src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798-803` and `src/vs/base/test/common/filters.test.ts:354` use the `editor.formatOnSave` name as test data.