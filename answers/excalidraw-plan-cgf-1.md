# Plan: adding a per-element boolean (called `pinned` below)

I haven't edited anything. The closest existing example is `locked`, a per-element boolean that already goes through every layer you listed, so the plan copies how `locked` is handled. Most of those layers treat the element as a whole object and copy every property. So the new field needs code in only a few places: the type, its defaults, restore, and the UI. The other layers need no code, as long as every change goes through `newElementWith` or `mutateElement`, which bump `version` and `versionNonce`.

## 1. Data model (required)

| File:line | Change |
|---|---|
| `packages/element/src/types.ts:40-87` (`_ExcalidrawElementBase`) | Add `pinned: boolean;` next to `locked: boolean;` at line 85. Every element type picks it up from here. |
| `packages/common/src/constants.ts:517-535` (`DEFAULT_ELEMENT_PROPS`) | Add `pinned: ExcalidrawElement["pinned"]` to the type (around line 525) and `pinned: false` to the value (around line 534). |
| `packages/element/src/newElement.ts:61-85` (`ElementConstructorOpts`) | Add `\| "pinned"` to the optional keys, next to `"locked"` at line 81. |
| `packages/element/src/newElement.ts:87-172` (`_newElementBase`) | Destructure `pinned = DEFAULT_ELEMENT_PROPS.pinned` (around line 108) and write it into the element literal (around line 168). This covers `newElement`, `newStickyNoteElement`, `newEmbeddableElement`, `newIframeElement`, and the other constructors that call it. |

## 2. Restore (.excalidraw import, localStorage load, collab input)

| File:line | Change |
|---|---|
| `packages/excalidraw/data/restore.ts:430-515` (`restoreElementWithProperties`) | Add `pinned: element.pinned ?? false,` to the `base` object next to `locked` at line 492. This is required: the generic `T` is `Required<Omit<ExcalidrawElement,"customData">>`, so it won't typecheck without it. Older files and older peers get the default here. |

`restoreElement` (`restore.ts:517`) and `restoreElements` (`restore.ts:946`) both go through that function, so they need no change. They're the entry points for:
- **Local storage load:** `excalidraw-app/App.tsx:243` (`restoreElements(localDataState?.elements, …)`)
- **File import and share links:** `excalidraw-app/App.tsx:269`, `:586`
- **Collab input:** `excalidraw-app/collab/Collab.tsx:771` (inside `_reconcileElements`), and `excalidraw-app/data/firebase.ts:219`, `:241`, `:262`

## 3. Persistence and export (no code change, verify only)

These paths serialise the whole element, so the new field is included automatically:
- **Local storage save:** `excalidraw-app/data/LocalData.ts:73-109` (`saveDataStateToLocalStorage`) runs `JSON.stringify(getNonDeletedElements(elements))` at line 92.
- **.excalidraw export:** `packages/excalidraw/data/json.ts:52-75` (`serializeAsJSON`) passes `elements` through unchanged. The shareable-link / database save at `excalidraw-app/data/index.ts:257` uses the same function.
- **Types:** `packages/excalidraw/data/types.ts:14-21` (`ExportedDataState`) and `:35-50` (`ImportedDataState`) both use `ExcalidrawElement`, so they update automatically.

## 4. Collaboration sync and reconciliation (no code change, one rule)

- **Broadcast:** `excalidraw-app/collab/Collab.tsx:960` (`broadcastElements`) and `:971` (`syncElements`) → `excalidraw-app/collab/Portal.tsx:91` (`JSON.stringify(data)`), filtered by `isSyncableElement` at `excalidraw-app/data/index.ts:46`. Whole elements are sent.
- **Firebase:** `excalidraw-app/data/firebase.ts:97` (`JSON.stringify(elements)`), reconciled around line 222.
- **Reconcile:** `packages/excalidraw/data/reconcile.ts:23-44` (`shouldDiscardRemoteElement`) and `:73-118` (`reconcileElements`) decide which copy wins by `version` and `versionNonce` alone.
- **The rule:** every write to `pinned` must go through `newElementWith` or `mutateElement` so the version is bumped. A direct write won't be sent to peers and will lose reconciliation.

## 5. Undo/redo (no code change)

