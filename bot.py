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
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('group_id', str(message.chat.id)))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ Ushbu guruh tenderlar keladigan asosiy guruh sifatida belgilandi!")
    else:
        bot.reply_to(message, "❌ Bu buyruqni faqat guruhda ishlatish mumkin.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (message.from_user.id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (telegram_id, full_name) VALUES (?, ?)", (message.from_user.id, message.from_user.first_name))
        conn.commit()
    conn.close()
    
    bot.reply_to(
        message, 
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        "Tender eslatma tizimiga xush kelibsiz.\n"
        "Menga tender havolasini (linkini) yuboring."
    )

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    url = message.text.strip()
    
    valid_sites = ["etender.uzex.uz", "xarid.uzex.uz", "xt-xarid.uz"]
    if not any(site in url for site in valid_sites):
        bot.reply_to(message, "❌ Xatolik! Kechirasiz, tizim faqat tender saytlari bilan ishlaydi (etender.uzex.uz, xarid.uzex.uz, xt-xarid.uz). Boshqa havolalar qabul qilinmaydi.")
        return
        
    msg = bot.reply_to(message, "⏳ Havola qabul qilindi! Ma'lumotlar olinmoqda (brauzer tekshirmoqda, ozgina kuting)...")
    
    data = asyncio.run(parse_tender(url))
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tenders WHERE link=?", (data['link'],))
    tender = cursor.fetchone()
    
    if not tender:
        cursor.execute('''INSERT INTO tenders (link, title, deadline, start_date, total_sum, deposit_sum, company_name, delivery_term, source_site) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (data['link'], data['title'], data['deadline'], data['start_date'], 
                        data['total_sum'], data['deposit_sum'], data['company_name'], data.get('delivery_term', 'Noma\'lum'), data['source_site']))
        conn.commit()
        
        tender_id = cursor.lastrowid
        
        result_text = (
            f"✅ <b>Yangi tender tizimga qo'shildi!</b>\n\n"
            f"📌 <b>Lot nomi:</b> {data['title']}\n"
            f"🏢 <b>Tashkilot:</b> {data['company_name']}\n"
            f"💰 <b>Jami summa:</b> {data['total_sum']}\n"
            f"🔒 <b>Zakalat:</b> {data['deposit_sum']}\n"
            f"🚚 <b>Yetkazib berish muddati:</b> {data.get('delivery_term', 'Noma\'lum')}\n"
            f"📅 <b>Boshlanish:</b> {data['start_date'].strftime('%Y-%m-%d %H:%M')}\n"
            f"⏳ <b>Tugash vaqti:</b> {data['deadline'].strftime('%Y-%m-%d %H:%M')}\n"
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
                cursor.execute("UPDATE tenders SET group_message_id=? WHERE id=?", (sent_msg.message_id, tender_id))
                conn.commit()
                if str(message.chat.id) != str(group_id):
                    bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text="✅ Tender guruhga yuborildi va bazaga qo'shildi!")
                else:
                    bot.delete_message(chat_id=message.chat.id, message_id=msg.message_id)
            except Exception as e:
                bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=f"Tender qo'shildi, lekin guruhga yuborishda xatolik: {e}")
        else:
            bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text=result_text, parse_mode="HTML")
            
    else:
        tender_id = tender[0]
        pending_updates[msg.message_id] = data
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(text="✅ Ha, yangilash", callback_data=f"upd_yes_{tender_id}_{msg.message_id}"),
            types.InlineKeyboardButton(text="❌ Yo'q", callback_data=f"upd_no_{tender_id}_{msg.message_id}")
        )
        bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, 
                              text="⚠️ Bu tender oldin qo'shilgan. Ma'lumotlarni yangilaysizmi?", 
                              reply_markup=markup)
        
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('upd_'))
def process_update(call):
    parts = call.data.split('_')
    action = parts[1]
    tender_id = int(parts[2])
    msg_id = int(parts[3])
    
    if action == 'no':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ Yangilanmadi. Eski ma'lumot saqlab qolindi.")
        if msg_id in pending_updates:
            del pending_updates[msg_id]
        return
        
    if action == 'yes':
        data = pending_updates.get(msg_id)
        if not data:
            bot.answer_callback_query(call.id, "Ma'lumot topilmadi, iltimos havolani qayta yuboring.", show_alert=True)
            return
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''UPDATE tenders SET title=?, deadline=?, start_date=?, total_sum=?, deposit_sum=?, company_name=?, delivery_term=?, source_site=? WHERE id=?''', 
                       (data['title'], data['deadline'], data['start_date'], data['total_sum'], data['deposit_sum'], data['company_name'], data.get('delivery_term', 'Noma\'lum'), data['source_site'], tender_id))
        
        # O'chirish: yangi tender sifatida eslatmalar boshidan boshlanishi uchun
        cursor.execute("DELETE FROM user_tender_mutes WHERE tender_id=?", (tender_id,))
        conn.commit()
        
        result_text = (
            f"🔄 <b>Tender ma'lumotlari yangilandi!</b>\n\n"
            f"📌 <b>Lot nomi:</b> {data['title']}\n"
            f"🏢 <b>Tashkilot:</b> {data['company_name']}\n"
            f"💰 <b>Jami summa:</b> {data['total_sum']}\n"
            f"🔒 <b>Zakalat:</b> {data['deposit_sum']}\n"
            f"🚚 <b>Yetkazib berish muddati:</b> {data.get('delivery_term', 'Noma\'lum')}\n"
            f"📅 <b>Boshlanish:</b> {data['start_date'].strftime('%Y-%m-%d %H:%M')}\n"
            f"⏳ <b>Tugash vaqti:</b> {data['deadline'].strftime('%Y-%m-%d %H:%M')}\n"
            f"🔗 <b>Havola:</b> {data['link']}"
        )
        
        cursor.execute("SELECT group_message_id FROM tenders WHERE id=?", (tender_id,))
        old_msg_row = cursor.fetchone()
        old_group_msg_id = old_msg_row[0] if old_msg_row and old_msg_row[0] else None

        cursor.execute("SELECT value FROM settings WHERE key='group_id'")
        group_row = cursor.fetchone()
        
        if group_row:
            group_id = int(group_row[0])
            
            if old_group_msg_id:
                try: 
                    bot.delete_message(chat_id=group_id, message_id=old_group_msg_id)
                except Exception as e: 
                    print(f"Failed to delete message: {e}")
                
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="🔕 Men uchun o'chirish", callback_data=f"mute_{tender_id}"))
            
            try:
                new_sent_msg = bot.send_message(chat_id=group_id, text=result_text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
                cursor.execute("UPDATE tenders SET group_message_id=? WHERE id=?", (new_sent_msg.message_id, tender_id))
                conn.commit()
                
                if str(call.message.chat.id) != str(group_id):
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Tender ma'lumotlari yangilandi va guruhga qayta yuborildi!")
                else:
                    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except Exception as e:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Yangilandi, lekin guruhga yuborishda xatolik: {e}")
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=result_text, parse_mode="HTML")
            
        conn.close()
        
        if msg_id in pending_updates:
            del pending_updates[msg_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('mute_'))
def process_mute(call):
    tender_id = int(call.data.split('_')[1])
    telegram_id = call.from_user.id
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_tender_mutes WHERE user_telegram_id=? AND tender_id=?", (telegram_id, tender_id))
    mute_entry = cursor.fetchone()
    
    if not mute_entry:
        cursor.execute("INSERT INTO user_tender_mutes (user_telegram_id, tender_id) VALUES (?, ?)", (telegram_id, tender_id))
        conn.commit()
        bot.answer_callback_query(call.id, "Siz uchun ushbu tender bo'yicha eslatmalar o'chirildi! 🔕", show_alert=True)
        if call.message.chat.type == 'private':
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except:
                pass
    else:
        bot.answer_callback_query(call.id, "Siz bu tenderni allaqachon o'chirgansiz.")
        
    conn.close()

def main():
    print("Bot ishga tushdi...")
    bot.infinity_polling()
