A pasted image goes through six stages: the paste listener parses the clipboard, a grey placeholder element is inserted, the file is hashed and stored in `this.files` (the `BinaryFiles` map) and decoded into `imageCache`, the scene is committed, then `onChange` uploads the file for collaboration and the canvas draws the cached `<img>`.

### 1. Paste event → file extraction
- **Listener registration:** `packages/excalidraw/components/App.tsx:4191-4198` attaches `EVENT.PASTE` on `ownerDocument` to `this.clipboard.pasteFromClipboard`. `this.clipboard` is an `AppClipboard` created at `App.tsx:692`.
- **Handler:** `AppClipboard.pasteFromClipboard` is at `packages/excalidraw/components/App.clipboard.ts:304`.
  - It returns early if Excalidraw isn't the active element, or if the element under the cursor isn't a canvas or is a writable element (`:313-332`).
  - `parseDataTransferEvent(event)` is at `:338`. Per the comment it must be called before any `await`, because Firefox clears `clipboardData`.
  - `dataTransferList.getFiles()` is at `:340`, then `parseClipboard(...)` at `:342`.
  - The host's `props.onPaste` hook runs at `:344-352`; returning `false` cancels the paste.
  - Control then passes to `insertClipboardContent(data, filesList, isPlainPaste)` at `:354`.
- **Parsing:** `parseDataTransferEvent` is at `packages/excalidraw/clipboard.ts:467`.
  - For `item.kind === "file"` (`:482`) it calls `item.getAsFile()`, then `getFileHandle`, then `normalizeFile` (`:483-492`).
  - `getFiles` filters to `kind === "file"` (`clipboard.ts:436-442`).
- **Routing:** `insertClipboardContent` is at `App.clipboard.ts:112`.
  - The paste position comes from the last pointer position (`:117-123`).
  - `imageFiles` are collected at `:158`. A raw `<svg>…</svg>` text paste is also turned into a file via `SVGStringToFile` (`:160-167`).
  - If the image tool is supported it calls `this.app.insertImages(imageFiles, sceneX, sceneY)` (`:169-175`).

### 2. Image element creation
- **`App.insertImages`** (`App.tsx:11898`):
  - It builds one placeholder per file with `newImagePlaceholder`, lays them out with `positionElementsOnGrid`, and inserts them with `insertNewElements` (`:11904-11911`).
  - **`newImagePlaceholder`** (`App.tsx:8988`) snaps to the grid, finds the frame under the cursor, and calls `newImageElement` with a 100px/zoom box (`:9014-9030`).
  - **`newImageElement`** (`packages/element/src/newElement.ts:673`) returns an image element with `status: "pending"`, `fileId: null`, `scale: [1,1]` and a transparent stroke (`:682-691`).
  - Each placeholder is then passed to `initializeImage` (`:11913-11931`). If that fails, the placeholder is marked `isDeleted` and an error message is set.
  - The results are re-laid out and committed with `updateScene({ elements, selectedElementIds, captureUpdate: IMMEDIATELY })` (`:11934-11958`), which makes the insertion undoable. `actionFinalize` runs at `:11960-11963`.

### 3. File data → `BinaryFiles` and `imageCache`
- **`App.initializeImage`** (`App.tsx:11563`):
  - SVGs are normalized with `normalizeSVG` (`:11576-11586`).
  - `fileId` comes from `props.generateIdForFile` or `generateIdFromFile`, which hashes the content. This happens *before* resizing so the id stays the same across clients (`:11588-11599`).
  - If the file is new, it is resized with `resizeImageFile` (using `imageOptions.maxWidthOrHeight`) and checked against `maxFileSizeBytes` (`:11601-11626`).
  - The `dataURL` is reused from `this.files` or created with `getDataURL(imageFile)` (`:11628-11629`).
  - `getLatestInitializedImageElement` (`:11691`) re-reads the placeholder from the scene, so edits made while loading are kept, and stamps it with `fileId` via `newElementWith`.
  - **Stored in `BinaryFiles`:** `this.addMissingFiles([{ mimeType, id: fileId, dataURL, created, lastRetrieved }])` (`:11636-11644`).
  - **`addMissingFiles`** (`App.tsx:4897`) copies `this.files`, skips ids that already exist, re-normalizes SVG data URLs (bumping `version`), then assigns `this.files = nextFiles` (`:4903-4933`). `this.files` is the `BinaryFiles` map.
  - **Decoded into `imageCache`:** if the id isn't cached yet, `addNewImagesToImageCache()` and `updateImageCache([element])` run (`:11646-11656`).
    - `updateImageCache` in `App.tsx:11776` wraps `updateImageCache` in `packages/element/src/image.ts:36`.
    - That function first stores the `loadHTMLImageElement(dataURL)` promise in `imageCache` to mark loading as in progress, then replaces it with the loaded `HTMLImageElement` (`image.ts:60-71`).
    - If decoding fails, `App.updateImageCache` sets `status: "error"` on the element (`App.tsx:11786-11801`).
  - Once the image has loaded, `getImageNaturalDimensions` gives the element its real size (`:11658-11675`).

