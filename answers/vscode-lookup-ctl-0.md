I found one place that registers both settings and one place that reads them to control saving. The other hits only mention `editor.formatOnSave` in the UI.

## Registration
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:391-395` registers `editor.formatOnSave`. It's a boolean with no explicit default and can be overridden per language.
- `src/vs/workbench/contrib/files/browser/files.contribution.ts:396-411` registers `editor.formatOnSaveMode`. It's a string enum (`file` | `modifications` | `modificationsIfAvailable`), defaults to `file`, and can be overridden per language. Its description (line 409) says it only applies when `editor.formatOnSave` is on.

## Reads and behaviour (the only place either setting is read)
In `src/vs/workbench/contrib/codeEditor/browser/saveParticipants.ts`, the class `FormatOnSaveParticipant` (line 216) handles format-on-save:
- **:230** Auto-saves (`SaveReason.AUTO`) return early, so they never format. This is the "`afterDelay` only formats on explicit save" behaviour.
- **:235** Both settings are read with the file's language and URI, so language-specific and resource-specific overrides apply.
- **:248-251** Reads `editor.formatOnSave` and stops if it's off.
- **:254** Reads `editor.formatOnSaveMode`.
- **:256-257** `file` formats the whole document with `formatDocumentWithSelectedProvider`.
- **:260** Any other mode asks source control for the changed ranges via `getModifiedRanges`, defined at `src/vs/workbench/contrib/format/browser/formatModified.ts:51`.
- **:261-263** `modificationsIfAvailable`: if there's no source control (`ranges === null`), it falls back to formatting the whole file.
- **:265-267** If changed ranges exist, it formats only those with `formatDocumentRangesWithSelectedProvider`. With `modifications` and no source control, nothing is formatted.
- **:243** The progress message includes a "configure" link that opens the `editor.formatOnSave` setting.
- **:458** Registers this participant as a text-file save participant.

## Other references (UI and docs only, no effect on behaviour)
- `src/vs/workbench/services/preferences/browser/preferencesService.ts:577`: listed in `getMostCommonlyUsedSettings()`.
- `src/vs/workbench/contrib/preferences/browser/settingsLayout.ts:33`: listed in `COMMONLY_USED_SETTINGS`, the Settings editor's "Commonly Used" section.
- `src/vs/workbench/contrib/welcomeWalkthrough/browser/editor/vs_code_editor_walkthrough.ts:113`: tip text mentioning the setting.
- `.vscode/settings.json:24,27,31` and `.vscode/extensions/vscode-selfhost-{test-provider,import-aid}/.vscode/settings.json:2`: the repo's own workspace settings, which turn it on.

## Excluded as tests
- `src/vs/base/test/common/filters.test.ts:354` (the setting name used as a fuzzy-match test string).
- `src/vs/workbench/api/test/browser/extHostConfiguration.test.ts:798-803` (an extension-host config update test).

**Separate setting:** notebooks use their own setting, `notebook.formatOnSave.enabled` (`src/vs/workbench/contrib/notebook/common/notebookCommon.ts:973`, registered at `notebook.contribution.ts:1197`, read at `notebook/browser/contrib/saveParticipants/saveParticipants.ts:80`). It does not read `editor.formatOnSave` or `editor.formatOnSaveMode`.