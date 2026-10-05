Based on my analysis of the codebase, here's a comprehensive plan for adding a new per-element boolean property that survives all required contexts:

## Files and Functions to Change

### 1. **Element Type Definition**
- **packages/element/src/types.ts:59-86** — `_ExcalidrawElementBase` interface — add the new boolean property here (all element types inherit it)
- **packages/element/src/types.ts:223-234** — `ExcalidrawElement` union type (auto-updated)

### 2. **Element Creation**
- **packages/element/src/newElement.ts:87-174** — `_newElementBase` and `newElement` functions — initialize property with default value
- **packages/element/src/newElement.ts:230** — `newStickyNoteElement` — if specific sticky note handling needed
- **packages/element/src/newElement.ts:245** — `newEmbeddableElement` — if specific embeddable handling needed

### 3. **Element Mutation & Updates**
- **packages/element/src/mutateElement.ts:27-30** — `ElementUpdate` type (auto-includes property via Partial)
- **packages/element/src/mutateElement.ts:40-123** — `mutateElement` function (auto-handles property)

### 4. **Restore/Import/Deserialization**
- **packages/excalidraw/data/restore.ts:517-615** — `restoreElement` function — handle property when importing with fallback to default
- **packages/excalidraw/data/restore.ts:946-1000** — `restoreElements` function (auto-calls restoreElement)

### 5. **Export/Serialization**
- **packages/excalidraw/data/json.ts:52-89** — `serializeAsJSON` function (auto-includes property via JSON.stringify)
- **packages/excalidraw/data/json.ts:77-89** — `saveAsJSON` function (auto-serializes)

### 6. **Local Storage**
- **excalidraw-app/data/LocalData.ts:73-109** — `saveDataStateToLocalStorage` function (auto-serializes elements)
- **excalidraw-app/data/localStorage.ts:37-74** — `importFromLocalStorage` function (auto-deserializes)

### 7. **History/Undo-Redo**
- **packages/excalidraw/history.ts:83-155** — `HistoryChangedEvent` class and `History.undo`/`redo` methods (auto-restore element state)
- **packages/excalidraw/actions/actionHistory.tsx:26-52** — `executeHistoryAction` function (auto-works with elements)

### 8. **Collaboration & Sync**
- **excalidraw-app/collab/Collab.tsx:601-618** — `_reconcileElements` method — reconciliation already handles all properties
- **excalidraw-app/collab/Collab.tsx:365-411** — `stopCollaboration` method (auto-includes property in sync)
- **excalidraw-app/collab/Collab.tsx:481-568** — `startCollaboration` method (auto-syncs)
- **excalidraw-app/data/index.ts:58-63** — `getSyncableElements` function (auto-includes all elements with property)
- **packages/element/src/delta.ts:1807-1998** — `checkForVisibleDifference` and `resolveConflicts` methods (auto-detects changes)

### 9. **Properties Panel UI**
- **packages/excalidraw/components/Actions.tsx:219-305** — `CombinedShapeProperties` component — add rendering of property toggle button
- **packages/excalidraw/components/Actions.tsx:307-401** — `CombinedArrowProperties` component — if applicable to arrows
- **packages/excalidraw/actions/actionProperties.tsx:193-227** — `changeProperty` function — create property change callback
- **packages/excalidraw/actions/actionProperties.tsx:184-191** — `getStylesPanelInfo` function (reference for panel info)
- **packages/excalidraw/components/shapeActionPredicates.ts** — Add predicate to `getShapeActionPredicates` return type (line 191) to conditionally show property in UI

### 10. **Type Checks & Predicates**
- **packages/element/src/typeChecks.ts:255-284** — `isExcalidrawElement` function (auto-works)
- Create new helper if needed: `isPropertyApplicableToElement(element)` in **packages/element/src/typeChecks.ts**

### 11. **Action Definitions (if using action system)**
- **packages/excalidraw/actions/** — Create or extend action definition if using action manager pattern

### 12. **Optional: Rendering**
- **packages/element/src/renderElement.ts:431-437** — `drawElementOnCanvas` function — if property affects visual appearance
- **packages/element/src/renderElement.ts:1011-1020** — `drawElement` function — if property affects rendering logic

### 13. **Optional: Cleanup/Validation**
- **packages/element/src/index.ts** — Export new helper functions if created
- **packages/excalidraw/components/App.tsx:5029-5041** — `mutateElement` method wrapper (auto-works)

---

**Key patterns to follow:**
- Property serializes/deserializes automatically via `JSON.stringify`/`JSON.parse`
- Element creation: initialize in `_newElementBase` with sensible default
- UI changes: add to properties panel alongside other element properties using `changeProperty` + action pattern
- No special handling needed for undo/redo, collaboration, or local storage—they all traverse element objects generically
- For rendering changes, update `drawElementOnCanvas` switch statement for your specific element types