### 4. Commit → `onChange`
- In `componentDidUpdate`, `this.store.commit(...)` runs at `App.tsx:4464`, then `this.props.onChange?.(elements, this.state, this.files)` and `onChangeEmitter.trigger(...)` at `App.tsx:4471-4472`.
- `this.files` is also available through the imperative API: `getFiles: () => this.files` at `App.tsx:810`.

### 5. Saving for collaboration (excalidraw.com app)
- **App `onChange`** (`excalidraw-app/App.tsx:715`):
  - When collaborating it calls `collabAPI.syncElements(elements)` (`:720-722`).
  - It always calls `LocalData.save(elements, appState, files, …)`, which saves locally to IndexedDB through `LocalData.fileStorage` and afterwards marks elements `status: "saved"` (`:726-755`).
- **`Collab.syncElements`** (`excalidraw-app/collab/Collab.tsx:971`) calls `broadcastElements` and then `queueSaveToFirebase`.
  - `broadcastElements` (`:960`) calls `portal.broadcastScene(...)`.
  - `queueSaveToFirebase` (`:990`) is a throttled save of the scene elements.
- **`Portal.broadcastScene`** (`excalidraw-app/collab/Portal.tsx:142`) calls `this.queueFileUpload()` at `:180` before sending the socket update.
- **`Portal.queueFileUpload`** (`Portal.tsx:104`) calls `fileManager.saveFiles({ elements, files: excalidrawAPI.getFiles() })` (`:106-109`).
  - Afterwards, elements whose file was uploaded get `status: "saved"` via `newElementWith`, committed with `CaptureUpdateAction.NEVER` (`:119-139`).
  - This status change is what tells other clients they can fetch the file.
- **`FileManager.saveFiles`** (`excalidraw-app/data/FileManager.ts:92`):
  - It collects initialized image elements whose file isn't already saved or being saved, and tracks them in `savingFiles` (`:101-113`).
  - It calls the injected `_saveFiles`, then moves the ids into `savedFiles` (`:116-122`).
- **Injected `saveFiles`** (`Collab.tsx:167-200`):
  - `encodeFilesForUpload` (`FileManager.ts:228`) encrypts each file with the room key and enforces `FILE_UPLOAD_MAX_BYTES`.
  - `saveFilesToFirebase` (`excalidraw-app/data/firebase.ts:145`) uploads to `files/rooms/<roomId>`, using the `collabFiles` storage prefix.
- **Receiving side:**
  - `fetchImageFilesFromFirebase` (`Collab.tsx:430`) picks images with `status === "saved"` that aren't tracked yet (`:441-453`) and loads them with `fileManager.getFiles`, which calls `loadFilesFromFirebase`.
  - The result goes to `excalidrawAPI.addFiles(loadedFiles)` (`Collab.tsx:801`).
  - `addFiles` (`App.tsx:4886`) calls `addMissingFiles`, clears the shape cache, triggers a scene update, and calls `addNewImagesToImageCache` (`:4888-4894`).

### 6. Rendering on the canvas
- `App.render` passes `renderConfig={{ imageCache: this.imageCache, … }}` to the static canvas (`App.tsx:2623-2624`).
- `drawElementOnCanvas`, `case "image"` (`packages/element/src/renderElement.ts:517`):
  - It looks up `renderConfig.imageCache.get(element.fileId)` (`:519-524`).
  - If the entry is a loaded image rather than a pending `Promise`, it clips to rounded corners if needed, applies the crop, and calls `drawImage`.
  - Otherwise it calls `drawImagePlaceholder` (`:361`, called at `:620`).
- Redraws happen when `addNewImagesToImageCache` finishes. It deletes the `ShapeCache` entries for updated elements and calls `scene.triggerUpdate()` (`App.tsx:11807-11831`). `scheduleImageRefresh` (`:11835`) is a throttled fallback.