# Plan: a new per-element boolean property

I'll use `pinned` as a placeholder name. I made no edits.

**The main point:** nearly every pipeline you listed treats elements as generic objects. Local storage, `.excalidraw` export, collab broadcast and Firebase all send the whole element as JSON. Reconciliation compares only `version`/`versionNonce`, and undo/redo compares all properties generically. So the changes you must make are: the type, the constructor, the restore default, and the action/panel. The places that list properties one by one (paste styles, the undo visibility check, test fixtures) need a deliberate decision each.

## 1. Type and default (required)

| File | Change |
|---|---|
| `packages/element/src/types.ts:85` | Add `pinned: boolean;` to `_ExcalidrawElementBase`, next to `locked`. Make it required, not optional, so the compiler flags every place that builds an element literal. |
| `packages/common/src/constants.ts:517-535` | Add `pinned: ExcalidrawElement["pinned"]` to the `DEFAULT_ELEMENT_PROPS` type and `pinned: false` to its value. |

## 2. Creation (required)

`packages/element/src/newElement.ts`:
- **`ElementConstructorOpts`** (`:61-85`): add `| "pinned"` to the `MarkOptional` list so callers can leave it out.
- **`_newElementBase`**: destructure it with `pinned = DEFAULT_ELEMENT_PROPS.pinned` (`:108`) and write it into the element literal (`:168`).

Other places that build full element literals will fail typecheck once the field is required. Add `pinned: false` in each:
- `packages/element/src/convertToShape.ts:624, 662, 702`
- `packages/excalidraw/charts/charts.constants.ts:53`
- the literals in `App.tsx` near `:3017`, `App.clipboard.ts:442`, `App.drawshape.ts:205`, `App.toolDrag.ts:66` and `actionBoundText.tsx:301`, if they turn out to be element literals rather than activeTool objects

Running `yarn test:typecheck` gives the full list.

`packages/element/src/duplicate.ts` (~`:117`) copies properties by spreading, so it needs nothing. Decide whether a duplicate keeps the flag; it will by default.

## 3. Restore: `.excalidraw` import, local storage load, collab receive (required)

- **`packages/excalidraw/data/restore.ts:449-493`, `restoreElementWithProperties`**: add `pinned: element.pinned ?? false` next to `locked` at `:492`.
  - The `Pick<T, keyof ExcalidrawElement>` type on `base` will force this.
  - This is the only place legacy files, old local-storage blobs, and elements from older collaborators get the default.
  - `...element` is spread first (`:503`), so older clients that don't know the field still keep it rather than dropping it.
- `restoreElements` (`:946`) goes through `restoreElement` into the function above, so it needs no change.

Every entry point already routes through `restoreElements`, so none of these change:
- **Local storage load:** `excalidraw-app/App.tsx:243` (fed by `importFromLocalStorage`, `excalidraw-app/data/localStorage.ts:37`).
- **File / link import:** `excalidraw-app/App.tsx:269, 586`, and `loadFromBlob`, reached via `packages/excalidraw/data/json.ts:102`.
- **Collab receive:** `excalidraw-app/collab/Collab.tsx:771` in `_reconcileElements`.
- **Firebase load:** `excalidraw-app/data/firebase.ts:219, 241, 262`.

## 4. Save, export and sync (no change needed; check only)

These all pass the element through whole:
- **Local storage save:** `excalidraw-app/data/LocalData.ts:90-93`, `JSON.stringify(getNonDeletedElements(elements))`.
- **`.excalidraw` export:** `packages/excalidraw/data/json.ts:52-75`, `serializeAsJSON`, which puts `elements` in as-is.
- **Collab broadcast:** `excalidraw-app/collab/Portal.tsx:142-180`, `broadcastScene`. It filters on `version`, so a toggle must bump the version, which `newElementWith` does.
- **Reconciliation:** `packages/excalidraw/data/reconcile.ts:23-44` (`shouldDiscardRemoteElement`) and `:73` (`reconcileElements`) compare only `version`/`versionNonce`. Nothing needs to change, as long as every write goes through `newElementWith` or `mutateElement`.
- **Firebase save:** `excalidraw-app/data/firebase.ts:218-222` restores, then reconciles, then encrypts the whole element.

## 5. Undo/redo (check one switch)

