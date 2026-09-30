from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3
import os

app = FastAPI(title="Tender VIP Dashboard API")

DB_PATH = "tendir.db"

class StatusUpdate(BaseModel):
    status: str

def get_connection():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

@app.get("/api/tenders")
def get_tenders():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenders ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.put("/api/tenders/{tender_id}/status")
def update_tender_status(tender_id: int, payload: StatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tenders SET status=? WHERE id=?", (payload.status, tender_id))
    conn.commit()
    conn.close()
    return {"success": True, "status": payload.status}

@app.get("/api/stats")
def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Bugun qo'shilganlar
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE date(created_at) = date('now', 'localtime') AND status != 'rejected'")
    today_count = cursor.fetchone()[0]
    
    # 1 kun qoldi (Shoshilinch: deadline hozirdan boshlab 24 soat ichida)
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline > datetime('now', 'localtime') AND deadline <= datetime('now', '+24 hours', 'localtime') AND status != 'rejected'")
    urgent_count = cursor.fetchone()[0]
    
    # Uzoqroq (deadline 24 soatdan uzoq)
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline > datetime('now', '+24 hours', 'localtime') AND status != 'rejected'")
    far_count = cursor.fetchone()[0]
    
    # Arxiv (Muddati o'tganlar yoki Rad etilganlar)
    cursor.execute("SELECT COUNT(*) FROM tenders WHERE deadline <= datetime('now', 'localtime') OR status = 'rejected'")
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
