I've finished searching and am writing up the list now. It's based on a regex search plus reading the code around each hit, with test files left out. `excalidraw-app/` has no `frameId` references at all, so every write is under `packages/`.

## 1. Main frame-membership helpers (`packages/element/src/frame.ts`)
- `frame.ts:67-69`: `bindElementsToFramesAfterDuplication` points duplicated children at the duplicated frame's id, or sets `null` if that frame wasn't duplicated. Called from `duplicate.ts:447`.
- `frame.ts:589-592`: `addElementsToFrame` sets `frameId: frame.id` on each element not already in that frame.
- `frame.ts:668-671`: `removeElementsFromFrame` sets `frameId: null` on the elements and their bound text.
- Wrappers that end up calling the two above:
  - `removeAllElementsFromFrame` (`frame.ts:680`)
  - `replaceAllElementsInFrame` (`frame.ts:689-690`)
  - `updateFrameMembershipOfSelectedElements` (`frame.ts:738`)

Where those helpers are called:
- `App.tsx:10865`, `:10917`, `:10992`, `:11009`, `:11035`, `:11046`: dragging and resizing on pointer-up.
- `App.duplicate.ts:131`: Alt-drag duplicate.
- `actionFrame.ts:83`: remove all from frame.
- `actionFrame.ts:166`: wrap selection in a frame.
- `actionGroup.tsx:148` and `:274`: group and ungroup.
- `actionFlip.ts:36` and `:61`, `actionAlign.tsx:72`, `actionDistribute.tsx:66`.
- `Stats/Dimension.tsx:209` and `:306`, `Stats/MultiDimension.tsx:292` and `:448`.

## 2. Direct mutations and updates
- `packages/excalidraw/components/App.tsx:3023`: sets `frameId: frame.id` on the selected children when a magic frame is created.
- `packages/excalidraw/actions/actionDeleteSelected.tsx:121`: sets `frameId: null` on the children of frames being deleted.
- `packages/excalidraw/clipboard.ts:181-183`: sets `frameId: null` on copied elements whose frame isn't being copied.
- `packages/excalidraw/data/restore.ts:884`: `repairFrameMembership` sets `element.frameId = null` when the frame doesn't exist.
- `packages/excalidraw/data/restore.ts:474`: restore normalizes the value to `element.frameId ?? null`.
- `packages/element/src/duplicate.ts:597-598`: sets `updates.frameId = null` when a duplicate's frame was vetoed.
- `packages/element/src/transform.ts:855` and `:864`: `Object.assign(..., { frameId: frame.id })` for frame children and their bound elements (converting skeleton elements into real ones).
- `packages/element/src/binding.ts` (`frameId` is one of the binding props listed at `:2362-2376`):
  - `:2514` (`BoundElement.rebindAffected`) sets `[bindingProp]: null`, which includes `frameId`, when the frame is missing or deleted.
  - `:2590` (`BindableElement.unbindAffected`) sets `[bindingProp]: null` on the children of a frame being unbound.
  - These are reached through `fixBindingsAfterDeletion` (`binding.ts:2321`, called from `actionDeleteSelected.tsx:278` and `App.text.ts:330`) and through undo/redo in `ElementsDelta` (`delta.ts:1938-2031`).

## 3. Duplication overrides
- `packages/excalidraw/actions/actionDuplicateSelection.tsx:80`: `frameId: duplicateFrameId ?? origElement.frameId`
- `packages/excalidraw/components/App.duplicate.ts:209`: `frameId: duplicateElement.frameId ?? origElement.frameId`

## 4. Initial value when an element is created
- `packages/element/src/newElement.ts:103` and `:156`: the base constructor defaults it to `null`.
- `packages/excalidraw/components/App.tsx:8865`, `:9025`, `:9209`, `:9232`, `:9404`: set to the top-layer frame at the pointer, or `null`.
- `packages/excalidraw/components/App.clipboard.ts:484` and `:534` (top-layer frame); `:581` (copied from an existing text element).
- `packages/excalidraw/components/App.text.ts:772`: new text element.
- `packages/excalidraw/components/App.toolDrag.ts:67`: top-layer frame at the drop point.
- `packages/excalidraw/components/App.bucketFill.ts:227-230` and `:261`: the owner's frame, or the top-layer frame.
- `packages/excalidraw/components/App.drawshape.ts:204`: copied from the source line.
- `packages/excalidraw/actions/actionBoundText.tsx:313`: container created for a text element takes the text's `frameId`.
- `packages/element/src/flowchart.ts:740`: new flowchart node takes `startNode.frameId`.
- `packages/element/src/convertToShape.ts:580`, `:623`, `:661`, `:701`: converted shapes keep the original `frameId`.

## Not included
Two generic mechanisms can also change `frameId`, but neither mentions it by name:
- Undo/redo and collaboration apply element diffs through `delta.ts`.
- `restore` spreads the whole element.

I didn't count read-only hits, such as `zindex.ts`, `renderer/staticScene.ts:486` and `App.tsx:6773`.