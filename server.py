import os
import threading
import uvicorn
from dashboard_api import app
from bot import main as bot_main
from scheduler import start_scheduler
from dotenv import load_dotenv

load_dotenv()

def run_bot_and_scheduler():
    start_scheduler()
    bot_main()

if __name__ == "__main__":
    # Start bot and scheduler in a background thread
    t = threading.Thread(target=run_bot_and_scheduler, daemon=True)
    t.start()
    
    # Start FastAPI server on main thread
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
