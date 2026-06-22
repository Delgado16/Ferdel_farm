from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime
from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator, registrar_bitacora
from respaldo import exportar_csv, exportar_json
from . import admin_bp
import functools

# ============================================
# HELPERS DE PARÁMETROS PARA REPORTES
# ============================================

def get_date_filters(default_monthly=True):
    """Retorna fecha_inicio y fecha_fin desde request.args con valores por defecto"""
    if default_monthly:
        start_default = datetime.now().strftime('%Y-%m-01')
    else:
        start_default = datetime.now().strftime('%Y-%m-%d')
    
    fecha_inicio = request.args.get('fecha_inicio', start_default)
    fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
    return fecha_inicio, fecha_fin

def get_corte_filter():
    """Retorna fecha_corte desde request.args con valor por defecto"""
    return request.args.get('fecha_corte', datetime.now().strftime('%Y-%m-%d'))

def get_period_date_range():
    """Retorna fecha_inicio, fecha_fin y periodo según los filtros rápidos"""
    from datetime import timedelta
    periodo = request.args.get('periodo', 'mes')
    today = datetime.now()
    
    if periodo == 'dia':
        fecha_inicio = today.strftime('%Y-%m-%d')
        fecha_fin = today.strftime('%Y-%m-%d')
    elif periodo == 'semana':
        fecha_inicio = (today - timedelta(days=6)).strftime('%Y-%m-%d')
        fecha_fin = today.strftime('%Y-%m-%d')
    elif periodo == 'mes':
        fecha_inicio = today.strftime('%Y-%m-01')
        fecha_fin = today.strftime('%Y-%m-%d')
    elif periodo == 'ano':
        fecha_inicio = today.strftime('%Y-01-01')
        fecha_fin = today.strftime('%Y-%m-%d')
    else:
        fecha_inicio = request.args.get('fecha_inicio', today.strftime('%Y-%m-01'))
        fecha_fin = request.args.get('fecha_fin', today.strftime('%Y-%m-%d'))
        periodo = 'personalizado'
        
    return fecha_inicio, fecha_fin, periodo

# ============================================
# DECORADOR DE CONTROL Y EXPORTACIÓN DE REPORTES
# ============================================

def report_handler(filename):
    """
    Decorador para centralizar la exportación CSV/JSON y el control de errores.
    Espera que la función retorne una tupla: (datos_exportar, template_name, context_dict)
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                if isinstance(result, tuple) and len(result) == 3:
                    datos, template_name, context = result
                    formato = request.args.get('formato', 'html')
                    
                    if formato in ['csv', 'json']:
                        if formato == 'csv':
                            return exportar_csv(datos, filename)
                        else:
                            return exportar_json(datos, filename)
                    
                    if 'now' not in context:
                        context['now'] = datetime.now()
                        
                    return render_template(template_name, **context)
                return result
            except Exception as e:
                flash(f"Error al generar reporte: {e}", "danger")
                return redirect(url_for('admin.reportes'))
        return wrapper
    return decorator

@admin_bp.route('/admin/reportes')
@admin_required
def reportes():
    """Panel principal de reportes ejecutivos"""
    return render_template('admin/reportes/reportes.html',
                            now=datetime.now())

@admin_bp.route('/admin/reporte/ventas')
@admin_required
@report_handler('reporte_ventas')
def reporte_ventas():
    """Reporte de ventas con filtros (incluye facturación normal y de ruta)"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    tipo_venta = request.args.get('tipo_venta', 'todos')
    vendedor_id = request.args.get('vendedor_id', '')
    
    with get_db_cursor() as cursor:
        # Query principal de ventas (UNION de facturación normal + facturación ruta)
        query = """
            SELECT 
                Fecha,
                Tipo_Venta,
                Vendedor,
                Cliente,
                Factura_Numero,
                Items,
                Cantidad_Total,
                Total_Venta,
                Origen
            FROM (
                -- FACTURACIÓN NORMAL
                SELECT 
                    DATE(fac.Fecha_Creacion) AS Fecha,
                    CASE 
                        WHEN fac.Credito_Contado = 0 THEN 'CONTADO' 
                        WHEN fac.Credito_Contado = 1 THEN 'CREDITO'
                        ELSE 'NO DEFINIDO'
                    END AS Tipo_Venta,
                    u.NombreUsuario AS Vendedor,
                    c.Nombre AS Cliente,
                    CAST(fac.ID_Factura AS CHAR) AS Factura_Numero,
                    COUNT(df.ID_Detalle) AS Items,
                    SUM(df.Cantidad) AS Cantidad_Total,
                    SUM(df.Total) AS Total_Venta,
                    'NORMAL' AS Origen
                FROM facturacion fac
                INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                INNER JOIN clientes c ON fac.IDCliente = c.ID_Cliente
                INNER JOIN usuarios u ON fac.ID_Usuario_Creacion = u.ID_Usuario
                WHERE DATE(fac.Fecha_Creacion) BETWEEN %s AND %s
                  AND fac.Estado = 'Activa'
                GROUP BY fac.ID_Factura, fac.Fecha_Creacion, fac.Credito_Contado, u.NombreUsuario, c.Nombre
                
                UNION ALL
                
                -- FACTURACIÓN DE RUTA
                SELECT 
                    DATE(fr.Fecha_Creacion) AS Fecha,
                    CASE 
                        WHEN fr.Credito_Contado = 1 THEN 'CONTADO' 
                        WHEN fr.Credito_Contado = 2 THEN 'CREDITO'
                        ELSE 'NO DEFINIDO'
                    END AS Tipo_Venta,
                    u.NombreUsuario AS Vendedor,
                    c.Nombre AS Cliente,
                    CONCAT('R-', fr.ID_FacturaRuta) AS Factura_Numero,
                    COUNT(dfr.ID_DetalleRuta) AS Items,
                    SUM(dfr.Cantidad) AS Cantidad_Total,
                    SUM(dfr.Total) AS Total_Venta,
                    'RUTA' AS Origen
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
                  AND fr.Estado = 'Activa'
                GROUP BY fr.ID_FacturaRuta, fr.Fecha_Creacion, fr.Credito_Contado, u.NombreUsuario, c.Nombre
            ) AS todas_ventas
            WHERE 1=1
        """
        
        params = [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin]
        
        # Filtro por tipo de venta
        if tipo_venta != 'todos':
            query += " AND Tipo_Venta = %s"
            params.append(tipo_venta.upper())
        
        # Filtro por vendedor
        if vendedor_id:
            query += " AND Vendedor IN (SELECT NombreUsuario FROM usuarios WHERE ID_Usuario = %s)"
            params.append(vendedor_id)
        
        query += " ORDER BY Fecha DESC, Origen"
        
        cursor.execute(query, params)
        ventas = cursor.fetchall()
        
        # Resumen general (incluye ambas fuentes)
        cursor.execute("""
            SELECT 
                COUNT(*) AS Total_Facturas,
                COUNT(DISTINCT Cliente) AS Clientes_Atendidos,
                COALESCE(SUM(Total_Venta), 0) AS Monto_Total,
                COALESCE(AVG(Total_Venta), 0) AS Ticket_Promedio
            FROM (
                -- Facturación normal
                SELECT 
                    c.Nombre AS Cliente,
                    SUM(df.Total) AS Total_Venta
                FROM facturacion fac
                INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                INNER JOIN clientes c ON fac.IDCliente = c.ID_Cliente
                WHERE DATE(fac.Fecha_Creacion) BETWEEN %s AND %s
                  AND fac.Estado = 'Activa'
                GROUP BY fac.ID_Factura, c.Nombre
                
                UNION ALL
                
                -- Facturación de ruta
                SELECT 
                    c.Nombre AS Cliente,
                    SUM(dfr.Total) AS Total_Venta
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                WHERE DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
                  AND fr.Estado = 'Activa'
                GROUP BY fr.ID_FacturaRuta, c.Nombre
            ) AS resumen
        """, [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin])
        resumen = cursor.fetchone()
        
        # Resumen por tipo de origen (normal vs ruta)
        cursor.execute("""
            SELECT 
                Origen,
                COUNT(*) AS Cantidad,
                COALESCE(SUM(Total_Venta), 0) AS Total
            FROM (
                SELECT 'NORMAL' AS Origen, SUM(df.Total) AS Total_Venta
                FROM facturacion fac
                INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                WHERE DATE(fac.Fecha_Creacion) BETWEEN %s AND %s 
                  AND fac.Estado = 'Activa'
                GROUP BY fac.ID_Factura
                
                UNION ALL
                
                SELECT 'RUTA' AS Origen, SUM(dfr.Total) AS Total_Venta
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE DATE(fr.Fecha_Creacion) BETWEEN %s AND %s 
                  AND fr.Estado = 'Activa'
                GROUP BY fr.ID_FacturaRuta
            ) AS origen_ventas
            GROUP BY Origen
        """, [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin])
        resumen_origen = cursor.fetchall()
        
        # Vendedores para filtro (de ambas fuentes)
        cursor.execute("""
            SELECT DISTINCT u.ID_Usuario, u.NombreUsuario
            FROM usuarios u
            WHERE u.Estado = 'ACTIVO'
              AND (
                  u.ID_Usuario IN (SELECT ID_Usuario_Creacion FROM facturacion)
                  OR u.ID_Usuario IN (SELECT ID_Usuario FROM asignacion_vendedores)
              )
            ORDER BY u.NombreUsuario
        """)
        vendedores = cursor.fetchall()
        
        return ventas, 'admin/reportes/reporte_ventas.html', {
            'ventas': ventas,
            'resumen': resumen,
            'resumen_origen': resumen_origen,
            'vendedores': vendedores,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'tipo_venta': tipo_venta,
            'vendedor_id': vendedor_id
        }

