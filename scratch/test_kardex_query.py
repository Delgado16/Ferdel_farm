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
    
    fecha_inicio = '2025-01-01'
    fecha_fin = '2026-12-31'
    tipo_movimiento_id = '' # None to test without filter
    
    query = """
        SELECT 
            b.Nombre AS Bodega,
            mi.Fecha,
            cm.Descripcion AS Tipo_Movimiento,
            mi.ID_Movimiento AS Documento_ID,
            p.COD_Producto AS Codigo,
            p.Descripcion AS Producto,
            CASE 
                WHEN cm.Letra IN ('E', 'C', 'TE') THEN ABS(dmi.Cantidad) 
                ELSE 0.00 
            END AS Cantidad_Entrada,
            CASE 
                WHEN cm.Letra IN ('S', 'V', 'TS', 'T') THEN ABS(dmi.Cantidad) 
                ELSE 0.00 
            END AS Cantidad_Salida,
            dmi.Costo_Unitario,
            ABS(dmi.Subtotal) AS Subtotal_Movimiento,
            u.NombreUsuario AS Creado_Por
        FROM movimientos_inventario mi
        JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
        JOIN productos p ON dmi.ID_Producto = p.ID_Producto
        JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
        JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
        JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
        WHERE mi.Estado = 'Activa'
          AND mi.Fecha BETWEEN %s AND %s
    """
    params = [fecha_inicio, fecha_fin]
    
    cursor.execute(query, params)
    res = cursor.fetchall()
    print(f"\nTotal movements without filter: {len(res)}")
    print("Examples:")
    for row in res[:5]:
        print(row)
        
    # Let's test with filter = 12 (Traslado Salida)
    query_filtered = query + " AND mi.ID_TipoMovimiento = %s"
    params_filtered = [fecha_inicio, fecha_fin, 12]
    cursor.execute(query_filtered, params_filtered)
    res_filtered = cursor.fetchall()
    print(f"\nTotal TS (Traslado Salida) movements: {len(res_filtered)}")
    print("Examples:")
    for row in res_filtered[:5]:
        print(row)

    # Let's test with filter = 13 (Traslado Entrada)
    params_filtered_te = [fecha_inicio, fecha_fin, 13]
    cursor.execute(query_filtered, params_filtered_te)
    res_filtered_te = cursor.fetchall()
    print(f"\nTotal TE (Traslado Entrada) movements: {len(res_filtered_te)}")
    print("Examples:")
    for row in res_filtered_te[:5]:
        print(row)
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Error:", e)
