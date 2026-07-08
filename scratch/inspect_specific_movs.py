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
        SELECT mi.ID_Movimiento, mi.Fecha, mi.Observacion, mi.Estado, mi.ID_TipoMovimiento,
               dmi.ID_Producto, dmi.Cantidad, dmi.Costo_Unitario, dmi.Subtotal
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        WHERE mi.ID_Movimiento IN (88, 90, 94, 96, 99)
    """)
    print("\n=== SPECIFIC MOVEMENTS DETAILS ===")
    for row in cursor.fetchall():
        print(row)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