@admin_bp.route('/admin/reporte/cartera')
@admin_required
@report_handler('reporte_cartera')
def reporte_cartera():
    """Reporte de cartera y cuentas por cobrar"""
    fecha_corte = get_corte_filter()
    estado = request.args.get('estado', 'todos')
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                c.Nombre AS Cliente,
                c.Telefono,
                cxc.Num_Documento,
                cxc.Fecha,
                cxc.Fecha_Vencimiento,
                DATEDIFF(%s, cxc.Fecha_Vencimiento) AS Dias_Vencido,
                cxc.Monto_Movimiento AS Monto_Original,
                cxc.Saldo_Pendiente,
                cxc.Estado AS Estado_Actual,
                CASE 
                    WHEN cxc.Estado = 'Pagada' THEN 'PAGADA'
                    WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) > 0 THEN 'VENCIDA'
                    ELSE 'PENDIENTE'
                END AS Estado_Calculado,
                CASE 
                    WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 0 THEN 'AL DIA'
                    WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 30 THEN '1-30 días'
                    WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 60 THEN '31-60 días'
                    WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 90 THEN '61-90 días'
                    ELSE '90+ días'
                END AS Rango_Mora
            FROM cuentas_por_cobrar cxc
            INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE cxc.Fecha <= %s
              AND cxc.Saldo_Pendiente > 0
        """
        params = [fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte]
        
        if estado != 'todos':
            if estado == 'vencida':
                query += " AND (cxc.Estado = 'Vencida' OR DATEDIFF(%s, cxc.Fecha_Vencimiento) > 0)"
                params.append(fecha_corte)
            else:
                query += " AND cxc.Estado = %s"
                params.append(estado.capitalize())
        
        query += " ORDER BY Dias_Vencido DESC"
        
        cursor.execute(query, params)
        cartera = cursor.fetchall()
        
        # Resumen de cartera
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN Dias_Vencido <= 0 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_Al_Dia,
                COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 1 AND 30 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_30_Dias,
                COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 31 AND 60 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_60_Dias,
                COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 61 AND 90 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_90_Dias,
                COALESCE(SUM(CASE WHEN Dias_Vencido > 90 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_90_Mas,
                COALESCE(SUM(Saldo_Pendiente), 0) AS Total_Cartera
            FROM (
                SELECT 
                    cxc.Saldo_Pendiente,
                    DATEDIFF(%s, cxc.Fecha_Vencimiento) AS Dias_Vencido
                FROM cuentas_por_cobrar cxc
                WHERE cxc.Estado IN ('Pendiente', 'Vencida')
                  AND cxc.Fecha <= %s
                  AND cxc.Saldo_Pendiente > 0
            ) AS calculo
        """, [fecha_corte, fecha_corte])
        resumen = cursor.fetchone()
        
        return cartera, 'admin/reportes/reporte_cartera.html', {
            'cartera': cartera,
            'resumen': resumen,
            'fecha_corte': fecha_corte,
            'estado': estado
        }

