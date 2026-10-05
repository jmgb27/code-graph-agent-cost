Here is the whole path from a Ctrl/Cmd+V to pixels on the canvas and bytes in Firebase. I traced it through the code and did not run it.

## 1. Paste event → clipboard parsing
- **Listener:** `App` registers a document-level `paste` listener that calls `this.clipboard.pasteFromClipboard` (`packages/excalidraw/components/App.tsx:4191-4197`). The toolbar "Paste" action reaches the same function with a synthetic event (`packages/excalidraw/actions/actionClipboard.tsx:92`, built by `createPasteEvent` at `packages/excalidraw/clipboard.ts:101`).
- **Shift+paste:** `onPasteShortcut` sets `IS_PLAIN_PASTE` (`App.clipboard.ts:287-296`).
- **`pasteFromClipboard`** (`packages/excalidraw/components/App.clipboard.ts:304`):
  - It gives up if interaction is disabled, if focus is outside the Excalidraw container, or if the cursor isn't over the canvas (`:306-333`).
  - `parseDataTransferEvent(event)` (`:338`) must run before any `await`, or some browsers (e.g. Firefox) clear `clipboardData`.
  - It collects `dataTransferList.getFiles()` (`:340`), then calls `parseClipboard` (`:342`) and the host's optional `props.onPaste` hook, which can cancel the paste (`:344-352`).
  - `insertClipboardContent(data, filesList, isPlainPaste)` (`:354`) does the insert, then the tool resets to selection (`:356`).
- **`parseDataTransferEvent`** (`packages/excalidraw/clipboard.ts:467`): for each `item.kind === "file"` it calls `item.getAsFile()`, `getFileHandle` and `normalizeFile`, and returns `{type, kind:"file", file, fileHandle}` (`:482-493`).
- **`parseClipboard`** (`clipboard.ts:523`): handles the text side (Excalidraw element JSON, mixed content, plain text). A raw image arrives as a file, so this mostly passes through.

## 2. Choosing the image branch
In `insertClipboardContent` (`App.clipboard.ts:112`):
- The paste position comes from `viewport.lastPosition`, converted with `viewportCoordsToSceneCoords` (`:117-123`).
- `imageFiles = dataTransferFiles.map(d => d.file)` (`:158`). SVG markup pasted as text is also turned into a file with `SVGStringToFile` (`:160-167`).
- If the image tool is supported, it calls `this.app.insertImages(imageFiles, sceneX, sceneY)` (`:169-175`).

## 3. Creating the image element
**`insertImages`** (`App.tsx:11898`):
1. It builds one placeholder per file with `newImagePlaceholder` (`App.tsx:8988`). This is a `newImageElement({type:"image", …})` that is 100/zoom px square, snapped to the grid, placed in any frame under the cursor, and has no `fileId` yet (`:9014-9030`).
2. `positionElementsOnGrid` lays them out and `insertNewElements(placeholders)` adds them to the scene (`:11905-11911`), so a placeholder shows right away.
3. For each placeholder it calls `initializeImage(placeholder, await normalizeFile(file))` (`:11914-11930`). If that fails, it sets `errorMessage` and marks the placeholder `isDeleted: true`.
4. It re-grids the images that succeeded and swaps them into the scene elements (`:11933-11943`).
5. `updateScene({ elements, selectedElementIds, captureUpdate: IMMEDIATELY })` makes the insert undoable (`:11945-11954`), then `actionFinalize` runs (`:11956-11959`).

**`initializeImage`** (`App.tsx:11563`):
- It checks the file type with `isSupportedImageFile` (`:11569`) and switches the cursor to "wait".
- SVGs are cleaned up with `normalizeSVG` and rebuilt with `SVGStringToFile` (`:11576-11586`).
- **File ID:** `props.generateIdForFile?.(file)` if the host provides one, otherwise `generateIdFromFile` (a digest of the file). This happens before any resizing, so the same image always gets the same ID (`:11588-11599`).
- If the file isn't already stored, it calls `resizeImageFile` with `imageOptions.maxWidthOrHeight` and throws `errors.fileTooBig` if the result is still over `maxFileSizeBytes` (`:11601-11623`).
- `dataURL` is reused from `this.files[fileId]` if present, otherwise it's built with `getDataURL(imageFile)` (`:11625-11626`).
- `getLatestInitializedImageElement` (`:11692-11705`) re-reads the placeholder from the scene, so edits made while loading aren't lost, and returns a copy with `newElementWith(…, { fileId })`.

## 4. Storing the file in `BinaryFiles`
- `initializeImage` calls `this.addMissingFiles([{ mimeType, id: fileId, dataURL, created, lastRetrieved }])` (`App.tsx:11636-11644`).
- **`addMissingFiles`** (`App.tsx:4897`):
  - It copies `this.files`, skips IDs that already exist, and adds the new `BinaryFileData` (`:4901-4912`).
  - SVG data URLs are re-normalized; if they change, `version` goes up so persistence layers re-save them (`:4914-4928`).
  - It then replaces `this.files` (`:4931`).
- **Types:**
  - `BinaryFiles = Record<id, BinaryFileData>` (`packages/excalidraw/types.ts:146`).
  - `BinaryFileData` has `mimeType`, `id`, `dataURL`, `created`, `lastRetrieved?`, `version?` (`types.ts:118-142`).
  - `App.files` is exposed through `AppClassProperties.files` (`types.ts:1196`).
- **The link:** the element only holds `fileId`, and `isInitializedImageElement` means `type === "image" && !!fileId` (`packages/element/src/typeChecks.ts:35-39`).

