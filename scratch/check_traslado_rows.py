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
    
    # Check details of ID_Movimiento = 250
    cursor.execute("""
        SELECT mi.ID_Movimiento, mi.ID_Bodega, mi.ID_Bodega_Destino, mi.ID_TipoMovimiento,
               dmi.ID_Producto, dmi.Cantidad, dmi.Costo_Unitario
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        WHERE mi.ID_Movimiento = 250
    """)
    print("\n=== DETAIL FOR ID_Movimiento = 250 ===")
    for row in cursor.fetchall():
        print(row)
        
    # Check if there is another movement for destination of 250 on the same date/product
    cursor.execute("""
        SELECT mi.ID_Movimiento, mi.ID_Bodega, mi.ID_Bodega_Destino, mi.ID_TipoMovimiento,
               dmi.ID_Producto, dmi.Cantidad, dmi.Costo_Unitario
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        WHERE mi.Fecha = '2026-02-06' AND dmi.ID_Producto = 5
    """)
    print("\n=== ALL MOVEMENTS ON 2026-02-06 FOR PRODUCT 5 ===")
    for row in cursor.fetchall():
        print(row)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
