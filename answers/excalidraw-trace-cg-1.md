Here's the path a pasted image takes, from the paste event to the pixels on the canvas. I only read files; nothing was edited.

## 1. The paste event
- The `paste` listener is attached to the document in edit mode only, and it calls `this.clipboard.pasteFromClipboard`: `packages/excalidraw/components/App.tsx:4191-4197`. `this.clipboard` is an `AppClipboard` instance: `App.tsx:692`.
- `AppClipboard.pasteFromClipboard` (`packages/excalidraw/components/App.clipboard.ts:304`) does the following:
  - It ignores the paste unless Excalidraw has focus, the cursor is over the canvas, and the focused element is not a text input (`:313-333`).
  - It calls `parseDataTransferEvent(event)` synchronously, before any other `await`, because Firefox clears `clipboardData` otherwise (`:338`). File items are pulled out with `item.getAsFile()` in `packages/excalidraw/clipboard.ts:467-516`, and `getFiles()` filters for `kind === "file"` (`clipboard.ts:440`).
  - `parseClipboard(...)` handles the text part of the clipboard (`App.clipboard.ts:342`, `clipboard.ts:523`).
  - The host app's `props.onPaste` hook runs next and can cancel the paste by returning `false` (`:344-352`).
  - Then it calls `insertClipboardContent(data, filesList, isPlainPaste)` (`:354`).
- `insertClipboardContent` (`App.clipboard.ts:112`) converts the cursor position to scene coordinates (`:117`) and maps the clipboard files to `File[]` (`:158`). Pasted SVG text is also turned into a file (`:160-166`). If the image tool is allowed, it calls `this.app.insertImages(imageFiles, sceneX, sceneY)` (`:169-171`).

## 2. Creating the image element
- `App.insertImages` (`App.tsx:11898`):
  - It creates one placeholder per file with `newImagePlaceholder` (`App.tsx:8988`). That calls `newImageElement` (`App.tsx:9014` → `packages/element/src/newElement.ts:673`), which sets `fileId: null` and `status: "pending"` (`newElement.ts:687`).
  - It lays the placeholders out in a grid and inserts them with `insertNewElements` (`:11905-11912`).
  - For each placeholder it calls `initializeImage(placeholder, await normalizeFile(file))` (`:11917`). If that fails, the placeholder is marked deleted and an error message is shown (`:11922-11928`).
  - It lays out the finished elements again and calls `updateScene({ elements, selectedElementIds, captureUpdate: IMMEDIATELY })`, which also makes the paste undoable (`:11933-11955`). It then runs `actionFinalize` (`:11957-11960`).

## 3. `initializeImage`: file id, `BinaryFiles`, image cache
`initializeImage` is at `App.tsx:11563`:
- It checks that the file is a supported image type (`:11569`). SVGs are normalized first (`:11576-11585`).
- The file id is `props.generateIdForFile` if the host provides one, otherwise `generateIdFromFile`, which hashes the file contents. The id is computed before any resizing (`:11589-11591`).
- If `this.files` doesn't already hold this file, the image is resized to `imageOptions.maxWidthOrHeight`. Files larger than `maxFileSizeBytes` are rejected (`:11601-11622`).
- The file is converted to a data URL with `getDataURL(imageFile)` (`:11624-11625`).
- `getLatestInitializedImageElement` re-reads the placeholder from the scene, so any edits made while loading are kept, and sets `fileId` on it (`:11692-11704`).
- **Stored in `BinaryFiles`:** `this.addMissingFiles([{ mimeType, id: fileId, dataURL, created, lastRetrieved }])` (`:11636-11644`).
  - `addMissingFiles` (`App.tsx:4897`) copies `this.files` (`public files: BinaryFiles`, `App.tsx:647`), skips ids that already exist, and re-normalizes SVG data URLs. For SVGs it bumps `version` so storage layers notice the change (`:4913-4927`).
  - It then assigns `this.files = nextFiles` (`:4932`).
