Perfect! Now let me create a comprehensive summary. Based on my analysis, here are all the places where an element's `frameId` is written (set, cleared, or changed) across packages/ and excalidraw-app/:

## frameId Mutation Locations

**Production Code Writes:**

1. packages/element/src/frame.ts:68 — `bindElementsToFramesAfterDuplication` via `mutateElement`
2. packages/element/src/frame.ts:591 — `addElementsToFrame` via `mutateElement`
3. packages/element/src/frame.ts:670 — `removeElementsFromFrame` via `mutateElement`
4. packages/element/src/transform.ts:855 — `transformElements` via `Object.assign`
5. packages/element/src/transform.ts:864 — `transformElements` via `Object.assign`
6. packages/element/src/duplicate.ts:598 — `duplicateElements` via direct assignment
7. packages/excalidraw/data/restore.ts:884 — `restore` via direct assignment
8. packages/excalidraw/clipboard.ts:182 — `paste` via object literal
9. packages/excalidraw/actions/actionDeleteSelected.tsx:121 — `actionDeleteSelected` via `newElementWith`
10. packages/excalidraw/actions/actionBoundText.tsx:313 — `actionBoundTextEdit` via `newElementWith`
11. packages/excalidraw/actions/actionDuplicateSelection.tsx:80 — `actionDuplicateSelection` via `newElementWith`
12. packages/excalidraw/components/App.tsx:3023 — `onMagicframeToolSelect` via `mutateElement`
13. packages/excalidraw/components/App.tsx:8865 — `insertNewElement` via object literal
14. packages/excalidraw/components/App.tsx:9025 — `drawElement` via object literal
15. packages/excalidraw/components/App.tsx:9209 — `handleDrawingCanvas` via object literal
16. packages/excalidraw/components/App.tsx:9232 — `handleDrawingCanvas` via object literal
17. packages/excalidraw/components/App.tsx:9404 — `drawElement` via object literal
18. packages/excalidraw/components/App.drawshape.ts:204 — `createLinearElement` via object literal
19. packages/excalidraw/components/App.clipboard.ts:484 — `pasteAsPlaintext` via object literal
20. packages/excalidraw/components/App.clipboard.ts:534 — `pasteElements` via object literal
21. packages/excalidraw/components/App.toolDrag.ts:67 — `dragNewElement` via object literal
22. packages/excalidraw/components/App.duplicate.ts:209 — `duplicateElements` via object literal