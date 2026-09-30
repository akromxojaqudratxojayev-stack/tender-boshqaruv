from bot import main as bot_main
from scheduler import start_scheduler
from dotenv import load_dotenv

load_dotenv()

def start():
    print("Tizim ishga tushirilmoqda...")
    start_scheduler()
    bot_main()

if __name__ == "__main__":
    try:
        start()
    except KeyboardInterrupt:
        print("Tizim to'xtatildi.")
