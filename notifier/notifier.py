from telethon.sync import TelegramClient
from datetime import datetime, time, timezone
import asyncio
import pytz

# 🔐 ДАННЫЕ ПЕРВОГО ТЕЛЕГРАМ-АККАУНТА
api_id = 19764091
api_hash = 'f55d30a423779a6320f220ae2bbc25f3'
channel_name = 'utracone'

local_tz = pytz.timezone('Europe/Warsaw')
today_start = datetime.combine(datetime.now().date(), time.min).replace(tzinfo=timezone.utc)

# Чаты, которые нужно игнорировать (по фрагментам)
EXCLUDED_KEYWORDS = [
    "бизнес в польше", "законы", "спулки", "ип в польше",
    "mcg warszawa", "invoices", "kadry", "telegram", "utracone"
]

def is_excluded(dialog):
    title = (getattr(dialog, 'name', '') or getattr(dialog.entity, 'title', '') or '').lower()
    return any(keyword in title for keyword in EXCLUDED_KEYWORDS)

async def main():
    async with TelegramClient('notifier', api_id, api_hash) as client:
        me = await client.get_me()
        dialogs = await client.get_dialogs(limit=300)

        channel = next((d for d in dialogs if d.name == channel_name and d.is_channel), None)
        if not channel:
            print(f"❌ Канал '{channel_name}' не найден.")
            return

        unanswered = []

        for dialog in dialogs:
            if is_excluded(dialog):
                continue

            entity = dialog.entity
            if getattr(entity, 'bot', False) or entity.id == me.id:
                continue

            last_msg = dialog.message
            if not last_msg or last_msg.date < today_start:
                continue

            await last_msg.get_sender()
            sender = last_msg.sender

            if dialog.unread_count == 0 and sender and sender.id != me.id:
                name = dialog.name or getattr(entity, 'username', 'Без имени')
                local_time = last_msg.date.astimezone(local_tz).strftime('%H:%M')
                message_text = last_msg.message or '[нет текста]'
                unanswered.append((name, local_time, message_text.strip()))

        if unanswered:
            msg = "📋 *Чаты без ответа (основной аккаунт):*\n\n"
            for name, time_str, text in unanswered:
                msg += f"– {name} ({time_str})\n  💬 {text}\n\n"
            msg = msg[:4000] + "..." if len(msg) > 4000 else msg
            await client.send_message(entity=channel.entity, message=msg)
        else:
            await client.send_message(entity=channel.entity, message="✅ Сегодня все чаты с ответом.")

if __name__ == '__main__':
    asyncio.run(main())

