Based on my analysis of the Excalidraw codebase, here's the complete list of every file and function that must change to add a new per-element boolean property that survives all layers:

## **TYPE & SCHEMA DEFINITIONS**

1. **packages/element/src/types.ts:40-87** — `_ExcalidrawElementBase` type definition
   - Add property to readonly type signature (line ~85, near `locked`)

## **DEFAULT VALUES**

2. **packages/common/src/constants.ts:517-535** — `DEFAULT_ELEMENT_PROPS` object
   - Add property to the exported constant with default value

## **ELEMENT CONSTRUCTION**

3. **packages/element/src/newElement.ts:61-85** — `ElementConstructorOpts` type
   - Add property to the optional fields union (line ~81, near `locked`)

4. **packages/element/src/newElement.ts:87-111** — `_newElementBase()` function
   - Add destructuring parameter with default (line ~108, near `locked = DEFAULT_ELEMENT_PROPS.locked`)

5. **packages/element/src/newElement.ts:137-170** — Element object literal in `_newElementBase()`
   - Add property to returned element object (line ~168, near `locked`)

## **ELEMENT MUTATION**

6. **packages/element/src/mutateElement.ts:27-30** — `ElementUpdate<TElement>` type
   - Property is already excluded by the `Omit<Partial<TElement>, ...>` pattern—no change needed for mutation signature, but verify in usage

## **IMPORT/RESTORE (from .excalidraw files)**

7. **packages/excalidraw/data/restore.ts:475-520** — `restoreElement()` function, element normalization block
   - Add normalization with `element.property ?? false` fallback (line ~492, near `locked: element.locked ?? false`)

8. **packages/excalidraw/data/restore.ts:~1340** — `restoreAppState()` function, active tool lock state
   - If applicable for tool-level state (check if new property needs tool-level default too)

## **EXPORT/SERIALIZATION**

- **packages/excalidraw/data/json.ts:52-74** — `serializeAsJSON()`
  - No code change needed—raw element serialization is automatic via JSON.stringify()
  - Verify elements array is serialized as-is (it is, line 62: `elements`)

## **ACTION/UI TOGGLE**

9. **packages/excalidraw/actions/actionElementLock.ts:20-158** — Template for toggle action
   - Create new file: `packages/excalidraw/actions/actionElementProperty.ts` (or similar)
   - Mirror the structure: `shouldPropertyBeSet()` check, `actionToggle[Property]()` action, icon/label, `perform()` function using `newElementWith()`, keyboard shortcut in `keyTest()`

10. **packages/excalidraw/actions/register.ts** — Action registry
    - Import and register the new action (verify registration pattern used by `actionToggleElementLock`)

## **PROPERTIES PANEL UI**

11. **packages/excalidraw/actions/actionProperties.tsx** — Properties panel component
    - Add toggle control (similar to how other boolean properties are displayed)
    - Add state getter from selected elements
    - Add onChange handler that calls the toggle action

## **TOOLBAR/CONTEXT MENU**

12. **packages/excalidraw/components/Toolbar.tsx:220-290** — Toolbar component
    - Add button/toggle (optional, depending on prominence; `LockButton` pattern at line ~275)

13. **packages/excalidraw/components/main-menu/DefaultItems.tsx** — Main menu
    - Add menu item to toggle property (optional; pattern at line ~439 for lock)

14. **packages/excalidraw/components/CommandPalette/CommandPalette.tsx** — Command palette
    - Add command to toggle property (optional; pattern at line ~559 for lock)

## **INTERACTION LAYER (prevents user actions)**

15. **packages/excalidraw/renderer/interactiveScene.ts:1920-1935** — Selection rendering
    - Check property in locked-element logic (line ~1927-1930: `element.locked`)
    - Adapt stroke/dashing based on property if visual feedback needed

16. **packages/excalidraw/renderer/interactiveScene.ts:2055-2065** — Move state check
    - Update condition checking locked elements (line ~2058: `!element.locked`)

17. **packages/excalidraw/components/App.tsx:6030-6040** — Element selection filtering
    - Add property to `opts?.includeLockedElements` check pattern (line ~6035)

18. **packages/excalidraw/components/App.tsx:9840-9850** — Multi-selection state
    - Check property in lock-state evaluation (line ~9844)

19. **packages/excalidraw/lasso/utils.ts:290-295** — Lasso selection filtering
    - Exclude elements based on property (line ~292: `|| element.locked`)

20. **packages/excalidraw/actions/actionSelectAll.ts:35-40** — Select-all action
    - Filter by property (line ~37: `!element.locked`)

## **UNDO/REDO (automatic via element versioning)**

- **packages/excalidraw/history.ts** — History system
  - No direct change needed—property mutations through `newElementWith()` automatically bump `version` and `versionNonce` (mutateElement.ts:177-179)

## **COLLABORATION/SYNC (automatic via versioning)**

- Collaboration sync uses `version`, `versionNonce`, and `updated` fields—all bumped automatically by `newElementWith()` and `mutateElement()` when the property changes
- No explicit sync code change needed if property flows through standard `newElementWith()` channels

## **LOCAL STORAGE (automatic via serialization)**

- **packages/excalidraw/data/EditorLocalStorage.ts** — LocalStorage wrapper
  - No change needed—elements are JSON-serialized/deserialized automatically, preserving all fields

## **TEST FIXTURES & SNAPSHOTS**

21. **packages/excalidraw/tests/fixtures/elementFixture.ts:30-40** — Element fixture
    - Add property to default fixture (line ~33: `locked: false`)

22. **packages/excalidraw/tests/elementLocking.test.tsx** — Element locking test suite
    - Add test cases for new property behavior (patterns at lines 24-100)

23. **packages/utils/tests/__snapshots__/export.test.ts.snap** — Export snapshot
    - Update or regenerate if test assertions capture element JSON

24. **packages/utils/tests/__snapshots__/utils.test.ts.snap** — Utils snapshot
    - Update or regenerate if test assertions capture element JSON

25. **packages/excalidraw/tests/__snapshots__/selection.test.tsx.snap** — Selection snapshot
    - Update or regenerate if element state is captured

26. **packages/excalidraw/tests/__snapshots__/history.test.tsx.snap** — History snapshot
    - Update or regenerate if undo/redo state is captured

27. **packages/excalidraw/tests/data/__snapshots__/restore.test.ts.snap** — Restore snapshot
    - Update or regenerate if restore behavior is validated

---

## **SUMMARY BY LAYER**

| Layer | Files | Automatic? |
|-------|-------|-----------|
| **Schema** | 1 (types.ts) | — |
| **Defaults** | 1 (constants.ts) | — |
| **Construction** | 2 (newElement.ts) | — |
| **Persist to Storage** | 1 (json.ts, automatic serialization) | ✓ |
| **Restore from Storage** | 1 (restore.ts) | — |
| **Undo/Redo** | 0 (automatic via newElementWith versioning) | ✓ |
| **Collaboration Sync** | 0 (automatic via version/versionNonce) | ✓ |
| **UI Interaction** | 1 action file + ~5 UI components | — |
| **Rendering/Selection** | 5 (renderer, App, lasso, selectAll) | — |
| **Tests** | ~8 (fixtures + snapshots) | — |

**Total: ~25 files/locations, ~10 require code logic changes; the rest inherit via TypeScript type inference and JSON serialization.**