@admin_bp.route('/admin/reporte/inventario')
@admin_required
@report_handler('reporte_inventario')
def reporte_inventario():
    """Reporte de inventario y productos"""
    categoria_id = request.args.get('categoria_id', '')
    stock_status = request.args.get('stock_status', 'todos')
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                p.COD_Producto AS Codigo,
                p.Descripcion AS Producto,
                cp.Descripcion AS Categoria,
                COALESCE(ib.Existencias, 0) AS Stock_Actual,
                p.Stock_Minimo,
                CASE 
                    WHEN COALESCE(ib.Existencias, 0) <= p.Stock_Minimo THEN 'STOCK BAJO'
                    WHEN COALESCE(ib.Existencias, 0) <= p.Stock_Minimo * 2 THEN 'STOCK MINIMO'
                    ELSE 'NORMAL'
                END AS Estado_Stock,
                p.Precio_Mercado,
                p.Precio_Mayorista,
                COALESCE(SUM(df.Cantidad), 0) AS Vendido_Ultimo_Mes,
                COALESCE(ib.Existencias, 0) * COALESCE(p.Precio_Mercado, 0) AS Valor_Inventario
            FROM productos p
            INNER JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
            LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
            LEFT JOIN detalle_facturacion df ON p.ID_Producto = df.ID_Producto
            LEFT JOIN facturacion fac ON df.ID_Factura = fac.ID_Factura 
                AND fac.Fecha_Creacion >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                AND fac.Estado = 'Activa'
            WHERE p.Estado = 'activo'
        """
        params = []
        
        if categoria_id:
            query += " AND p.ID_Categoria = %s"
            params.append(categoria_id)
        
        query += " GROUP BY p.ID_Producto, ib.Existencias"
        
        if stock_status == 'critico':
            query += " HAVING Stock_Actual <= Stock_Minimo"
        elif stock_status == 'minimo':
            query += " HAVING Stock_Actual <= Stock_Minimo * 2 AND Stock_Actual > Stock_Minimo"
        elif stock_status == 'normal':
            query += " HAVING Stock_Actual > Stock_Minimo * 2"
        
        query += " ORDER BY Estado_Stock, Stock_Actual ASC"
        
        cursor.execute(query, params)
        inventario = cursor.fetchall()
        
        # Categorías para filtro
        cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto WHERE Estado = 'Activo'")
        categorias = cursor.fetchall()
        
        # Resumen
        cursor.execute("""
            SELECT 
                COUNT(*) AS Total_Productos,
                SUM(CASE WHEN Stock_Actual <= Stock_Minimo THEN 1 ELSE 0 END) AS Stock_Critico,
                SUM(CASE WHEN Stock_Actual <= 0 THEN 1 ELSE 0 END) AS Stock_Cero,
                SUM(Stock_Actual * COALESCE(Precio_Mercado, 0)) AS Valor_Inventario
            FROM (
                SELECT 
                    p.ID_Producto,
                    p.Stock_Minimo,
                    COALESCE(ib.Existencias, 0) AS Stock_Actual,
                    p.Precio_Mercado
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE p.Estado = 'activo'
            ) AS calculo
        """)
        resumen = cursor.fetchone()
        
        return inventario, 'admin/reportes/reporte_inventario.html', {
            'inventario': inventario,
            'resumen': resumen,
            'categorias': categorias,
            'categoria_id': categoria_id,
            'stock_status': stock_status
        }

@admin_bp.route('/admin/reporte/estado_resultados')
@admin_required
@report_handler('reporte_estado_resultados')
def reporte_estado_resultados():
    """Estado de resultados financiero"""
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    
    año = int(mes.split('-')[0])
    mes_num = int(mes.split('-')[1])
    
    with get_db_cursor() as cursor:
        # Ingresos por ventas (solo contado)
        cursor.execute("""
            SELECT 
                'INGRESOS' AS Tipo,
                'Ventas de Contado' AS Concepto,
                COALESCE(SUM(df.Total), 0) AS Monto
            FROM facturacion fac
            INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
            WHERE MONTH(fac.Fecha_Creacion) = %s 
              AND YEAR(fac.Fecha_Creacion) = %s
              AND fac.Estado = 'Activa'
              AND fac.Credito_Contado = 1
        """, [mes_num, año])
        ingresos_ventas = cursor.fetchall()
        
        # Ingresos por cobros de cartera
        cursor.execute("""
            SELECT 
                'INGRESOS' AS Tipo,
                'Cobros de Cartera' AS Concepto,
                COALESCE(SUM(ad.Monto_Aplicado), 0) AS Monto
            FROM abonos_detalle ad
            WHERE MONTH(ad.Fecha) = %s AND YEAR(ad.Fecha) = %s
        """, [mes_num, año])
        ingresos_abonos = cursor.fetchall()
        
        # Gastos generales
        cursor.execute("""
            SELECT 
                'GASTOS' AS Tipo,
                tg.Nombre AS Concepto,
                COALESCE(SUM(gg.Monto), 0) AS Monto
            FROM gastos_generales gg
            INNER JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
            WHERE MONTH(gg.Fecha) = %s AND YEAR(gg.Fecha) = %s
              AND gg.Estado = 'Activo'
            GROUP BY tg.ID_Tipo_Gasto
            ORDER BY Monto DESC
        """, [mes_num, año])
        gastos = cursor.fetchall()
        
        # Consolidar resultados
        resultados = []
        total_ingresos = 0
        total_gastos = 0
        
        for ingreso in ingresos_ventas:
            resultados.append(ingreso)
            total_ingresos += float(ingreso['Monto'])
        
        for ingreso in ingresos_abonos:
            resultados.append(ingreso)
            total_ingresos += float(ingreso['Monto'])
        
        for gasto in gastos:
            resultados.append(gasto)
            total_gastos += float(gasto['Monto'])
        
        utilidad = total_ingresos - total_gastos
        margen = (utilidad / total_ingresos * 100) if total_ingresos > 0 else 0
        
        # ============================================
        # MESES DISPONIBLES - VERSIÓN CORREGIDA
        # ============================================
        cursor.execute("""
            SELECT DISTINCT 
                CONCAT(YEAR(f.Fecha_Creacion), '-', LPAD(MONTH(f.Fecha_Creacion), 2, '0')) AS mes
            FROM facturacion f
            WHERE f.Estado = 'Activa'
            ORDER BY CONCAT(YEAR(f.Fecha_Creacion), '-', LPAD(MONTH(f.Fecha_Creacion), 2, '0')) DESC
            LIMIT 12
        """)
        meses_disponibles = cursor.fetchall()
        
        return resultados, 'admin/reportes/reporte_estado_resultados.html', {
            'resultados': resultados,
            'total_ingresos': total_ingresos,
            'total_gastos': total_gastos,
            'utilidad': utilidad,
            'margen': margen,
            'mes_actual': mes,
            'meses_disponibles': meses_disponibles
        }

@admin_bp.route('/admin/reporte/utilidad_ventas')
@admin_required
@report_handler('reporte_utilidad_ventas')
def reporte_utilidad_ventas():
    """Reporte de utilidad y margen de ventas (Local + Ruta)"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                Canal,
                Fecha,
                Documento_ID,
                Cliente,
                Producto,
                Cantidad_Vendidas,
                Costo_Total,
                Venta_Total,
                Utilidad_Neta,
                Porcentaje_Margen
            FROM (
                SELECT 
                    'Local' AS Canal,
                    DATE(f.Fecha_Creacion) AS Fecha,
                    CAST(f.ID_Factura AS CHAR) AS Documento_ID,
                    c.Nombre AS Cliente,
                    p.Descripcion AS Producto,
                    df.Cantidad AS Cantidad_Vendidas,
                    COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = df.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(f.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        df.Costo, 
                        0.00
                    ) * df.Cantidad AS Costo_Total,
                    df.Total AS Venta_Total,
                    (df.Total - (COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = df.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(f.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        df.Costo, 
                        0.00
                    ) * df.Cantidad)) AS Utilidad_Neta,
                    ROUND(((df.Total - (COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = df.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(f.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        df.Costo, 
                        0.00
                    ) * df.Cantidad)) / NULLIF(df.Total, 0)) * 100, 2) AS Porcentaje_Margen
                FROM facturacion f
                JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                JOIN clientes c ON f.IDCliente = c.ID_Cliente
                JOIN productos p ON df.ID_Producto = p.ID_Producto
                WHERE f.Estado = 'Activa'
                  AND DATE(f.Fecha_Creacion) BETWEEN %s AND %s
                
                UNION ALL
                
                SELECT 
                    'Ruta' AS Canal,
                    DATE(fr.Fecha_Creacion) AS Fecha,
                    CONCAT('R-', fr.ID_FacturaRuta) AS Documento_ID,
                    c.Nombre AS Cliente,
                    p.Descripcion AS Producto,
                    dfr.Cantidad AS Cantidad_Vendidas,
                    COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = dfr.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(fr.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        dfr.Costo, 
                        0.00
                    ) * dfr.Cantidad AS Costo_Total,
                    dfr.Total AS Venta_Total,
                    (dfr.Total - (COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = dfr.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(fr.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        dfr.Costo, 
                        0.00
                    ) * dfr.Cantidad)) AS Utilidad_Neta,
                    ROUND(((dfr.Total - (COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = dfr.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(fr.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        dfr.Costo, 
                        0.00
                    ) * dfr.Cantidad)) / NULLIF(dfr.Total, 0)) * 100, 2) AS Porcentaje_Margen
                FROM facturacion_ruta fr
                JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                JOIN productos p ON dfr.ID_Producto = p.ID_Producto
                WHERE fr.Estado = 'Activa'
                  AND DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
            ) AS u_ventas
            ORDER BY Fecha DESC, Documento_ID DESC
        """
        cursor.execute(query, [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin])
        resultados = cursor.fetchall()
        
        # Resumen acumulativo
        cursor.execute("""
            SELECT 
                COALESCE(SUM(Costo_Total), 0) AS Costo_Acumulado,
                COALESCE(SUM(Venta_Total), 0) AS Venta_Acumulada,
                COALESCE(SUM(Utilidad_Neta), 0) AS Utilidad_Acumulada,
                ROUND((COALESCE(SUM(Utilidad_Neta), 0) / NULLIF(COALESCE(SUM(Venta_Total), 0), 0)) * 100, 2) AS Margen_Promedio
            FROM (
                SELECT 
                    COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = df.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(f.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        df.Costo, 
                        0.00
                    ) * df.Cantidad AS Costo_Total,
                    df.Total AS Venta_Total,
                    (df.Total - (COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = df.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(f.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        df.Costo, 
                        0.00
                    ) * df.Cantidad)) AS Utilidad_Neta
                FROM facturacion f
                JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.Estado = 'Activa'
                  AND DATE(f.Fecha_Creacion) BETWEEN %s AND %s
                
                UNION ALL
                
                SELECT 
                    COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = dfr.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(fr.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        dfr.Costo, 
                        0.00
                    ) * dfr.Cantidad AS Costo_Total,
                    dfr.Total AS Venta_Total,
                    (dfr.Total - (COALESCE(
                        (SELECT dmi_c.Costo_Unitario 
                         FROM detalle_movimientos_inventario dmi_c
                         JOIN movimientos_inventario mi_c ON dmi_c.ID_Movimiento = mi_c.ID_Movimiento
                         JOIN catalogo_movimientos cm_c ON mi_c.ID_TipoMovimiento = cm_c.ID_TipoMovimiento
                         WHERE dmi_c.ID_Producto = dfr.ID_Producto
                           AND mi_c.Estado = 'Activa'
                           AND (cm_c.Adicion LIKE '%%SUMA%%' OR cm_c.Letra IN ('E', 'C'))
                           AND mi_c.Fecha <= DATE(fr.Fecha_Creacion)
                         ORDER BY mi_c.Fecha DESC, mi_c.ID_Movimiento DESC
                         LIMIT 1
                        ),
                        dfr.Costo, 
                        0.00
                    ) * dfr.Cantidad)) AS Utilidad_Neta
                FROM facturacion_ruta fr
                JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.Estado = 'Activa'
                  AND DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
            ) AS resumen
        """, [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin])
        resumen = cursor.fetchone()
        
        return resultados, 'admin/reportes/reporte_utilidad_ventas.html', {
            'resultados': resultados,
            'resumen': resumen,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }

@admin_bp.route('/admin/reporte/caja_ruta')
@admin_required
def reporte_caja_ruta():
    """Redirección al reporte unificado de conciliación monetaria"""
    return redirect(url_for('admin.reporte_conciliacion_monetaria', **request.args))

@admin_bp.route('/admin/reporte/kardex')
@admin_required
@report_handler('reporte_kardex')
def reporte_kardex():
    """Reporte de Kardex de movimientos de inventario"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    bodega_id = request.args.get('bodega_id', '')
    producto_id = request.args.get('producto_id', '')
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                b.Nombre AS Bodega,
                mi.Fecha,
                cm.Descripcion AS Tipo_Movimiento,
                mi.ID_Movimiento AS Documento_ID,
                p.COD_Producto AS Codigo,
                p.Descripcion AS Producto,
                CASE 
                    WHEN cm.Adicion LIKE '%%SUMA%%' OR cm.Adicion = '+' OR cm.Letra IN ('E', 'C') THEN dmi.Cantidad 
                    ELSE 0.00 
                END AS Cantidad_Entrada,
                CASE 
                    WHEN cm.Adicion LIKE '%%RESTA%%' OR cm.Adicion = '-' OR cm.Letra IN ('S', 'V') THEN dmi.Cantidad 
                    ELSE 0.00 
                END AS Cantidad_Salida,
                dmi.Costo_Unitario,
                dmi.Subtotal AS Subtotal_Movimiento,
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
        
        if bodega_id:
            query += " AND mi.ID_Bodega = %s"
            params.append(bodega_id)
        if producto_id:
            query += " AND dmi.ID_Producto = %s"
            params.append(producto_id)
            
        query += " ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Catálogos para filtros
        cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
        bodegas = cursor.fetchall()
        
        cursor.execute("SELECT ID_Producto, Descripcion FROM productos WHERE Estado = 'activo'")
        productos = cursor.fetchall()
        
        return resultados, 'admin/reportes/reporte_kardex.html', {
            'resultados': resultados,
            'bodegas': bodegas,
            'productos': productos,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'bodega_id': bodega_id,
            'producto_id': producto_id
        }

