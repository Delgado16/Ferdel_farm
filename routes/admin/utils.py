"""
Funciones compartidas entre módulos del administrador
"""
import json
from decimal import Decimal
from datetime import datetime, date
from config.database import get_db_cursor


def obtener_metricas_kpis():
    """Obtiene las métricas principales del dashboard"""
    with get_db_cursor() as cursor:
        # Usuarios activos
        cursor.execute("SELECT COUNT(*) as count FROM usuarios WHERE UPPER(Estado) = 'ACTIVO'")
        usuarios_count = cursor.fetchone()['count']
        
        # Empresas activas
        cursor.execute("SELECT COUNT(*) as count FROM empresa WHERE Estado = 'Activo'")
        empresas_count = cursor.fetchone()['count']
        
        # Ventas de hoy (solo contado)
        cursor.execute("""
            SELECT COALESCE(SUM(Ventas_Totales), 0) AS Total_Ventas_Contado_Hoy
            FROM (
                SELECT COALESCE(SUM(df.Total), 0) AS Ventas_Totales 
                FROM detalle_facturacion df
                INNER JOIN facturacion fac ON df.ID_Factura = fac.ID_Factura
                WHERE fac.Fecha_Creacion >= CURDATE() 
                AND fac.Fecha_Creacion < CURDATE() + INTERVAL 1 DAY
                AND fac.Estado = 'Activa'
                AND fac.Credito_Contado = 0
                
                UNION ALL
                
                SELECT COALESCE(SUM(dfr.Total), 0) AS Ventas_Totales 
                FROM detalle_facturacion_ruta dfr
                INNER JOIN facturacion_ruta facr ON dfr.ID_FacturaRuta = facr.ID_FacturaRuta
                WHERE facr.Fecha_Creacion >= CURDATE()
                AND facr.Fecha_Creacion < CURDATE() + INTERVAL 1 DAY
                AND facr.Estado = 'Activa'
                AND facr.Credito_Contado = 1
            ) AS Ventas
        """)
        ventas_hoy = cursor.fetchone()['Total_Ventas_Contado_Hoy'] or 0
        
        # Cobros de hoy
        cursor.execute("""
            SELECT COALESCE(SUM(Monto_Cobrado), 0) AS Total_Cobrado_Hoy
            FROM (
                SELECT Monto_Aplicado AS Monto_Cobrado
                FROM abonos_detalle
                WHERE DATE(Fecha) = CURDATE()
                UNION ALL
                SELECT pc.Monto AS Monto_Cobrado
                FROM pagos_cuentascobrar pc
                INNER JOIN cuentas_por_cobrar cxc ON pc.ID_Movimiento = cxc.ID_Movimiento
                WHERE DATE(pc.Fecha) = CURDATE()
                AND cxc.Estado != 'Anulada'
            ) AS Cobros
        """)
        cobros_hoy = cursor.fetchone()['Total_Cobrado_Hoy'] or 0
        
        # Saldo pendiente total
        cursor.execute("""
            SELECT COALESCE(SUM(Saldo_Pendiente), 0) AS Saldo_Total_Pendiente
            FROM cuentas_por_cobrar
            WHERE Estado IN ('Pendiente', 'Vencida')
        """)
        saldo_pendiente = cursor.fetchone()['Saldo_Total_Pendiente'] or 0
        
        # Facturas vencidas
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM cuentas_por_cobrar
            WHERE Estado = 'Vencida' AND Saldo_Pendiente > 0
        """)
        facturas_vencidas = cursor.fetchone()['count'] or 0
        
        # Productos con stock bajo
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM inventario_bodega ib
            INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
            WHERE ib.Existencias <= p.Stock_Minimo
        """)
        productos_bajo_stock = cursor.fetchone()['count'] or 0
    
    return {
        'usuarios_count': usuarios_count,
        'empresas_count': empresas_count,
        'ventas_hoy': float(ventas_hoy),
        'cobros_hoy': float(cobros_hoy),
        'saldo_pendiente': float(saldo_pendiente),
        'facturas_vencidas': facturas_vencidas,
        'productos_bajo_stock': productos_bajo_stock
    }

def obtener_ventas_mes():
    """Obtiene datos de ventas del mes actual para gráficos"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                DAY(fac.Fecha_Creacion) AS Dia,
                COALESCE(SUM(df.Total), 0) AS Total_Vendido
            FROM facturacion fac
            INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
            WHERE MONTH(fac.Fecha_Creacion) = MONTH(CURDATE()) 
              AND YEAR(fac.Fecha_Creacion) = YEAR(CURDATE())
              AND fac.Estado = 'Activa'
            GROUP BY DAY(fac.Fecha_Creacion)
            ORDER BY Dia ASC
        """)
        return cursor.fetchall()

def obtener_top_clientes_deudores():
    """Obtiene los 5 clientes con mayor deuda"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                c.Nombre AS Cliente,
                c.Telefono,
                COALESCE(SUM(cxc.Saldo_Pendiente), 0) AS Deuda_Total
            FROM cuentas_por_cobrar cxc
            INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE cxc.Estado IN ('Pendiente', 'Vencida')
            GROUP BY c.ID_Cliente
            ORDER BY Deuda_Total DESC
            LIMIT 5
        """)
        return cursor.fetchall()

