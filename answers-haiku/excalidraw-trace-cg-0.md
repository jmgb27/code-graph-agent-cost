Based on my analysis of the Excalidraw codebase, here's the complete trace of pasting an image from the clipboard:

## **Image Paste Flow: Clipboard → Canvas**

### **1. Paste Event Reception**
- **packages/excalidraw/components/App.clipboard.ts:81** — `onCut`, `onCopy`, `onPaste` event handlers detect clipboard events
- **packages/excalidraw/clipboard.ts:467** — `parseDataTransferEvent` extracts clipboard items (files and text)
  - Normalizes files with **packages/excalidraw/data/blob.ts:486** (`normalizeFile`)
  - Gets file handles with **packages/excalidraw/clipboard.ts:485** (`getFileHandle`)

### **2. Clipboard Parsing**
- **packages/excalidraw/clipboard.ts:523** — `parseClipboard` determines clipboard content type
- **packages/excalidraw/clipboard.ts:331** — `parseClipboardEventTextData` parses text/HTML content
- Returns `ClipboardData` (**packages/excalidraw/clipboard.ts:47**) with `files`, `elements`, or `mixedContent`

### **3. Image File Insertion**
- **packages/excalidraw/components/App.clipboard.ts:112** — `insertClipboardContent` routes image files to `insertImages`
- **packages/excalidraw/components/App.clipboard.ts:171** — calls `app.insertImages(imageFiles, sceneX, sceneY)`

### **4. Image Element Creation - Placeholder Phase**
- **packages/excalidraw/components/App.tsx:11898** — `insertImages` creates placeholder elements
- **packages/excalidraw/components/App.tsx:8988** — `newImagePlaceholder` generates placeholder with:
  - `status: "pending"` (**packages/element/src/types.ts:166**)
  - `fileId: null` (**packages/element/src/types.ts:164**)
  - Grid-positioned size (100 / zoom level) (**packages/excalidraw/components/App.tsx:9012**)
- **packages/element/src/newElement.ts:673** — `newImageElement` creates `ExcalidrawImageElement` (**packages/element/src/types.ts:161**)
- **packages/excalidraw/components/App.tsx:11911** — placeholders inserted into scene via `insertNewElements`

### **5. Image Initialization & File ID Generation**
- **packages/excalidraw/components/App.tsx:11563** — `initializeImage` processes actual image file
- **packages/excalidraw/components/App.tsx:11590** — generates `FileId` via `generateIdFromFile` (or custom `generateIdForFile` prop)
- **packages/excalidraw/data/blob.ts:357** — `resizeImageFile` resizes if needed (respects `imageOptions.maxWidthOrHeight`)
- **packages/excalidraw/data/blob.ts:276** — `getDataURL` converts file to base64 DataURL

### **6. Binary File Storage**
- **packages/excalidraw/components/App.tsx:11636** — `addMissingFiles` creates `BinaryFileData` (**packages/excalidraw/types.ts:118**):
  ```
  {
    id: FileId,
    mimeType: IMAGE_MIME_TYPES | MIME_TYPES.binary,
    dataURL: DataURL (base64 encoded),
    created: Date.now(),
    lastRetrieved: Date.now()
  }
  ```
- **packages/excalidraw/components/App.tsx:647** — stored in `app.files: BinaryFiles` (**packages/excalidraw/types.ts:146**)
- **packages/excalidraw/types.ts:146** — `BinaryFiles = Record<FileId, BinaryFileData>`

### **7. Image Cache Population**
- **packages/excalidraw/components/App.tsx:11646** — `addNewImagesToImageCache` queues file
- **packages/element/src/image.ts:36** — `updateImageCache` loads HTMLImageElement asynchronously
- **packages/element/src/image.ts:21** — `loadHTMLImageElement` creates Image object with dataURL
- **packages/excalidraw/components/App.tsx:648** — stored in `app.imageCache: Map<FileId, HTMLImageElement>`

### **8. Update Image Element**
- **packages/excalidraw/components/App.tsx:11699** — `getLatestInitializedImageElement` updates element with `fileId`
- **packages/element/src/newElement.ts:683** — element now has:
  - `fileId: FileId` (from **packages/element/src/types.ts:164**)
  - `status: "saved"` (from **packages/element/src/types.ts:166**)
  - Natural dimensions calculated from loaded image

### **9. Collaboration Synchronization**
- **excalidraw-app/collab/Collab.tsx:795** — `loadImageFiles` fetches files from Firebase for remote users
- **excalidraw-app/data/FileManager.ts:92** — `saveFiles` identifies image elements and queues files
- **excalidraw-app/data/firebase.ts:145** — `saveFilesToFirebase` uploads files to Firebase Storage:
  - Path: `files/rooms/{roomId}/{fileId}`
  - Uses encryption key from room (`roomKey`)
- **excalidraw-app/data/firebase.ts:187** — `saveToFirebase` saves elements with `saveCollabRoomToFirebase`

### **10. Canvas Rendering**
- **packages/element/src/renderElement.ts:963** — `renderElement` checks image status
- **packages/element/src/renderElement.ts:95** — `isPendingImageElement` checks if `imageCache.has(fileId)`
- **packages/excalidraw/renderer/renderNewElementScene.ts:101** — `renderNewElementScene` renders preview during insertion
- **packages/element/src/renderElement.ts** calls `drawElement` to render HTMLImageElement to canvas context

### **Key Data Structures**

| Structure | Location | Purpose |
|-----------|----------|---------|
| `ExcalidrawImageElement` | packages/element/src/types.ts:161 | Canvas element with `fileId`, `status`, `crop`, `scale` |
| `BinaryFileData` | packages/excalidraw/types.ts:118 | File metadata + base64 `dataURL` |
| `BinaryFiles` | packages/excalidraw/types.ts:146 | Map of `FileId` → `BinaryFileData` |
| `FileId` | packages/element/src/types.ts:439 | File identifier (branded string from SHA digest) |
| `ImageCache` | packages/excalidraw/components/App.tsx:648 | Map of `FileId` → HTMLImageElement Promise |

### **State Transitions**
```
File on Clipboard
    ↓
parseDataTransferEvent (packages/excalidraw/clipboard.ts:467)
    ↓
insertClipboardContent (packages/excalidraw/components/App.clipboard.ts:112)
    ↓
insertImages (packages/excalidraw/components/App.tsx:11898)
  ├─ newImagePlaceholder → status: "pending", fileId: null
  └─ initializeImage → status: "saved", fileId: FileId
    ├─ generateIdFromFile → FileId
    ├─ getDataURL → DataURL
    ├─ addMissingFiles → BinaryFiles[fileId]
    └─ updateImageCache → HTMLImageElement
        ↓
    renderElement (packages/element/src/renderElement.ts:963)
        ↓
    Canvas (interactive/static)
```