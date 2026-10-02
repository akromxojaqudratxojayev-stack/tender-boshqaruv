import os
import re
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
        data = asyncio.run(parse_tender(url))
    except Exception as e:
        bot.edit_message_text(f"Xatolik yuz berdi: {e}", chat_id=msg.chat.id, message_id=msg.message_id)
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tenders WHERE link=?", (data['link'],))
    tender = cursor.fetchone()
    
    if not tender:
        cursor.execute('''INSERT INTO tenders (link, title, deadline, start_date, total_sum, deposit_sum, company_name, delivery_term, source_site) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id''',
                       (data['link'], data['title'], data['deadline'], data['start_date'], 
                        data['total_sum'], data['deposit_sum'], data['company_name'], data.get('delivery_term', "Noma'lum"), data['source_site']))
        res = cursor.fetchone()
        tender_id = res[0] if res else cursor.lastrowid
        conn.commit()
        
        send_tender_to_group(tender_id, data, msg)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(text="✅ Ha, yangilash", callback_data=f"upd_yes_{tender['id']}"),
            types.InlineKeyboardButton(text="❌ Yo'q", callback_data=f"upd_no_{tender['id']}")
        )
        bot.edit_message_text("⚠️ Bu tender oldin qo'shilgan. Ma'lumotlarni yangilaysizmi?", 
                              chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=markup)
        
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

def build_group_markup(tender_id):
    markup = types.InlineKeyboardMarkup()
    # "O'ynash" - Play
    markup.add(
        types.InlineKeyboardButton(text="🎮 O'ynash", callback_data=f"play_{tender_id}"),
        types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{tender_id}")
    )
    return markup

def send_tender_to_group(tender_id, data, msg, is_update=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='group_id'")
    group_row = cursor.fetchone()
    
    result_text = build_tender_text(data, tender_id, is_update)
    markup = build_group_markup(tender_id)
    
    if group_row:
        group_id = int(group_row[0])
        try:
            sent_msg = bot.send_message(chat_id=group_id, text=result_text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
            cursor.execute("UPDATE tenders SET group_message_id=? WHERE id=?", (sent_msg.message_id, tender_id))
            conn.commit()
            bot.edit_message_text("✅ Tender guruhga yuborildi va bazaga qo'shildi!" if not is_update else "✅ Tender ma'lumotlari yangilandi va guruhga qayta yuborildi!", 
                                  chat_id=msg.chat.id, message_id=msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"Tender qo'shildi, lekin guruhga yuborishda xatolik: {e}", chat_id=msg.chat.id, message_id=msg.message_id)
    else:
        bot.edit_message_text("Tender qo'shildi, lekin asosiy guruh belgilanmagan (/set_group ni guruhda ishlating).", chat_id=msg.chat.id, message_id=msg.message_id)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('upd_'))
def handle_update(call):
    parts = call.data.split('_')
    action = parts[1]
    tender_id = parts[2]
    
    if action == 'no':
        bot.edit_message_text("❌ Yangilanmadi. Eski ma'lumot saqlab qolindi.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        return
        
    bot.edit_message_text("⏳ Yangilanmoqda...", chat_id=call.message.chat.id, message_id=call.message.message_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT link, group_message_id FROM tenders WHERE id=?", (tender_id,))
    row = cursor.fetchone()
    
    if not row:
        bot.edit_message_text("Ma'lumot topilmadi, iltimos havolani qayta yuboring.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        conn.close()
        return
        
    url = row['link'] if type(row) is dict else row[0]
    group_msg_id = row['group_message_id'] if type(row) is dict else row[1]
    
    try:
        data = asyncio.run(parse_tender(url))
    except Exception as e:
        bot.edit_message_text(f"Xatolik yuz berdi: {e}", chat_id=call.message.chat.id, message_id=call.message.message_id)
        conn.close()
        return
        
    cursor.execute('''UPDATE tenders SET title=?, deadline=?, start_date=?, total_sum=?, deposit_sum=?, company_name=?, delivery_term=?, source_site=? WHERE id=?''',
                   (data['title'], data['deadline'], data['start_date'], data['total_sum'], data['deposit_sum'], data['company_name'], data.get('delivery_term', "Noma'lum"), data['source_site'], tender_id))
    cursor.execute("DELETE FROM user_tender_mutes WHERE tender_id=?", (tender_id,))
    conn.commit()
    
    cursor.execute("SELECT value FROM settings WHERE key='group_id'")
    group_row = cursor.fetchone()
    if group_row and group_msg_id:
        group_id = int(group_row[0])
        try:
            bot.delete_message(chat_id=group_id, message_id=group_msg_id)
        except Exception as e:
            print("Failed to delete message: ", e)
            
    send_tender_to_group(tender_id, data, call.message, is_update=True)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('play_'))
def handle_play(call):
    tender_id = call.data.split('_')[1]
    try:
        old_text = call.message.html_text
        old_text = re.sub(r'^(✅ QATNASHAMIZ|❌ RAD ETILDI)\n+', '', old_text)
        old_text = re.sub(r'\n+👤 Qaror: .*', '', old_text)
        
        new_text = f"✅ QATNASHAMIZ\n{old_text}\n\n👤 Qaror: {call.from_user.first_name}"
        bot.edit_message_text(new_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=build_group_markup(tender_id), disable_web_page_preview=True)
        bot.send_message(call.message.chat.id, "Tender hujjatlarini tayyorlashni boshlang.", reply_to_message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Siz 'O'ynash' tugmasini bosdingiz!", show_alert=False)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def handle_reject(call):
    tender_id = call.data.split('_')[1]
    try:
        old_text = call.message.html_text
        old_text = re.sub(r'^(✅ QATNASHAMIZ|❌ RAD ETILDI)\n+', '', old_text)
        old_text = re.sub(r'\n+👤 Qaror: .*', '', old_text)
        
        new_text = f"❌ RAD ETILDI\n{old_text}\n\n👤 Qaror: {call.from_user.first_name}"
        bot.edit_message_text(new_text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", disable_web_page_preview=True)
        bot.answer_callback_query(call.id, "Tender rad etildi!", show_alert=False)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Xatolik: {e}")

def main():
    print("Bot ishga tushdi...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
