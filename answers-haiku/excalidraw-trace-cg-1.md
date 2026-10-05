Now I have enough context. Let me compile the complete trace of how images are pasted from clipboard to rendered on canvas.

## Image Paste Flow: Clipboard to Canvas Rendering

### 1. **Paste Event & Event Listener**
- **packages/excalidraw/components/App.tsx:3961** - `addEventListeners()` registers paste event via `addEventListener(this.excalidrawContainerRef.current, EVENT.PASTE, this.clipboard.onPaste, ...)`
- The actual paste event handler is in **packages/excalidraw/components/App.clipboard.ts** (referenced but not shown in source)

### 2. **Data Transfer Parsing**
- **packages/excalidraw/clipboard.ts:467** - `parseDataTransferEvent()` extracts clipboard data, including image files (kind: "file")
  - For clipboard events: extracts from `event.clipboardData?.items`
  - Normalizes files via `normalizeFile()` (**packages/excalidraw/data/blob.ts**)
  - Returns `ParsedDataTranferList` with file data and MIME type

- **packages/excalidraw/clipboard.ts:523** - `parseClipboard()` processes the parsed list

### 3. **Clipboard Content Router**
- **packages/excalidraw/components/App.clipboard.ts:112** - `insertClipboardContent()` routes parsed data
  - For image files: calls **packages/excalidraw/components/App.tsx:11898** - `insertImages()`

### 4. **Placeholder Creation & File Processing**
- **packages/excalidraw/components/App.tsx:11898** - `insertImages()` async flow:
  1. Creates placeholders using **packages/excalidraw/components/App.tsx:8988** - `newImagePlaceholder()` → calls **packages/element/src/newElement.ts:673** - `newImageElement()` → creates `ExcalidrawImageElement` with status: "pending", fileId: null
  2. Inserts placeholders into scene via **packages/excalidraw/components/App.tsx:6755** - `insertNewElements()` → **packages/element/src/Scene.ts:342** - `insertElementsAtIndex()`

### 5. **Image Initialization & BinaryFiles Storage**
- **packages/excalidraw/components/App.tsx:11563** - `initializeImage()` processes each image file:
  1. Generates file ID via **packages/excalidraw/data/blob.ts:261** - `generateIdFromFile()` (SHA-1 digest)
  2. Converts File to DataURL via **packages/excalidraw/data/blob.ts:276** - `getDataURL()` using FileReader
  3. Creates `BinaryFileData` object: `{ id, mimeType, dataURL, created, lastRetrieved }`
  4. Calls **packages/excalidraw/components/App.tsx:4897** - `addMissingFiles()` → stores in **packages/excalidraw/components/App.tsx:647** - `this.files` (BinaryFiles record)

### 6. **Element & Cache Updates**
- **packages/excalidraw/components/App.tsx:11807** - `addNewImagesToImageCache()` calls:
  - **packages/element/src/image.ts:36** - `updateImageCache()` with fileIds
    - Calls **packages/element/src/image.ts:21** - `loadHTMLImageElement(dataURL)` to create HTMLImageElement
    - Caches in **packages/excalidraw/components/App.tsx:648** - `this.imageCache` (Map<FileId, {image, mimeType}>)

- Scene replaces placeholder with initialized element via **packages/excalidraw/components/App.tsx:3110** - `syncActionResult()` → **packages/element/src/Scene.ts:271** - `replaceAllElements()`

### 7. **State & History**
- **packages/excalidraw/components/App.tsx:4936** - `updateScene()` with:
  - New elements (image with fileId populated, status: "saved")
  - CaptureUpdateAction.IMMEDIATELY → **packages/element/src/store.ts:440** - `Store.create()` → history capture for undo/redo

### 8. **Rendering Pipeline**
- **packages/element/src/Scene.ts:303** - `triggerUpdate()` → calls registered render callbacks
- **packages/excalidraw/components/App.tsx:3829** - `this.scene.onUpdate(this.triggerRender)` → triggers React render

- React renders canvases:
  - **packages/excalidraw/components/canvases/NewElementCanvas.tsx:27** - Renders new elements via **packages/excalidraw/renderer/renderNewElementScene.ts** (throttled)
  - Main canvas renders via **packages/excalidraw/scene/Renderer.ts:42** - `Renderer` class:
    - **packages/excalidraw/scene/Renderer.ts:57** - `getVisibleElementsWithRenderOffsets()` filters visible elements
    - Iterates through elements, checks **packages/element/src/renderElement.ts:95** - `isPendingImageElement()` (has fileId but not in imageCache)
    - Renders using **packages/element/src/image.ts** - `updateImageCache` for pending images

### 9. **Collaboration Sync**
- `this.files` (BinaryFiles) passed to **packages/excalidraw/data/json.ts:52** - `serializeAsJSON()` when exporting
- Sent via Portal/WebSocket for collaborative editing (**excalidraw-app/collab/Portal.tsx** + **excalidraw-app/collab/Collab.tsx**)
- Remote clients receive via **packages/excalidraw/components/App.tsx:4936** - `updateScene()` with replaceFiles flag

### Key Type Definitions
- **packages/excalidraw/types.ts:146** - `BinaryFiles = Record<ExcalidrawElement["id"], BinaryFileData>`
- **packages/excalidraw/types.ts:118** - `BinaryFileData { mimeType, id, dataURL, created, lastRetrieved, version }`
- **packages/element/src/types.ts:161** - `ExcalidrawImageElement` with fileId, status ("pending"|"saved"|"error"), scale, crop