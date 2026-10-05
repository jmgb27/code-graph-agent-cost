Perfect! Now I have a comprehensive list. Let me compile all the frameId write locations:

## Summary: All Places Where Element's frameId is Written

Based on the codebase analysis, here are all the locations where an element's `frameId` is written (set, cleared, or changed), across `packages/` and `excalidraw-app/`:

### Direct frameId Mutations via `mutateElement`:

1. **packages/element/src/frame.ts:68** - `bindElementsToFramesAfterDuplication()`
   - Sets `frameId: nextFrameId ?? null`

2. **packages/element/src/frame.ts:591** - `addElementsToFrame()`
   - Sets `frameId: frame.id`

3. **packages/element/src/frame.ts:670** - `removeElementsFromFrame()`
   - Sets `frameId: null`

4. **packages/element/src/flowchart.ts:740** - `FlowChartCreator.createNodes()`
   - Sets `frameId: startNode.frameId`

### Direct frameId Assignments (not via mutateElement):

5. **packages/element/src/transform.ts:855** - `convertToExcalidrawElements()`
   - Direct assignment via `Object.assign(elementInFrame, { frameId: frame.id })`

6. **packages/element/src/transform.ts:864** - `convertToExcalidrawElements()`
   - Direct assignment via `Object.assign(ele, { frameId: frame.id })` (for bound elements)

7. **packages/element/src/duplicate.ts:598** - `reconcileDuplicatedElements()`
   - Sets `frameId: null` for duplicates with vetoed (excluded) frame references

### Direct frameId Mutations (not via Object methods):

8. **packages/excalidraw/data/restore.ts:884** - `repairFrameMembership()`
   - Direct assignment `element.frameId = null` when containing frame doesn't exist