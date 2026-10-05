## Plan: adding a per-element boolean property (called `myFlag` below)

**The main point:** `locked` is already a per-element boolean, and it survives every layer you listed. Storage, export, collab and undo/redo all pass or diff whole element objects, so the new property only needs code in about 5 places. Most layers need no change as long as the flag is **always changed through `newElementWith`/`mutateElement`**, because that bumps `version` and `versionNonce`.

### 1. Schema and defaults (must change)

| File:line | Change |
|---|---|
| `packages/element/src/types.ts:85` (`_ExcalidrawElementBase`) | Add `myFlag: boolean;` next to `locked`. |
| `packages/common/src/constants.ts:517-535` (`DEFAULT_ELEMENT_PROPS`) | Add `myFlag: ExcalidrawElement["myFlag"]` to the type and `myFlag: false` to the value. |
| `packages/element/src/newElement.ts:61-84` (`ElementConstructorOpts`) | Add `\| "myFlag"` to the `MarkOptional` list, as `locked` is at `:81`. Without this, every `newElement*` caller fails the type check. |
| `packages/element/src/newElement.ts:87-172` (`_newElementBase`) | Destructure `myFlag = DEFAULT_ELEMENT_PROPS.myFlag` (like `:108`) and emit it in the element literal (like `:168`). Every `newXElement` factory (sticky note `:230`, embeddable `:245`, iframe `:253`, frame `:263`, magicframe `:280`, text `:335`, plus the linear/image/freedraw ones) goes through this, so they need no change. |

### 2. Restore: `.excalidraw` import, local-storage load, collab receive (must change)
- `packages/excalidraw/data/restore.ts:430-493` (`restoreElementWithProperties`): add `myFlag: element.myFlag ?? false,` to `base`, next to `locked` at `:492`.
  - Old files and old clients' payloads lack the field, so this fills in the default.
  - It's also required by the type: `T extends Required<Omit<ExcalidrawElement,"customData">>` at `:431`.
  - All `restoreElement` branches (`:517-752`) call this, so you don't edit them one by one.
- `restoreElements` (`restore.ts:946`) is the path used by:
  - import: `loadFromBlob` → `restore`
  - app start from local storage: `excalidraw-app/App.tsx` `initializeScene` → `importFromLocalStorage` → `restore`
  - collab receive: `excalidraw-app/collab/Collab.tsx:771` in `_reconcileElements`

  So the one edit above covers all three.

### 3. Properties-panel toggle (must change)
1. **Action:** add `actionToggleMyFlag` in `packages/excalidraw/actions/actionProperties.tsx`, modeled on `actionChangeOpacity` (`:956-997`), using the `changeProperty` (`:193`) and `getFormValue` (`:229`) helpers.
   - `perform` should return `elements: changeProperty(elements, appState, el => newElementWith(el, { myFlag: value }), true)` with `captureUpdate: CaptureUpdateAction.IMMEDIATELY`. That setting is what makes it undoable.
   - `PanelComponent` should render a toggle. Use `components/Switch.tsx` or `CheckboxItem.tsx`, or a button like `actionTogglePolygon`'s panel (`actions/actionLinearEditor.tsx:105-170`).
   - Optionally add `currentItemMyFlag` to AppState if new elements should inherit it. Opacity does this with `currentItemOpacity`.
2. `packages/excalidraw/actions/types.ts:45` (`ActionName` union, near `"changeOpacity"` at `:77`): add `"toggleMyFlag"`.
3. `packages/excalidraw/actions/index.ts:18`: export the new action next to `actionChangeOpacity`.
4. `packages/excalidraw/components/shapeActionPredicates.ts:88` (`getShapeActionPredicates`): add a `myFlag:` predicate, for example `hasSelection` or `forToolOrSelection(...)`, next to `opacity` at `:157`.
5. `packages/excalidraw/components/Actions.tsx`: render `{predicates.myFlag && renderAction("toggleMyFlag")}` in each layout:
   - `SelectedShapeActions` (full panel), near `:191`
   - `CombinedShapeProperties` (compact/mobile popover, `:219`), near `:298`
   - `CompactShapeActions` `:605` / `MobileShapeActions` `:724`, if you want it outside the popover
