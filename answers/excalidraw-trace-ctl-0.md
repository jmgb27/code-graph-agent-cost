Pasting an image goes through 5 stages: the clipboard is parsed, a placeholder element is inserted, the image is initialized and its data stored in `BinaryFiles`, the file is uploaded for collaboration, and the canvas draws it from `imageCache`.

## 1. Paste event → parsed files

- **Listener:** `App` registers a document `paste` listener that calls `this.clipboard.pasteFromClipboard` (`packages/excalidraw/components/App.tsx:4191-4198`). `this.clipboard` is an `AppClipboard` created at `App.tsx:692`.
- **`AppClipboard.pasteFromClipboard`** (`packages/excalidraw/components/App.clipboard.ts:304`):
  - It returns early if interaction is disabled, if Excalidraw isn't the active element, or if the cursor isn't over the canvas or is over a writable element (`:306-333`).
  - `parseDataTransferEvent(event)` runs before any other `await`, because Firefox clears `clipboardData` after the event frame (`:335-338`).
  - `dataTransferList.getFiles()` collects the file items (`:340`), then `parseClipboard(...)` parses the rest (`:342`).
  - If the host passed an `props.onPaste` handler, it runs next; returning `false` cancels the paste (`:344-352`).
  - Then it calls `insertClipboardContent(data, filesList, isPlainPaste)` (`:354`) and switches back to the selection tool (`:356`).
- **`parseDataTransferEvent`** (`packages/excalidraw/clipboard.ts:467`) reads `event.clipboardData.items` (`:473`). For each item with `kind === "file"` it calls `item.getAsFile()` and `normalizeFile()` and returns `{kind:"file", file, fileHandle}` (`:482-492`). `getFiles` is attached to the result at `:516`.
- **`insertClipboardContent`** (`App.clipboard.ts:112`):
  - It converts the last pointer position to scene coordinates (`:117-123`).
  - It handles errors, mixed HTML content and spreadsheets first (`:125-155`).
  - It maps the parsed files to `File[]` (`:158`). If there are no files but the text is `<svg…</svg>`, it turns the text into a file with `SVGStringToFile` (`:160-166`).
  - If the image tool is supported, it calls `this.app.insertImages(imageFiles, sceneX, sceneY)` (`:169-171`).

## 2. Image element creation

- **`App.insertImages`** (`App.tsx:11898`):
  - It creates one placeholder per file with `newImagePlaceholder` and lays them out with `positionElementsOnGrid` (`:11905-11910`).
  - It inserts the placeholders into the scene right away with `insertNewElements` (`:11911`).
  - It calls `initializeImage(placeholder, await normalizeFile(file))` for each file in parallel (`:11914-11919`). If one fails, it shows the error and marks that placeholder `isDeleted` (`:11921-11927`).
  - It re-positions the initialized elements and commits them with `updateScene` using `CaptureUpdateAction.IMMEDIATELY`, which records the insert for undo and selects the new elements (`:11933-11954`).
  - Finally it runs `actionFinalize` (`:11956-11959`).
- **`newImagePlaceholder`** (`App.tsx:8988`) snaps to the grid, finds the frame under the cursor, sizes the element at 100/zoom, and calls `newImageElement` (`:9014`).
- **`newImageElement`** (`packages/element/src/newElement.ts:673`) sets `status: "pending"` and `fileId: null` by default (`:687-688`).

## 3. File data stored in `BinaryFiles` (`this.files`)

**`App.initializeImage`** (`App.tsx:11563`):

1. It rejects unsupported types with `isSupportedImageFile` (`:11569`). For SVGs it normalizes the markup with `normalizeSVG` (`:11576-11585`).
2. It builds the `fileId` before any resizing, so the id stays the same wherever the file is used. It uses `props.generateIdForFile` if given, otherwise `generateIdFromFile`, which hashes the file contents (`:11588-11592`; `packages/excalidraw/data/blob.ts:261`).
3. If the file isn't already in `this.files`, it resizes it with `resizeImageFile` to `imageOptions.maxWidthOrHeight` (`blob.ts:357`) and checks `maxFileSizeBytes` (`:11601-11622`).
4. It gets the `dataURL` from the existing entry or from `getDataURL(imageFile)` (`:11625-11626`; `blob.ts:276`).
5. `getLatestInitializedImageElement` sets the `fileId` on the latest version of the placeholder (`:11631`, `:11692-11705`).
6. **`addMissingFiles([{mimeType, id, dataURL, created, lastRetrieved}])`** stores the file data (`:11636-11644`):
   - `addMissingFiles` (`App.tsx:4897`) copies `this.files`, skips ids that already exist (`:4907`), and re-normalizes SVG data URLs, bumping `version` when they change (`:4914-4928`).
   - It then assigns `this.files = nextFiles` (`:4931`). `this.files` is declared at `App.tsx:647`.

