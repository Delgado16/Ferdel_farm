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
    
    # Let's count movements per type
    cursor.execute("""
        SELECT cm.ID_TipoMovimiento, cm.Descripcion, cm.Letra, cm.Adicion, COUNT(mi.ID_Movimiento) as Total_Movimientos
        FROM catalogo_movimientos cm
        LEFT JOIN movimientos_inventario mi ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
        GROUP BY cm.ID_TipoMovimiento, cm.Descripcion, cm.Letra, cm.Adicion
    """)
    print("\n=== MOVIMIENTOS POR TIPO ===")
    for row in cursor.fetchall():
        print(row)
        
    # Let's also check if there are any movements that might have 0 entry and 0 exit in the current logic
    cursor.execute("""
        SELECT DISTINCT cm.ID_TipoMovimiento, cm.Descripcion, cm.Letra, cm.Adicion
        FROM catalogo_movimientos cm
        WHERE NOT (cm.Adicion LIKE '%SUMA%' OR cm.Adicion = '+' OR cm.Letra IN ('E', 'C'))
          AND NOT (cm.Adicion LIKE '%RESTA%' OR cm.Adicion = '-' OR cm.Letra IN ('S', 'V'))
    """)
    print("\n=== TIPOS QUE NO ENTRAN NI EN SUMA NI EN RESTA ACTUALMENTE ===")
    for row in cursor.fetchall():
        print(row)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
