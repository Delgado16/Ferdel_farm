import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn_config = {
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'admin'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'database': os.environ.get('DB_NAME', 'db_ferdel')
}

try:
    conn = mysql.connector.connect(**conn_config)
    cursor = conn.cursor(dictionary=True)
    
    # catalogo_movimientos
    cursor.execute("SELECT * FROM catalogo_movimientos")
    print("\n=== CATALOGO MOVIMIENTOS ===")
    for c in cursor.fetchall():
        print(c)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
