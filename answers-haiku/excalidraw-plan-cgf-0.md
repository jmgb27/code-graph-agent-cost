Based on my exploration of the Excalidraw codebase using CodeGraph, here's a comprehensive plan for adding a new per-element boolean property that survives all layers:

## **Files and Functions to Change**

### **1. Element Type Definition** (Core)
- **`packages/element/src/types.ts:40`** — `_ExcalidrawElementBase` type
  - Add the new boolean property as a readonly field

### **2. Element Creation & Initialization**
- **`packages/element/src/newElement.ts:61`** — `ElementConstructorOpts` type
  - Add property as optional in constructor options
  
- **`packages/element/src/newElement.ts:87`** — `_newElementBase()` function
  - Initialize the property with a default value (lines 98-170)

### **3. UI Action System**
- **`packages/excalidraw/actions/types.ts:45`** — `ActionName` type
  - Add new action name constant to the union (e.g., `"toggleMyProperty"`)

- **`packages/excalidraw/actions/register.ts:3`** — `actions` array + `register()` function
  - Register new action via `register()` call (no file modification needed, just add action definition)

- **Create new action file** (e.g., `packages/excalidraw/actions/actionToggleMyProperty.tsx`)
  - Implement action using pattern from existing property actions (like `toggleElementLock`)
  - Use the reusable `changeProperty()` helper function

### **4. Property Change Helper** (No changes)
- **`packages/excalidraw/actions/actionProperties.tsx:193`** — `changeProperty()` function
  - Already generic; will work with new property automatically

### **5. Automatic Persistence Layers** (No changes needed)

These work automatically through the type system:

- **`packages/element/src/mutateElement.ts:40`** — `mutateElement()` function  
  - Automatically handles all properties via generic iteration
  
- **`packages/element/src/mutateElement.ts:27`** — `ElementUpdate<TElement>` type
  - Automatically includes new property
  
- **`packages/excalidraw/history.ts:15`** — `HistoryDelta` class
  - History tracking works automatically via `Delta.calculate()`
  
- **`packages/element/src/delta.ts:77`** — `Delta` class  
  - Diffs calculated automatically for all properties
  
- **`packages/element/src/delta.ts:1885`** — `resolveConflicts()` method
  - Collaboration reconciliation works generically
  
- **`packages/excalidraw/data/index.ts:44`** — `ExportedElements` type
  - Export/import via JSON serialization (automatic)
  
- **`excalidraw-app/data/LocalData.ts:73`** — `saveDataStateToLocalStorage()`
  - Local storage via `JSON.stringify()` (automatic)
  
- **`excalidraw-app/data/firebase.ts:93`** — Firebase serialization
  - Sync layer via JSON encryption (automatic)

### **6. UI Components** (Optional, depends on desired UX)
- **`packages/excalidraw/components/Actions.tsx`** or similar
  - Add UI toggle/panel component if needed (follows pattern of existing property toggles)

### **Summary: Edit These Files**
1. `packages/element/src/types.ts` — add to `_ExcalidrawElementBase` type
2. `packages/element/src/newElement.ts` — update `ElementConstructorOpts` + `_newElementBase()`
3. `packages/excalidraw/actions/types.ts` — add to `ActionName` union
4. Create `packages/excalidraw/actions/actionToggleMyProperty.tsx` — new action implementation
5. Register action in appropriate action file or via `register()`

**Everything else is automatic** — the property survives storage, export, collaboration, undo/redo, and sync through Excalidraw's generic property handling architecture.