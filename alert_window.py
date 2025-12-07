<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8" />
    <title>Telegram Desktop Alerts</title>

    <!-- Socket.IO клиент -->
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js" crossorigin="anonymous"></script>

    <style>
        * {
            box-sizing: border-box;
        }

        html, body {
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #111827;
            color: #fff;
        }

        body {
            display: flex;
            flex-direction: column;
        }

        .status-bar {
            padding: 10px 16px;
            background: #020617;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            border-bottom: 1px solid #1f2937;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #ef4444;
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
        }

        .status-dot.connected {
            background: #22c55e;
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.8);
        }

        .status-text {
            opacity: 0.9;
        }

        .queue-info {
            padding: 6px 16px;
            font-size: 13px;
            color: #9ca3af;
            border-bottom: 1px solid #1f2937;
        }

        .queue-info strong {
            color: #fbbf24;
        }

        /* Оверлей */
        .overlay {
            position: fixed;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle at top, rgba(248, 113, 113, 0.3), transparent 60%),
                        radial-gradient(circle at bottom, rgba(248, 250, 252, 0.1), transparent 55%),
                        #111827;
            z-index: 1000;
        }

        .overlay.hidden {
            display: none;
        }

        .alert-card {
            width: min(900px, 92vw);
            max-height: 90vh;
            background: linear-gradient(145deg, #7f1d1d, #b91c1c);
            border-radius: 24px;
            padding: 28px 32px;
            box-shadow:
                0 30px 60px rgba(0, 0, 0, 0.55),
                0 0 0 2px rgba(248, 250, 252, 0.05);
            display: flex;
            flex-direction: column;
            gap: 18px;
            position: relative;
            overflow: hidden;
        }

        .alert-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at top right, rgba(254, 249, 195, 0.35), transparent 60%);
            pointer-events: none;
        }

        .alert-header {
            display: flex;
            align-items: center;
            gap: 12px;
            position: relative;
            z-index: 1;
        }

        .alert-icon {
            width: 42px;
            height: 42px;
            border-radius: 999px;
            background: rgba(248, 250, 252, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            border: 1px solid rgba(248, 250, 252, 0.4);
        }

        .alert-title-block {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .alert-title {
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }

        .alert-subtitle {
            font-size: 13px;
            opacity: 0.85;
        }

        .meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            font-size: 13px;
            opacity: 0.95;
            position: relative;
            z-index: 1;
        }

        .meta-pill {
            padding: 4px 9px;
            border-radius: 999px;
            background: rgba(30, 64, 175, 0.22);
            border: 1px solid rgba(191, 219, 254, 0.4);
        }

        .meta-pill.time {
            background: rgba(6, 95, 70, 0.25);
            border-color: rgba(187, 247, 208, 0.55);
        }

        .meta-pill.queue {
            background: rgba(30, 64, 175, 0.15);
            border-color: rgba(191, 219, 254, 0.4);
        }

        .message-box {
            margin-top: 4px;
            padding: 14px 16px;
            border-radius: 16px;
            background: rgba(15, 23, 42, 0.88);
            border: 1px solid rgba(248, 250, 252, 0.15);
            box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.7);
            white-space: pre-wrap;
            font-size: 15px;
            line-height: 1.55;
            overflow-y: auto;
            max-height: 40vh;
        }

        .form-row {
            display: flex;
            gap: 16px;
            margin-top: 8px;
            position: relative;
            z-index: 1;
            flex-wrap: wrap;
        }

        .field {
            flex: 1 1 220px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            font-size: 13px;
        }

        .field label {
            opacity: 0.9;
        }

        .field input[type="text"] {
            padding: 8px 10px;
            border-radius: 10px;
            border: 1px solid rgba(248, 250, 252, 0.35);
            background: rgba(15, 23, 42, 0.9);
            color: #f9fafb;
            font-size: 14px;
            outline: none;
        }

        .field input[type="text"]:focus {
            border-color: #fbbf24;
            box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.7);
        }

        .checkbox-row {
            flex: 1 1 220px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }

        .checkbox-row input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
        }

        .actions-row {
            margin-top: 10px;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            align-items: center;
            position: relative;
            z-index: 1;
        }

        .hint {
            font-size: 12px;
            opacity: 0.8;
        }

        .btn-confirm {
            padding: 10px 18px;
            border-radius: 999px;
            border: none;
            font-weight: 600;
            font-size: 14px;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            cursor: pointer;
            color: #111827;
            background: linear-gradient(to right, #facc15, #f97316);
            box-shadow:
                0 10px 25px rgba(15, 23, 42, 0.7),
                0 0 0 1px rgba(15, 23, 42, 0.9);
            transition: transform 0.05s ease, box-shadow 0.05s ease, filter 0.05s ease;
        }

        .btn-confirm:disabled {
            opacity: 0.55;
            cursor: default;
            filter: grayscale(0.6);
            box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.8);
        }

        .btn-confirm:not(:disabled):active {
            transform: translateY(1px);
            box-shadow:
                0 4px 12px rgba(15, 23, 42, 0.9),
                0 0 0 1px rgba(15, 23, 42, 0.9);
        }

        @media (max-width: 640px) {
            .alert-card {
                padding: 20px 16px;
                border-radius: 0;
                width: 100%;
                height: 100%;
            }

            .message-box {
                max-height: 50vh;
            }

            .form-row {
                flex-direction: column;
            }

            .actions-row {
                flex-direction: column;
                align-items: stretch;
            }

            .btn-confirm {
                width: 100%;
                justify-content: center;
            }
        }
    </style>
