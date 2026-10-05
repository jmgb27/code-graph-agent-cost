Based on my comprehensive search, here are all the places where an element's `frameId` is written (set, cleared, or changed) across the codebase:

## Direct Assignments

- **packages/excalidraw/data/restore.ts:884** — `element.frameId = null;`
- **packages/element/src/duplicate.ts:598** — `updates.frameId = null;`

## Object.assign Operations

- **packages/element/src/transform.ts:855** — `Object.assign(elementInFrame, { frameId: frame.id });`
- **packages/element/src/transform.ts:864** — `Object.assign(ele, { frameId: frame.id });`

## Mutation/Creation Function Calls

- **packages/excalidraw/actions/actionDeleteSelected.tsx:121** — `newElementWith(el, { frameId: null })`
- **packages/excalidraw/components/App.tsx:3023** — `this.scene.mutateElement(child, { frameId: frame.id });`

## Object Literals (Element Creation)

- **packages/element/src/frame.ts:68** — `frameId: nextFrameId ?? null,`
- **packages/element/src/frame.ts:591** — `frameId: frame.id,`
- **packages/element/src/frame.ts:670** — `frameId: null,`
- **packages/excalidraw/data/restore.ts:474** — `frameId: element.frameId ?? null,`
- **packages/excalidraw/actions/actionDuplicateSelection.tsx:80** — `frameId: duplicateFrameId ?? origElement.frameId,`
- **packages/excalidraw/clipboard.ts:182** — `frameId: null,`
- **packages/excalidraw/components/App.tsx:8865** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.tsx:9025** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.tsx:9209** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.tsx:9232** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.tsx:9404** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.clipboard.ts:484** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.clipboard.ts:534** — `frameId: topLayerFrame ? topLayerFrame.id : null,`
- **packages/excalidraw/components/App.drawshape.ts:204** — `frameId: line.frameId,`
- **packages/excalidraw/components/App.duplicate.ts:209** — `frameId: duplicateElement.frameId ?? origElement.frameId,`
- **packages/excalidraw/components/App.toolDrag.ts:67** — `frameId: app.getTopLayerFrameAtSceneCoords(center)?.id ?? null,`
- **packages/excalidraw/actions/actionBoundText.tsx:313** — `frameId: textElement.frameId,`
- **packages/element/src/flowchart.ts:740** — `frameId: startNode.frameId,`
- **packages/excalidraw/renderer/staticScene.ts:486** — `frameId: element.frameId,`