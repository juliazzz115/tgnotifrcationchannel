const { contextBridge, ipcRenderer } = require('electron');

// Предоставляем API для веб-страницы
contextBridge.exposeInMainWorld('electronAPI', {
  // Функция для отправки уведомления в Electron
  notifyElectron: (data) => {
    ipcRenderer.send('new-notification', data);
  }
});

console.log('✅ Preload script загружен');
