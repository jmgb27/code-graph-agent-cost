I've found all the direct writes and the helpers that call them, and I'm writing up the answer now.

There are no `frameId` writes in `excalidraw-app/`; the string doesn't appear there at all. Every write is in `packages/`. Tests, snapshots and locale files are excluded below.

## 1. Core helpers that write `frameId` (in `packages/element/src/frame.ts`)

| Location | What it writes |
|---|---|
| `packages/element/src/frame.ts:67-69` | `bindElementsToFramesAfterDuplication` sets each duplicate to the duplicated frame's id, or `null` |
| `packages/element/src/frame.ts:589-592` | `addElementsToFrame` sets `frameId: frame.id` on the elements and their bound text |
| `packages/element/src/frame.ts:668-671` | `removeElementsFromFrame` sets `frameId: null` on the elements and their bound text |
| `packages/element/src/frame.ts:675-680` | `removeAllElementsFromFrame` goes through `removeElementsFromFrame` |
| `packages/element/src/frame.ts:684-690` | `replaceAllElementsInFrame` calls remove-all, then add |
| `packages/element/src/frame.ts:738` | `updateFrameMembershipOfSelectedElements` goes through `removeElementsFromFrame` |

## 2. Other direct writes (mutating existing elements)

- `packages/element/src/duplicate.ts:597-598`: sets `updates.frameId = null` when the duplicate's frame was vetoed (`onDuplicate`).
- `packages/element/src/binding.ts:2513`: `unbindAffected` runs `updateElementWith(boundElement, { [bindingProp]: null })`. `bindingProp` can be `"frameId"` (the visitor is at `binding.ts:2419-2421`), so this clears `frameId` when the frame is deleted. The main caller is `fixBindingsAfterDeletion`.
- `packages/element/src/transform.ts:855` and `:864`: `Object.assign(..., { frameId: frame.id })` on frame children and their bound elements, for the skeleton → element API.
- `packages/excalidraw/data/restore.ts:884`: `repairFrameMembership` sets `element.frameId = null` when the frame doesn't exist (called at `:1023`).
- `packages/excalidraw/data/restore.ts:474`: normalises it on restore, `frameId: element.frameId ?? null`.
- `packages/excalidraw/actions/actionDeleteSelected.tsx:121`: when a frame is deleted, its children get `newElementWith(el, { frameId: null })`.
- `packages/excalidraw/actions/actionDuplicateSelection.tsx:80`: `frameId: duplicateFrameId ?? origElement.frameId`.
- `packages/excalidraw/clipboard.ts:181-183`: when copying without the containing frame, the copied element gets `frameId: null`.
- `packages/excalidraw/components/App.tsx:3023`: wrapping the selection in a new magic frame runs `mutateElement(child, { frameId: frame.id })`.
- `packages/excalidraw/components/App.duplicate.ts:209`: alt-drag duplicate resets to `duplicateElement.frameId ?? origElement.frameId`.
- `packages/excalidraw/components/App.clipboard.ts:572-581`: re-laid-out pasted text gets `newElementWith(..., { frameId })`.

## 3. Set when a new element is created

- `packages/element/src/newElement.ts:103` and `:156`: the base factory defaults to `frameId = null`.
- `packages/excalidraw/components/App.tsx:8865`, `:9025`, `:9209`, `:9232`, `:9404`: `frameId: topLayerFrame ? topLayerFrame.id : null` when creating shapes, linear, freedraw, image and embeddable elements.
- `packages/excalidraw/components/App.clipboard.ts:484` and `:534`: pasted elements and pasted text get `topLayerFrame?.id`.
- `packages/excalidraw/components/App.text.ts:720-726` and `:772`: new text gets the frame's id, unless its container is in a different frame.
- `packages/excalidraw/components/App.toolDrag.ts:67`: tool drag uses `getTopLayerFrameAtSceneCoords(center)?.id ?? null`.
- `packages/excalidraw/components/App.drawshape.ts:204`: copies `line.frameId`.
- `packages/excalidraw/components/App.bucketFill.ts:227-230` and `:261`: uses the owner's frame.
- `packages/element/src/convertToShape.ts:553` (computed), then `:580`, `:623`, `:661`, `:701`: converted shapes get the enclosing frame.
- `packages/element/src/flowchart.ts:740`: new flowchart nodes get `startNode.frameId`.
- `packages/excalidraw/actions/actionBoundText.tsx:313`: the new container gets `textElement.frameId`.

## 4. Call sites that change `frameId` through the helpers in section 1

- `App.tsx:10865` and `:10992` call `addElementsToFrame`.
- `App.tsx:10917` calls `removeElementsFromFrame`.
- `App.tsx:11009` and `:11035` call `updateFrameMembershipOfSelectedElements`.
- `App.tsx:11046` calls `replaceAllElementsInFrame`.
- `App.duplicate.ts:131` calls `addElementsToFrame`.
- `actions/actionFrame.ts:83` calls `removeAllElementsFromFrame`, and `:166` calls `addElementsToFrame`.
- `actions/actionGroup.tsx:148` calls `removeElementsFromFrame`, and `:274` calls `replaceAllElementsInFrame`.
- `actions/actionAlign.tsx:72`, `actionDistribute.tsx:66`, and `actionFlip.ts:36` and `:61` call `updateFrameMembershipOfSelectedElements`.
- `components/Stats/Dimension.tsx:209` and `:306` call `replaceAllElementsInFrame`.
- `components/Stats/MultiDimension.tsx:292` and `:448` call `replaceAllElementsInFrame`.
- `element/src/duplicate.ts:447` calls `bindElementsToFramesAfterDuplication`.
- `actions/actionDeleteSelected.tsx:278` and `App.text.ts:330` call `fixBindingsAfterDeletion`, which reaches the `frameId` clear in `binding.ts`.

## Not writes (for completeness)

- `packages/excalidraw/renderer/staticScene.ts:486` builds a temporary label object for rendering only.
- Undo/redo (`packages/element/src/delta.ts`) also restores `frameId`, but it applies property changes generically and never names `frameId`.