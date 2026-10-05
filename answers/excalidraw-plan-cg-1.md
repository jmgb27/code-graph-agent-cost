I've planned this without editing any files. The plan uses a placeholder property called **`pinned`**; rename it to whatever you want.

The main finding is that most of the persistence and sync pipeline copies elements as whole objects, so it needs no changes. The only required data-layer changes are the element type, the defaults, the element factory, and restore. `locked` is an existing per-element boolean that already works on all five paths, so it's the template throughout, and opacity is the template for the panel control.

## 1. Data model (required)

| File | Change |
|---|---|
| `packages/element/src/types.ts:85` | Add `pinned: boolean;` next to `locked` in `_ExcalidrawElementBase` (lines 40–88). Make it required rather than optional: restore then guarantees the value is always there, and TypeScript flags every place that builds an element literal. |
| `packages/common/src/constants.ts:517-536` | Add `pinned: ExcalidrawElement["pinned"]` to the `DEFAULT_ELEMENT_PROPS` type and `pinned: false` to its value. |
| `packages/element/src/newElement.ts:61-86` | Add `\| "pinned"` to the optional keys of `ElementConstructorOpts` (after `"locked"` at :81). |
| `packages/element/src/newElement.ts:87-171` | In `_newElementBase`, add the default `pinned = DEFAULT_ELEMENT_PROPS.pinned` (like :108) and put `pinned` in the element literal (like :168). |

After this, `yarn test:typecheck` will list every hand-written element literal that is now missing the property. Known ones, all currently setting `locked: false`:
- `packages/element/src/convertToShape.ts:624,662,702`
- `packages/excalidraw/actions/actionBoundText.tsx:301`
- `packages/excalidraw/components/App.tsx:3017, 8864, 8924, 8977, 9024, 9208, 9231, 9403, 9454`
- `packages/excalidraw/components/App.drawshape.ts:205`, `App.clipboard.ts:442`, `App.toolDrag.ts:66`
- `packages/excalidraw/charts/charts.constants.ts:53`

## 2. `.excalidraw` import/export and local storage restore (required)

- **`packages/excalidraw/data/restore.ts:440-503` (`restoreElementWithProperties`)**: add `pinned: element.pinned ?? false,` next to `locked` at :492. This is the one change that makes the property survive loading:
  - Old files, old local storage and older collaborators' payloads don't have the field, so it gets normalised to `false` here.
  - It covers every load path, because they all go through `restoreElements` → `restoreElement` (:517):
    - `loadFromJSON`
    - local storage: `excalidraw-app/App.tsx:243`
    - URL imports: `excalidraw-app/App.tsx:269`
    - collaboration: `excalidraw-app/collab/Collab.tsx:771`
  - The object spread at :506 keeps unknown properties, so no other edit is needed in that function.

**No change needed** (whole elements are serialised, with no property allow-lists):
- `packages/excalidraw/data/json.ts:52` `serializeAsJSON` puts `elements` in the output unchanged.
- `excalidraw-app/data/LocalData.ts:73` `saveDataStateToLocalStorage` writes `JSON.stringify(getNonDeletedElements(elements))`.
- `excalidraw-app/data/localStorage.ts:37` `importFromLocalStorage` uses `JSON.parse`, then restore as above.

## 3. Collaboration sync and reconciliation (no change needed)

These work as long as the toggle changes the element with `newElementWith`/`mutateElement` (`packages/element/src/mutateElement.ts:149` / `:40`), which bump `version`/`versionNonce`:
- `excalidraw-app/collab/Collab.tsx:960` `broadcastElements` and `:971` `syncElements` send whole elements.
- `excalidraw-app/data/index.ts:58` `getSyncableElements` only filters out invisible elements.
- `excalidraw-app/data/firebase.ts:218-261` saves whole elements.
- `packages/excalidraw/data/reconcile.ts:23` `shouldDiscardRemoteElement` and `:73` `reconcileElements` choose between versions using only `version`/`versionNonce`.
- `excalidraw-app/collab/Collab.tsx:761` `_reconcileElements` restores remote elements first, so section 2 covers older peers.

## 4. Undo/redo (no change needed)

- `packages/element/src/delta.ts:1165` `ElementsDelta.calculate` diffs every property whenever `versionNonce` changes (:1234). `stripIrrelevantProps` (:2206) only removes `id` and `updated`.
- The visible-change check at `delta.ts:1857-1872` falls through to `default: return true`, so a change to `pinned` counts as a real, undoable change.
- The action must return `captureUpdate: CaptureUpdateAction.IMMEDIATELY`, as `actionChangeOpacity` does at `packages/excalidraw/actions/actionProperties.tsx:971`.
- Only edit `delta.ts` if you want the flag *excluded* from history.

## 5. Properties panel toggle (required)

1. **`packages/excalidraw/actions/actionProperties.tsx`**: add `actionTogglePinned = register<boolean>({ name: "togglePinned", label: "labels.pinned", trackEvent: false, perform, PanelComponent })`, modelled on `actionChangeOpacity` (:956-997).
   - `perform`: `changeProperty(elements, appState, el => newElementWith(el, { pinned: value }), true)` (helper at :193), returning `captureUpdate: CaptureUpdateAction.IMMEDIATELY`.
   - `PanelComponent`: `getFormValue(elements, app, el => el.pinned, true, false)` (helper at :229), rendering a checkbox (`packages/excalidraw/components/CheckboxItem.tsx`) that calls `updateData(!value)`. Handle a mixed selection (`null` = no common value).
2. **`packages/excalidraw/actions/types.ts:77`**: add `| "togglePinned"` to the `ActionName` union.
3. **`packages/excalidraw/actions/index.ts:18`**: export `actionTogglePinned`.
4. **`packages/excalidraw/components/shapeActionPredicates.ts`** (`getShapeActionPredicates`, returned object around :120-175): add `pinned: hasSelection` (or a per-type check).
5. **`packages/excalidraw/components/Actions.tsx`**: render `{predicates.pinned && renderAction("togglePinned")}` in each layout:
   - `SelectedShapeActions` (:129), next to opacity at :191
   - `CombinedShapeProperties` (:219), next to :298. It's used by `CompactShapeActions` (:605).
   - `MobileShapeActions` (:724)
6. **`packages/excalidraw/locales/en.json`**: add `"pinned": "…"` under `"labels"` (:2, next to `"opacity"` at :44).

**Optional: a default for new elements.** If new elements should pick up the last-used value (like `currentItemOpacity`):
- `packages/excalidraw/types.ts:456`: add `currentItemPinned`.
- `packages/excalidraw/appState.ts:37` and `:183`: add the default and its storage config.
- `App.tsx` element creation sites (:8854 etc.): pass `pinned: this.state.currentItemPinned`.
- The action's `perform`: also set `appState.currentItemPinned`.

## 6. Tests and fixtures

- `packages/excalidraw/tests/fixtures/elementFixture.ts:33`: add `pinned: false`.
- `packages/excalidraw/tests/helpers/api.ts:221` and `:308`: add an optional `pinned?` and `pinned: rest.pinned ?? false` in `API.createElement`.
- New tests to add:
  - Restore: a file without the field gives `false`; `true` is kept.
  - `serializeAsJSON` round-trip.
  - `reconcileElements`: the higher version's value wins.
  - Undo/redo after the toggle.
  - A panel toggle test.
- Run `yarn test:update`, since element snapshots will now include `"pinned": false`, then `yarn test:typecheck`.