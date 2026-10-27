from app import app
from config.database import get_db_cursor

fecha_str = '2026-09-10'

with app.app_context():
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                u.ID_Usuario,
                u.NombreUsuario AS Vendedor,
                COUNT(DISTINCT fr.ID_FacturaRuta) AS Facturas,
                COALESCE(SUM(CASE WHEN fr.Credito_Contado = 1 THEN dfr.Total ELSE 0 END), 0) AS Ventas_Contado,
                COALESCE(SUM(CASE WHEN fr.Credito_Contado = 2 THEN dfr.Total ELSE 0 END), 0) AS Ventas_Credito,
                COALESCE(SUM(dfr.Total), 0) AS Total_Vendido
            FROM facturacion_ruta fr
            INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
            INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
            WHERE DATE(fr.Fecha_Creacion) = %s AND fr.Estado = 'Activa'
            GROUP BY u.ID_Usuario, u.NombreUsuario
        """, [fecha_str])
        vendedores_db = cursor.fetchall()
        print("Vendedores DB:", vendedores_db)

        # Gastos por vendedor en ruta
        cursor.execute("""
            SELECT 
                mcr.ID_Usuario,
                COALESCE(SUM(mcr.Monto), 0) AS Gastos_Ruta
            FROM movimientos_caja_ruta mcr
            WHERE mcr.Tipo = 'GASTO'
              AND mcr.Estado = 'ACTIVO'
              AND DATE(mcr.Fecha) = %s
            GROUP BY mcr.ID_Usuario
        """, [fecha_str])
        gastos_vendedores = {row['ID_Usuario']: float(row['Gastos_Ruta']) for row in cursor.fetchall()}
        print("Gastos por vendedor:", gastos_vendedores)

        # Abonos en efectivo por vendedor
        cursor.execute("""
            SELECT 
                Cobrador_ID,
                COALESCE(SUM(Monto), 0) AS Abonos_Efectivo
            FROM (
                SELECT ad.ID_Usuario AS Cobrador_ID, ad.Monto_Aplicado AS Monto
                FROM abonos_detalle ad
                LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                WHERE DATE(ad.Fecha) = %s AND (ad.ID_MetodoPago = 1 OR mp.Nombre LIKE '%%Efectivo%%' OR ad.ID_MetodoPago IS NULL)
                
                UNION ALL
                
                SELECT ag.ID_Usuario AS Cobrador_ID, ag.Monto_Aplicado AS Monto
                FROM abonos_general ag
                LEFT JOIN metodos_pago mp ON ag.ID_MetodoPago = mp.ID_MetodoPago
                WHERE DATE(ag.Fecha) = %s AND (ag.ID_MetodoPago = 1 OR mp.Nombre LIKE '%%Efectivo%%' OR ag.ID_MetodoPago IS NULL)
                
                UNION ALL
                
                SELECT pc.ID_Usuario_Creacion AS Cobrador_ID, pc.Monto AS Monto
                FROM pagos_cuentascobrar pc
                LEFT JOIN metodos_pago mp ON pc.ID_MetodoPago = mp.ID_MetodoPago
                WHERE DATE(pc.Fecha) = %s AND (pc.ID_MetodoPago = 1 OR mp.Nombre LIKE '%%Efectivo%%' OR pc.ID_MetodoPago IS NULL)
            ) AS abonos
            WHERE Cobrador_ID IS NOT NULL
            GROUP BY Cobrador_ID
        """, [fecha_str, fecha_str, fecha_str])
        abonos_vendedores = {row['Cobrador_ID']: float(row['Abonos_Efectivo']) for row in cursor.fetchall()}
        print("Abonos por vendedor:", abonos_vendedores)
