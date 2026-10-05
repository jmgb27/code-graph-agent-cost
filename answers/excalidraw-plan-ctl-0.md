I haven't edited anything. The property name `flag: boolean` below is a placeholder. The model to copy is `locked`, the existing per-element boolean: it's typed, defaulted, restored and diffed the same way. Most layers copy every element property automatically, so you only change code in five places. The rest you just need to check.

## Must change

### 1. Element type (the compiler then points to most other edits)
- **`packages/element/src/types.ts:85`**: add `flag: boolean;` to `_ExcalidrawElementBase` next to `locked`. Make it required, not optional. Two type checks then fail until the property is set:
  - `_newElementBase`, whose object literal is typed as `ExcalidrawGenericElement` (`newElement.ts:137`).
  - `restoreElementWithProperties`, whose `base: Pick<T, keyof ExcalidrawElement>` is built from `Required<...>` (`restore.ts:431`, `restore.ts:449`).

### 2. Default and constructor
- **`packages/common/src/constants.ts:517-534`** `DEFAULT_ELEMENT_PROPS`: add `flag: ExcalidrawElement["flag"]` to the type and `flag: false` to the value.
- **`packages/element/src/newElement.ts:61-85`** `ElementConstructorOpts`: add `| "flag"` to the `MarkOptional` list so callers don't have to pass it.
- **`packages/element/src/newElement.ts:87-172`** `_newElementBase`: destructure `flag = DEFAULT_ELEMENT_PROPS.flag` (next to `locked` at :108) and write `flag` into the object (next to :168). Every element factory (`newElement`, `newTextElement`, `newLinearElement`, `newImageElement`, frames, sticky notes, and so on, at :179–683) goes through this function. `transform.ts` (`convertToExcalidrawElements`, line 89) uses `ElementConstructorOpts`, so it picks the property up automatically.

### 3. Restore (covers loading from local storage, `.excalidraw` import, collab receive, Firebase and library)
- **`packages/excalidraw/data/restore.ts:449-493`** `restoreElementWithProperties`: add `flag: element.flag ?? false,` next to `locked` at :492. Old files and older clients' payloads don't have the key, so this is what makes them load safely. Every per-type branch of `restoreElement` (:517) and `restoreElements` (:946) goes through this `base`.

### 4. Action (the toggle)
- **`packages/excalidraw/actions/actionProperties.tsx`**: add `export const actionToggleFlag = register<boolean>({...})`, modelled on `actionChangeRoundness` (:1748-1828).
  - `perform`: `changeProperty(elements, appState, el => newElementWith(el, { flag: value }))` (helper at :193), returning `captureUpdate: CaptureUpdateAction.IMMEDIATELY` (see :1776).
    - `IMMEDIATELY` is what records an undo/redo entry.
    - `newElementWith` bumps `version` and `versionNonce`, which collab needs to broadcast and reconcile the change.
  - `PanelComponent`: a checkbox or toggle button whose value comes from `getFormValue(elements, app, el => el.flag, el => true, hasSel => hasSel ? null : false)` (:229).
  - For a single-button toggle, `actionTogglePolygon` (`actions/actionLinearEditor.tsx:106-200`) is the pattern: work out the next state across the selection and render a button.
- **`packages/excalidraw/actions/types.ts:108-145`**: add `| "toggleFlag"` to the `ActionName` union.
- **`packages/excalidraw/actions/index.ts:10-24`**: export `actionToggleFlag`. Registration is automatic: `register()` appends to `actions` (`actions/register.ts:5-15`), and `App.tsx:912` calls `this.actionManager.registerAll(actions)`. The module just has to be imported, which `actionProperties.tsx` already is.

### 5. Properties panel
- **`packages/excalidraw/components/shapeActionPredicates.ts:117-188`** `getShapeActionPredicates`: add a visibility flag, for example `flag: hasSelection` or `forToolOrSelection(...)` (:98) if it should also show while a drawing tool is active.
- **`packages/excalidraw/components/Actions.tsx`**: render `{predicates.flag && renderAction("toggleFlag")}` in all three layouts:
  - `SelectedShapeActions`, the full desktop panel (:160-199), for example after `changeOpacity` at :191.
  - `CompactShapeActions` (:605), inside the combined properties popover (:283-298).
  - `MobileShapeActions` (:724).