## 4. Image cache (decoded image for rendering)

This continues inside `initializeImage`:

- If `imageCache` has no entry for the `fileId`, it calls `addNewImagesToImageCache()` and `updateImageCache([element])` (`App.tsx:11646-11656`).
- **`App.updateImageCache`** (`:11776`) delegates to `updateImageCache` in `packages/element/src/image.ts:36`, which:
  - calls `loadHTMLImageElement(fileData.dataURL)` (`image.ts:21`, `:60`), which creates `new Image()` with `src = dataURL`;
  - stores the promise in `imageCache` first (`:67`) and swaps in the loaded `HTMLImageElement` once it resolves (`:71`).
  - If loading fails, `App.updateImageCache` sets `status: "error"` on the element (`App.tsx:11786-11800`).
- **`addNewImagesToImageCache`** (`:11807`) clears the `ShapeCache` entry and calls `scene.triggerUpdate()` so the canvas re-renders (`:11823-11833`).
- Back in `initializeImage`, it waits for the cached image and applies the image's natural dimensions to the element (`:11658-11676`).

## 5. Saving for collaboration (excalidraw-app)

1. **`onChange`:** after every update, `App.componentDidUpdate` calls `props.onChange(elements, state, this.files)` (`App.tsx:4470-4472`).
2. **App `onChange`** (`excalidraw-app/App.tsx:715`):
   - While collaborating, it calls `collabAPI.syncElements(elements)` (`:720-721`).
   - It also calls `LocalData.save(...)` for local IndexedDB storage. When that finishes, it sets `status: "saved"` on elements whose files are stored (`:726-753`).
3. **`Collab.syncElements`** (`excalidraw-app/collab/Collab.tsx:971`) calls `broadcastElements` → `portal.broadcastScene`, and `queueSaveToFirebase` (`:990`), which saves the scene document.
4. **`Portal.broadcastScene`** (`excalidraw-app/collab/Portal.tsx:142`) sends the elements over the socket, including the image element (still `status:"pending"`, with its `fileId`). It then calls **`queueFileUpload()`** (`:180`).
5. **`Portal.queueFileUpload`** (`Portal.tsx:104`, throttled by `FILE_UPLOAD_TIMEOUT`) calls `fileManager.saveFiles({elements, files: excalidrawAPI.getFiles()})` (`:106-109`). `getFiles` returns `this.files` (`App.tsx:810`).
6. **`FileManager.saveFiles`** (`excalidraw-app/data/FileManager.ts:92`):
   - It collects the `fileId`s of image elements that aren't already saved or being saved and tracks them in `savingFiles` (`:101-112`).
   - It calls the injected `_saveFiles` (`:116`) and records the results in `savedFiles` or `erroredFiles_save` (`:120-126`).
7. **Collab's `saveFiles` callback** (`Collab.tsx:167-180`):
   - `encodeFilesForUpload` (`FileManager.ts:228`) turns the `dataURL` into bytes, then compresses and encrypts it with the room key (`:243-253`). It also enforces `FILE_UPLOAD_MAX_BYTES` (`:255-261`).
   - `saveFilesToFirebase` (`excalidraw-app/data/firebase.ts:145`) uploads each file to `files/rooms/<roomId>/<fileId>` with `uploadBytes` (`:160-163`).
8. **Status flip:** after the upload, `queueFileUpload` sets `status: "saved"` on each element that `shouldUpdateImageElementStatus` matches (file saved and element `"pending"`; `FileManager.ts:202-209`). This uses `newElementWith` and `updateScene` with `CaptureUpdateAction.NEVER`, so it isn't recorded in undo history (`Portal.tsx:120-138`). That element change is broadcast again, which tells other clients to fetch the file.
9. **Receiving side:** other clients find initialized image elements whose files they aren't tracking yet (`Collab.tsx:444-445`). They fetch them with `fileManager.getFiles` (`:455`), which uses `loadFilesFromFirebase` (`:159-165`), and add them through `addFiles`. That runs `addMissingFiles` and `addNewImagesToImageCache` (`App.tsx:4886-4894`).

## 6. Rendering on the canvas

- `App` passes `imageCache: this.imageCache` into the canvas render config (`App.tsx:2624`, `:2649`).
- **`drawElementOnCanvas`, `case "image"`** (`packages/element/src/renderElement.ts:517`):
  - It looks up `renderConfig.imageCache.get(element.fileId)` (`:519-525`).
  - If the image has loaded (not a Promise), it clips for roundness if needed and applies the crop or natural size (`:527-547`).
  - It then calls `context.drawImage(img, …, element.width, element.height)` (`:607-617`). SVGs in dark theme are inverted, with a separate code path for Safari (`:549-604`).
- **Placeholder:** until the image has loaded, `drawImagePlaceholder` (`renderElement.ts:361`) draws a grey box with the image icon, or the error icon when `status === "error"` (`:376-379`).