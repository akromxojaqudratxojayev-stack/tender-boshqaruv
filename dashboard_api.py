from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from database import get_connection

app = FastAPI(title="Tender VIP Dashboard API")

class StatusUpdate(BaseModel):
    status: str

@app.get("/api/tenders")
def get_tenders():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenders ORDER BY id DESC")
    rows = cursor.fetchall()
    
    results = [dict(row) for row in rows]
    conn.close()
    return results

@app.put("/api/tenders/{tender_id}/status")
def update_tender_status(tender_id: int, payload: StatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tenders SET status=? WHERE id=?", (payload.status, tender_id))
    
    # Notify Telegram group if applicable
    try:
        cursor.execute("SELECT title, link, group_message_id, full_text FROM tenders WHERE id=?", (tender_id,))
    except:
        cursor.execute("SELECT title, link, group_message_id, NULL FROM tenders WHERE id=?", (tender_id,))
    tender = cursor.fetchone()
    
    if tender:
        title = tender[0]
        link = tender[1]
        msg_id = tender[2]
        full_text = tender[3]
        
        cursor.execute("SELECT value FROM settings WHERE key='group_id'")
        group_row = cursor.fetchone()
        if group_row and msg_id:
            group_id = int(group_row[0])
            import os
            import telebot
            from dotenv import load_dotenv
            load_dotenv()
            bot_token = os.getenv("BOT_TOKEN")
            if bot_token:
                bot = telebot.TeleBot(bot_token)
                try:
                    if payload.status == "rejected":
                        if full_text:
                            bot.send_message(group_id, f"❌ <b>RAD ETILDI</b>\n\n{full_text}", parse_mode="HTML", reply_to_message_id=msg_id, disable_web_page_preview=True)
                        else:
                            bot.send_message(group_id, f"❌ <b>RAD ETILDI</b>\n\n<a href='{link}'>{title}</a>", parse_mode="HTML", reply_to_message_id=msg_id)
                    elif payload.status == "played":
                        if full_text:
                            bot.send_message(group_id, f"✅ <b>QATNASHAMIZ</b>\n\n{full_text}\n\n<i>Tender hujjatlarini tayyorlashni boshlang.</i>", parse_mode="HTML", reply_to_message_id=msg_id, disable_web_page_preview=True)
                        else:
                            bot.send_message(group_id, f"✅ <b>QATNASHAMIZ</b>\n\n<a href='{link}'>{title}</a>\n\n<i>Tender hujjatlarini tayyorlashni boshlang.</i>", parse_mode="HTML", reply_to_message_id=msg_id)
                except Exception as e:
                    print("Telegram notification error:", e)
                    
    conn.commit()
    conn.close()
    return {"success": True, "status": payload.status}

@app.get("/api/stats")
def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    
    # PostgreSQL queries
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE DATE(created_at) = CURRENT_DATE AND status != 'rejected'")
    today_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline > CURRENT_TIMESTAMP AND deadline <= CURRENT_TIMESTAMP + INTERVAL '24 hours' AND status != 'rejected' AND DATE(created_at) != CURRENT_DATE")
    urgent_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline > CURRENT_TIMESTAMP + INTERVAL '24 hours' AND status != 'rejected' AND DATE(created_at) != CURRENT_DATE")
    far_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE (deadline <= CURRENT_TIMESTAMP OR status = 'rejected')")
    archive_count = cursor.fetchone()[0]
    
    conn.close()
    return {"today_count": today_count, "urgent_count": urgent_count, "far_count": far_count, "archive_count": archive_count}

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    with open("dashboard_ui/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/old", response_class=HTMLResponse)
def serve_old_dashboard():
    with open("dashboard_ui/old_index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/debug")
def debug():
    import os
    return {"cmd": os.popen("ps aux").read()}

class ToggleReminder(BaseModel):
    enabled: bool

@app.get("/api/settings/reminders")
def get_reminders_setting():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='reminders_enabled'")
    row = cursor.fetchone()
    conn.close()
    
    is_enabled = True if not row else (str(row[0]) == '1' or str(row[0]).lower() == 'true')
    return {"reminders_enabled": is_enabled}

@app.put("/api/settings/reminders")
def update_reminders_setting(payload: ToggleReminder):
    conn = get_connection()
    cursor = conn.cursor()
    val = '1' if payload.enabled else '0'
    
    cursor.execute("SELECT value FROM settings WHERE key='reminders_enabled'")
    exists = cursor.fetchone()
    if exists:
        cursor.execute("UPDATE settings SET value=? WHERE key='reminders_enabled'", (val,))
    else:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('reminders_enabled', ?)", (val,))
        
    conn.commit()
    conn.close()
    return {"reminders_enabled": payload.enabled}


@app.get('/api/clear-db')
def clear_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tenders')
    conn.commit()
    conn.close()
    return {'status': 'success', 'message': 'Barcha ma\'lumotlar tozalandi!'}
