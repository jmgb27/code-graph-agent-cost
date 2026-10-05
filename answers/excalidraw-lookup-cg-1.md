I found no frameId writes in `excalidraw-app/`. Every write is in `packages/`. Test files are excluded. Line numbers are from the current `master` checkout.

## 1. Core mutation helpers (`packages/element/src/frame.ts`)
Most frame-membership changes go through these functions.
- `frame.ts:67-69`: `bindElementsToFramesAfterDuplication` sets `frameId: nextFrameId ?? null` on duplicates, pointing them at the duplicated frame or clearing it. It's called from `duplicate.ts:447`.
- `frame.ts:589-593`: `addElementsToFrame` sets `frameId: frame.id` when it differs.
- `frame.ts:668-672`: `removeElementsFromFrame` sets `frameId: null`.
- `frame.ts:675-680`: `removeAllElementsFromFrame` wraps `removeElementsFromFrame`.
- `frame.ts:684-690`: `replaceAllElementsInFrame` removes all children, then adds them again.
- `frame.ts:697-738`: `updateFrameMembershipOfSelectedElements` calls `removeElementsFromFrame` (line 738).

## 2. Direct writes elsewhere in `packages/element`
- `newElement.ts:103` and `newElement.ts:156`: `_newElementBase` defaults `frameId = null` and writes it onto every new element.
- `transform.ts:855` and `transform.ts:864`: `Object.assign(..., { frameId: frame.id })` when frame skeleton children are converted.
- `duplicate.ts:597-598`: `updates.frameId = null` when the frame being duplicated is vetoed.
- `binding.ts:2514`: `updateElementWith(boundElement, { [bindingProp]: null })`. This clears `frameId` when the frame is missing or deleted. `bindingProp` can be `"frameId"` (see `binding.ts:2419-2421`); `binding.ts:2519` then skips any rebinding for frames.
- `convertToShape.ts:580`, `:623`, `:661`, `:701`: shapes created by shape recognition inherit `frameId`.
- `flowchart.ts:740`: a new flowchart node gets `frameId: startNode.frameId`.

## 3. Direct writes in `packages/excalidraw`
**Deleting and restoring**
- `actions/actionDeleteSelected.tsx:121`: `newElementWith(el, { frameId: null })` when the parent frame is deleted.
- `data/restore.ts:474`: normalizes to `frameId: element.frameId ?? null`.
- `data/restore.ts:884`: `element.frameId = null` inside `repairFrameMembership`, when the frame no longer exists. This is a direct mutation.
- `clipboard.ts:181-183`: sets `frameId: null` on copied elements whose frame isn't being copied.

**App.tsx**
- `components/App.tsx:3023`: `mutateElement(child, { frameId: frame.id })` when wrapping the selection in a magic frame.
- `components/App.tsx:8865`, `:9025`, `:9209`, `:9232`, `:9404`: new elements get `frameId: topLayerFrame ? topLayerFrame.id : null`.

**Other App.\* modules**
- `components/App.clipboard.ts:484`, `:534`: pasted elements get the top-layer frame (same expression as above).
- `components/App.clipboard.ts:572-581`: a pasted text element carries over `frameId`.
- `components/App.toolDrag.ts:67`: `frameId: app.getTopLayerFrameAtSceneCoords(center)?.id ?? null`.
- `components/App.text.ts:772`: new text elements get `frameId`.
- `components/App.bucketFill.ts:261`: bucket-fill polygons get `frameId`.
- `components/App.drawshape.ts:204`: a new element gets `frameId: line.frameId`.
- `components/App.duplicate.ts:209`: `frameId: duplicateElement.frameId ?? origElement.frameId`.

**Actions**
- `actions/actionDuplicateSelection.tsx:80`: `frameId: duplicateFrameId ?? origElement.frameId`.
- `actions/actionBoundText.tsx:313`: the new container inherits `frameId: textElement.frameId`.

## 4. Callers that change membership through the section 1 helpers
- **App.tsx**:
  - `addElementsToFrame`: `:10865`, `:10992`
  - `removeElementsFromFrame`: `:10917`
  - `updateFrameMembershipOfSelectedElements`: `:11009`, `:11035`
  - `replaceAllElementsInFrame`: `:11046`
- **`App.duplicate.ts:131`**: `addElementsToFrame`.
- **`actions/actionFrame.ts`**: `removeAllElementsFromFrame` at `:83`, `addElementsToFrame` at `:166`.
- **`actions/actionGroup.tsx`**: `removeElementsFromFrame` at `:148`, `replaceAllElementsInFrame` at `:274`.
- **`updateFrameMembershipOfSelectedElements`**: `actions/actionAlign.tsx:72`, `actions/actionDistribute.tsx:66`, `actions/actionFlip.ts:36` and `actions/actionFlip.ts:61`.
- **`replaceAllElementsInFrame`**:
  - `components/Stats/Dimension.tsx:209`, `:306`
  - `components/Stats/MultiDimension.tsx:292`, `:448`

## Not writes
- `renderer/staticScene.ts:486` copies `frameId` onto a temporary label object used only for drawing; no scene element changes.
- `zindex.ts:587-609` and `App.tsx:6778` only read `frameId`.
- Undo/redo (`delta.ts`) and collaboration updates may also change `frameId` when they apply stored element changes. That code never names `frameId`, so this search can't list those places.