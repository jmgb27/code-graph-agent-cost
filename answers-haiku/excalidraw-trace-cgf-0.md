## Image Paste Flow Trace

Here's the complete flow from clipboard paste to canvas rendering with collaboration:

### 1. **Paste Event Capture**
- **packages/excalidraw/components/App.clipboard.ts:304** — `pasteFromClipboard()` handles the paste event
- Calls `parseDataTransferEvent()` to extract clipboard items (files, text, etc.)

### 2. **File Parsing & Image Extraction**
- **packages/excalidraw/clipboard.ts:467** — `parseDataTransferEvent()` processes clipboard data
  - Identifies file items from clipboard/drag-and-drop
  - Normalizes files via `normalizeFile()`
- **packages/excalidraw/components/App.clipboard.ts:112** — `insertClipboardContent()` routes to image handling
  - Line 158: Extracts image files from parsed data
  - Line 171: Calls `this.app.insertImages(imageFiles, sceneX, sceneY)`

### 3. **Image Element Insertion & Placeholder Creation**
- **packages/excalidraw/components/App.tsx:11898** — `insertImages()` orchestrates insertion
  - Line 11905: Creates placeholder image elements via `newImagePlaceholder()`
  - Line 11911: Inserts placeholders into scene using `insertNewElements()`

### 4. **Image Initialization & File Data Generation**
- **packages/excalidraw/components/App.tsx:11563** — `initializeImage()` processes each image
  - Line 11590: Generates unique `fileId` via `generateIdFromFile()` (packages/excalidraw/data/blob.ts:261)
  - Line 11606: Resizes image if needed via `resizeImageFile()`
  - Line 11626: Converts image to DataURL via `getDataURL()`

### 5. **BinaryFiles Storage (In-Memory)**
- **packages/excalidraw/components/App.tsx:11636** — `addMissingFiles()` stores file data
  - Creates `BinaryFileData` object with: `mimeType`, `id`, `dataURL`, `created`, `lastRetrieved`
  - Stores in `this.files` (type: `BinaryFiles` = Record<FileId, BinaryFileData>)
  - **packages/excalidraw/types.ts:146** — BinaryFiles type definition

### 6. **Image Cache Loading**
- **packages/excalidraw/components/App.tsx:11649** — `updateImageCache()` loads image into memory
  - **packages/element/src/image.ts:36** — `updateImageCache()` implementation
  - Line 60: `loadHTMLImageElement()` creates HTMLImageElement from DataURL
  - Stores in `this.imageCache` for fast rendering

### 7. **Scene Update & Element Replacement**
- **packages/excalidraw/components/App.tsx:11941** — `updateScene()` updates canvas state
  - **packages/excalidraw/components/App.tsx:4936** — `updateScene()` definition
  - Replaces placeholder with initialized image element
  - Updates `selectedElementIds` to highlight the new image
  - **packages/element/src/Scene.ts:271** — `replaceAllElements()` updates scene graph
  - **packages/element/src/Scene.ts:303** — `triggerUpdate()` triggers re-render

### 8. **Canvas Rendering**
- **packages/excalidraw/components/App.tsx:2309** — React `render()` method called
- **packages/excalidraw/scene/Renderer.ts:42** — `Renderer` draws elements
- Image HTML element from cache is rendered via canvas drawing primitives

### 9. **Collaboration & Persistence**

**Local Storage:**
- **excalidraw-app/data/LocalData.ts:137** — `LocalData.save()` persists to localStorage
- Stores elements and appState with file data

**Firebase Collaboration:**
- **excalidraw-app/collab/Collab.tsx:323** — `saveCollabRoomToFirebase()` syncs to server
- **excalidraw-app/data/firebase.ts:187** — `saveToFirebase()` encrypts and stores
  - Line 179: Encrypts elements using room key
  - Line 212/234: Uploads to Firestore document
- **excalidraw-app/collab/Portal.tsx:104** — `queueFileUpload()` uploads binary file data
  - **excalidraw-app/collab/Collab.tsx:795** — `loadImageFiles()` fetches from server
  - **excalidraw-app/data/firebase.ts:160** — `saveFilesToFirebase()` stores in Firebase Storage
  - File status updated to `"saved"` when complete (Portal.tsx:129)

### Key File References

| Component | File | Lines |
|-----------|------|-------|
| Paste Handler | `packages/excalidraw/components/App.clipboard.ts` | 304-362 |
| Image Insertion | `packages/excalidraw/components/App.tsx` | 11898-11960 |
| Image Initialization | `packages/excalidraw/components/App.tsx` | 11563-11685 |
| Binary File Data Type | `packages/excalidraw/types.ts` | 118-146 |
| Image Cache Update | `packages/element/src/image.ts` | 21-89 |
| Scene Update | `packages/element/src/Scene.ts` | 271-309 |
| Firebase Storage | `excalidraw-app/data/firebase.ts` | 58-235 |
| Collaboration Sync | `excalidraw-app/collab/Collab.tsx` | 323-363 |