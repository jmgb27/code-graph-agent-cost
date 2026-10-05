# Plan: a per-element boolean property

I'll call it `highlighted` here; use your own name. The existing per-element boolean `locked` follows the same path, so each step below copies what `locked` does.

The main finding is that most of the requested paths need no code change. Local storage, `.excalidraw` export, collab broadcast, reconciliation and undo/redo all handle elements as whole objects and key off `version`/`versionNonce`. There's no per-key allowlist anywhere. The only real work is:
1. Adding the field to the type.
2. Giving it a default when elements are created and restored.
3. Changing it only through the version-bumping helpers.
4. Adding the panel action.

## 1. Type and default (required)

| File:line | Change |
|---|---|
| `packages/element/src/types.ts:85` (`_ExcalidrawElementBase`) | Add `highlighted: boolean;` next to `locked`. |
| `packages/common/src/constants.ts:517-535` (`DEFAULT_ELEMENT_PROPS`) | Add `highlighted: ExcalidrawElement["highlighted"]` to the type and `highlighted: false` to the value. |
| `packages/element/src/newElement.ts:61-85` (`ElementConstructorOpts`) | Add `\| "highlighted"` to the `MarkOptional` list, so callers can leave it out. |
| `packages/element/src/newElement.ts:87-172` (`_newElementBase`) | Destructure `highlighted = DEFAULT_ELEMENT_PROPS.highlighted` (like line 108) and add it to the element literal (like line 168). Every `newXElement` factory (sticky note at `:230`, embeddable at `:245`, etc.) goes through this function. |

`duplicateElement` (`packages/element/src/duplicate.ts:103`) deep-copies the element, so duplicates keep the value without any change.

## 2. Restore: the key step for `.excalidraw` import, local storage and collab

In `packages/excalidraw/data/restore.ts:430-514`, `restoreElementWithProperties` needs `highlighted: element.highlighted ?? false,` next to `locked` at line 492.

- This is where old files, old localStorage data and elements from older collab clients get the default.
- The `Required<Omit<ExcalidrawElement,…>>` constraint on `base` makes `yarn test:typecheck` fail until you add it.
- Every entry point runs through `restoreElement` (`:517`) → `restoreElements`:
  - Local storage load: `excalidraw-app/App.tsx:243`
  - File open/import: `excalidraw-app/App.tsx:269` and `:586`, plus `restore()` in `packages/excalidraw/data/restore.ts`
  - Incoming collab elements: `excalidraw-app/collab/Collab.tsx:771` (`_reconcileElements`)
  - Firebase room snapshot: `excalidraw-app/data/firebase.ts:219`
  - Library items: `restoreLibraryItems` in the same file

## 3. Serialization: no change needed (verified)

- **Local storage:** `saveDataStateToLocalStorage` (`excalidraw-app/data/LocalData.ts:73-109`) runs `JSON.stringify(getNonDeletedElements(elements))` on whole elements.
- **`.excalidraw` export:** `serializeAsJSON` (`packages/excalidraw/data/json.ts:52-75`) writes `elements` unchanged, and `saveAsJSON` (`:77`) calls it.
- **Collab send:** `Portal.broadcastScene` (`excalidraw-app/collab/Portal.tsx:142-180`) sends any element whose `version` is higher than the last broadcast version (`:156`). `getSyncableElements` and `isSyncableElement` (`excalidraw-app/data/index.ts:46-63`) filter only on deletion and size.
- **Reconciliation:** `reconcileElements` and `shouldDiscardRemoteElement` (`packages/excalidraw/data/reconcile.ts:23-113`) compare only `version` and `versionNonce`.

**Constraint:** every toggle must go through `newElementWith` or `mutateElement`, which bump `version` and `versionNonce`. Assigning the field directly won't sync to other clients and won't win reconciliation.

## 4. Undo/redo: no change needed (verified)

- `Delta.calculate` (`packages/element/src/delta.ts:112-143`) diffs every top-level key of the element.
- `ElementsDelta.stripIrrelevantProps` (`:2206`) drops only `id` and `updated`.
- `ElementsDelta.postProcess` (`:2165`) special-cases only `boundElements` and `points`.
- `ElementsDelta.applyDelta` (`:1732-1781`) applies the partial through `newElementWith`.