- **Image cache:** if the file isn't cached yet, it calls `addNewImagesToImageCache()` and `updateImageCache([element])` (`:11646-11655`).
  - Both wrap `updateImageCache` in `packages/element/src/image.ts:36`. That function stores an `HTMLImageElement` promise in the cache right away, created by `loadHTMLImageElement(dataURL)` (`image.ts:21`), and replaces it with the loaded image once it resolves (`image.ts:66-72`).
  - Files that fail to load get `status: "error"` on their elements (`App.tsx:11786-11800`).
- Once the `HTMLImageElement` is available, the element's width and height are set from the image's natural size (`:11657-11676`).

## 4. Saving for collaboration (excalidraw-app)
- Each render ends in `App`'s `componentDidUpdate` (`App.tsx:4262`), which calls `props.onChange(elements, state, this.files)` (`App.tsx:4471`).
- The app's `onChange` handler (`excalidraw-app/App.tsx:715`) does two things:
  - While collaborating, it calls `collabAPI.syncElements(elements)` (`:720-721`).
  - Separately, it calls `LocalData.save(elements, appState, files)` for local persistence (`:727`).
- `Collab.syncElements` (`excalidraw-app/collab/Collab.tsx:971`) calls `broadcastElements` (`:960`) and `queueSaveToFirebase` (`:990`).
  - `broadcastElements` calls `portal.broadcastScene(...)`.
  - `broadcastScene` calls `this.queueFileUpload()` (`excalidraw-app/collab/Portal.tsx:180`) before sending the encrypted elements over the socket.
- `Portal.queueFileUpload` is throttled (`Portal.tsx:104`). It calls `collab.fileManager.saveFiles({ elements, files: excalidrawAPI.getFiles() })` (`:106-109`).
- `FileManager.saveFiles` (`excalidraw-app/data/FileManager.ts:92`) picks the initialized image elements whose files are neither saved nor currently being saved (`:103-113`). It passes them to the `saveFiles` callback that `Collab` set up.
- That callback (`Collab.tsx:167-199`) does two things:
  - It encrypts the files with the room key via `encodeFilesForUpload` (`FileManager.ts:228`).
  - It uploads them with `saveFilesToFirebase` to `collabFiles/<roomId>/<fileId>` (`excalidraw-app/data/firebase.ts:145`, which uses `uploadBytes` at `:160`).
- After the upload, `shouldUpdateImageElementStatus` (`FileManager.ts:202`) finds elements that are still `pending` but whose files are now saved. `queueFileUpload` changes them to `status: "saved"` with `updateScene(..., CaptureUpdateAction.NEVER)` (`Portal.tsx:119-137`).
  - The status change gives the element a new version, so it is broadcast again. Collaborators see `"saved"` and fetch the file through `fileManager.getFiles` → `loadFilesFromFirebase` (`Collab.tsx:159-165`, `:455`).

## 5. Rendering on the canvas
- The static canvas gets `renderConfig.imageCache = this.imageCache` (`App.tsx:2624`).
  - `staticScene.ts` calls `renderElement(...)` for each visible element (`packages/excalidraw/renderer/staticScene.ts:414`).
- In `renderElement`, the `case "image"` branch (`packages/element/src/renderElement.ts:517`) looks up `renderConfig.imageCache.get(element.fileId)`.
  - If the entry is a loaded `HTMLImageElement` and not a Promise, it draws the image. The draw applies the rounded-corner clip, any `crop`, and dark-mode inversion for SVGs (`:517-560+`).
  - Otherwise it draws a placeholder with `drawImagePlaceholder` (`renderElement.ts:361`). `isPendingImageElement` (`renderElement.ts:95`) marks initialized images that aren't cached yet.
- When new images load, `addNewImagesToImageCache` clears `ShapeCache` for those elements and calls `scene.triggerUpdate()` to redraw (`App.tsx:11825-11835`).
  - As a fallback, the interactive-scene render callback calls a throttled `scheduleImageRefresh` (`App.tsx:4483`, `:11839`), which picks up any images that were missed.