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
    
    cursor.execute("""
        SELECT cm.Descripcion, MIN(dmi.Cantidad) as Min_Cant, MAX(dmi.Cantidad) as Max_Cant
        FROM detalle_movimientos_inventario dmi
        JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
        JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
        GROUP BY cm.Descripcion
    """)
    print("\n=== MIN/MAX QUANTITIES PER TYPE ===")
    for row in cursor.fetchall():
        print(row)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
