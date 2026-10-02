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
    
    # Map rows to dict
    columns = ["id", "link", "title", "deadline", "source_site", "created_at", "start_date", "total_sum", "deposit_sum", "company_name", "delivery_term", "group_message_id", "status", "is_started_notified"]
    
    results = []
    for row in rows:
        results.append(dict(zip(columns, row)))
    conn.close()
    return results

@app.put("/api/tenders/{tender_id}/status")
def update_tender_status(tender_id: int, payload: StatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tenders SET status=? WHERE id=?", (payload.status, tender_id))
    
    # Notify Telegram group if applicable
    cursor.execute("SELECT title, link, group_message_id FROM tenders WHERE id=?", (tender_id,))
    tender = cursor.fetchone()
    if tender:
        title = tender[0]
        link = tender[1]
        msg_id = tender[2]
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
                        bot.send_message(group_id, f"❌ <b>RAD ETILDI:</b>\n<a href='{link}'>{title}</a>", parse_mode="HTML", reply_to_message_id=msg_id)
                    elif payload.status == "played":
                        bot.send_message(group_id, f"✅ <b>O'YNALMOQDA (O'ynash so'rovi):</b>\n<a href='{link}'>{title}</a>", parse_mode="HTML", reply_to_message_id=msg_id)
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
    
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline > CURRENT_TIMESTAMP AND deadline <= CURRENT_TIMESTAMP + INTERVAL '24 hours' AND status != 'rejected'")
    urgent_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline > CURRENT_TIMESTAMP + INTERVAL '24 hours' AND status != 'rejected'")
    far_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline <= CURRENT_TIMESTAMP OR status = 'rejected'")
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
