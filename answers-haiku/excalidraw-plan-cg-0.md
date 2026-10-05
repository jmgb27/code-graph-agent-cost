Based on my exploration of the codebase, here's a comprehensive plan for adding a new per-element boolean property that survives all required systems:

## **Data Model & Element Types**
- **packages/element/src/types.ts:40** — `_ExcalidrawElementBase` type (add property here)
- **packages/element/src/types.ts:223** — `ExcalidrawElement` union type (inherits the property)

## **Element Creation**
- **packages/element/src/newElement.ts:61** — `ElementConstructorOpts` type (mark property as optional in constructor)
- **packages/element/src/newElement.ts:144** — `_newElementBase` function (initialize property in new elements)

## **Element Mutation**
- **packages/element/src/mutateElement.ts:27** — `ElementUpdate` type (add property to updatable fields, excluding `id`, `updated`, `created`)
- **packages/element/src/mutateElement.ts:40** — `mutateElement` function (apply updates)

## **Export/Restore**
- **packages/excalidraw/data/restore.ts:246** — `RestoredDataState` type (property included in restored elements)
- **packages/excalidraw/data/restore.ts:517** — `restoreElement` function (validate/normalize property during restore)
- **packages/excalidraw/data/restore.ts:1254** — `restoreAppState` function (if element defaults need merging with local state)

## **Local Storage**
- **excalidraw-app/data/localStorage.ts:37** — `importFromLocalStorage` (automatic via JSON serialization)
- **excalidraw-app/data/LocalData.ts:73** — `saveDataStateToLocalStorage` (automatic via JSON serialization)
- **excalidraw-app/appState.ts** — `clearAppStateForLocalStorage` (verify it doesn't strip element properties)

## **Collaboration & Reconciliation**
- **packages/excalidraw/data/reconcile.ts:73** — `reconcileElements` function (property handled via version/versionNonce comparison)
- **packages/excalidraw/data/reconcile.ts:23** — `shouldDiscardRemoteElement` function (property preserved in conflict resolution)
- **excalidraw-app/data/index.ts:46** — `isSyncableElement` function (property doesn't affect syncability)
- **excalidraw-app/collab/Collab.tsx:761** — `_reconcileElements` method (automatic via reconcileElements call)

## **Undo/Redo (History)**
- **packages/element/src/delta.ts:77** — `Delta` class (automatic handling for element diffs)
- **packages/element/src/store.ts:497** — `StoreDelta.calculate` at line 525 (automatic calculation of element property changes)
- **packages/excalidraw/history.ts:117** — `History.record` method (automatic recording via StoreDelta)

## **Properties Panel UI**
- **packages/excalidraw/actions/types.ts:45** — `ActionName` type (add action name for toggling property if needed)
- **packages/excalidraw/components/App.tsx** — properties panel component registration (likely around L4000+)
- **packages/excalidraw/components/Actions.tsx** — likely contains shape/properties action components
- Create new properties action file or update existing element properties component to handle the toggle

## **Type Guards (Optional)**
- **packages/element/src/typeChecks.ts** — might add type predicates if property is specific to certain element types

## **Notes**
- **Automatic via JSON serialization**: Local storage, export/import formats, and data transfer automatically serialize the property (no special handling needed unless you need validation/transformation)
- **Automatic via delta system**: Undo/redo and collaboration both track element changes through the delta system—any property on `ExcalidrawElement` that's not in the exclusion list (`id`, `updated`, `created`) is automatically included
- **Properties panel**: This is the only system requiring explicit UI implementation; mutations via `mutateElement` will automatically trigger history recording and collaboration sync