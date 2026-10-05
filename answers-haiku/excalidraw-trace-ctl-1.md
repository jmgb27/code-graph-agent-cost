## Image Paste Flow Trace

### 1. **Clipboard Paste Event**
- **File**: `packages/excalidraw/components/App.clipboard.ts`
- **Line**: 304-362
- **Function**: `AppClipboard.pasteFromClipboard()`
- **Key Steps**:
  - Captures `ClipboardEvent`
  - Calls `parseDataTransferEvent()` to extract clipboard data (line 338)
  - Calls `parseClipboard()` to process clipboard content (line 342)
  - Invokes `insertClipboardContent()` with parsed data (line 354)

### 2. **Clipboard Content Routing**
- **File**: `packages/excalidraw/components/App.clipboard.ts`
- **Line**: 112-281
- **Function**: `AppClipboard.insertClipboardContent()`
- **Key Steps**:
  - Detects image files in `dataTransferFiles` (line 158)
  - For image files, calls `this.app.insertImages()` (line 171)

### 3. **Create Image Placeholders & Initialize**
- **File**: `packages/excalidraw/components/App.tsx`
- **Line**: 11898-11960
- **Function**: `App.insertImages()`
- **Key Steps**:
  - Creates placeholder image elements (line 11905-11910)
  - Inserts placeholders into scene (line 11911)
  - For each placeholder, calls `initializeImage()` with normalized file (line 11917-11919)
  - Positions initialized images and updates scene (line 11933-11954)

### 4. **Initialize Image & Store File Data**
- **File**: `packages/excalidraw/components/App.tsx`
- **Line**: 11563-11685
- **Function**: `App.initializeImage()`
- **Key Steps**:
  - Generates unique file ID from image data (line 11590-11592)
  - Resizes image if needed (line 11606-11614)
  - Converts image to data URL (line 11625-11626)
  - **Stores file in BinaryFiles**: Calls `addMissingFiles()` (line 11636-11644)
    - Creates file object with: `{ id, mimeType, dataURL, created, lastRetrieved }`
  - Updates image cache (line 11649-11651)
  - Gets natural image dimensions from cache (line 11669-11675)

### 5. **Store in BinaryFiles Map**
- **File**: `packages/excalidraw/components/App.tsx`
- **Line**: 4897-4934
- **Function**: `App.addMissingFiles()`
- **Key Steps**:
  - Takes `BinaryFiles` or `BinaryFileData[]` array
  - Merges into `this.files` map (line 4901, 4931)
  - Each file stored with key = `fileId`, value = `BinaryFileData` (line 4911-4912)
  - BinaryFileData includes: `id`, `mimeType`, `dataURL`, `created`, `lastRetrieved`

### 6. **Load & Cache Image**
- **File**: `packages/element/src/image.ts`
- **Line**: 36-89
- **Function**: `updateImageCache()`
- **Key Steps**:
  - Takes `fileIds`, `files` (BinaryFiles), and `imageCache` (line 37-43)
  - For each fileId, retrieves `fileData` from `files` map (line 50)
  - Calls `loadHTMLImageElement(fileData.dataURL)` (line 60)
  - Stores Promise in cache immediately (line 67)
  - Awaits Promise resolution and stores resolved image (line 69, 71)

### 7. **Load HTMLImageElement**
- **File**: `packages/element/src/image.ts`
- **Line**: 21-32
- **Function**: `loadHTMLImageElement()`
- **Key Steps**:
  - Creates new `HTMLImageElement` (line 23)
  - Sets `image.src = dataURL` (line 30)
  - Resolves Promise when image loads (line 24-25)

### 8. **Export for Collaboration/Persistence**
- **File**: `packages/excalidraw/components/App.tsx`
- **Line**: 4262-4474
- **Function**: `App.componentDidUpdate()`
- **Key Steps**:
  - Commits elements to store (line 4464)
  - Calls `props.onChange()` with elements, state, **and `this.files`** (line 4471)
  - Triggers `onChangeEmitter` with same data (line 4472)
  - **BinaryFiles exported here**: Consumer receives all image data via `files` parameter

### 9. **Render on Canvas**
- **File**: `packages/element/src/renderElement.ts`
- **Line**: 517-620
- **Function**: `drawElement()` - "image" case
- **Key Steps**:
  - Gets image cache entry using `element.fileId` (line 519-522)
  - Retrieves HTMLImageElement from cache (line 523-525)
  - If resolved (not Promise), draws to canvas:
    - Handles rounded corners (line 528-538)
    - Extracts crop region if present (line 540-547)
    - Calls `context.drawImage()` with HTMLImageElement (line 607-616)
    - Handles dark mode SVG inversion (line 553-601)

### Data Flow Summary

```
Clipboard Paste Event
         ↓
parseDataTransferEvent() [clipboard.ts:338]
         ↓
parseClipboard() [clipboard.ts:342]
         ↓
insertClipboardContent() [App.clipboard.ts:112]
         ↓
insertImages() [App.tsx:11898]
         ↓
initializeImage() [App.tsx:11563]
         ↓
addMissingFiles() → this.files[fileId] = BinaryFileData [App.tsx:4897]
         ↓
updateImageCache() [image.ts:36]
         ↓
loadHTMLImageElement() + imageCache[fileId] = resolved image [image.ts:21]
         ↓
onChange(elements, state, files) [App.tsx:4471] ← FILES EXPORTED HERE
         ↓
drawElement() + context.drawImage(cachedImage) [renderElement.ts:517]
         ↓
Image renders on canvas
```