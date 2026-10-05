Based on my analysis of the codebase, here's a comprehensive plan for adding a new per-element boolean property (let's call it `myProperty` as an example):

## Files and Functions to Change

### 1. **Element Type Definition**
- **File:** `packages/element/src/types.ts`
  - **Line 40-87:** Modify `_ExcalidrawElementBase` type to add `myProperty: boolean`

### 2. **Element Mutation & Creation**
- **File:** `packages/element/src/mutateElement.ts`
  - **Line 27:** Update `ElementUpdate` type (automatic through Partial<TElement>)
  - **Line 40-48:** `mutateElement()` function handles all properties automatically
  - **Line 149-181:** `newElementWith()` function handles all properties automatically

- **File:** `packages/element/src/newElement.ts`
  - Add `myProperty` to default element creation function (creates default values)

### 3. **Element Duplication**
- **File:** `packages/element/src/duplicate.ts`
  - **Line 103-134:** `duplicateElement()` function (handled by `deepCopyElement`)
  - **Line 625-692:** `deepCopyElement()` function (automatic - copies all properties)
  - Property automatically survives duplication through deep copy

### 4. **Serialization & Export**
- **File:** `packages/utils/src/export.ts`
  - **Line 52-74:** `serializeAsJSON()` function (automatic - includes all element properties)
  - Property is automatically included in exported JSON

- **File:** `packages/excalidraw/data/json.ts`
  - **Line 25-29:** `JSONExportData` type (automatic)
  - **Line 52-75:** `serializeAsJSON()` function (automatic)

### 5. **Deserialization & Restore**
- **File:** `packages/excalidraw/data/restore.ts`
  - **Line 430-449:** `restoreElementWithProperties()` function - add default in `base` object:
    ```
    myProperty: element.myProperty ?? false  // or your default value
    ```
  - **Line 517-527:** `restoreElement()` function (calls restoreElementWithProperties)
  - **Line 946-1017:** `restoreElements()` function (uses restoreElement)

### 6. **Collaboration Sync & Reconciliation**
- **File:** `packages/excalidraw/data/reconcile.ts`
  - **Line 23-43:** `shouldDiscardRemoteElement()` function (automatic - compares version/versionNonce)
  - **Line 73-118:** `reconcileElements()` function (automatic - preserves property through reconciliation)
  - No changes needed - uses version/versionNonce to determine winner

### 7. **Local Storage**
- **File:** `packages/excalidraw/data/EditorLocalStorage.ts`
  - No changes needed - transparent JSON serialization/deserialization

### 8. **Undo/Redo**
- **File:** `packages/excalidraw/history.ts`
  - **Line 51-63:** `HistoryDelta.calculate()` (automatic - tracks all property changes)
  - Property is automatically included in delta calculation
  - No changes needed

### 9. **Action to Toggle Property**
- **File:** Create `packages/excalidraw/actions/actionToggleMyProperty.ts`
  - Define `actionToggleMyProperty` action following the pattern from `actionElementLock.ts:25-158`
  - Implement `perform()` function using `newElementWith()` to toggle the property
  - Optional: Add keyboard shortcut support in `keyTest()`

### 10. **Action Type Registration**
- **File:** `packages/excalidraw/actions/types.ts`
  - **Line 45-145:** Add `"toggleMyProperty"` to the `ActionName` union type

### 11. **Action Shortcuts**
- **File:** `packages/excalidraw/actions/shortcuts.ts`
  - Add keyboard shortcut entry for `toggleMyProperty` if desired

### 12. **Action Index/Export**
- **File:** `packages/excalidraw/actions/index.ts`
  - Add export statement: `export { actionToggleMyProperty } from "./actionToggleMyProperty"`

### 13. **Properties Panel UI**
- **File:** `packages/excalidraw/actions/actionProperties.tsx`
  - Find relevant PanelComponent (around line 1779-2055)
  - Add `{renderAction("toggleMyProperty")}` to the JSX return value

### 14. **Tests** (Optional but recommended)
- **File:** Create `packages/excalidraw/actions/actionToggleMyProperty.test.tsx`
  - Follow pattern from `actionElementLock.test.tsx`
  
- **File:** `packages/excalidraw/tests/data/restore.test.ts`
  - Add test to verify property is restored from exported files

- **File:** `packages/excalidraw/tests/data/reconcile.test.ts`
  - Add test to verify property survives collaboration reconciliation

---

## Automatic Handling (No Changes Needed)

These systems automatically handle any new property:
- ✅ Local storage (JSON serialization)
- ✅ Undo/redo delta tracking
- ✅ Collaboration version/versionNonce tracking
- ✅ Element duplication (deepCopyElement copies all properties)
- ✅ Forward-compatibility in restore (spreads original properties: line 501-502 of restore.ts)