- `packages/element/src/delta.ts:112-143` (`Delta.calculate`) compares every top-level key, so a change to `pinned` is recorded automatically. `stripIrrelevantProps` (`delta.ts:2206`) only removes `id` and `updated`.
- `delta.ts:1809-1875` (`checkForVisibleDifference`): its `switch` returns `true` for any key it doesn't list, so an undo step that only changes `pinned` is still treated as a real change and not skipped. Don't add `pinned` to the metadata cases at lines 1860-1865, or pinned-only steps would be skipped as invisible.
- `packages/element/src/store.ts:691` (`getChangedElements`) detects changes by object identity, which `newElementWith` provides.
- **The rule:** the toggle action must return `captureUpdate: CaptureUpdateAction.IMMEDIATELY`, as `actionChangeOpacity` does at `actionProperties.tsx:972`.

## 6. Properties-panel toggle

| File:line | Change |
|---|---|
| `packages/excalidraw/actions/actionProperties.tsx` | Add `actionTogglePinned = register<boolean>({ name: "togglePinned", … })`, modelled on `actionChangeOpacity` (lines 956-975). `perform` should call `changeProperty(elements, appState, el => newElementWith(el, { pinned: value }), true)` (the helper is at lines 193-227) and return `CaptureUpdateAction.IMMEDIATELY`. `PanelComponent` should read the current value with `getFormValue` (line 229) and render a checkbox or `ButtonIcon` that calls `updateData(!value)`. |
| `packages/excalidraw/actions/types.ts:45` (`ActionName`) | Add `\| "togglePinned"`. |
| `packages/excalidraw/actions/index.ts:18-24` | Export `actionTogglePinned` from `./actionProperties`. This import is what registers it, via `register.ts:5` → `App.tsx:912` `registerAll(actions)`. |
| `packages/excalidraw/components/shapeActionPredicates.ts:88-189` (`getShapeActionPredicates`) | Add a `pinned` flag, for example `pinned: hasSelection`. |
| `packages/excalidraw/components/Actions.tsx` | Render `{predicates.pinned && renderAction("togglePinned")}` in each layout: `SelectedShapeActions` (129, e.g. after `changeOpacity` at line 191), `MobileShapeActions` (724, near line 298), and `CompactShapeActions` (605). |
| `packages/excalidraw/locales/en.json:44` (the `labels` block) | Add a `"pinned"` label string. |

## 7. Optional and related spots

- **Copy/paste styles:** `packages/excalidraw/actions/actionStyles.ts:124` (and `:190`). Add `pinned` here only if it should count as a "style".
- **Behaviour:** if `pinned` should affect behaviour, the `locked` checks show where to add them: `packages/element/src/typeChecks.ts:173/190/246`, `packages/element/src/selection.ts:34`, `packages/excalidraw/components/App.tsx:6035`, `packages/excalidraw/renderer/interactiveScene.ts:1927`.
- **Setting it on new elements:** a `currentItemPinned` field in `AppState` (`packages/excalidraw/types.ts`), `packages/excalidraw/appState.ts` (defaults and storage config), and the `newElement` call sites in `App.tsx`. Only needed if you want a value chosen in the panel to apply to elements drawn afterwards.
- **Literal `locked: false` sites:** these build element objects directly: `App.tsx:3017, 8864, 8924, 8977, 9024, 9208, 9231, 9403, 9454`, `App.drawshape.ts:205`, `App.clipboard.ts:442`, `App.toolDrag.ts:66`, `actionBoundText.tsx:301`, `convertToShape.ts:624/662/702`, `charts.constants.ts:53`. Any typed as a full element will fail typecheck until they include `pinned`. Run `yarn test:typecheck` to find which.

## 8. Tests and fixtures

- `packages/excalidraw/tests/helpers/api.ts:221` and `:308` (`API.createElement`): add a `pinned?` option and default.
- `packages/excalidraw/tests/fixtures/elementFixture.ts:33`: add `pinned: false`.
- New tests:
  - **Restore:** an element without the field restores to `false`, and `true` round-trips (`tests/data/restore.test.ts`).
  - **Reconcile:** a higher-version remote toggle wins (`tests/data/reconcile.test.ts`).
  - **Undo/redo:** toggle → undo → redo (`tests/history.test.tsx`).
- Then run `yarn test:update`. Snapshots will change because every element now has `pinned: false`.