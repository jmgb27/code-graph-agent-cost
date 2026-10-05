Here's the path from the paste event to the image on the canvas. Paths are relative to the repo root.

## 1. Paste event → clipboard parsing

- **Listener:** a document-level `paste` listener is registered to `this.clipboard.pasteFromClipboard` in `packages/excalidraw/components/App.tsx:4191-4197`. Cmd/Ctrl+V first calls `onPasteShortcut` (`App.tsx:5207`), which sets the `IS_PLAIN_PASTE` flag from Shift (`packages/excalidraw/components/App.clipboard.ts:287-296`).
- **`pasteFromClipboard`** (`App.clipboard.ts:304`):
  - It does nothing unless the editor is focused and the cursor is over the canvas (`:313-333`).
  - `parseDataTransferEvent(event)` runs before any other `await`, because browsers like Firefox clear `clipboardData` afterwards (`:335-338`).
    - In `packages/excalidraw/clipboard.ts:467-518`, each `DataTransferItem` with `kind === "file"` becomes `{ type, kind: "file", file, fileHandle }` via `item.getAsFile()` plus `normalizeFile` (`:482-492`).
  - `dataTransferList.getFiles()` keeps only the file items (`clipboard.ts:436-442`).
  - `parseClipboard(...)` builds the text/elements view (`clipboard.ts:523`).
  - The host's `props.onPaste` can cancel the paste by returning `false` (`App.clipboard.ts:344-352`).
  - `insertClipboardContent(data, filesList, isPlainPaste)` is then called (`:354`).
- **`insertClipboardContent`** (`App.clipboard.ts:112`):
  - It converts the last pointer position to scene coordinates (`:117-123`).
  - Pasted files are mapped to `File[]` (`:158`). Pasted SVG text is also turned into a file with `SVGStringToFile` (`:160-167`).
  - If the image tool is allowed, it calls `this.app.insertImages(imageFiles, sceneX, sceneY)` (`:169-176`).

## 2. Creating the image element

- **`insertImages`** (`App.tsx:11898`):
  1. **Placeholders:** it creates one placeholder per file with `newImagePlaceholder` (`App.tsx:8988`). That calls `newImageElement` (`App.tsx:9014`, defined in `packages/element/src/newElement.ts:673`), which sets `status: "pending"` and `fileId: null` by default (`newElement.ts:687-688`). The placeholders are laid out with `positionElementsOnGrid` and added to the scene with `insertNewElements` (`App.tsx:11905-11911`, `:6755`).
  2. **Initialization:** each placeholder goes through `initializeImage(placeholder, await normalizeFile(file))` (`:11914-11920`). On error, the placeholder is marked `isDeleted` and an error message is shown (`:11921-11928`).
  3. **Commit:** the initialized elements are re-laid out, selected, and committed with `updateScene({... captureUpdate: IMMEDIATELY})` (`:11933-11954`), then `actionFinalize` runs (`:11956-11959`).

## 3. `initializeImage`: file ID, data URL and BinaryFiles (`App.tsx:11563`)

- **Validation:** it checks the file with `isSupportedImageFile` (`:11569`). SVGs are normalized with `normalizeSVG` (`:11576-11586`).
- **File ID:** it uses `props.generateIdForFile` if the host provides one, otherwise `generateIdFromFile` (a digest of the file, `packages/excalidraw/data/blob.ts:261`). This happens before any resizing (`App.tsx:11588-11599`).
- **Resize and size check:** these only run if the file isn't already in `this.files`. It calls `resizeImageFile` (`blob.ts:357`) and enforces `imageOptions.maxFileSizeBytes` (`App.tsx:11601-11623`).
- **Data URL:** `getDataURL(imageFile)` (`blob.ts:276`), or the existing data URL is reused (`App.tsx:11625-11626`).
- **Element update:** `getLatestInitializedImageElement` re-reads the placeholder from the scene, in case it changed meanwhile, and applies `newElementWith(..., { fileId })` (`:11631`, `:11692-11705`).
- **Stored in BinaryFiles:** `this.addMissingFiles([{ mimeType, id: fileId, dataURL, created, lastRetrieved }])` (`:11636-11644`).
  - `addMissingFiles` (`App.tsx:4897-4934`) copies `this.files`, skips IDs that already exist, and re-normalizes SVG data URLs, bumping `version` if one changes (`:4914-4928`). It then assigns `this.files = nextFiles` (`:4931`).
