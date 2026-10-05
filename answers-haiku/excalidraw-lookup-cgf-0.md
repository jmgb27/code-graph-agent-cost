Based on the CodeGraph exploration, I found all the places where an element's `frameId` is written (set, cleared, or changed). Here's the comprehensive list:

## Direct frameId Writes

### packages/element/src/frame.ts
- **67-69**: `bindElementsToFramesAfterDuplication()` - writes `frameId: nextFrameId ?? null` via mutateElement
- **590-592**: `addElementsToFrame()` - writes `frameId: frame.id` via mutateElement
- **669-671**: `removeElementsFromFrame()` - writes `frameId: null` via mutateElement

### packages/element/src/flowchart.ts
- **738-742**: `FlowChartNodeCreator` constructor - writes `frameId: startNode.frameId` via mutateElement for pending nodes

## Indirect frameId Writes

These functions call the above functions and indirectly write frameId:

### packages/excalidraw/actions/actionFrame.ts
- **83**: `actionRemoveAllElementsFromFrame()` - calls `removeAllElementsFromFrame()`
- **166-170**: `actionWrapSelectionInFrame()` - calls `addElementsToFrame()`

### packages/element/src/frame.ts (additional)
- **680**: `removeAllElementsFromFrame()` called from another context
- **690**: `replaceAllElementsInFrame()` calls both `removeAllElementsFromFrame()` and `addElementsToFrame()`
- **738**: `updateFrameMembershipOfSelectedElements()` - calls `removeElementsFromFrame()`

### packages/excalidraw/components/App.duplicate.ts
- Likely calls `bindElementsToFramesAfterDuplication()` during duplication

## Summary

All frameId writes go through the **`mutateElement()` function** with these patterns:
- `frameId: null` (clear/remove from frame)
- `frameId: frame.id` (add to frame)
- `frameId: nextFrameId ?? null` (rebind during duplication)
- `frameId: startNode.frameId` (assign during flowchart operations)