6. `packages/excalidraw/locales/en.json:2` (`labels`, near `"opacity"` at `:44`): add the label string(s).
7. Optional: `packages/excalidraw/actions/actionStyles.ts:118-133` (paste styles). Add `myFlag: elementStylesToCopyFrom?.myFlag` if copy/paste styles should carry it.

### 4. Layers that need no code change (worth checking in tests)

| Concern | Where | Why nothing changes |
|---|---|---|
| Local storage save | `excalidraw-app/data/LocalData.ts:73-109` (`saveDataStateToLocalStorage`) | Saves `JSON.stringify(getNonDeletedElements(elements))`, so all element fields are kept. The `clearAppStateForLocalStorage` filter only applies to appState. |
| Local storage load | `excalidraw-app/data/localStorage.ts:37-74` (`importFromLocalStorage`) | Raw `JSON.parse`, then normalized by `restore` (section 2). |
| `.excalidraw` export | `packages/excalidraw/data/json.ts:52-75` (`serializeAsJSON`) | `elements` are written unfiltered. `ExportedDataState` (`data/types.ts:14`) is typed by `ExcalidrawElement`, so it picks up the field automatically. |
| Collab send | `excalidraw-app/collab/Collab.tsx:960-988` (`broadcastElements`/`queueBroadcastAllElements`) → `excalidraw-app/collab/Portal.tsx:142-175` (`broadcastScene`) | Sends whole elements. Elements are chosen by `version > broadcastedElementVersions` plus `isSyncableElement` (`excalidraw-app/data/index.ts:46`), so the toggle **must bump `version`**, which `newElementWith` does. Firebase save (`queueSaveToFirebase`) also stores whole elements. |
| Collab reconcile | `packages/excalidraw/data/reconcile.ts:23-44` (`shouldDiscardRemoteElement`), `:73-118` (`reconcileElements`) | Decides by `version`/`versionNonce` only, never by field. |
| Undo/redo capture | `packages/element/src/delta.ts:1165-1263` (`ElementsDelta.calculate`) → `Delta.calculate` `:112` / `getDifferences` `:430` | Shallow diff over all keys; only `id` and `updated` are stripped (`stripIrrelevantProps` `:2206`). |
| Undo/redo apply | `delta.ts:1732-1782` (`applyDelta`) | Sets every key of `delta.inserted` generically. |
| Undo "visible change" filter | `delta.ts:1809-1875` (`checkForVisibleDifference`) | An unknown key falls to `default: return true`, so a `myFlag`-only change counts as a real history entry and isn't skipped. Only add a case if the flag is metadata that should *not* create an undo step. |

### 5. Construction sites and tests
- Full element literals written by hand in tests need the field or the type check fails:
  - `packages/excalidraw/tests/fixtures/elementFixture.ts:33`
  - `packages/excalidraw/tests/helpers/api.ts:221` (opts type) and `:308`: add `myFlag: rest.myFlag ?? false`
- Call sites that pass `locked: false` into `newElement*` don't need to change once the field is optional in `ElementConstructorOpts`:
  - `packages/element/src/convertToShape.ts:624/662/702`
  - `components/App.tsx:3017, 8864…9454`
  - `App.drawshape.ts:205`
  - `App.clipboard.ts:442`
  - `App.toolDrag.ts:66`
  - `actions/actionBoundText.tsx:301`
  - `charts/charts.constants.ts:53`

  Check each one for whether it should *copy* the source element's `myFlag`, for example conversions and bound-text wrapping.
- Suggested tests:
  - `packages/excalidraw/tests/data/restore.test.ts`: the missing field defaults to `false`, and `true` round-trips.
  - `packages/excalidraw/tests/history.test.tsx`: toggle, undo, redo.
  - `excalidraw-app/tests/collab.test.tsx`: a remote toggle is reconciled.
  - A `serializeAsJSON` → `loadFromBlob` round-trip.
- Run `yarn test:typecheck` and `yarn test:update`. Element snapshots across many suites will gain `"myFlag": false`, which is expected.

### 6. Only if the flag changes rendering or behavior
If it affects drawing, add it to the renderer/shape path in `packages/element/src/renderElement.ts` and `shape.ts`. The shape cache is keyed by element version, so a version bump already invalidates it. If it gates interaction, follow the `locked` checks, e.g. `packages/element/src/typeChecks.ts:173`, `selection.ts:34`, `App.tsx:6035`.

This is a plan only; I didn't edit any files.