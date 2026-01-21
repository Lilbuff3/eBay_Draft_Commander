const { ipcRenderer, shell } = require('electron')

// Expose some node APIs to window if needed
window.electron = {
    openExternal: (url) => shell.openExternal(url),
    // Setup for drag/drop improvements later
}
