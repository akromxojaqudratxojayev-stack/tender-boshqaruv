import os
print("Checking Playwright dependencies...")
os.system("python -m playwright install chromium")

import os
import re
import telebot
from dotenv import load_dotenv
from database import get_connection, init_db
from scraper import parse_tender
import asyncio
import threading

scrape_lock = threading.Lock()

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "BU_YERGA_TOKEN_YOZILADI")

init_db()

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['set_group'])
def set_group(message):
    if message.chat.type in ['group', 'supergroup']:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('group_id', str(message.chat.id)))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ Ushbu guruh tenderlar keladigan asosiy guruh sifatida belgilandi!")
    else:
        bot.reply_to(message, "❌ Bu buyruqni faqat guruhda ishlatish mumkin.")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (telegram_id, full_name) VALUES (?, ?)", (message.from_user.id, message.from_user.first_name))
        conn.commit()
    conn.close()
    bot.reply_to(message, f"Assalomu alaykum, {message.from_user.first_name}!\nTender eslatma tizimiga xush kelibsiz.\nMenga tender havolasini (linkini) yuboring.")

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    url = message.text.strip()
    valid_sites = ["etender.uzex.uz", "xarid.uzex.uz", "xt-xarid.uz"]
    if not any(site in url for site in valid_sites):
        bot.reply_to(message, "❌ Xatolik! Kechirasiz, tizim faqat tender saytlari bilan ishlaydi (etender.uzex.uz, xarid.uzex.uz, xt-xarid.uz). Boshqa havolalar qabul qilinmaydi.")
        return
        
    msg = bot.reply_to(message, "⏳ Havola qabul qilindi! Ma'lumotlar olinmoqda (brauzer tekshirmoqda, ozgina kuting)...")
    
    try:
        with scrape_lock:
            data = parse_tender(url)
    except Exception as e:
        bot.edit_message_text(f"Xatolik yuz berdi: {e}", chat_id=msg.chat.id, message_id=msg.message_id)
        return
        
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tenders WHERE link=?", (data['link'],))
        tender = cursor.fetchone()
        
        if not tender:
            full_text_val = build_tender_text(data, 0)
            cursor.execute('''INSERT INTO tenders (link, title, deadline, start_date, total_sum, deposit_sum, company_name, delivery_term, source_site, full_text) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id''',
                           (data['link'], data['title'], data['deadline'], data['start_date'], 
                            data['total_sum'], data['deposit_sum'], data['company_name'], data.get('delivery_term', "Noma'lum"), data['source_site'], full_text_val))
            res = cursor.fetchone()
            tender_id = res[0] if res else cursor.lastrowid
            conn.commit()
            
            full_text_val = build_tender_text(data, tender_id)
            cursor.execute("UPDATE tenders SET full_text=? WHERE id=?", (full_text_val, tender_id))
            conn.commit()
            send_tender_to_group(tender_id, data, msg)
        else:
            bot.edit_message_text("⚠️ Bu tender oldin tizimga qo'shilgan va bazada mavjud.", 
                                  chat_id=msg.chat.id, message_id=msg.message_id)
            
        conn.close()
    except Exception as e:
        bot.edit_message_text(f"Xatolik (Baza): {e}", chat_id=msg.chat.id, message_id=msg.message_id)
        if 'conn' in locals():
            conn.close()

def build_tender_text(data, tender_id, is_update=False):
    lot_match = re.search(r'/(\d+)$', data['link'])
    lot_num = lot_match.group(1) if lot_match else "Noma'lum"
    
    items_str = data.get('items_str', '')
    
    text = f"Tender #{tender_id} · lot {lot_num}\n\n"
    text += f"📌 {data['title']}\n"
    text += f"🏛 {data['company_name']}\n"
    text += f"💰 {data['total_sum']}\n"
    text += f"⏳ Muddat: {data['deadline'].strftime('%d.%m.%Y %H:%M')}\n\n"
    
    if items_str:
        text += f"{items_str}\n\n"
        
    text += f"🔗 {data['link']}"
    
    return text

def send_tender_to_group(tender_id, data, msg, is_update=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='group_id'")
    group_row = cursor.fetchone()
    
    result_text = build_tender_text(data, tender_id, is_update)
    
    if group_row:
        group_id = int(group_row[0])
        try:
            sent_msg = bot.send_message(chat_id=group_id, text=result_text, parse_mode="HTML", disable_web_page_preview=True)
            cursor.execute("UPDATE tenders SET group_message_id=? WHERE id=?", (sent_msg.message_id, tender_id))
            conn.commit()
            bot.edit_message_text("✅ Tender guruhga yuborildi va bazaga qo'shildi!", 
                                  chat_id=msg.chat.id, message_id=msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"Tender qo'shildi, lekin guruhga yuborishda xatolik: {e}", chat_id=msg.chat.id, message_id=msg.message_id)
    else:
        bot.edit_message_text("Tender qo'shildi, lekin asosiy guruh belgilanmagan (/set_group ni guruhda ishlating).", chat_id=msg.chat.id, message_id=msg.message_id)
    conn.close()

def main():
    print("Bot ishga tushdi...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
