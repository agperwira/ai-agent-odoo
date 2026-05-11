"""
Entry point CLI — jalankan dengan: python main.py
Untuk Telegram bot: python main_telegram.py
"""

from datetime import datetime
from utils.agent   import chat_with_agent
from utils.session import save_history


def main():
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=== Widya Analytics AI Agent for Odoo ===")
    print(f"Session : {session_id}")
    print("Perintah: 'clear' = reset sesi | 'exit' = keluar\n")

    while True:
        try:
            inp = input("Anda: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar.")
            break

        if not inp:
            continue
        if inp.lower() in ('exit', 'quit'):
            break
        if inp.lower() == 'clear':
            save_history(session_id, [])
            print("Riwayat sesi direset.\n")
            continue

        print(chat_with_agent(inp, session_id), "\n")


if __name__ == "__main__":
    main()