- **`packages/element/src/delta.ts`**:
  - Deltas are computed from all keys generically.
  - `stripIrrelevantProps` (`:2206-2212`) removes only `id` and `updated`, so `pinned` is recorded.
- **`ElementsDelta.checkForVisibleDifference`** (`:1809-1875`): history skips entries it judges to have no visible change. Its `switch` at `:1857-1873` returns `true` for any unknown key. **Do not** add `pinned` to the metadata cases at `:1860-1865`. If you did, undoing a toggle of a flag that doesn't change rendering would be skipped silently. Leaving it on the default branch is correct even when the flag isn't visual.
- The toggle action must return `captureUpdate: CaptureUpdateAction.IMMEDIATELY` to create a history entry (see §6).

## 6. Properties-panel toggle (required)

**Action: `packages/excalidraw/actions/actionProperties.tsx`.** Add `actionChangePinned = register<boolean>({...})`, modelled on `actionChangeOpacity` (`:956-997`):
- **`perform`**: `changeProperty(elements, appState, (el) => newElementWith(el, { pinned: value }), true)` and `captureUpdate: CaptureUpdateAction.IMMEDIATELY`.
- **`PanelComponent`**: read the common value with `getFormValue(elements, app, (el) => el.pinned, true, false)` (`:229-271`). Render `packages/excalidraw/components/Switch.tsx` or `CheckboxItem.tsx` inside a `<fieldset><legend>`, and call `updateData(!value)` on change.

**Registration:**
- `packages/excalidraw/actions/types.ts:~77`: add `| "changePinned"` to the `ActionName` union.
- `packages/excalidraw/actions/index.ts:~18`: re-export `actionChangePinned`.

**Visibility predicate:** in `packages/excalidraw/components/shapeActionPredicates.ts`, add `pinned: hasSelection` (or a type-specific rule) to the object returned by `getShapeActionPredicates` (`:88`, near `opacity` at `:157`). The `ShapeActionPredicates` type (`:191`) picks it up automatically.

**Rendering in `packages/excalidraw/components/Actions.tsx`:**
- `SelectedShapeActions` (desktop full panel): add `{predicates.pinned && renderAction("changePinned")}` near `:191`.
- `CombinedShapeProperties` popover (used by `CompactShapeActions` at `:605` and `MobileShapeActions` at `:724`): add the same near `:298`.

**Label:** add `"pinned": "…"` under `labels` in `packages/excalidraw/locales/en.json`, next to `:44`.

## 7. Optional, depending on what you want

- **Copy/paste styles:** `packages/excalidraw/actions/actionStyles.ts:118-133` lists style properties one by one. Add `pinned: elementStylesToCopyFrom?.pinned` only if it counts as a style.
- **New elements inheriting the last value:** only needed if new elements should take on the last-used toggle, the way opacity does with `currentItemOpacity`. If so:
  - add `currentItemPinned` to `AppState` in `packages/excalidraw/types.ts:~456`, to the default in `packages/excalidraw/appState.ts:~37`, and to the storage config in `appState.ts:~183` (`{ browser: true, export: false, server: false }`)
  - set it in the action's `perform`
  - pass it at each creation site that currently passes `currentItemOpacity`: `App.tsx:8854, 8923, 8976, 9023, 9199, 9226, 9401, 9453`, `App.text.ts:743`, `App.drawshape.ts:246`, `App.bucketFill.ts:146, 260`, `App.toolDrag.ts:64`, `App.clipboard.ts:436`, `convertToShape.ts:586…`

  I'd skip this unless it's actually wanted.
- **Programmatic API:** `packages/element/src/transform.ts:89` (`ExcalidrawElementSkeleton`) builds on `ElementConstructorOpts`, so skeletons accept `pinned` automatically once §2 is done.

## 8. Tests and fixtures

- `packages/excalidraw/tests/fixtures/elementFixture.ts:33`: add `pinned: false`.
- `packages/excalidraw/tests/helpers/api.ts:221, 308` (`API.createElement`): add the option and default it.
- **Suggested new tests:**
  - restore of an element with no `pinned` gives `false`; `true` round-trips through `serializeAsJSON` → `loadFromBlob`
  - toggle action → undo → redo, using `packages/excalidraw/tests/history.test.tsx` as the pattern
  - `reconcileElements` picks up a remote `pinned` change when the remote version is higher
- Then run `yarn test:typecheck` and `yarn test:update`. Snapshots across the suite will change because every element gains the key.