</head>
<body>

    <div class="status-bar">
        <div id="status-dot" class="status-dot"></div>
        <div id="status-text" class="status-text">Подключение к серверу...</div>
    </div>

    <div class="queue-info">
        Ожидающих уведомлений в очереди: <strong><span id="queue-count">0</span></strong>
    </div>

    <div id="alert-overlay" class="overlay hidden">
        <div class="alert-card">
            <div class="alert-header">
                <div class="alert-icon">⚠️</div>
                <div class="alert-title-block">
                    <div class="alert-title">Новое сообщение Telegram</div>
                    <div class="alert-subtitle">
                        Канал: <span id="channel-name">—</span>
                    </div>
                </div>
            </div>

            <div class="meta-row">
                <div class="meta-pill time">
                    Время: <span id="alert-time">—:—</span>,
                    дата: <span id="alert-date">__.__.____</span>
                </div>
                <div class="meta-pill queue">
                    В очереди ещё: <span id="queue-inline-count">0</span>
                </div>
            </div>

            <div class="message-box" id="message-text">
                Ожидаю сообщений из Telegram...
            </div>

            <div class="form-row">
                <div class="field">
                    <label for="user-name">Ваше имя (кто видел это сообщение):</label>
                    <input id="user-name" type="text" autocomplete="off" placeholder="Например: Мария" />
                </div>
                <div class="checkbox-row">
                    <input id="confirm-checkbox" type="checkbox" />
                    <label for="confirm-checkbox">
                        Я прочитал(а) сообщение и взял(а) его в работу
                    </label>
                </div>
            </div>

            <div class="actions-row">
                <div class="hint">
                    Уведомление нельзя пропустить — нужно подтвердить и указать имя.
                </div>
                <button id="confirm-btn" class="btn-confirm" disabled>
                    Подтвердить и закрыть
                </button>
            </div>
        </div>
    </div>

    <script>
        // Элементы
        const statusDot = document.getElementById("status-dot");
        const statusText = document.getElementById("status-text");
        const queueCountEl = document.getElementById("queue-count");
        const queueInlineEl = document.getElementById("queue-inline-count");

        const overlayEl = document.getElementById("alert-overlay");
        const channelNameEl = document.getElementById("channel-name");
        const messageTextEl = document.getElementById("message-text");
        const alertTimeEl = document.getElementById("alert-time");
        const alertDateEl = document.getElementById("alert-date");

        const userNameInput = document.getElementById("user-name");
        const confirmCheckbox = document.getElementById("confirm-checkbox");
        const confirmBtn = document.getElementById("confirm-btn");

        // Очередь уведомлений
        const alertQueue = [];
        let currentAlert = null;
        let isShowing = false;

        function updateQueueCounters() {
            const count = alertQueue.length;
            queueCountEl.textContent = String(count);
            queueInlineEl.textContent = String(count);
        }

        function showOverlay(alert) {
            currentAlert = alert;
            isShowing = true;

            channelNameEl.textContent = alert.channel_name || "Канал";
            messageTextEl.textContent = alert.message_text || "[Без текста]";
            alertTimeEl.textContent = alert.timestamp || "—:—";
            alertDateEl.textContent = alert.date || "__.__.____";

            userNameInput.value = "";
            confirmCheckbox.checked = false;
            confirmBtn.disabled = true;

            overlayEl.classList.remove("hidden");
            userNameInput.focus();
        }

        function hideOverlay() {
            overlayEl.classList.add("hidden");
            isShowing = false;
            currentAlert = null;
        }

        function showNextAlertIfAny() {
            updateQueueCounters();
            if (alertQueue.length === 0) {
                hideOverlay();
                return;
            }
            const next = alertQueue.shift();
            updateQueueCounters();
            showOverlay(next);
        }

        // Подключение Socket.IO
        const socket = io();

        socket.on("connect", () => {
            statusDot.classList.add("connected");
            statusText.textContent = "Подключено к серверу уведомлений";
        });

        socket.on("disconnect", () => {
            statusDot.classList.remove("connected");
            statusText.textContent = "Нет подключения к серверу";
        });

        socket.on("connected", (data) => {
            // Сервер присылает "connected" сразу после подключения — можно игнорировать
            console.log("Socket.IO handshake:", data);
        });

        // Главное событие от сервера
        socket.on("new_alert", (data) => {
            console.log("new_alert:", data);
            alertQueue.push(data);
            if (!isShowing) {
                showNextAlertIfAny();
            } else {
                updateQueueCounters();
            }
        });

        // Подтверждение с клиента
        function canConfirm() {
            return (
                currentAlert &&
                userNameInput.value.trim().length > 0 &&
                confirmCheckbox.checked
            );
        }

        userNameInput.addEventListener("input", () => {
            confirmBtn.disabled = !canConfirm();
        });

        confirmCheckbox.addEventListener("change", () => {
            confirmBtn.disabled = !canConfirm();
        });

        confirmBtn.addEventListener("click", () => {
            if (!currentAlert || !canConfirm()) {
                return;
            }

            const name = userNameInput.value.trim();

            socket.emit("alert_confirmed", {
                message_id: currentAlert.message_id,
                user_name: name,
            });

            // Переходим сразу к следующему алерту,
            // ответ от сервера используется только для логов.
            showNextAlertIfAny();
        });

        socket.on("confirmation_received", (data) => {
            console.log("Подтверждение принято сервером:", data);
        });
    </script>
</body>
</html>
