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
    
    cursor.execute("SHOW TRIGGERS LIKE 'detalle_movimientos_inventario'")
    print("\n=== TRIGGERS ON detalle_movimientos_inventario ===")
    for row in cursor.fetchall():
        print(f"Trigger: {row['Trigger']}")
        print(f"Event: {row['Event']}")
        print(f"Timing: {row['Timing']}")
        print(f"Statement:\n{row['Statement']}")
        print("-" * 50)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
