import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(override=True)

from config.settings import DB_CONFIG
import mysql.connector

print("DB_CONFIG is:")
for k, v in DB_CONFIG.items():
    if k == 'password':
        print(f"  {k}: {repr(v[:2])}... (len={len(v)})")
    else:
        print(f"  {k}: {v}")

try:
    pool = mysql.connector.pooling.MySQLConnectionPool(**DB_CONFIG)
    print("Pool init succeeded!")
    conn = pool.get_connection()
    print("Connection from pool succeeded!")
    conn.close()
except Exception as e:
    import traceback
    traceback.print_exc()
