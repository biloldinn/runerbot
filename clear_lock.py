import os
from database import db

def main():
    print("Clearing instance locks (Sync)...")
    from database import db
    db.system_locks.delete_many({})
    print("Done. You can now start the bot locally.")

if __name__ == "__main__":
    main()