- **`packages/excalidraw/locales/en.json`** (near `"edges"`/`"sharp"` at :46): add a `labels.flag` string.

## Check, but no change expected

| Concern | Where | Why nothing to change |
|---|---|---|
| Local storage save | `excalidraw-app/data/LocalData.ts:73-96` `saveDataStateToLocalStorage` | Saves `JSON.stringify(getNonDeletedElements(elements))` with no element filtering. |
| Local storage load | `excalidraw-app/data/localStorage.ts:37-74` `importFromLocalStorage`, then `excalidraw-app/App.tsx:243` `restoreElements` | Parses raw JSON, then uses step 3. |
| `.excalidraw` export | `packages/excalidraw/data/json.ts:52-75` `serializeAsJSON` / `saveAsJSON` (:77) | Elements are written unchanged. Only the app state is cleaned. |
| `.excalidraw` import | `json.ts:102` `loadFromJSON`, then `data/blob.ts:161` `restoreElements` in `loadFromBlob` (:198) | Uses step 3. |
| Collab send | `excalidraw-app/collab/Portal.tsx:142-183` `broadcastScene` | Sends whole element objects when `element.version` has increased, so step 4 must use `newElementWith`. |
| Collab receive | `excalidraw-app/collab/Collab.tsx:761-782` `_reconcileElements` | Calls `restoreElements` (step 3), then `reconcileElements`. |
| Reconciliation | `packages/excalidraw/data/reconcile.ts:23-39` `shouldDiscardRemoteElement`, `:73` `reconcileElements` | Whole-element last-writer-wins on `version`/`versionNonce`. It never compares individual properties. |
| Firebase room persistence | `excalidraw-app/data/firebase.ts:187` `saveToFirebase`, `:249` `loadFromFirebase` | Uses `restoreElements` and `getSyncableElements` (`excalidraw-app/data/index.ts:46-63`), which filter only on deletion and size. |
| Shareable link | `excalidraw-app/data/index.ts:202` `importFromBackend`, `:248` `exportToBackend` | Same serialize and restore path. |
| Undo/redo diffing | `packages/element/src/delta.ts` `ElementsDelta` (stripping at :2206-2212, `postProcess` at :2165) | `Delta` diffs every key except `id` and `updated`, and primitive values need no post-processing. Applying the delta goes through `newElementWith` (:1781). |
| Undo "visible change" filter | `delta.ts:1809-1875` `checkForVisibleDifference` | The `default: return true` at :1871 already treats a toggle as visible, so undo stops on it. Only add `case "flag": return false` (next to `created` at :1864) if the flag has no visible effect and should be skipped. |
| Update typing | `packages/element/src/mutateElement.ts:27-30` `ElementUpdate` | `flag` should stay mutable, so don't add it to the `Omit`. That list is only for lifetime metadata like `created`. |
| Duplicate | `packages/element/src/duplicate.ts` (~:117) | Duplicates copy all properties with a spread, so the flag is carried over. Only reset it there if copies shouldn't inherit it, the way `created` is reset. |

## Tests and fixtures
- **`packages/excalidraw/tests/helpers/api.ts`**: `API.createElement` has an options type near :191 and builds the element near :309. Add `flag?` and default it, like `created`.
- **`packages/excalidraw/tests/fixtures/elementFixture.ts:31`**: add `flag: false`.
- Snapshots: every serialized element gains `"flag": false`, so run `yarn test:update`. That includes `packages/element/src/__tests__/__snapshots__/transform.test.ts.snap` and the history, restore and collab snapshots.
- New tests to add:
  - `restore` defaults a missing `flag` to `false`, and keeps `true`.
  - Toggle → undo → redo, in `tests/history.test.tsx`.
  - `reconcileElements` keeps the higher-version remote `flag`.
  - `serializeAsJSON` followed by `loadFromBlob` keeps the value.
- Then run `yarn test:typecheck`. Anything this list missed will show up as a type error from the required `flag` field.

**Optional:**
- A sticky "current item" default, like `currentItemRoundness`, set in `AppState` and passed into `newElement` from `App.tsx`.
- A `CommandPalette.tsx` entry (see :338 for `togglePolygon`).
- A `CHANGELOG.md` line.
- Documenting the field in `dev-docs`.