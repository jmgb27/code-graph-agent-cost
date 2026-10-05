Based on my comprehensive search through the codebase, here are all the places where an element's `frameId` is written (set, cleared, or changed):

## Direct Assignments
- **packages/element/src/duplicate.ts:598** - `updates.frameId = null;`
- **packages/excalidraw/data/restore.ts:884** - `element.frameId = null;`

## Via mutateElement() calls
- **packages/element/src/frame.ts:68** - `mutateElement(nextElement, nextElementMap, { frameId: nextFrameId ?? null })`
- **packages/element/src/frame.ts:591** - `mutateElement(element, elementsMap, { frameId: frame.id })`
- **packages/element/src/frame.ts:670** - `mutateElement(element, elementsMap, { frameId: null })`
- **packages/element/src/flowchart.ts:740** - `mutateElement(node, elementsMap, { frameId: startNode.frameId })`
- **packages/excalidraw/clipboard.ts:182** - `mutateElement(copiedElement, elementsMap, { frameId: null })`
- **packages/excalidraw/components/App.tsx:3023** - `this.scene.mutateElement(child, { frameId: frame.id })`

## Via Object.assign() calls
- **packages/element/src/transform.ts:855** - `Object.assign(elementInFrame, { frameId: frame.id })`
- **packages/element/src/transform.ts:864** - `Object.assign(ele, { frameId: frame.id })`

## Via Element Creation Functions (newElement, newArrowElement, etc.)
- **packages/excalidraw/components/App.tsx:8865** - `newFreeDrawElement({ frameId: ... })`
- **packages/excalidraw/components/App.tsx:9025** - `newImageElement({ frameId: ... })`
- **packages/excalidraw/components/App.tsx:9209** - `newArrowElement({ frameId: ... })`
- **packages/excalidraw/components/App.tsx:9232** - `newLinearElement({ frameId: ... })`
- **packages/excalidraw/components/App.tsx:9404** - baseElementAttributes with `frameId: ...`
- **packages/excalidraw/components/App.drawshape.ts:204** - `newArrowElement({ frameId: line.frameId })`
- **packages/excalidraw/components/App.clipboard.ts:484** - `newTextElement({ frameId: ... })`
- **packages/excalidraw/actions/actionBoundText.tsx:313** - `newElement({ frameId: textElement.frameId })`
- **packages/excalidraw/data/restore.ts:474** - element restoration with `frameId: element.frameId ?? null`

## Via newElementWith() calls
- **packages/excalidraw/components/App.clipboard.ts:534** - `newElementWith(element, { frameId: ... })`
- **packages/excalidraw/actions/actionDeleteSelected.tsx:121** - `newElementWith(el, { frameId: null })`

## Via duplicateElements() overrides
- **packages/excalidraw/components/App.duplicate.ts:209** - duplication overrides: `frameId: duplicateElement.frameId ?? origElement.frameId`
- **packages/excalidraw/actions/actionDuplicateSelection.tsx:80** - duplication overrides: `frameId: duplicateFrameId ?? origElement.frameId`

## Via Element Creation Functions (sticky notes)
- **packages/excalidraw/components/App.toolDrag.ts:67** - `newStickyNoteElement({ frameId: ... })`