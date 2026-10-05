I found 14 places that change `frameId` on an element that already exists, and about 17 more that set it when an element is created. `excalidraw-app/` never writes `frameId`, so everything below is in `packages/`. Test files are left out.

## 1. Changing `frameId` on an existing element

**The frame helpers in `packages/element/src/frame.ts`** (most frame changes go through these):
- `frame.ts:67-69`: `bindElementsToFramesAfterDuplication` sets `frameId` to the duplicated frame's id, or `null` if the frame wasn't duplicated.
- `frame.ts:589-593`: `addElementsToFrame` sets `frameId = frame.id`. This includes bound text elements.
- `frame.ts:668-672`: `removeElementsFromFrame` sets `frameId = null`.
- `removeAllElementsFromFrame` (`frame.ts:675`) and `replaceAllElementsInFrame` (`frame.ts:684`) work by calling those two helpers. `updateFrameMembershipOfSelectedElements` (`frame.ts:697`) also calls `removeElementsFromFrame`. The helpers' callers are in `actionFrame.ts`, `actionGroup.tsx`, `App.tsx`, `App.duplicate.ts`, `Stats/Dimension.tsx` and `Stats/MultiDimension.tsx`.

**Other direct writes:**
- `packages/element/src/binding.ts:2514`: `updateElementWith(boundElement, { [bindingProp]: null })`. This is a generic write that clears `frameId` (`bindingProp === "frameId"`) when the frame is missing or deleted.
- `packages/element/src/duplicate.ts:597-598`: `updates.frameId = null` when the duplicate's frame is vetoed.
- `packages/element/src/flowchart.ts:738-742`: pending flowchart nodes get `frameId: startNode.frameId`.
- `packages/element/src/transform.ts:855`: `Object.assign(elementInFrame, { frameId: frame.id })`, used when converting skeleton frame children.
- `packages/element/src/transform.ts:864`: the same for their bound elements.
- `packages/excalidraw/data/restore.ts:884`: `element.frameId = null` in `repairFrameMembership`, when the frame no longer exists.
- `packages/excalidraw/clipboard.ts:181-183`: sets `frameId: null` on the copied element when its frame isn't being copied too.
- `packages/excalidraw/actions/actionDeleteSelected.tsx:121`: `newElementWith(el, { frameId: null })` for the children of a frame being deleted.
- `packages/excalidraw/components/App.tsx:3023`: `this.scene.mutateElement(child, { frameId: frame.id })` puts selected elements into a new magic frame.

## 2. Setting `frameId` when an element is created or duplicated

- `packages/element/src/newElement.ts:103` sets the default `frameId = null`, and `newElement.ts:156` assigns it to the element.
- `packages/excalidraw/data/restore.ts:474`: `frameId: element.frameId ?? null`
- `packages/element/src/convertToShape.ts:553` works out the frame, then uses it at `:580`, `:623`, `:661` and `:701`.
- `packages/excalidraw/components/App.tsx:8865`, `:9025`, `:9209`, `:9232`, `:9404`: `frameId: topLayerFrame ? topLayerFrame.id : null`
- `packages/excalidraw/components/App.clipboard.ts:484`, `:534` (top-layer frame) and `:581` (copied from pasted data at `:572`).
- `packages/excalidraw/components/App.text.ts:720` works out the frame, then uses it at `:772`.
- `packages/excalidraw/components/App.bucketFill.ts:227` works out the frame, then uses it at `:261`.
- `packages/excalidraw/components/App.toolDrag.ts:67`: `frameId: app.getTopLayerFrameAtSceneCoords(center)?.id ?? null`
- `packages/excalidraw/components/App.drawshape.ts:204`: `frameId: line.frameId`
- `packages/excalidraw/actions/actionBoundText.tsx:313`: `frameId: textElement.frameId`
- `packages/excalidraw/actions/actionDuplicateSelection.tsx:80`: `frameId: duplicateFrameId ?? origElement.frameId`
- `packages/excalidraw/components/App.duplicate.ts:209`: `frameId: duplicateElement.frameId ?? origElement.frameId`

History undo/redo and collaboration also apply `frameId` changes. They do this through generic element-delta and reconcile code, which never refers to `frameId` by name, so it doesn't appear as a separate site above.