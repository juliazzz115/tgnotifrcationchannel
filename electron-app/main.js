const { app, BrowserWindow, ipcMain, Tray, Menu } = require('electron');
const path = require('path');

let mainWindow;
let tray;

// URL вашего Railway приложения
const RAILWAY_URL = 'https://tgnotifrcationchannel-production.up.railway.app/';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false, // Начинаем скрытым
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    title: 'Telegram Alerts',
    // Убираем titleBar для более чистого вида
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 10, y: 10 }
  });

  // Загружаем Railway сайт
  mainWindow.loadURL(RAILWAY_URL);

  // Открываем DevTools для отладки (можно убрать потом)
  // mainWindow.webContents.openDevTools();

  // Когда окно закрывают - просто скрываем его
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
    return false;
  });

  // Следим за сообщениями из веб-страницы
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('✅ Страница загружена');

    // Инжектируем код для отслеживания новых уведомлений
    mainWindow.webContents.executeJavaScript(`
      // Переопределяем Socket.IO событие new_alert для связи с Electron
      if (typeof socket !== 'undefined') {
        const originalOn = socket.on.bind(socket);
        socket.on = function(event, handler) {
          if (event === 'new_alert') {
            // Добавляем наш обработчик
            return originalOn(event, (data) => {
              // Сообщаем Electron о новом уведомлении
              window.electronAPI?.notifyElectron(data);
              // Вызываем оригинальный обработчик
              handler(data);
            });
          }
          return originalOn(event, handler);
        };
        console.log('🔔 Electron мониторинг уведомлений активирован');
      }
    `);
  });

  // Показываем окно когда оно готово
  mainWindow.once('ready-to-show', () => {
    console.log('✅ Окно готово (но остается скрытым)');
    // НЕ показываем окно - оно будет показано при первом уведомлении
  });
}

// Создаем иконку в menu bar (системный трей)
function createTray() {
  // Примечание: добавьте файл icon.png (512x512) для иконки в menu bar
  // Пока используем стандартную иконку Electron
  // tray = new Tray(path.join(__dirname, 'icon.png'));

  // Временно: используем nativeImage для создания простой иконки
  const { nativeImage } = require('electron');
  const image = nativeImage.createEmpty();
  tray = new Tray(image);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Показать окно',
      click: () => {
        showWindow();
      }
    },
    {
      label: 'Скрыть окно',
      click: () => {
        mainWindow.hide();
      }
    },
    { type: 'separator' },
    {
      label: 'Выход',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Telegram Alerts');
  tray.setContextMenu(contextMenu);

  // Клик на иконку - показать/скрыть окно
  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      showWindow();
    }
  });
}

// Функция показа окна с разворачиванием
function showWindow() {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
    // Разворачиваем на весь экран
    mainWindow.setFullScreen(true);
  }
}

// Обработка уведомления о новом сообщении
ipcMain.on('new-notification', (event, data) => {
  console.log('🔔 НОВОЕ УВЕДОМЛЕНИЕ!', data);

  // Показываем и разворачиваем окно
  showWindow();

  // Опционально: системное уведомление macOS
  // (но у вас уже есть в браузере)
});

// Запуск приложения
app.whenReady().then(() => {
  createWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      showWindow();
    }
  });
});

// Выход из приложения
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Полный выход
app.on('before-quit', () => {
  app.isQuitting = true;
});

console.log('🚀 Telegram Alerts запущено');