@admin_bp.route('/admin/reporte/gastos_vehiculos')
@admin_required
@report_handler('reporte_gastos_vehiculos')
def reporte_gastos_vehiculos():
    """Reporte de costos y gastos por vehículo"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    vehiculo_id = request.args.get('vehiculo_id', '')
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                v.Placa,
                CONCAT(v.Marca, ' ', v.Modelo) AS Vehiculo,
                gg.Fecha,
                tg.Nombre AS Categoria_Gasto,
                sg.Nombre AS Subcategoria,
                gg.N_Factura AS Factura_N,
                prov.Nombre AS Proveedor,
                gvd.Kilometraje,
                gvd.Tipo_Mantenimiento,
                gvd.Taller,
                gg.Monto AS Importe_Gasto,
                gg.Descripcion AS Notas
            FROM gastos_generales gg
            JOIN vehiculos v ON gg.ID_Vehiculo = v.ID_Vehiculo
            JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
            LEFT JOIN subcategorias_gasto sg ON gg.ID_Subcategoria = sg.ID_Subcategoria
            LEFT JOIN proveedores prov ON gg.ID_Proveedor = prov.ID_Proveedor
            LEFT JOIN gastos_vehiculo_detalle gvd ON gg.ID_Gasto = gvd.ID_Gasto
            WHERE gg.Estado = 'Activo'
              AND gg.Fecha BETWEEN %s AND %s
        """
        params = [fecha_inicio, fecha_fin]
        
        if vehiculo_id:
            query += " AND gg.ID_Vehiculo = %s"
            params.append(vehiculo_id)
            
        query += " ORDER BY v.Placa, gg.Fecha DESC"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Filtro de vehículos
        cursor.execute("SELECT ID_Vehiculo, Placa, Marca, Modelo FROM vehiculos WHERE Estado != 'Inactivo'")
        vehiculos = cursor.fetchall()
        
        return resultados, 'admin/reportes/reporte_gastos_vehiculos.html', {
            'resultados': resultados,
            'vehiculos': vehiculos,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'vehiculo_id': vehiculo_id
        }

@admin_bp.route('/admin/reporte/compras_cargas')
@admin_required
@report_handler('reporte_compras_cargas')
def reporte_compras_cargas():
    """Reporte de auditoría de cargas de compras y control de recepción"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    estado = request.args.get('estado', 'todos')
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                cpr.ID_Carga,
                prov.Nombre AS Proveedor,
                cpr.Num_Factura AS Factura_N,
                cpr.Fecha_Carga AS Fecha_Envio,
                p.Descripcion AS Producto,
                cpd.Cantidad_Cargada AS Cantidad_Esperada,
                cpd.Cantidad_Recibida AS Cantidad_Recibida,
                (cpd.Cantidad_Cargada - cpd.Cantidad_Recibida) AS Diferencia_Cajas,
                cpd.Costo_Unitario AS Costo_Unitario,
                (cpd.Cantidad_Cargada * cpd.Costo_Unitario) AS Costo_Total_Esperado,
                (cpd.Cantidad_Recibida * cpd.Costo_Unitario) AS Costo_Total_Recibido,
                cpr.Estado AS Estado_Recepcion,
                cpr.Fecha_Recepcion AS Fecha_Recepcion,
                uc.NombreUsuario AS Usuario_Carga,
                ur.NombreUsuario AS Usuario_Recepcion
            FROM cargas_pendientes_recepcion cpr
            JOIN cargas_pendientes_detalle cpd ON cpr.ID_Carga = cpd.ID_Carga
            JOIN proveedores prov ON cpr.ID_Proveedor = prov.ID_Proveedor
            JOIN productos p ON cpd.ID_Producto = p.ID_Producto
            JOIN usuarios uc ON cpr.ID_Usuario_Carga = uc.ID_Usuario
            LEFT JOIN usuarios ur ON cpr.ID_Usuario_Recepcion = ur.ID_Usuario
            WHERE cpr.Fecha_Carga BETWEEN %s AND %s
        """
        params = [fecha_inicio, fecha_fin]
        
        if estado != 'todos':
            query += " AND cpr.Estado = %s"
            params.append(estado.upper())
            
        query += " ORDER BY cpr.Fecha_Carga DESC, cpr.ID_Carga DESC"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        return resultados, 'admin/reportes/reporte_compras_cargas.html', {
            'resultados': resultados,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'estado': estado
        }

@admin_bp.route('/admin/reporte/conciliacion_productos')
@admin_required
def reporte_conciliacion_productos():
    """Redirección al reporte unificado de consolidado de carga y ventas"""
    return redirect(url_for('admin.reporte_consolidado_carga_ventas', **request.args))