- **Image cache and sizing:** if the image isn't cached yet, it calls `addNewImagesToImageCache()` and `updateImageCache([element])` (`:11646-11656`). It then waits for the loaded `<img>` and applies its natural width and height, centred on the placeholder (`:11658-11676`, `getImageNaturalDimensions` at `:11746-11772`).

## 4. Saving for collaboration (excalidraw-app)

1. **`onChange`:** after the scene update, `componentDidUpdate` (`App.tsx:4262`) calls `props.onChange(elements, state, this.files)` (`App.tsx:4471-4472`).
2. **App handler:** in `excalidraw-app/App.tsx:715-722`, if collaboration is active it calls `collabAPI.syncElements(elements)`. It also always calls `LocalData.save(elements, appState, files, …)` for local IndexedDB storage (`:726-753`).
3. **`syncElements`:** `excalidraw-app/collab/Collab.tsx:971-974` calls `broadcastElements` and `queueSaveToFirebase` (the scene document).
4. **Broadcast:** `Portal.broadcastScene` (`excalidraw-app/collab/Portal.tsx:143`) sends the element, which carries `fileId` but not the pixel data. It also calls `this.queueFileUpload()` (`Portal.tsx:180`).
5. **`queueFileUpload`** (`Portal.tsx:104`, throttled by `FILE_UPLOAD_TIMEOUT`) calls `fileManager.saveFiles({ elements, files: excalidrawAPI.getFiles() })`.
6. **`FileManager.saveFiles`** (`excalidraw-app/data/FileManager.ts:92-139`) picks out initialized image elements whose file isn't saved or being saved yet. It tracks them in `savingFiles` and calls the injected `_saveFiles`.
7. **Upload:** the `_saveFiles` passed in at `Collab.tsx:167-200`:
   - encrypts the files with the room key using `encodeFilesForUpload` (`FileManager.ts:228`);
   - uploads them with `saveFilesToFirebase` to `files/rooms/<roomId>/<fileId>` (`excalidraw-app/data/firebase.ts:145-172`, `uploadBytes` at `:161`).
8. **Status:** after upload, `queueFileUpload` marks those elements `status: "saved"` via `shouldUpdateImageElementStatus`, with `captureUpdate: NEVER` (`Portal.tsx:119-139`). That change is broadcast and tells other clients to fetch the file.
9. **Receiving side:** peers load missing files through `fileManager.getFiles` → `loadFilesFromFirebase` (`Collab.tsx:158-165`, `:440-455`).

## 5. Rendering on the canvas

- **Image cache:** `updateImageCache` (`packages/element/src/image.ts:36`) calls `loadHTMLImageElement(fileData.dataURL)` (`image.ts:21`).
  - It first stores the in-progress promise with `imageCache.set(fileId, {image: promise, mimeType})`, then replaces it with the loaded `HTMLImageElement` (`image.ts:59-71`).
  - If loading fails, the element is marked `status: "error"` (`App.tsx:11786-11801`).
- **Redraw trigger:** `addNewImagesToImageCache` clears the element's `ShapeCache` and calls `scene.triggerUpdate()` so the canvas redraws (`App.tsx:11823-11833`).
- **Hand-off to the renderer:** the static canvas receives `renderConfig.imageCache = this.imageCache` (`App.tsx:2624`). `renderElement` is called from `packages/excalidraw/renderer/staticScene.ts:414+`.
- **Drawing** (`packages/element/src/renderElement.ts:517`, the `case "image"` branch):
  - It looks up `renderConfig.imageCache.get(element.fileId)`.
  - If the entry is a loaded `<img>` rather than a promise, it draws it with `context.drawImage`, applying crop, rounded corners, and SVG inversion in dark mode (`:517-615`).
  - Otherwise it draws a placeholder with `drawImagePlaceholder` (`:620`, defined at `:361`).
  - `isPendingImageElement` (`:95-100`) marks elements that aren't in the cache yet.