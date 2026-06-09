from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime
from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator, registrar_bitacora
from respaldo import exportar_csv, exportar_json
from . import admin_bp

@admin_bp.route('/admin/reportes')
@admin_required
def reportes():
    """Panel principal de reportes ejecutivos"""
    return render_template('admin/reportes/reportes.html',
                            now=datetime.now())

@admin_bp.route('/admin/reporte/ventas')
@admin_required
def reporte_ventas():
    """Reporte de ventas con filtros (incluye facturación normal y de ruta)"""
    try:
        fecha_inicio = request.args.get('fecha_inicio', datetime.now().strftime('%Y-%m-01'))
        fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
        tipo_venta = request.args.get('tipo_venta', 'todos')
        vendedor_id = request.args.get('vendedor_id', '')
        formato = request.args.get('formato', 'html')
        
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
            
            if formato == 'csv':
                return exportar_csv(ventas, 'reporte_ventas')
            elif formato == 'json':
                return exportar_json(ventas, 'reporte_ventas')
            
            return render_template('admin/reportes/reporte_ventas.html',
                                 ventas=ventas,
                                 resumen=resumen,
                                 resumen_origen=resumen_origen,
                                 vendedores=vendedores,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 tipo_venta=tipo_venta,
                                 vendedor_id=vendedor_id,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/admin/reporte/cartera')
@admin_required
def reporte_cartera():
    """Reporte de cartera y cuentas por cobrar"""
    try:
        fecha_corte = request.args.get('fecha_corte', datetime.now().strftime('%Y-%m-%d'))
        estado = request.args.get('estado', 'todos')
        formato = request.args.get('formato', 'html')
        
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
            
            if formato == 'csv':
                return exportar_csv(cartera, 'reporte_cartera')
            elif formato == 'json':
                return exportar_json(cartera, 'reporte_cartera')
            
            return render_template('admin/reportes/reporte_cartera.html',
                                 cartera=cartera,
                                 resumen=resumen,
                                 fecha_corte=fecha_corte,
                                 estado=estado,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/admin/reporte/inventario')
@admin_required
def reporte_inventario():
    """Reporte de inventario y productos"""
    try:
        categoria_id = request.args.get('categoria_id', '')
        stock_status = request.args.get('stock_status', 'todos')
        formato = request.args.get('formato', 'html')
        
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
            
            if formato == 'csv':
                return exportar_csv(inventario, 'reporte_inventario')
            elif formato == 'json':
                return exportar_json(inventario, 'reporte_inventario')
            
            return render_template('admin/reportes/reporte_inventario.html',
                                 inventario=inventario,
                                 resumen=resumen,
                                 categorias=categorias,
                                 categoria_id=categoria_id,
                                 stock_status=stock_status,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/admin/reporte/estado_resultados')
@admin_required
def reporte_estado_resultados():
    """Estado de resultados financiero"""
    try:
        mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        formato = request.args.get('formato', 'html')
        
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
            
            if formato == 'csv':
                return exportar_csv(resultados, 'estado_resultados')
            elif formato == 'json':
                return exportar_json(resultados, 'estado_resultados')
            
            return render_template('admin/reportes/reporte_estado_resultados.html',
                                 resultados=resultados,
                                 total_ingresos=total_ingresos,
                                 total_gastos=total_gastos,
                                 utilidad=utilidad,
                                 margen=margen,
                                 mes_actual=mes,
                                 meses_disponibles=meses_disponibles,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))