@admin_bp.route('/admin/reporte/conciliacion_monetaria')
@admin_required
@report_handler('reporte_conciliacion_monetaria')
def reporte_conciliacion_monetaria():
    """Reporte de conciliación monetaria completa de ruta (Contado, Crédito, Abonos)"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=False)
    vendedor_id = request.args.get('vendedor_id', '')
    
    with get_db_cursor() as cursor:
        query = """
            WITH Facturado_CTE AS (
                SELECT 
                    fr.ID_Asignacion,
                    COALESCE(SUM(dfr.Total), 0.00) AS Total_Facturado_Contado
                FROM facturacion_ruta fr
                JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.Credito_Contado = 1
                  AND fr.Estado = 'Activa'
                GROUP BY fr.ID_Asignacion
            ),
            Abonos_CTE AS (
                SELECT 
                    ad.ID_Asignacion,
                    COALESCE(SUM(ad.Monto_Aplicado), 0.00) AS Total_Abonos_Detallados
                FROM abonos_detalle ad
                GROUP BY ad.ID_Asignacion
            ),
            Caja_CTE AS (
                SELECT 
                    mcr.ID_Asignacion,
                    COALESCE(SUM(CASE WHEN mcr.Tipo = 'APERTURA' THEN mcr.Monto ELSE 0 END), 0.00) AS Caja_Apertura,
                    COALESCE(SUM(CASE WHEN mcr.Tipo = 'VENTA' THEN mcr.Monto ELSE 0 END), 0.00) AS Caja_Ventas_Registradas,
                    COALESCE(SUM(CASE WHEN mcr.Tipo = 'ABONO' THEN mcr.Monto ELSE 0 END), 0.00) AS Caja_Abonos_Registrados,
                    COALESCE(SUM(CASE WHEN mcr.Tipo = 'GASTO' THEN mcr.Monto ELSE 0 END), 0.00) AS Caja_Gastos_Ruta,
                    COALESCE(SUM(CASE WHEN mcr.Tipo = 'CIERRE' THEN mcr.Monto ELSE 0 END), 0.00) AS Caja_Cierre_Declarado
                FROM movimientos_caja_ruta mcr
                WHERE mcr.Estado = 'ACTIVO'
                GROUP BY mcr.ID_Asignacion
            )
            SELECT 
                av.ID_Asignacion,
                av.Fecha_Asignacion AS Fecha,
                r.Nombre_Ruta AS Ruta,
                u.NombreUsuario AS Vendedor,
                
                COALESCE(f.Total_Facturado_Contado, 0.00) AS Facturado_Contado,
                COALESCE(c.Caja_Ventas_Registradas, 0.00) AS Efectivo_Ventas_Caja,
                (COALESCE(f.Total_Facturado_Contado, 0.00) - COALESCE(c.Caja_Ventas_Registradas, 0.00)) AS Discrepancia_Dinero_Ventas,
                
                COALESCE(a.Total_Abonos_Detallados, 0.00) AS Abonos_Clientes_Detalle,
                COALESCE(c.Caja_Abonos_Registrados, 0.00) AS Efectivo_Abonos_Caja,
                (COALESCE(a.Total_Abonos_Detallados, 0.00) - COALESCE(c.Caja_Abonos_Registrados, 0.00)) AS Discrepancia_Dinero_Abonos,
                
                COALESCE(c.Caja_Apertura, 0.00) AS Caja_Inicial,
                COALESCE(c.Caja_Gastos_Ruta, 0.00) AS Egresos_Gastos_Ruta,
                (
                    COALESCE(c.Caja_Apertura, 0.00) + 
                    COALESCE(c.Caja_Ventas_Registradas, 0.00) + 
                    COALESCE(c.Caja_Abonos_Registrados, 0.00) - 
                    COALESCE(c.Caja_Gastos_Ruta, 0.00)
                ) AS Saldo_Teorico_Total,
                COALESCE(c.Caja_Cierre_Declarado, 0.00) AS Caja_Cierre_Declarado,
                (
                    COALESCE(c.Caja_Cierre_Declarado, 0.00) - 
                    (
                        COALESCE(c.Caja_Apertura, 0.00) + 
                        COALESCE(c.Caja_Ventas_Registradas, 0.00) + 
                        COALESCE(c.Caja_Abonos_Registrados, 0.00) - 
                        COALESCE(c.Caja_Gastos_Ruta, 0.00)
                    )
                ) AS Cuadre_Final_Caja
            FROM asignacion_vendedores av
            JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
            JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
            LEFT JOIN Facturado_CTE f ON av.ID_Asignacion = f.ID_Asignacion
            LEFT JOIN Abonos_CTE a ON av.ID_Asignacion = a.ID_Asignacion
            LEFT JOIN Caja_CTE c ON av.ID_Asignacion = c.ID_Asignacion
            WHERE av.Estado IN ('Activa', 'Finalizada')
              AND av.Fecha_Asignacion BETWEEN %s AND %s
        """
        params = [fecha_inicio, fecha_fin]
        
        if vendedor_id:
            query += " AND av.ID_Usuario = %s"
            params.append(vendedor_id)
            
        query += " ORDER BY av.Fecha_Asignacion DESC, r.Nombre_Ruta"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Filtro de vendedores
        cursor.execute("""
            SELECT u.ID_Usuario, u.NombreUsuario 
            FROM usuarios u
            INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
            WHERE u.Estado = 'ACTIVO'
              AND r.Nombre_Rol LIKE '%%Vendedor%%'
            ORDER BY u.NombreUsuario
        """)
        vendedores = cursor.fetchall()
        
        return resultados, 'admin/reportes/reporte_conciliacion_monetaria.html', {
            'resultados': resultados,
            'vendedores': vendedores,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'vendedor_id': vendedor_id
        }

@admin_bp.route('/admin/reporte/cxp')
@admin_required
@report_handler('reporte_cxp')
def reporte_cxp():
    """Reporte ejecutivo de cuentas por pagar (CxP)"""
    fecha_corte = get_corte_filter()
    estado = request.args.get('estado', 'todos')
    
    with get_db_cursor() as cursor:
        query = """
            SELECT 
                p.Nombre AS Proveedor,
                p.Telefono,
                cpp.Num_Documento,
                cpp.Fecha,
                cpp.Fecha_Vencimiento,
                DATEDIFF(%s, cpp.Fecha_Vencimiento) AS Dias_Vencido,
                cpp.Monto_Movimiento AS Monto_Original,
                cpp.Saldo_Pendiente,
                cpp.Estado AS Estado_Actual,
                CASE 
                    WHEN cpp.Estado = 'Pagada' THEN 'PAGADA'
                    WHEN DATEDIFF(%s, cpp.Fecha_Vencimiento) > 0 THEN 'VENCIDA'
                    ELSE 'PENDIENTE'
                END AS Estado_Calculado,
                CASE 
                    WHEN DATEDIFF(%s, cpp.Fecha_Vencimiento) <= 0 THEN 'AL DIA'
                    WHEN DATEDIFF(%s, cpp.Fecha_Vencimiento) <= 30 THEN '1-30 días'
                    WHEN DATEDIFF(%s, cpp.Fecha_Vencimiento) <= 60 THEN '31-60 días'
                    WHEN DATEDIFF(%s, cpp.Fecha_Vencimiento) <= 90 THEN '61-90 días'
                    ELSE '90+ días'
                END AS Rango_Mora
            FROM cuentas_por_pagar cpp
            INNER JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
            WHERE cpp.Fecha <= %s
              AND cpp.Saldo_Pendiente > 0
        """
        params = [fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte]
        
        if estado != 'todos':
            if estado == 'vencida':
                query += " AND (cpp.Estado = 'Vencida' OR DATEDIFF(%s, cpp.Fecha_Vencimiento) > 0)"
                params.append(fecha_corte)
            else:
                query += " AND cpp.Estado = %s"
                params.append(estado.capitalize())
        
        query += " ORDER BY Dias_Vencido DESC"
        
        cursor.execute(query, params)
        cartera = cursor.fetchall()
        
        # Resumen de CxP
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN Dias_Vencido <= 0 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_Al_Dia,
                COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 1 AND 30 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_30_Dias,
                COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 31 AND 60 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_60_Dias,
                COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 61 AND 90 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_90_Dias,
                COALESCE(SUM(CASE WHEN Dias_Vencido > 90 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_90_Mas,
                COALESCE(SUM(Saldo_Pendiente), 0) AS Total_Cartera
            FROM (
                SELECT 
                    cpp.Saldo_Pendiente,
                    DATEDIFF(%s, cpp.Fecha_Vencimiento) AS Dias_Vencido
                FROM cuentas_por_pagar cpp
                WHERE cpp.Estado IN ('Pendiente', 'Vencida')
                  AND cpp.Fecha <= %s
                  AND cpp.Saldo_Pendiente > 0
            ) AS calculo
        """, [fecha_corte, fecha_corte])
        resumen = cursor.fetchone()
        
        return cartera, 'admin/reportes/reporte_cxp.html', {
            'cartera': cartera,
            'resumen': resumen,
            'fecha_corte': fecha_corte,
            'estado': estado
        }

