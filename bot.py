import os
import telebot
from telebot import types
from dotenv import load_dotenv
from database import get_connection, init_db
from scraper import parse_tender
import asyncio

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "BU_YERGA_TOKEN_YOZILADI")

init_db()

bot = telebot.TeleBot(TOKEN)
pending_updates = {}

@bot.message_handler(commands=['set_group'])
def set_group(message):
    if message.chat.type in ['group', 'supergroup']:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", ('group_id', str(message.chat.id)))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ Ushbu guruh tenderlar keladigan asosiy guruh sifatida belgilandi!")
    else:
        bot.reply_to(message, "Bu buyruqni faqat guruhlarda ishlatish mumkin.")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Assalomu alaykum! Menga tender havolasini yuboring (etender.uzex.uz, xarid.uzex.uz, xt-xarid.uz). Men ma'lumotlarni yig'ib bazaga qo'shaman va guruhga yuboraman.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    valid_sites = ["etender.uzex.uz", "xarid.uzex.uz", "xt-xarid.uz"]
    if not any(site in url for site in valid_sites):
        bot.reply_to(message, "❌ Xatolik! Kechirasiz, tizim faqat tender saytlari bilan ishlaydi (etender.uzex.uz, xarid.uzex.uz, xt-xarid.uz). Boshqa havolalar qabul qilinmaydi.")
        return
        
    msg = bot.reply_to(message, "⏳ Havola qabul qilindi! Ma'lumotlar olinmoqda (brauzer tekshirmoqda, ozgina kuting)...")
    
    data = asyncio.run(parse_tender(url))
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tenders WHERE link=%s", (data['link'],))
    tender = cursor.fetchone()
    
    if not tender:
        cursor.execute('''INSERT INTO tenders (link, title, deadline, start_date, total_sum, deposit_sum, company_name, delivery_term, source_site) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                       (data['link'], data['title'], data['deadline'], data['start_date'], 
                        data['total_sum'], data['deposit_sum'], data['company_name'], data.get('delivery_term', 'Noma\'lum'), data['source_site']))
        tender_id = cursor.fetchone()[0]
        conn.commit()
        
        delivery = data.get('delivery_term', "Noma'lum")
        items_str = data.get('items_str', '')
        result_text = (
            f"✅ <b>Yangi tender tizimga qo'shildi!</b>\n\n"
            f"📌 <b>Lot nomi:</b> {data['title']}\n"
            f"🏢 <b>Tashkilot:</b> {data['company_name']}\n"
            f"💰 <b>Jami summa:</b> {data['total_sum']}\n"
            f"🔒 <b>Zakalat:</b> {data['deposit_sum']}\n"
            f"🚚 <b>Yetkazib berish muddati:</b> {delivery}\n"
            f"📅 <b>Boshlanish:</b> {data['start_date'].strftime('%Y-%m-%d %H:%M')}\n"
            f"⏳ <b>Tugash vaqti:</b> {data['deadline'].strftime('%Y-%m-%d %H:%M')}\n{items_str}\n\n"
            f"🔗 <b>Havola:</b> {data['link']}"
        )
        
        # Check if group is configured
        cursor.execute("SELECT value FROM settings WHERE key='group_id'")
        group_row = cursor.fetchone()
        
        if group_row:
            group_id = int(group_row[0])
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="🔕 Men uchun o'chirish", callback_data=f"mute_{tender_id}"))
            
            try:
                sent_msg = bot.send_message(chat_id=group_id, text=result_text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
                cursor.execute("UPDATE tenders SET group_message_id=%s WHERE id=%s", (sent_msg.message_id, tender_id))
                conn.commit()
                bot.edit_message_text("✅ Muvaffaqiyatli! Tender bazaga qo'shildi va guruhga yuborildi.", chat_id=msg.chat.id, message_id=msg.message_id)
            except Exception as e:
                bot.edit_message_text(f"⚠️ Bazaga qo'shildi, lekin guruhga yuborishda xatolik: {e}", chat_id=msg.chat.id, message_id=msg.message_id)
        else:
            bot.edit_message_text("⚠️ Bazaga qo'shildi, lekin asosiy guruh belgilanmagan. /set_group orqali guruhni belgilang.", chat_id=msg.chat.id, message_id=msg.message_id)
            
    else:
        bot.edit_message_text("ℹ️ Bu tender avvalroq bazaga qo'shilgan ekan.", chat_id=msg.chat.id, message_id=msg.message_id)
        
    conn.close()

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    run_bot()
