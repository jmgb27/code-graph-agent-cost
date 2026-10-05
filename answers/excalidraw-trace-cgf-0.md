Here's the path a pasted clipboard image takes, from the browser `paste` event to the pixels on the canvas.

## 1. The paste event
- **Listener:** `App.componentDidMount` listens for `EVENT.PASTE` on `ownerDocument` and calls `this.clipboard.pasteFromClipboard` — `packages/excalidraw/components/App.tsx:4191-4198`. The context-menu or action paste builds a synthetic event with `createPasteEvent` and calls the same function (`packages/excalidraw/actions/actionClipboard.tsx:92`).
- **Shift held:** `AppClipboard.onPasteShortcut` sets `IS_PLAIN_PASTE` when Shift is down — `packages/excalidraw/components/App.clipboard.ts:287-296`.
- **`pasteFromClipboard`** — `App.clipboard.ts:304-362`:
  - It returns early if interaction is disabled, focus is outside Excalidraw, the cursor isn't over the canvas, or the target is a text input (`:306-333`).
  - `parseDataTransferEvent(event)` (`:338`) must run before any `await`, otherwise Firefox clears `clipboardData`.
  - It then calls `dataTransferList.getFiles()` (`:340`), then `parseClipboard(...)` (`:342`), then the host's `props.onPaste` hook, which can cancel the paste by returning `false` (`:344-352`).
  - Finally it calls `insertClipboardContent` (`:354`) and resets the tool (`:356`).

## 2. Reading the clipboard
- `parseDataTransferEvent` — `packages/excalidraw/clipboard.ts:467-518`. For each item with `kind === "file"` it calls `item.getAsFile()` and then `normalizeFile` (`:482-493`). It returns a list with `getFiles`/`getData` helpers attached (`:513-517`).
- `parseClipboard` — `clipboard.ts:523-555` parses the text part. That matters for pasted Excalidraw elements, not for raw images.

## 3. Choosing the image branch
- `insertClipboardContent` — `App.clipboard.ts:112`:
  - It converts the cursor position to scene coordinates (`:117-123`).
  - `imageFiles` is built from the pasted files (`:158`). Pasted `<svg>…</svg>` text is turned into a file with `SVGStringToFile` (`:160-167`).
  - If image files exist and the image tool is supported, it calls `this.app.insertImages(imageFiles, sceneX, sceneY)` (`:169-176`).

## 4. Creating the image element
- **`App.insertImages`** — `App.tsx:11898-11960`:
  1. For each file it creates a 100px placeholder with `newImagePlaceholder` (`App.tsx:8988-9031`). That calls `newImageElement({type:"image", ...})`, which has no `fileId` yet.
  2. The placeholders are laid out with `positionElementsOnGrid` and inserted with `insertNewElements` (`:11905-11911`).
  3. Each placeholder goes through `initializeImage(placeholder, await normalizeFile(file))` (`:11914-11930`). If that fails, the placeholder is marked `isDeleted` and an error is shown.
  4. The initialized elements are positioned again, then committed with `updateScene({ elements, selectedElementIds, captureUpdate: CaptureUpdateAction.IMMEDIATELY })` (`:11941-11954`). `IMMEDIATELY` makes the paste undoable. It then runs `actionFinalize` (`:11956-11959`).
- **`App.initializeImage`** — `App.tsx:11563-11685`:
  - It checks the type with `isSupportedImageFile`. SVGs are cleaned with `normalizeSVG` (`:11569-11586`).
  - **The file ID** is `props.generateIdForFile` if the host provides it, otherwise `generateIdFromFile`. The default is a SHA-1 hash of the file contents, with a `nanoid(40)` fallback (`packages/excalidraw/data/blob.ts:261-273`). The ID is computed *before* resizing (`:11588-11599`).
  - If the file isn't already known, it is downsized with `resizeImageFile` to `imageOptions.maxWidthOrHeight` and checked against `maxFileSizeBytes` (`:11601-11623`). The data URL comes from `getDataURL(imageFile)` (`:11625-11626`).
  - `getLatestInitializedImageElement` returns `newElementWith(latestPlaceholder, { fileId })`. This keeps any edits made to the placeholder in the meantime (`:11692-11705`).
  - Once the image has loaded, `getImageNaturalDimensions` sets `x/y/width/height` from the image's real size (`:11669-11675`, `:11746-11768`).

## 5. Storing the file in `BinaryFiles`
- `BinaryFiles` is `Record<ExcalidrawElement["id"], BinaryFileData>` — `packages/excalidraw/types.ts:146`. `BinaryFileData` holds `{ mimeType, id, dataURL, created, lastRetrieved?, version? }` — `types.ts:118-142`.
- `initializeImage` calls `this.addMissingFiles([{ mimeType, id: fileId, dataURL, created, lastRetrieved }])` — `App.tsx:11636-11644`.
- `addMissingFiles` — `App.tsx:4897-4934`:
  - It skips IDs that already exist (`:4907`).
  - For SVGs it re-normalizes the data URL and bumps `version` so the persistence layer re-saves it (`:4914-4928`).
  - It then replaces `this.files` (`:4931`).