@admin_bp.route('/admin/reporte/flujo_caja')
@admin_required
@report_handler('reporte_flujo_caja')
def reporte_flujo_caja():
    """Reporte de Flujo de Caja General (Oficina)"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    
    with get_db_cursor() as cursor:
        # Movimientos detallados
        query = """
            SELECT 
                DATE(cm.Fecha) AS Fecha,
                cm.ID_Movimiento,
                cm.Tipo_Movimiento,
                cm.Descripcion,
                cm.Monto,
                cm.Referencia_Documento,
                cm.Estado,
                u.NombreUsuario AS Creado_Por
            FROM caja_movimientos cm
            JOIN usuarios u ON cm.ID_Usuario = u.ID_Usuario
            WHERE DATE(cm.Fecha) BETWEEN %s AND %s
            ORDER BY cm.Fecha DESC, cm.ID_Movimiento DESC
        """
        cursor.execute(query, [fecha_inicio, fecha_fin])
        resultados = cursor.fetchall()
        
        # Totales del período (activos)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto ELSE 0 END), 0) AS Total_Entradas,
                COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'SALIDA' THEN Monto ELSE 0 END), 0) AS Total_Salidas
            FROM caja_movimientos
            WHERE Estado = 'ACTIVO'
              AND DATE(Fecha) BETWEEN %s AND %s
        """, [fecha_inicio, fecha_fin])
        resumen = cursor.fetchone()
        
        return resultados, 'admin/reportes/reporte_flujo_caja.html', {
            'resultados': resultados,
            'resumen': resumen,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }

