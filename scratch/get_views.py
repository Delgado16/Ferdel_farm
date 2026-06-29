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

views = ['vista_gastos_unificados', 'vista_kardex_productos', 'vw_entradas_inventario']

try:
    conn = mysql.connector.connect(**conn_config)
    cursor = conn.cursor()
    
    for view in views:
        try:
            cursor.execute(f"SHOW CREATE VIEW {view}")
            res = cursor.fetchone()
            print(f"\n--- {view} ---")
            print(res[1])
        except Exception as ve:
            print(f"Error reading view {view}: {ve}")
            
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