def obtener_productos_bajo_stock():
    """Obtiene productos con stock bajo"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                p.Descripcion AS Producto,
                p.COD_Producto,
                ib.Existencias AS Stock_Actual,
                p.Stock_Minimo,
                (p.Stock_Minimo - ib.Existencias) AS Faltante
            FROM inventario_bodega ib
            INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
            WHERE ib.Existencias <= p.Stock_Minimo
            ORDER BY ib.Existencias ASC
            LIMIT 10
        """)
        return cursor.fetchall()

def obtener_gastos_mes():
    """Obtiene gastos del mes por categoría"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                tg.Nombre AS Tipo_Gasto,
                COALESCE(SUM(gg.Monto), 0) AS Total_Gastado
            FROM gastos_generales gg
            INNER JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
            WHERE MONTH(gg.Fecha) = MONTH(CURDATE()) 
              AND YEAR(gg.Fecha) = YEAR(CURDATE())
              AND gg.Estado = 'Activo'
            GROUP BY tg.ID_Tipo_Gasto
            ORDER BY Total_Gastado DESC
            LIMIT 5
        """)
        return cursor.fetchall()

def obtener_ventas_vendedores():
    """Obtiene ventas por vendedor del día actual"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                u.NombreUsuario AS Vendedor,
                COUNT(DISTINCT fr.ID_FacturaRuta) AS Facturas,
                COALESCE(SUM(dfr.Total), 0) AS Total_Vendido
            FROM facturacion_ruta fr
            INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
            INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
            WHERE DATE(fr.Fecha_Creacion) = CURDATE() AND fr.Estado = 'Activa'
            GROUP BY u.ID_Usuario
            ORDER BY Total_Vendido DESC
            LIMIT 5
        """)
        return cursor.fetchall()

def obtener_rutas_activas():
    """Obtiene rutas activas con vendedor y vehículo"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                r.Nombre_Ruta AS Ruta,
                u.NombreUsuario AS Vendedor,
                v.Placa AS Vehiculo,
                av.Estado
            FROM asignacion_vendedores av
            INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
            INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
            LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
            WHERE av.Estado = 'Activa'
        """)
        return cursor.fetchall()

def obtener_ventas_7dias():
    """Obtiene ventas de los últimos 7 días"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                DATE(fac.Fecha_Creacion) AS Fecha,
                COALESCE(SUM(df.Total), 0) AS Total_Vendido
            FROM facturacion fac
            INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
            WHERE fac.Fecha_Creacion >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
              AND fac.Estado = 'Activa'
            GROUP BY DATE(fac.Fecha_Creacion)
            ORDER BY Fecha ASC
        """)
        return cursor.fetchall()

def obtener_movimientos_caja():
    """Obtiene movimientos de caja del día actual"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                Tipo,
                COUNT(*) as Cantidad,
                COALESCE(SUM(Monto), 0) as Total
            FROM movimientos_caja_ruta
            WHERE DATE(Fecha) = CURDATE() AND Estado = 'ACTIVO'
            GROUP BY Tipo
        """)
        return cursor.fetchall()

def obtener_proximos_vencimientos():
    """Obtiene facturas con próximos vencimientos (7 días)"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                c.Nombre AS Cliente,
                cxc.Num_Documento,
                cxc.Fecha_Vencimiento,
                cxc.Saldo_Pendiente
            FROM cuentas_por_cobrar cxc
            INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE cxc.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
              AND cxc.Estado = 'Pendiente'
              AND cxc.Saldo_Pendiente > 0
            ORDER BY cxc.Fecha_Vencimiento ASC
            LIMIT 5
        """)
        return cursor.fetchall()

def preparar_datos_graficos(ventas_mes, ventas_7dias, gastos_mes, movimientos_caja):
    """Prepara datos JSON para los gráficos del dashboard"""
    # Datos para gráfico de ventas del mes
    ventas_mes_data = {
        'dias': [v['Dia'] for v in ventas_mes],
        'totales': [float(v['Total_Vendido']) for v in ventas_mes]
    }
    
    # Datos para gráfico de tendencia 7 días
    ventas_7dias_data = {
        'fechas': [v['Fecha'].strftime('%d/%m') for v in ventas_7dias],
        'totales': [float(v['Total_Vendido']) for v in ventas_7dias]
    }
    
    # Datos para gráfico de gastos
    gastos_mes_data = {
        'categorias': [g['Tipo_Gasto'] for g in gastos_mes],
        'montos': [float(g['Total_Gastado']) for g in gastos_mes]
    }
    
    return {
        'ventas_mes_json': json.dumps(ventas_mes_data),
        'ventas_7dias_json': json.dumps(ventas_7dias_data),
        'gastos_mes_json': json.dumps(gastos_mes_data)
    }