## 6. Loading the image for drawing (`imageCache`)
- Still in `initializeImage`: if `imageCache` has no entry for the ID, it calls `addNewImagesToImageCache()` and `this.updateImageCache([el])` (`App.tsx:11646-11656`). It then awaits `imageCache.get(fileId).image` (`:11658`).
- `App.updateImageCache` — `App.tsx:11776-11804` calls the element-package `updateImageCache` (`packages/element/src/image.ts:36-89`):
  - `loadHTMLImageElement(fileData.dataURL)` loads the image.
  - The cache first holds the *promise*, then the loaded `HTMLImageElement` (`image.ts:60-71`).
  - Images that fail to load get `status: "error"` (`App.tsx:11786-11800`).
- `addNewImagesToImageCache` — `App.tsx:11807-11835` clears `ShapeCache` for the updated elements and calls `scene.triggerUpdate()` to redraw.

## 7. Saving for collaboration (excalidraw-app)
- After the scene update, `componentDidUpdate` (`App.tsx:4262`) calls `store.commit` (`:4464`) and then `this.props.onChange(elements, this.state, this.files)` (`:4471`).
- The app's `onChange` — `excalidraw-app/App.tsx:715-754`:
  - When collaborating it calls `collabAPI.syncElements(elements)` (`:721`).
  - It always calls `LocalData.save(elements, appState, files, …)` (`:727`). This saves files locally through `LocalFileManager` (a `FileManager` subclass, `excalidraw-app/data/LocalData.ts:53`, with `_save` at `:118`), then marks the images `status: "saved"` (`:731-750`).
- **Sending elements:** `Collab.syncElements` → `broadcastElements` + `queueSaveToFirebase` (`excalidraw-app/collab/Collab.tsx:971-974`, `:960-969`, `:990-1002`). Then `Portal.broadcastScene` (`excalidraw-app/collab/Portal.tsx:142-183`) sends only the changed elements over the socket (`:154-182`) and calls `this.queueFileUpload()` (`:180`).
- **Uploading the file:**
  - `Portal.queueFileUpload` (throttled) — `Portal.tsx:104-140` calls `fileManager.saveFiles({ elements, files: excalidrawAPI.getFiles() })`.
  - `FileManager.saveFiles` — `excalidraw-app/data/FileManager.ts:92-137` picks initialized image elements whose file isn't already saved or being saved at this version (`:101-113`). It calls the injected `_saveFiles` and records the results in `savedFiles`/`erroredFiles_save`.
  - The injected saver, set up in the `Collab` constructor (`Collab.tsx:157-178`), encrypts the files with the room key (`encodeFilesForUpload`) and calls `saveFilesToFirebase` with the prefix `collabFiles/<roomId>`.
  - `saveFilesToFirebase` uploads each file to Firebase Storage with `uploadBytes` at `${prefix}/${id}` (`excalidraw-app/data/firebase.ts:145-172`).
- **Telling peers:** after the upload, elements for which `shouldUpdateImageElementStatus` is true get `status: "saved"`, applied with `updateScene(..., CaptureUpdateAction.NEVER)` (`Portal.tsx:120-139`). The comment says this signals collaborators to pull the file. On their side, `loadFilesFromFirebase` downloads and decrypts it (`firebase.ts:274-302`), and `excalidrawAPI.addFiles` adds it (`excalidraw-app/App.tsx:487-492`, `App.tsx:4886-4895`).
- **Scene backup:** the throttled `queueSaveToFirebase` calls `saveCollabRoomToFirebase` (`Collab.tsx:323-338`), which saves the scene document to Firestore.

## 8. Drawing on the canvas
- The static canvas render config receives `imageCache: this.imageCache` — `App.tsx:2624` (also `:2649`).
- The static and new-element scene renderers call `renderElement` → `drawElement` — `packages/element/src/renderElement.ts:963-1009`, `:1011`. The `"image"` case (`:1107`) leads to `drawElementOnCanvas` (`:431`).
- `drawElementOnCanvas`, `case "image"` — `renderElement.ts:517-620`:
  - It looks up `renderConfig.imageCache.get(element.fileId)` (`:519-522`).
  - If the loaded image is there (not a pending promise), it applies an optional rounded-corner clip and crop (`:527-547`). In dark mode, SVGs are inverted, with a Safari-specific temporary canvas (`:549+`). It then calls `context.drawImage`.
  - Otherwise `drawImagePlaceholder` (`:361`, called at `:620`) draws the placeholder until the cache is filled and `scene.triggerUpdate()` triggers a redraw.