@admin_bp.route('/admin/reporte/rotacion_productos')
@admin_required
@report_handler('reporte_rotacion_productos')
def reporte_rotacion_productos():
    """Reporte de rotación e indicadores de venta por producto"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    categoria_id = request.args.get('categoria_id', '')
    
    with get_db_cursor() as cursor:
        # Query principal de rotación (Ventas totales por producto de Facturación Normal y Ruta)
        query = """
            SELECT 
                Codigo,
                Producto,
                Categoria,
                SUM(Cantidad) AS Cantidad_Vendida,
                SUM(Total_Venta) AS Ventas_Totales,
                SUM(Costo_Total) AS Costo_Acumulado,
                (SUM(Total_Venta) - SUM(Costo_Total)) AS Utilidad_Bruta,
                ROUND(((SUM(Total_Venta) - SUM(Costo_Total)) / NULLIF(SUM(Total_Venta), 0)) * 100, 2) AS Margen_Porcentaje
            FROM (
                -- Ventas Oficina
                SELECT 
                    p.COD_Producto AS Codigo,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    p.ID_Categoria,
                    df.Cantidad,
                    df.Total AS Total_Venta,
                    df.Cantidad * COALESCE(df.Costo, 0) AS Costo_Total
                  FROM facturacion fac
                  JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                  JOIN productos p ON df.ID_Producto = p.ID_Producto
                  JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                  WHERE fac.Estado = 'Activa'
                    AND DATE(fac.Fecha_Creacion) BETWEEN %s AND %s
                    
                  UNION ALL
                  
                  -- Ventas Ruta
                  SELECT 
                      p.COD_Producto AS Codigo,
                      p.Descripcion AS Producto,
                      cp.Descripcion AS Categoria,
                      p.ID_Categoria,
                      dfr.Cantidad,
                      dfr.Total AS Total_Venta,
                      dfr.Cantidad * COALESCE(dfr.Costo, 0) AS Costo_Total
                  FROM facturacion_ruta fr
                  JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                  JOIN productos p ON dfr.ID_Producto = p.ID_Producto
                  JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                  WHERE fr.Estado = 'Activa'
                    AND DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
              ) AS ventas_unificadas
              WHERE 1=1
          """
        params = [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin]
        
        if categoria_id:
            query += " AND ID_Categoria = %s"
            params.append(categoria_id)
            
        query += " GROUP BY Codigo, Producto, Categoria ORDER BY Cantidad_Vendida DESC"
        
        cursor.execute(query, params)
        rotacion = cursor.fetchall()
        
        # Categorías para filtros
        cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto WHERE Estado = 'Activo'")
        categorias = cursor.fetchall()
        
        return rotacion, 'admin/reportes/reporte_rotacion_productos.html', {
            'rotacion': rotacion,
            'categorias': categorias,
            'categoria_id': categoria_id,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }

@admin_bp.route('/admin/reporte/consolidado_carga_ventas')
@admin_required
@report_handler('reporte_consolidado_carga_ventas')
def reporte_consolidado_carga_ventas():
    """Reporte consolidado de carga en camiones vs vendido por facturas en ruta"""
    fecha_inicio, fecha_fin = get_date_filters(default_monthly=True)
    vendedor_id = request.args.get('vendedor_id', '')
    categoria_id = request.args.get('categoria_id', '')
    
    with get_db_cursor() as cursor:
        # Obtener todos los vendedores para el selector
        cursor.execute("""
            SELECT u.ID_Usuario, u.NombreUsuario 
            FROM usuarios u
            INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
            WHERE u.Estado = 'ACTIVO'
              AND r.Nombre_Rol LIKE '%%Vendedor%%'
            ORDER BY u.NombreUsuario
        """)
        vendedores = cursor.fetchall()
        
        # Obtener todas las categorías para el selector
        cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto WHERE Estado = 'Activo'")
        categorias = cursor.fetchall()
        
        # Si no hay vendedor_id seleccionado, obtenemos el listado de vendedores con asignaciones
        if not vendedor_id:
            cursor.execute("""
                SELECT 
                    u.ID_Usuario,
                    u.NombreUsuario AS Vendedor,
                    GROUP_CONCAT(DISTINCT r.Nombre_Ruta SEPARATOR ', ') AS Rutas,
                    MIN(av.Fecha_Asignacion) AS Primera_Asignacion,
                    MAX(av.Fecha_Asignacion) AS Ultima_Asignacion,
                    COUNT(DISTINCT av.ID_Asignacion) AS Total_Asignaciones
                FROM asignacion_vendedores av
                JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                GROUP BY u.ID_Usuario, u.NombreUsuario
                ORDER BY u.NombreUsuario
            """, (fecha_inicio, fecha_fin))
            vendedores_activos = cursor.fetchall()
            
            return vendedores_activos, 'admin/reportes/reporte_consolidado_carga_ventas.html', {
                'vendedores_activos': vendedores_activos,
                'vendedores': vendedores,
                'categorias': categorias,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'vendedor_id': vendedor_id,
                'categoria_id': categoria_id
            }
        
        # Si hay un vendedor_id seleccionado, obtenemos su consolidado
        params_carga = [fecha_inicio, fecha_fin, vendedor_id]
        params_venta = [fecha_inicio, fecha_fin, vendedor_id]
        params_devolucion = [fecha_inicio, fecha_fin, vendedor_id]
        params_stock = [fecha_inicio, fecha_fin, vendedor_id]
        
        query = """
            SELECT 
                p.ID_Producto,
                p.COD_Producto AS Codigo,
                p.Descripcion AS Producto,
                cp.Descripcion AS Categoria,
                COALESCE(carga.Total_Cargado, 0.00) AS Total_Cargado,
                COALESCE(venta.Total_Vendido, 0.00) AS Total_Vendido,
                COALESCE(devolucion.Total_Devuelto, 0.00) AS Total_Devuelto,
                COALESCE(stock.Stock_Camion, 0.00) AS Stock_Camion,
                (COALESCE(carga.Total_Cargado, 0.00) 
                 - COALESCE(venta.Total_Vendido, 0.00) 
                 - COALESCE(devolucion.Total_Devuelto, 0.00) 
                 - COALESCE(stock.Stock_Camion, 0.00)) AS Diferencia
            FROM productos p
            JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
            LEFT JOIN (
                SELECT 
                    mrd.ID_Producto,
                    SUM(mrd.Cantidad) AS Total_Cargado
                FROM movimientos_ruta_cabecera mrc
                JOIN movimientos_ruta_detalle mrd ON mrc.ID_Movimiento = mrd.ID_Movimiento
                JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
                WHERE mrc.Estado = 'ACTIVO'
                  AND (cm.Descripcion LIKE '%%CARGA%%' OR cm.Letra = 'C' OR mrc.ID_TipoMovimiento = 15)
                  AND av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  AND av.ID_Usuario = %s
                GROUP BY mrd.ID_Producto
            ) carga ON p.ID_Producto = carga.ID_Producto
            LEFT JOIN (
                SELECT 
                    dfr.ID_Producto,
                    SUM(dfr.Cantidad) AS Total_Vendido
                FROM facturacion_ruta fr
                JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                WHERE fr.Estado = 'Activa'
                  AND av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  AND av.ID_Usuario = %s
                GROUP BY dfr.ID_Producto
            ) venta ON p.ID_Producto = venta.ID_Producto
            LEFT JOIN (
                SELECT 
                    mrd.ID_Producto,
                    SUM(mrd.Cantidad) AS Total_Devuelto
                FROM movimientos_ruta_cabecera mrc
                JOIN movimientos_ruta_detalle mrd ON mrc.ID_Movimiento = mrd.ID_Movimiento
                JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
                WHERE mrc.Estado = 'ACTIVO'
                  AND mrc.ID_TipoMovimiento = 11 -- Devolución Ruta
                  AND av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  AND av.ID_Usuario = %s
                GROUP BY mrd.ID_Producto
            ) devolucion ON p.ID_Producto = devolucion.ID_Producto
            LEFT JOIN (
                SELECT 
                    ir.ID_Producto,
                    SUM(ir.Cantidad) AS Stock_Camion
                FROM inventario_ruta ir
                JOIN asignacion_vendedores av ON ir.ID_Asignacion = av.ID_Asignacion
                WHERE av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  AND av.ID_Usuario = %s
                GROUP BY ir.ID_Producto
            ) stock ON p.ID_Producto = stock.ID_Producto
            WHERE (carga.Total_Cargado > 0 OR venta.Total_Vendido > 0 OR devolucion.Total_Devuelto > 0 OR stock.Stock_Camion > 0)
        """
        
        params = params_carga + params_venta + params_devolucion + params_stock
        
        if categoria_id:
            query += " AND p.ID_Categoria = %s"
            params.append(categoria_id)
            
        query += " ORDER BY Total_Cargado DESC, p.Descripcion"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Obtener facturas realizadas en ruta por este vendedor en el período
        cursor.execute("""
            SELECT 
                fr.ID_FacturaRuta AS Factura_ID,
                CONCAT('R-', fr.ID_FacturaRuta) AS Factura_N,
                fr.Fecha_Creacion AS Fecha,
                c.Nombre AS Cliente,
                fr.Credito_Contado,
                COALESCE(SUM(dfr.Total), 0.00) AS Total
            FROM facturacion_ruta fr
            JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
            JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
            WHERE fr.Estado = 'Activa'
              AND av.ID_Usuario = %s
              AND av.Fecha_Asignacion BETWEEN %s AND %s
            GROUP BY fr.ID_FacturaRuta, fr.Fecha_Creacion, c.Nombre, fr.Credito_Contado
            ORDER BY fr.Fecha_Creacion DESC
        """, (vendedor_id, fecha_inicio, fecha_fin))
        facturas_realizadas = cursor.fetchall()
        
        # Obtener devoluciones de ruta realizadas por este vendedor en el período
        cursor.execute("""
            SELECT 
                mrc.ID_Movimiento,
                mrc.Fecha_Movimiento AS Fecha,
                r.Nombre_Ruta AS Ruta,
                mrc.Documento_Numero,
                mrc.Total_Productos,
                mrc.Total_Subtotal
            FROM movimientos_ruta_cabecera mrc
            JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
            JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
            WHERE mrc.Estado = 'ACTIVO'
              AND mrc.ID_TipoMovimiento = 11 -- Devolución Ruta
              AND av.ID_Usuario = %s
              AND av.Fecha_Asignacion BETWEEN %s AND %s
            ORDER BY mrc.Fecha_Movimiento DESC
        """, (vendedor_id, fecha_inicio, fecha_fin))
        devoluciones_realizadas = cursor.fetchall()
        
        return resultados, 'admin/reportes/reporte_consolidado_carga_ventas.html', {
            'resultados': resultados,
            'facturas_realizadas': facturas_realizadas,
            'devoluciones_realizadas': devoluciones_realizadas,
            'vendedores': vendedores,
            'categorias': categorias,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'vendedor_id': vendedor_id,
            'categoria_id': categoria_id
        }

@admin_bp.route('/admin/reporte/consolidado_carga_ventas/detalle')
@admin_required
def reporte_consolidado_carga_ventas_detalle():
    """Obtiene el desglose de movimientos de carga, facturas y devoluciones de un producto"""
    from flask import jsonify
    try:
        producto_id = request.args.get('producto_id', '')
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        vendedor_id = request.args.get('vendedor_id', '')
        
        if not producto_id or not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Parámetros insuficientes'}), 400
            
        with get_db_cursor() as cursor:
            # 1. Cargar detalles de Carga (Movimientos)
            params_carga = [producto_id, fecha_inicio, fecha_fin]
            filter_vendedor = ""
            if vendedor_id:
                filter_vendedor = " AND av.ID_Usuario = %s"
                params_carga.append(vendedor_id)
                
            query_cargas = f"""
                SELECT 
                    mrc.ID_Movimiento AS Movimiento_ID,
                    DATE_FORMAT(mrc.Fecha_Movimiento, '%%Y-%%m-%%d') AS Fecha,
                    u.NombreUsuario AS Vendedor,
                    r.Nombre_Ruta AS Ruta,
                    mrd.Cantidad
                FROM movimientos_ruta_detalle mrd
                JOIN movimientos_ruta_cabecera mrc ON mrd.ID_Movimiento = mrc.ID_Movimiento
                JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
                JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE mrd.ID_Producto = %s
                  AND mrc.Estado = 'ACTIVO'
                  AND (cm.Descripcion LIKE '%%CARGA%%' OR cm.Letra = 'C' OR mrc.ID_TipoMovimiento = 15)
                  AND av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  {filter_vendedor}
                ORDER BY mrc.Fecha_Movimiento DESC
            """
            cursor.execute(query_cargas, params_carga)
            cargas = cursor.fetchall()
            
            # Formatear Decimales para cargas
            for c in cargas:
                if 'Cantidad' in c and c['Cantidad'] is not None:
                    c['Cantidad'] = float(c['Cantidad'])
            
            # 2. Cargar detalles de Ventas (Facturas)
            params_venta = [producto_id, fecha_inicio, fecha_fin]
            if vendedor_id:
                params_venta.append(vendedor_id)
                
            query_ventas = f"""
                SELECT 
                    fr.ID_FacturaRuta AS Factura_ID,
                    CONCAT('R-', fr.ID_FacturaRuta) AS Factura_N,
                    DATE_FORMAT(fr.Fecha_Creacion, '%%Y-%%m-%%d') AS Fecha,
                    u.NombreUsuario AS Vendedor,
                    r.Nombre_Ruta AS Ruta,
                    c.Nombre AS Cliente_Nombre,
                    dfr.Cantidad,
                    dfr.Total
                FROM detalle_facturacion_ruta dfr
                JOIN facturacion_ruta fr ON dfr.ID_FacturaRuta = dfr.ID_FacturaRuta
                JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                WHERE dfr.ID_Producto = %s
                  AND fr.Estado = 'Activa'
                  AND av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  {filter_vendedor}
                ORDER BY fr.Fecha_Creacion DESC
            """
            cursor.execute(query_ventas, params_venta)
            ventas = cursor.fetchall()
            
            # Formatear Decimales para ventas
            for v in ventas:
                if 'Cantidad' in v and v['Cantidad'] is not None:
                    v['Cantidad'] = float(v['Cantidad'])
                if 'Total' in v and v['Total'] is not None:
                    v['Total'] = float(v['Total'])
                    
            # 3. Cargar detalles de Devoluciones
            params_devolucion = [producto_id, fecha_inicio, fecha_fin]
            if vendedor_id:
                params_devolucion.append(vendedor_id)
                
            query_devoluciones = f"""
                SELECT 
                    mrc.ID_Movimiento AS Movimiento_ID,
                    DATE_FORMAT(mrc.Fecha_Movimiento, '%%Y-%%m-%%d') AS Fecha,
                    u.NombreUsuario AS Vendedor,
                    r.Nombre_Ruta AS Ruta,
                    mrd.Cantidad
                FROM movimientos_ruta_detalle mrd
                JOIN movimientos_ruta_cabecera mrc ON mrd.ID_Movimiento = mrc.ID_Movimiento
                JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
                JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE mrd.ID_Producto = %s
                  AND mrc.Estado = 'ACTIVO'
                  AND mrc.ID_TipoMovimiento = 11 -- Devolución Ruta
                  AND av.Fecha_Asignacion BETWEEN %s AND %s
                  AND av.Estado IN ('Activa', 'Finalizada')
                  {filter_vendedor}
                ORDER BY mrc.Fecha_Movimiento DESC
            """
            cursor.execute(query_devoluciones, params_devolucion)
            devoluciones = cursor.fetchall()
            
            # Formatear Decimales para devoluciones
            for d in devoluciones:
                if 'Cantidad' in d and d['Cantidad'] is not None:
                    d['Cantidad'] = float(d['Cantidad'])
                    
            return jsonify({
                'cargas': cargas,
                'ventas': ventas,
                'devoluciones': devoluciones
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/reporte/categoria_compras')
@admin_required
@report_handler('reporte_categoria_compras')
def reporte_categoria_compras():
    """Reporte de Compras por Categoría y Proveedor"""
    fecha_inicio, fecha_fin, periodo = get_period_date_range()
    categoria_id = request.args.get('categoria_id', '')
    proveedor_id = request.args.get('proveedor_id', '')
    
    with get_db_cursor() as cursor:
        # Query de compras agrupadas por producto
        query = """
            SELECT 
                p.ID_Producto,
                p.COD_Producto AS Codigo,
                p.Descripcion AS Producto,
                cp.Descripcion AS Categoria,
                SUM(dmi.Cantidad) AS Cantidad_Comprada,
                SUM(dmi.Subtotal) AS Monto_Comprado
            FROM movimientos_inventario mi
            JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
            JOIN productos p ON dmi.ID_Producto = p.ID_Producto
            JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
            WHERE mi.Estado = 'Activa'
              AND mi.ID_TipoMovimiento = 1 -- Compra
              AND mi.Fecha BETWEEN %s AND %s
        """
        params = [fecha_inicio, fecha_fin]
        
        if categoria_id:
            query += " AND p.ID_Categoria = %s"
            params.append(categoria_id)
            
        if proveedor_id:
            query += " AND mi.ID_Proveedor = %s"
            params.append(proveedor_id)
            
        query += " GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, cp.Descripcion ORDER BY Monto_Comprado DESC, p.Descripcion"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Formatear decimales en los resultados
        for r in resultados:
            r['Cantidad_Comprada'] = float(r['Cantidad_Comprada'])
            r['Monto_Comprado'] = float(r['Monto_Comprado'])
        
        # Obtener categorías
        cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto WHERE Estado = 'Activo' ORDER BY Descripcion")
        categorias = cursor.fetchall()
        
        # Obtener proveedores
        cursor.execute("SELECT ID_Proveedor, Nombre FROM proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
        proveedores = cursor.fetchall()
        
        fecha_inicio_formatted = datetime.strptime(fecha_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
        fecha_fin_formatted = datetime.strptime(fecha_fin, '%Y-%m-%d').strftime('%d/%m/%Y')
        
        return resultados, 'admin/reportes/reporte_categoria_compras.html', {
            'resultados': resultados,
            'categorias': categorias,
            'proveedores': proveedores,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'fecha_inicio_formatted': fecha_inicio_formatted,
            'fecha_fin_formatted': fecha_fin_formatted,
            'categoria_id': categoria_id,
            'proveedor_id': proveedor_id,
            'periodo': periodo
        }

@admin_bp.route('/admin/reporte/categoria_ventas')
@admin_required
@report_handler('reporte_categoria_ventas')
def reporte_categoria_ventas():
    """Reporte de Ventas por Categoría"""
    fecha_inicio, fecha_fin, periodo = get_period_date_range()
    categoria_id = request.args.get('categoria_id', '')
    
    with get_db_cursor() as cursor:
        # Query de ventas agrupadas por producto
        query = """
            SELECT 
                p.ID_Producto,
                p.COD_Producto AS Codigo,
                p.Descripcion AS Producto,
                cp.Descripcion AS Categoria,
                SUM(venta.Cantidad_Vendida) AS Cantidad_Vendida,
                SUM(venta.Monto_Vendido) AS Monto_Vendido
            FROM productos p
            JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
            JOIN (
                SELECT 
                    df.ID_Producto,
                    df.Cantidad AS Cantidad_Vendida,
                    df.Total AS Monto_Vendido
                FROM facturacion fac
                JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                WHERE fac.Estado = 'Activa'
                  AND DATE(fac.Fecha_Creacion) BETWEEN %s AND %s
                
                UNION ALL
                
                SELECT 
                    dfr.ID_Producto,
                    dfr.Cantidad AS Cantidad_Vendida,
                    dfr.Total AS Monto_Vendido
                FROM facturacion_ruta fr
                JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.Estado = 'Activa'
                  AND DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
            ) venta ON p.ID_Producto = venta.ID_Producto
            WHERE 1=1
        """
        params = [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin]
        
        if categoria_id:
            query += " AND p.ID_Categoria = %s"
            params.append(categoria_id)
            
        query += " GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, cp.Descripcion ORDER BY Monto_Vendido DESC, p.Descripcion"
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        # Formatear decimales en los resultados
        for r in resultados:
            r['Cantidad_Vendida'] = float(r['Cantidad_Vendida'])
            r['Monto_Vendido'] = float(r['Monto_Vendido'])
        
        # Obtener categorías
        cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto WHERE Estado = 'Activo' ORDER BY Descripcion")
        categorias = cursor.fetchall()
        
        fecha_inicio_formatted = datetime.strptime(fecha_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
        fecha_fin_formatted = datetime.strptime(fecha_fin, '%Y-%m-%d').strftime('%d/%m/%Y')
        
        return resultados, 'admin/reportes/reporte_categoria_ventas.html', {
            'resultados': resultados,
            'categorias': categorias,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'fecha_inicio_formatted': fecha_inicio_formatted,
            'fecha_fin_formatted': fecha_fin_formatted,
            'categoria_id': categoria_id,
            'periodo': periodo
        }