A top-level boolean is therefore recorded and reverted automatically, provided the action returns `captureUpdate: CaptureUpdateAction.IMMEDIATELY`.

## 5. Properties-panel toggle

| File:line | Change |
|---|---|
| `packages/excalidraw/actions/actionProperties.tsx` (new, modelled on `actionChangeOpacity` at `:956-997`) | Add `export const actionToggleHighlighted = register<boolean>({ name: "toggleHighlighted", label: "labels.highlighted", trackEvent: false, perform })`. `perform` uses `changeProperty(elements, appState, el => newElementWith(el, { highlighted: value }), true)` (`changeProperty` is at `:193`) and returns `captureUpdate: CaptureUpdateAction.IMMEDIATELY`. The `PanelComponent` reads the shared value with `getFormValue(elements, app, el => el.highlighted, true, …)` (`:229`) and renders `<CheckboxItem checked={…} onChange={updateData}>` (`packages/excalidraw/components/CheckboxItem.tsx:8`) or `Switch` (`components/Switch.tsx:13`). |
| `packages/excalidraw/actions/types.ts:66-108` (`ActionName` union) | Add `\| "toggleHighlighted"`. |
| `packages/excalidraw/actions/index.ts:10-23` | Re-export `actionToggleHighlighted` from `./actionProperties`. |
| `packages/excalidraw/components/shapeActionPredicates.ts:88` (`getShapeActionPredicates`, near `opacity` at `:157`) | Add a `highlighted` predicate saying when the control shows (e.g. `hasSelection`). |
| `packages/excalidraw/components/Actions.tsx:191` (`SelectedShapeActions`, full desktop panel) | Add `{predicates.highlighted && renderAction("toggleHighlighted")}`. |
| `packages/excalidraw/components/Actions.tsx:284-299` (compact properties popover) | Add the same line after `changeOpacity`. |
| `packages/excalidraw/components/Actions.tsx:619` / `:738` (other compact and mobile layouts that call `getShapeActionPredicates`) | Add the same line if the toggle should appear there too. |
| `packages/excalidraw/locales/en.json` (`"labels"` block, `:2`, near `"opacity"` at `:44`) | Add `"highlighted": "…"`. |

## 6. Optional and follow-on

- **New shapes inherit the last value:** add `currentItemHighlighted` to `AppState` (`packages/excalidraw/types.ts:456`), `getDefaultAppState` (`packages/excalidraw/appState.ts:37`) and the storage-config map (`appState.ts:183`, `{ browser: true, export: false, server: false }`). Then pass it wherever `currentItemOpacity` is passed at creation: `App.toolDrag.ts:64`, `App.drawshape.ts:246`, `App.text.ts:743`, `App.clipboard.ts:436`, `App.bucketFill.ts:146` and `:260`.
- **Copy/paste styles:** add it to the `newElementWith` call in `packages/excalidraw/actions/actionStyles.ts:118-133`, if it counts as a style.
- **Programmatic API:** `ExcalidrawElementSkeleton` / `convertToExcalidrawElements` (`packages/element/src/transform.ts:215` and `:572`) already accept base props through `ElementConstructorOpts`, so no change is needed.
- **Hand-built element objects:** several places build elements as full object literals, for example `charts/charts.constants.ts:53`, `tests/fixtures/elementFixture.ts:33` and `tests/helpers/api.ts:308`. Where one is typed as a full element, `yarn test:typecheck` will flag the missing field; add `highlighted: false`.
- **Rendering or behaviour:** whatever the flag should actually do on the canvas goes in `renderer/` or `element/` code. That depends on what the flag means, so I haven't planned it.

## 7. Tests

After the change, run `yarn test:typecheck`, then `yarn test:update`. Nearly every element snapshot will gain `"highlighted": false`. Add targeted tests for:
- Restore defaulting a missing key: `packages/excalidraw/tests/data/restore.test.ts`
- Toggle, then undo and redo: `packages/excalidraw/tests/history.test.tsx`
- A newer `version` carrying the flag winning reconciliation: `packages/excalidraw/tests/data/reconcile.test.ts`