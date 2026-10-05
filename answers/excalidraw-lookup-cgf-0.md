I found about 20 places that write an element's `frameId` in `packages/`, and none in `excalidraw-app/`. I started with `codegraph_explore`, which gave me the frame helpers and their callers. It doesn't index property writes, so I found the assignments themselves with `rg` for `frameId:` and `frameId =` and checked each hit in context. Tests are excluded.

## 1. Frame membership helpers (`packages/element/src/frame.ts`)
These are the main places membership changes:
- `packages/element/src/frame.ts:68`: `bindElementsToFramesAfterDuplication` points each duplicate at its duplicated frame, or sets `null` (`frameId: nextFrameId ?? null`). Called from `packages/element/src/duplicate.ts:447`.
- `packages/element/src/frame.ts:591`: `addElementsToFrame` sets `frameId: frame.id`, including on bound text.
- `packages/element/src/frame.ts:670`: `removeElementsFromFrame` clears it (`frameId: null`), including on bound text.
- Wrappers that end up in one of the two above:
  - `removeAllElementsFromFrame` (`:680`)
  - `replaceAllElementsInFrame` (`:689`)
  - `updateFrameMembershipOfSelectedElements` (`:738`), which clears it for selected elements that are no longer inside their frame.

**Callers of these helpers:**
- Adding to a frame:
  - `packages/excalidraw/actions/actionFrame.ts:166`: add to frame.
  - `packages/excalidraw/components/App.duplicate.ts:131`
  - `packages/excalidraw/components/App.tsx:10865` and `:10992`: pointer up after a drag.
- Removing from a frame:
  - `packages/excalidraw/actions/actionFrame.ts:83`: remove all elements from the frame.
  - `packages/excalidraw/actions/actionGroup.tsx:148`
  - `packages/excalidraw/components/App.tsx:10917`
- Replacing a frame's children:
  - `packages/excalidraw/actions/actionGroup.tsx:274`
  - `packages/excalidraw/components/App.tsx:11046`
  - `packages/excalidraw/components/Stats/Dimension.tsx:209` and `:306`
  - `packages/excalidraw/components/Stats/MultiDimension.tsx:292` and `:448`
- Updating membership after a move or transform:
  - `packages/excalidraw/components/App.tsx:11009` and `:11035`
  - `packages/excalidraw/actions/actionAlign.tsx:72`
  - `packages/excalidraw/actions/actionDistribute.tsx:66`
  - `packages/excalidraw/actions/actionFlip.ts:36` and `:61`

## 2. Direct mutations of existing elements
- `packages/excalidraw/components/App.tsx:3023`: after wrapping the selection in a new frame, each child gets `mutateElement(child, { frameId: frame.id })`.
- `packages/excalidraw/actions/actionDeleteSelected.tsx:121`: when a frame is deleted, its children get `frameId: null`.
- `packages/excalidraw/clipboard.ts:182`: a copied element is detached (`frameId: null`) if its frame isn't also being copied.
- `packages/excalidraw/components/App.clipboard.ts:581`: pasted text elements get the `frameId` from the re-laid-out text.
- `packages/element/src/duplicate.ts:598`: `reconcileDuplicatedElements` sets `updates.frameId = null` when the target frame was vetoed, then applies it with `Object.assign` at about `:611`.
- `packages/excalidraw/data/restore.ts:884`: `repairFrameMembership` does `element.frameId = null` when the frame doesn't exist. Called at `:1023`.
- `packages/element/src/transform.ts:855` and `:864`: `convertToExcalidrawElements` uses `Object.assign(..., { frameId: frame.id })` on frame children and their bound elements.
- `packages/element/src/binding.ts:2514`: `BoundElement.rebindAffected` sets `{ [bindingProp]: null }`, which covers `frameId` because `bindableElementsVisitor` (`:2419-2421`) visits `"frameId"`. So if an element's frame is missing or deleted, its `frameId` is cleared. The same generic write also appears at `:2552` and `:2593`. `:2552` can't be reached for `frameId` because of the early return at `:2519`. I didn't confirm whether `:2593` can ever be reached for `frameId`: it only fires if a frame's `boundElements` lists the child, which normally doesn't happen.

## 3. Initial value when an element is created or restored
- `packages/element/src/newElement.ts:103` and `:156`: base default `frameId = null`, then assigned to the new element.
- `packages/excalidraw/data/restore.ts:474`: `frameId: element.frameId ?? null`.
- Set to the top-layer frame at creation (`topLayerFrame ? topLayerFrame.id : null`):
  - `packages/excalidraw/components/App.tsx:8865`, `:9025`, `:9209`, `:9232`, `:9404`
  - `packages/excalidraw/components/App.clipboard.ts:484` and `:534`
  - `packages/excalidraw/components/App.toolDrag.ts:67` (`getTopLayerFrameAtSceneCoords(...)?.id ?? null`)
- Set from an existing element or computed context:
  - `packages/excalidraw/components/App.bucketFill.ts:261`, using the value computed at `:227`.
  - `packages/excalidraw/components/App.text.ts:772`
  - `packages/excalidraw/components/App.drawshape.ts:204` (`line.frameId`)
  - `packages/excalidraw/actions/actionBoundText.tsx:313` (`textElement.frameId`)
  - `packages/element/src/flowchart.ts:740` (`startNode.frameId`)
  - `packages/element/src/convertToShape.ts:580`, `:623`, `:661`, `:701`
- Duplication overrides:
  - `packages/excalidraw/actions/actionDuplicateSelection.tsx:80`: `duplicateFrameId ?? origElement.frameId`.
  - `packages/excalidraw/components/App.duplicate.ts:209`: `duplicateElement.frameId ?? origElement.frameId`.

## Not direct writes
Undo/redo and collaboration sync can also change `frameId`, but only by applying whole-element property diffs or replacing elements. They never name the field, so they don't appear above. `App.tsx:6773-6778` and `zindex.ts:609` only read `frameId` to decide where to insert or reorder elements.