## 5. Decoding into the image cache
Back in `initializeImage`:
- If the cache has no entry for the ID, it calls `addNewImagesToImageCache()` and then `this.updateImageCache([initializedImageElement])` (`App.tsx:11646-11656`). An error in the cache update is thrown and turned into `errors.imageInsertError`.
- It awaits the `HTMLImageElement` from the cache, then sets the element's natural size with `getImageNaturalDimensions` and `Object.assign` (`:11658-11676`).

The helpers:
- **`App.updateImageCache`** (`App.tsx:11776`) calls `_updateImageCache` from `packages/element/src/image.ts:36`. Any files that fail to load get `status: "error"` on their elements, with `CaptureUpdateAction.NEVER` (`App.tsx:11786-11801`).
- **`updateImageCache`** (`image.ts:36-89`):
  - For each `fileId` it reads `files[fileId]` and rejects `MIME_TYPES.binary`.
  - It calls `loadHTMLImageElement(dataURL)`, which is `new Image()` with `src = dataURL` (`image.ts:21-32`).
  - It stores the **promise** in `imageCache` straight away (`:67`), then replaces it with the loaded image (`:71`).
- **Cache type:** `imageCache: Map<FileId, { image: HTMLImageElement | Promise<…>, mimeType }>` (`types.ts:1189-1195`).
- **`addNewImagesToImageCache`** (`App.tsx:11807-11835`): after the cache fills, it clears `ShapeCache` for the updated elements and calls `scene.triggerUpdate()` to re-render. `scheduleImageRefresh` is a throttled fallback for the same job (`:11839-11841`).

## 6. Rendering on the canvas
- `StaticCanvasRenderConfig` carries `imageCache` (`packages/excalidraw/scene/types.ts:32`).
- The static and new-element renderers call `renderElement` (`packages/element/src/renderElement.ts:963`), which calls `drawElement` (`:1011`). Image elements are drawn through the per-element canvas cache: `generateElementWithCanvas` (`:687`), keyed on zoom, theme and crop, then blitted by `drawElementFromCanvas` (`:762`).
- **`drawElementOnCanvas`**, `case "image"` (`renderElement.ts:517`):
  - It gets `cacheEntry = renderConfig.imageCache.get(element.fileId)` (`:519-525`).
  - Once the image has loaded (not a `Promise`), it clips to `roundRect` if the element has roundness (`:528-538`).
  - It uses `element.crop` or the image's natural size as the source rectangle (`:540-547`) and calls `drawImage`.
  - In dark mode, SVGs are inverted, with a temporary-canvas workaround on Safari (`:549+`).
  - If the image hasn't loaded, or `status === "error"`, `drawImagePlaceholder` draws the grey box with a placeholder or error icon (`:361-385`).

## 7. Saving for collaboration (excalidraw-app)
1. **Scene changes reach collab:** `updateScene` changes the scene, which triggers the host's `onChange(elements, appState, files)` (`excalidraw-app/App.tsx:715`). If a session is active, it calls `collabAPI.syncElements(elements)` (`:720-721`). It also calls `LocalData.save(elements, appState, files)` for local persistence (`:727`).
2. **`Collab.syncElements`** (`excalidraw-app/collab/Collab.tsx:971`):
   - It calls `broadcastElements`, which sends only when the scene version increased, via `portal.broadcastScene(WS_SUBTYPES.UPDATE, …)` (`:960-969`).
   - It calls `queueSaveToFirebase`, which is throttled and ends in `saveCollabRoomToFirebase` → `saveToFirebase` (`:990-1002`, `:323`; `excalidraw-app/data/firebase.ts:187`). That saves the element JSON only, not the image bytes.
3. **`Portal.broadcastScene`** (`excalidraw-app/collab/Portal.tsx:142`) sends only elements whose version changed and calls `this.queueFileUpload()` (`:180`).
4. **`Portal.queueFileUpload`** (`Portal.tsx:104`, throttled by `FILE_UPLOAD_TIMEOUT`):
   - It calls `collab.fileManager.saveFiles({ elements, files: excalidrawAPI.getFiles() })` (`:106-109`).
   - Afterwards it sets `status: "saved"` on image elements where `shouldUpdateImageElementStatus` is true (the file is saved and the element's status is `"pending"`), with `CaptureUpdateAction.NEVER` (`:120-139`). That status change tells other peers they can fetch the file.
5. **`FileManager.saveFiles`** (`excalidraw-app/data/FileManager.ts:92`):
   - For each initialized image element whose `files[fileId]` isn't already saved or being saved at that version (`isFileSavedOrBeingSaved`, `:80-86`), it adds the file to `addedFiles` and marks it in `savingFiles` (`:101-113`).
   - It then calls the injected `_saveFiles` and records the results in `savedFiles` / `erroredFiles_save` (`:115-136`).
   - `shouldPreventUnload` blocks leaving the page while uploads are running (`:189-197`, used in `Collab.beforeUnload` at `Collab.tsx:299`).
6. **The injected `saveFiles`** (`Collab.tsx:167-200`):
   - `encodeFilesForUpload` encrypts the files with the room key, capped at `FILE_UPLOAD_MAX_BYTES`.
   - `saveFilesToFirebase({ prefix: `${collabFiles}/${roomId}`, files })` (`:173-180`) uploads each file with `uploadBytes` to `ref(storage, `${prefix}/${id}`)` (`excalidraw-app/data/firebase.ts:145-172`).

**Other peers:** they get the element over the socket, with `fileId` and eventually `status: "saved"`. They fetch the file through `FileManager.getFiles` → `loadFilesFromFirebase(`files/rooms/${roomId}`, …)` (`Collab.tsx:165`), add it with `addFiles` → `addMissingFiles` → `addNewImagesToImageCache` (`App.tsx:4886-4895`), and it renders through the same `drawElementOnCanvas` path.