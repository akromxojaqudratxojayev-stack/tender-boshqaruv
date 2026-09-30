import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from database import get_connection
from bot import bot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def calculate_reminders(deadline: datetime):
    now = datetime.now()
    time_left = deadline - now
    hours_left = time_left.total_seconds() / 3600
    
    remind_now = False
    reminder_text = ""
    
    if 47 < hours_left <= 48:
        remind_now = True
        reminder_text = "⏳ Tender tugashiga 2 kun qoldi!"
    elif 23 < hours_left <= 24:
        remind_now = True
        reminder_text = "⏰ Tender tugashiga 1 kun qoldi!"
    elif 17 < hours_left <= 18:
        remind_now = True
        reminder_text = "⏰ Tender tugashiga 18 soat qoldi!"
    elif 0 < hours_left <= 12:
        hour_int = int(hours_left)
        if hour_int in [12, 9, 6, 3]:
            remind_now = True
            reminder_text = f"🔥 DIQQAT: Tender tugashiga {hour_int} soat qoldi!"
            
    return remind_now, reminder_text

def check_tenders():
    conn = get_connection()
    cursor = conn.cursor()
    
    # We fetch both active (for normal reminders) and played (for start notifications)
    cursor.execute("SELECT id, link, title, deadline, total_sum, company_name, delivery_term, status, is_started_notified FROM tenders WHERE status IN ('active', 'played')")
    tenders = cursor.fetchall()
    
    cursor.execute("SELECT telegram_id FROM users WHERE is_active=1")
    users = cursor.fetchall()
    
    for tender in tenders:
        tender_id, link, title, deadline_str, total_sum, company, delivery_term, status, is_started_notified = tender
        try:
            if isinstance(deadline_str, str):
                deadline = datetime.fromisoformat(deadline_str)
            else:
                deadline = deadline_str
        except:
            continue
            
        now = datetime.now()
        
        # 1. "O'YNALDI" (played) logikasi: faqatgina vaqti tugaganda 1 marta "O'yin boshlandi" xabari ketadi
        if status == 'played':
            if deadline <= now and not is_started_notified:
                for user in users:
                    user_id = user[0]
                    msg = (
                        f"🚀 <b>O'YIN BOSHLANDI!</b>\n\n"
                        f"📌 <b>Lot nomi:</b> {title}\n"
                        f"🏢 <b>Tashkilot:</b> {company}\n"
                        f"💰 <b>Jami summa:</b> {total_sum}\n"
                        f"🔗 <b>Havola:</b> {link}"
                    )
                    try:
                        bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
                    except: pass
                # Mark as notified
                cursor.execute("UPDATE tenders SET is_started_notified=1 WHERE id=?", (tender_id,))
                conn.commit()
            continue # played status uchun normal eslatmalar ketmaydi
            
        # 2. "ACTIVE" logikasi: normal eslatmalar
        if status == 'active' and deadline > now:
            should_remind, text = calculate_reminders(deadline)
            if should_remind:
                for user in users:
                    user_id = user[0]
                    cursor.execute("SELECT id FROM user_tender_mutes WHERE user_telegram_id=? AND tender_id=?", (user_id, tender_id))
                    is_muted = cursor.fetchone()
                    
                    if not is_muted:
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton(text="🔕 Men uchun o'chirish", callback_data=f"mute_{tender_id}"))
                        
                        msg = (
                            f"{text}\n\n"
                            f"📌 <b>Lot nomi:</b> {title}\n"
                            f"🏢 <b>Tashkilot:</b> {company}\n"
                            f"💰 <b>Jami summa:</b> {total_sum}\n"
                            f"🚚 <b>Yetkazib berish:</b> {delivery_term}\n"
                            f"🔗 <b>Havola:</b> {link}"
                        )
                        try:
                            bot.send_message(chat_id=user_id, text=msg, reply_markup=markup, parse_mode="HTML")
                        except: pass
                        
    conn.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_tenders, 'interval', minutes=60)
    scheduler.start()
    print("Scheduler (eslatma tizimi) ishga tushdi...")
