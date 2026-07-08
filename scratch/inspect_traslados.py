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
    
    # 1. Columns of movimientos_inventario
    cursor.execute("DESCRIBE movimientos_inventario")
    print("\n=== COLUMNS OF movimientos_inventario ===")
    for col in cursor.fetchall():
        print(f"{col['Field']}: {col['Type']}")
        
    # 2. Get a few examples of ID_TipoMovimiento = 6 (Traslado)
    cursor.execute("""
        SELECT mi.ID_Movimiento, mi.Fecha, mi.ID_Bodega, mi.ID_Bodega_Destino, mi.ID_TipoMovimiento, dmi.ID_Producto, dmi.Cantidad
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        WHERE mi.ID_TipoMovimiento = 6
        LIMIT 5
    """)
    print("\n=== EXAMPLES OF ID_TipoMovimiento = 6 ===")
    for row in cursor.fetchall():
        print(row)
        
    # 3. Get a few examples of ID_TipoMovimiento = 12 (Traslado Salida)
    cursor.execute("""
        SELECT mi.ID_Movimiento, mi.Fecha, mi.ID_Bodega, mi.ID_Bodega_Destino, mi.ID_TipoMovimiento, dmi.ID_Producto, dmi.Cantidad
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        WHERE mi.ID_TipoMovimiento = 12
        LIMIT 5
    """)
    print("\n=== EXAMPLES OF ID_TipoMovimiento = 12 ===")
    for row in cursor.fetchall():
        print(row)

    # 4. Get a few examples of ID_TipoMovimiento = 13 (Traslado Entrada)
    cursor.execute("""
        SELECT mi.ID_Movimiento, mi.Fecha, mi.ID_Bodega, mi.ID_Bodega_Destino, mi.ID_TipoMovimiento, dmi.ID_Producto, dmi.Cantidad
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        WHERE mi.ID_TipoMovimiento = 13
        LIMIT 5
    """)
    print("\n=== EXAMPLES OF ID_TipoMovimiento = 13 ===")
    for row in cursor.fetchall():
        print(row)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
