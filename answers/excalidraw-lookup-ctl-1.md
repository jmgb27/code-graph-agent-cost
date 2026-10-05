I found every non-test write of `frameId` and checked each one in context. No file under `excalidraw-app/` writes `frameId`; every write is in `packages/`. Test files are left out.

## Direct changes to existing elements

**Frame membership helpers** (`packages/element/src/frame.ts`)
- `frame.ts:67-69`: `bindElementsToFramesAfterDuplication` points duplicates at the duplicated frame, or clears the field if the frame wasn't duplicated (`nextFrameId ?? null`).
- `frame.ts:589-593`: `addElementsToFrame` sets `frameId: frame.id` on each element that isn't already in the frame, including bound text.
- `frame.ts:668-672`: `removeElementsFromFrame` clears it (`frameId: null`). Other helpers such as `replaceAllElementsInFrame`, `removeAllElementsFromFrame` and `updateFrameMembershipOfSelectedElements` change `frameId` by calling these two.

**Other places**
- `packages/element/src/duplicate.ts:597-598`: `updates.frameId = null` when a duplicate's frame was vetoed.
- `packages/element/src/binding.ts:2515`: `updateElementWith(boundElement, { [bindingProp]: null })`. The property name is dynamic, and here it can be `"frameId"` (see `binding.ts:2364` and `binding.ts:2421`). It clears the field when the frame is missing or deleted.
- `packages/element/src/transform.ts:855` and `transform.ts:864`: `Object.assign(..., { frameId: frame.id })` sets it on frame children and their bound elements when converting skeleton elements.
- `packages/excalidraw/data/restore.ts:884`: `element.frameId = null` in `repairFrameMembership`, when the containing frame doesn't exist.
- `packages/excalidraw/actions/actionDeleteSelected.tsx:121`: `newElementWith(el, { frameId: null })` when the element's frame is being deleted.
- `packages/excalidraw/clipboard.ts:181-183`: sets `frameId: null` on a copied element whose frame isn't being copied too.
- `packages/excalidraw/components/App.tsx:3023`: `this.scene.mutateElement(child, { frameId: frame.id })` when wrapping the selection in a new frame.

## Set when an element is created, duplicated or restored
- `packages/element/src/newElement.ts:103` and `newElement.ts:156`: the base constructor defaults it to `null` and assigns it.
- `packages/excalidraw/data/restore.ts:474`: `frameId: element.frameId ?? null`.
- `packages/excalidraw/actions/actionDuplicateSelection.tsx:80`: `duplicateFrameId ?? origElement.frameId`.
- `packages/excalidraw/components/App.duplicate.ts:209`: `duplicateElement.frameId ?? origElement.frameId` (the Alt-drag duplicate).
- `packages/excalidraw/components/App.tsx:8865`, `App.tsx:9025`, `App.tsx:9209`, `App.tsx:9232` and `App.tsx:9404`: `frameId: topLayerFrame ? topLayerFrame.id : null` for new elements.
- `packages/excalidraw/components/App.clipboard.ts:484`, `App.clipboard.ts:534` and `App.clipboard.ts:581`: pasted elements.
- `packages/excalidraw/components/App.toolDrag.ts:67`: `getTopLayerFrameAtSceneCoords(center)?.id ?? null`.
- `packages/excalidraw/components/App.text.ts:772`: the value is computed at `App.text.ts:720`.
- `packages/excalidraw/components/App.bucketFill.ts:261`: the value is computed at `App.bucketFill.ts:227-230`.
- `packages/excalidraw/components/App.drawshape.ts:204`: `frameId: line.frameId`.
- `packages/excalidraw/actions/actionBoundText.tsx:313`: the new container takes `textElement.frameId`.
- `packages/element/src/flowchart.ts:740`: `frameId: startNode.frameId`.
- `packages/element/src/convertToShape.ts:580`, `convertToShape.ts:623`, `convertToShape.ts:661` and `convertToShape.ts:701`: the value is computed at `convertToShape.ts:553`.

## Matches that are not writes
- `packages/excalidraw/renderer/staticScene.ts:486`: a render-only label object built from `element.frameId`. It is never stored in the scene.
- The type definition (`packages/element/src/types.ts:74`) and the reads and local variables in `zindex.ts`, `frame.ts:233`/`frame.ts:244`/`frame.ts:504`/`frame.ts:523`, `duplicate.ts:363`, `renderNewElementScene.ts:59` and `App.tsx:6656`–`App.tsx:6788`.