# -*- coding: utf-8 -*-
from decimal import Decimal
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import date, datetime, time, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator
from .. import admin_bp

@admin_bp.route('/monitoreo-vendedores')
@admin_required
@bitacora_decorator("MONITOREO-VENDEDORES")
def admin_monitoreo_vendedores():
    """Panel de monitoreo de vendedores - Vista principal y API"""
    try:
        vendedor_id = request.args.get('id', type=int)
        
        # Si es petición API (tiene id)
        if vendedor_id:
            with get_db_cursor(True) as cursor:
                fecha_str = request.args.get('fecha')
                if fecha_str:
                    try:
                        fecha_consulta = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                    except ValueError:
                        return jsonify({
                            'success': False, 
                            'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                        }), 400
                else:
                    fecha_consulta = date.today()
                
                # Obtener asignación del vendedor (activa o finalizada en la fecha consultada)
                cursor.execute("""
                    SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Vehiculo, 
                           r.Nombre_Ruta, r.Descripcion,
                           av.Fecha_Asignacion, av.Hora_Inicio, av.Hora_Fin,
                           v.Placa as VehiculoPlaca, av.Estado
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                    WHERE av.ID_Usuario = %s 
                      AND (
                        (av.Estado = 'Activa' AND DATE(av.Fecha_Asignacion) <= %s)
                        OR
                        (av.Estado = 'Finalizada' AND DATE(av.Fecha_Asignacion) <= %s AND DATE(COALESCE(av.Fecha_Finalizacion, av.Fecha_Asignacion)) >= %s)
                      )
                    ORDER BY CASE WHEN av.Estado = 'Activa' THEN 0 ELSE 1 END,
                             av.Fecha_Asignacion DESC, av.ID_Asignacion DESC
                    LIMIT 1
                """, (vendedor_id, fecha_consulta, fecha_consulta, fecha_consulta))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    return jsonify({
                        'success': False, 
                        'error': 'El vendedor no tiene una ruta asignada en esta fecha'
                    }), 404
                
                id_asignacion = asignacion['ID_Asignacion']
                id_ruta = asignacion.get('ID_Ruta')
                
                # CAJA EN EFECTIVO (desde movimientos_caja_ruta para la asignación, consistente con calcular_saldo_caja_ruta)
                cursor.execute("""
                    SELECT
                        COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN Monto ELSE 0 END), 0) as total_apertura,
                        COALESCE(SUM(CASE WHEN Tipo = 'VENTA' AND (Tipo_Pago = 'CONTADO' OR Tipo_Pago IS NULL) AND (ID_MetodoPago = 1 OR ID_MetodoPago IS NULL) THEN Monto ELSE 0 END), 0) as total_ventas_efectivo,
                        COALESCE(SUM(CASE WHEN Tipo = 'ABONO' AND (ID_MetodoPago = 1 OR ID_MetodoPago IS NULL) THEN Monto ELSE 0 END), 0) as total_abonos_efectivo,
                        COALESCE(SUM(CASE WHEN Tipo = 'GASTO' THEN Monto ELSE 0 END), 0) as total_gastos
                    FROM movimientos_caja_ruta
                    WHERE ID_Asignacion = %s
                      AND DATE(Fecha) <= %s
                      AND Estado = 'ACTIVO'
                """, (id_asignacion, fecha_consulta))
                caja_row = cursor.fetchone() or {}
                apertura = float(caja_row.get('total_apertura') or 0.0)
                ventas_efectivo = float(caja_row.get('total_ventas_efectivo') or 0.0)
                abonos_efectivo = float(caja_row.get('total_abonos_efectivo') or 0.0)
                gastos_caja = float(caja_row.get('total_gastos') or 0.0)
                
                # Total de efectivo en caja = apertura + ventas_efectivo + abonos_efectivo - gastos_caja
                caja_total = apertura + ventas_efectivo + abonos_efectivo - gastos_caja
                
                # ABONOS REGISTRADOS EN LA FECHA (todos los métodos de pago, AGRUPADOS por cliente y método)
                cursor.execute("""
                    SELECT 
                        ad.ID_Cliente,
                        c.Nombre as cliente,
                        COALESCE(mp.Nombre, 'Efectivo') as metodo_pago,
                        COALESCE(SUM(ad.Monto_Aplicado), 0) as monto,
                        COUNT(DISTINCT COALESCE(CAST(ad.ID_Movimiento_Caja AS CHAR), CAST(ad.Fecha AS CHAR))) as cantidad_abonos,
                        COUNT(ad.ID_Detalle) as cantidad_facturas,
                        GROUP_CONCAT(DISTINCT COALESCE(cc.Num_Documento, 'Saldo General') ORDER BY cc.Num_Documento SEPARATOR ', ') as documentos,
                        MAX(ad.Fecha) as ultima_fecha
                    FROM abonos_detalle ad
                    INNER JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                    LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                    LEFT JOIN cuentas_por_cobrar cc ON ad.ID_CuentaCobrar = cc.ID_Movimiento
                    LEFT JOIN movimientos_caja_ruta mcr ON ad.ID_Movimiento_Caja = mcr.ID_Movimiento
                    WHERE ad.ID_Asignacion = %s 
                      AND DATE(ad.Fecha) = %s
                      AND (ad.ID_Movimiento_Caja IS NULL OR mcr.Estado = 'ACTIVO')
                    GROUP BY ad.ID_Cliente, c.Nombre, COALESCE(mp.Nombre, 'Efectivo')
                    ORDER BY ultima_fecha DESC
                """, (id_asignacion, fecha_consulta))
                abonos_hoy = cursor.fetchall() or []
                
                # LISTA DE GASTOS DEL DÍA EN EFECTIVO (para mostrar)
                cursor.execute("""
                    SELECT 
                        ID_Movimiento,
                        Concepto,
                        Monto,
                        Fecha
                    FROM movimientos_caja_ruta
                    WHERE ID_Asignacion = %s 
                      AND DATE(Fecha) = %s
                      AND Tipo = 'GASTO'
                      AND Estado = 'ACTIVO'
                    ORDER BY Fecha DESC
                """, (id_asignacion, fecha_consulta))
                gastos_hoy = cursor.fetchall() or []
                total_gastos_dia = sum(float(g['Monto'] or 0) for g in gastos_hoy)

                # CARGAS DE COMBUSTIBLE POR CONVENIO (Estación San José - no descuentan efectivo de caja)
                cursor.execute("""
                    SELECT 
                        gg.ID_Gasto,
                        gg.Monto,
                        gg.Fecha_Registro,
                        gg.Descripcion,
                        gvd.Kilometraje,
                        COALESCE(gvd.Taller, 'Estación de Servicio San José') as Gasolinera
                    FROM gastos_generales gg
                    LEFT JOIN gastos_vehiculo_detalle gvd ON gg.ID_Gasto = gvd.ID_Gasto
                    WHERE gg.ID_Usuario_Registro = %s
                      AND DATE(gg.Fecha) = %s
                      AND UPPER(gg.Estado) = 'ACTIVO'
                      AND (UPPER(gvd.Tipo_Mantenimiento) = 'COMBUSTIBLE' OR gg.Descripcion LIKE %s)
                    ORDER BY gg.ID_Gasto DESC
                """, (vendedor_id, fecha_consulta, 'Carga de combustible%'))
                cargas_combustible = cursor.fetchall() or []
                total_combustible = sum(float(c['Monto'] or 0) for c in cargas_combustible)
                
                # Inventario actual en ruta (usando el último precio facturado en la asignación o Precio_Ruta como respaldo)
                cursor.execute("""
                    SELECT ir.ID_Producto,
                           p.COD_Producto as Codigo,
                           p.Descripcion as NombreProducto,
                           ir.Cantidad,
                           COALESCE(
                               (SELECT dfr.Precio
                                FROM detalle_facturacion_ruta dfr
                                INNER JOIN facturacion_ruta fr ON dfr.ID_FacturaRuta = fr.ID_FacturaRuta
                                WHERE fr.ID_Asignacion = %s
                                  AND fr.Estado = 'Activa'
                                  AND dfr.ID_Producto = ir.ID_Producto
                                  AND dfr.Precio > 0
                                ORDER BY fr.ID_FacturaRuta DESC
                                LIMIT 1),
                               p.Precio_Ruta,
                               0
                           ) as PrecioVenta
                    FROM inventario_ruta ir
                    JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    WHERE ir.ID_Asignacion = %s AND ir.Cantidad > 0
                    ORDER BY p.Descripcion ASC
                """, (id_asignacion, id_asignacion))
                inventario = cursor.fetchall() or []
                
                # Cuentas a crédito y sus saldos actuales (desde cuentas_por_cobrar)
                if id_ruta:
                    cursor.execute("""
                        SELECT cxc.ID_Movimiento,
                               COALESCE(cxc.Num_Documento, CONCAT('CXC-', cxc.ID_Movimiento)) as Num_Documento,
                               c.Nombre as NombreCliente,
                               COALESCE(cxc.Monto_Movimiento, 0) as Monto_Original,
                               COALESCE(cxc.Saldo_Pendiente, 0) as Saldo_Actual,
                               COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Cliente,
                               cxc.Fecha,
                               cxc.Fecha_Vencimiento,
                               CASE 
                                   WHEN cxc.Fecha_Vencimiento IS NOT NULL AND cxc.Fecha_Vencimiento < CURDATE() THEN 'Vencida'
                                   ELSE cxc.Estado
                               END as Estado_Cuenta,
                               CASE WHEN fr.ID_Asignacion = %s THEN 1 ELSE 0 END as Es_Asignacion_Actual
                        FROM cuentas_por_cobrar cxc
                        INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
                        LEFT JOIN facturacion_ruta fr ON cxc.ID_FacturaRuta = fr.ID_FacturaRuta
                        WHERE cxc.Estado IN ('Pendiente', 'Vencida')
                          AND cxc.Saldo_Pendiente > 0
                          AND (fr.ID_Asignacion = %s OR c.ID_Ruta = %s)
                        ORDER BY Es_Asignacion_Actual DESC, cxc.Fecha_Vencimiento ASC, cxc.ID_Movimiento DESC
                    """, (id_asignacion, id_asignacion, id_ruta))
                else:
                    cursor.execute("""
                        SELECT cxc.ID_Movimiento,
                               COALESCE(cxc.Num_Documento, CONCAT('CXC-', cxc.ID_Movimiento)) as Num_Documento,
                               c.Nombre as NombreCliente,
                               COALESCE(cxc.Monto_Movimiento, 0) as Monto_Original,
                               COALESCE(cxc.Saldo_Pendiente, 0) as Saldo_Actual,
                               COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Cliente,
                               cxc.Fecha,
                               cxc.Fecha_Vencimiento,
                               CASE 
                                   WHEN cxc.Fecha_Vencimiento IS NOT NULL AND cxc.Fecha_Vencimiento < CURDATE() THEN 'Vencida'
                                   ELSE cxc.Estado
                               END as Estado_Cuenta,
                               CASE WHEN fr.ID_Asignacion = %s THEN 1 ELSE 0 END as Es_Asignacion_Actual
                        FROM cuentas_por_cobrar cxc
                        INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
                        LEFT JOIN facturacion_ruta fr ON cxc.ID_FacturaRuta = fr.ID_FacturaRuta
                        WHERE cxc.Estado IN ('Pendiente', 'Vencida')
                          AND cxc.Saldo_Pendiente > 0
                          AND (fr.ID_Asignacion = %s OR cxc.ID_Usuario_Creacion = %s)
                        ORDER BY Es_Asignacion_Actual DESC, cxc.Fecha_Vencimiento ASC, cxc.ID_Movimiento DESC
                    """, (id_asignacion, id_asignacion, vendedor_id))
                facturas_pendientes = cursor.fetchall() or []
                
                # Resumen del día (facturas únicas activas y monto neto)
                cursor.execute("SHOW COLUMNS FROM facturacion_ruta LIKE 'Descuento'")
                tiene_descuento = bool(cursor.fetchone())
                expr_neto = "GREATEST(0, COALESCE(SUM(dfr.Cantidad * dfr.Precio), 0) - COALESCE(fr.Descuento, 0))" if tiene_descuento else "COALESCE(SUM(dfr.Cantidad * dfr.Precio), 0)"
                group_desc = ", fr.Descuento" if tiene_descuento else ""

                cursor.execute(f"""
                    SELECT COUNT(*) as total_facturas,
                           COALESCE(SUM(sub.Neto), 0) as total_vendido,
                           COALESCE(SUM(CASE WHEN sub.Credito_Contado = 1 THEN sub.Neto ELSE 0 END), 0) as total_contado,
                           COALESCE(SUM(CASE WHEN sub.Credito_Contado = 2 THEN sub.Neto ELSE 0 END), 0) as total_credito
                    FROM (
                        SELECT fr.ID_FacturaRuta, fr.Credito_Contado, {expr_neto} as Neto
                        FROM facturacion_ruta fr
                        JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                        WHERE fr.ID_Asignacion = %s
                          AND DATE(fr.Fecha) = %s
                          AND fr.Estado = 'Activa'
                        GROUP BY fr.ID_FacturaRuta, fr.Credito_Contado{group_desc}
                    ) sub
                """, (id_asignacion, fecha_consulta))
                resumen = cursor.fetchone() or {}
                
                # Info vendedor
                cursor.execute("""
                    SELECT ID_Usuario, NombreUsuario 
                    FROM usuarios 
                    WHERE ID_Usuario = %s
                """, (vendedor_id,))
                vendedor_info = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'vendedor': {
                        'id': vendedor_info['ID_Usuario'], 
                        'nombre': vendedor_info['NombreUsuario']
                    },
                    'fecha_consulta': fecha_consulta.isoformat(),
                    'ruta': {
                        'nombre': asignacion['Nombre_Ruta'] or 'Sin nombre',
                        'vehiculo': asignacion.get('VehiculoPlaca', 'N/A'),
                        'hora_inicio': str(asignacion['Hora_Inicio']) if asignacion['Hora_Inicio'] else None,
                        'hora_fin': str(asignacion['Hora_Fin']) if asignacion['Hora_Fin'] else None,
                        'estado': asignacion.get('Estado', 'Activa')
                    },
                    'caja': {
                        'apertura': apertura,
                        'ventas_efectivo': ventas_efectivo,
                        'abonos_efectivo': abonos_efectivo,
                        'gastos': gastos_caja,
                        'total': caja_total
                    },
                    'inventario': [{
                        'codigo': i.get('Codigo') or '',
                        'nombre': i['NombreProducto'],
                        'cantidad': float(i['Cantidad'] or 0),
                        'precio': float(i['PrecioVenta'] or 0)
                    } for i in inventario],
                    'facturas_pendientes': [{
                        'documento': f['Num_Documento'],
                        'cliente': f['NombreCliente'],
                        'monto_original': float(f['Monto_Original'] or 0),
                        'total': float(f['Saldo_Actual'] or 0),
                        'saldo_actual': float(f['Saldo_Actual'] or 0),
                        'saldo_cliente': float(f['Saldo_Cliente'] or 0),
                        'fecha': f['Fecha'].strftime('%d/%m/%Y') if hasattr(f.get('Fecha'), 'strftime') else (str(f['Fecha']) if f.get('Fecha') else 'N/A'),
                        'fecha_vencimiento': f['Fecha_Vencimiento'].strftime('%d/%m/%Y') if hasattr(f.get('Fecha_Vencimiento'), 'strftime') else (str(f['Fecha_Vencimiento']) if f.get('Fecha_Vencimiento') else 'N/A'),
                        'estado': f['Estado_Cuenta'],
                        'es_asignacion_actual': bool(f['Es_Asignacion_Actual'])
                    } for f in facturas_pendientes],
                    'abonos_hoy': [{
                        'cliente': a['cliente'],
                        'monto': float(a['monto'] or 0),
                        'metodo_pago': a['metodo_pago'],
                        'cantidad_abonos': int(a['cantidad_abonos'] or 1),
                        'cantidad_facturas': int(a['cantidad_facturas'] or 1),
                        'documentos': a.get('documentos') or '',
                        'fecha': a['ultima_fecha'].isoformat() if a.get('ultima_fecha') else None
                    } for a in abonos_hoy],
                    'gastos_hoy': [{
                        'concepto': g['Concepto'],
                        'monto': float(g['Monto']),
                        'fecha': g['Fecha'].isoformat() if g['Fecha'] else None,
                        'es_convenio': False
                    } for g in gastos_hoy] + [{
                        'concepto': f"Combustible ({'Km ' + str(c['Kilometraje']) if c.get('Kilometraje') else 'Ruta'}) - Convenio {c['Gasolinera']}",
                        'monto': float(c['Monto']),
                        'fecha': c['Fecha_Registro'].isoformat() if c.get('Fecha_Registro') else None,
                        'es_convenio': True
                    } for c in cargas_combustible],
                    'resumen': {
                        'total_facturas': int(resumen.get('total_facturas') or 0),
                        'total_vendido': float(resumen.get('total_vendido') or 0),
                        'total_contado': float(resumen.get('total_contado') or 0),
                        'total_credito': float(resumen.get('total_credito') or 0),
                        'total_abonos': sum(int(a['cantidad_abonos'] or 1) for a in abonos_hoy),
                        'total_abonos_agrupados': len(abonos_hoy),
                        'total_abonos_monto': sum(float(a['monto'] or 0) for a in abonos_hoy),
                        'total_gastos': total_gastos_dia,
                        'total_gastos_cantidad': len(gastos_hoy),
                        'total_combustible_convenio': total_combustible,
                        'total_combustible_cantidad': len(cargas_combustible)
                    }
                })
        
        # Cargar página principal
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT u.ID_Usuario, u.NombreUsuario
                FROM usuarios u
                INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Empresa = %s 
                  AND r.Nombre_Rol = 'Vendedor' 
                  AND u.Estado = 'ACTIVO'
                ORDER BY u.NombreUsuario
            """, (session.get('id_empresa', session.get('empresa_id', 1)),))
            vendedores = cursor.fetchall()
            
            hoy = date.today().isoformat()
            api_url = url_for('admin.admin_monitoreo_vendedores')
            
            return render_template(
                'admin/ventas/monitoreo/monitore_vendedores.html', 
                vendedores=vendedores, 
                hoy=hoy,
                api_url=api_url
            )
                                   
    except Exception as e:
        if request.args.get('id'):
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/catalogos/rutas/asignacion')
@admin_required
def admin_asignacion_rutas():
    """Vista principal para gestionar asignaciones de rutas"""
    try:
        empresa_id = session.get('id_empresa', 1)

        if not empresa_id:
            flash('No se ha identificado la empresa', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener asignaciones activas
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    u.ID_Usuario,
                    u.NombreUsuario AS Vendedor,
                    r.Nombre_Ruta,
                    r.ID_Ruta,
                    v.ID_Vehiculo,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    CONCAT(v.Placa, ' - ', v.Marca, ' ', v.Modelo) AS Vehiculo_Completo,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado AS Estado_Asignacion,
                    ua.NombreUsuario AS Asignado_Por,
                    rol.Nombre_Rol AS Rol_Vendedor,
                    a.Hora_Inicio,
                    a.Hora_Fin,
                    a.ID_Usuario_Asigna
                FROM asignacion_vendedores a
                LEFT JOIN usuarios u ON a.ID_Usuario = u.ID_Usuario
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios ua ON a.ID_Usuario_Asigna = ua.ID_Usuario
                WHERE a.ID_Empresa = %s
                ORDER BY a.ID_Asignacion DESC, a.Estado
                LIMIT 10
            """, (empresa_id,))
            asignaciones_raw = cursor.fetchall()
            
            # Verificar el tipo de datos devuelto
            if asignaciones_raw:
                pass
            
            # Procesar asignaciones para formatear correctamente
            asignaciones = []
            for asignacion in asignaciones_raw:
                # Crear una copia del diccionario si ya es un diccionario
                if isinstance(asignacion, dict):
                    asignacion_dict = asignacion.copy()
                else:
                    # Si es una tupla, convertir a diccionario
                    asignacion_dict = {}
                    for i, col in enumerate(cursor.description):
                        col_name = col[0]
                        value = asignacion[i]
                        asignacion_dict[col_name] = value
                
                # Formatear fechas
                if asignacion_dict.get('Fecha_Asignacion'):
                    fecha_val = asignacion_dict['Fecha_Asignacion']
                    if isinstance(fecha_val, (datetime, date)):
                        asignacion_dict['Fecha_Asignacion_fmt'] = fecha_val.strftime('%d/%m/%Y')
                    else:
                        # Convertir a string y tomar los primeros 10 caracteres
                        fecha_str = str(fecha_val)
                        asignacion_dict['Fecha_Asignacion_fmt'] = fecha_str[:10] if len(fecha_str) >= 10 else fecha_str
                else:
                    asignacion_dict['Fecha_Asignacion_fmt'] = None
                
                if asignacion_dict.get('Fecha_Finalizacion'):
                    fecha_val = asignacion_dict['Fecha_Finalizacion']
                    if isinstance(fecha_val, (datetime, date)):
                        asignacion_dict['Fecha_Finalizacion_fmt'] = fecha_val.strftime('%d/%m/%Y')
                    else:
                        # Convertir a string y tomar los primeros 10 caracteres
                        fecha_str = str(fecha_val)
                        asignacion_dict['Fecha_Finalizacion_fmt'] = fecha_str[:10] if len(fecha_str) >= 10 else fecha_str
                else:
                    asignacion_dict['Fecha_Finalizacion_fmt'] = None
                
                # Formatear horas
                if asignacion_dict.get('Hora_Inicio'):
                    hora_val = asignacion_dict['Hora_Inicio']
                    if isinstance(hora_val, timedelta):
                        total_seconds = int(hora_val.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        asignacion_dict['Hora_Inicio_fmt'] = f"{hours:02d}:{minutes:02d}"
                    elif isinstance(hora_val, time):
                        asignacion_dict['Hora_Inicio_fmt'] = hora_val.strftime('%H:%M')
                    else:
                        # Si es string, extraer solo la parte de tiempo
                        hora_str = str(hora_val)
                        if ':' in hora_str:
                            asignacion_dict['Hora_Inicio_fmt'] = hora_str[:5]
                        else:
                            asignacion_dict['Hora_Inicio_fmt'] = hora_str
                else:
                    asignacion_dict['Hora_Inicio_fmt'] = None
                
                if asignacion_dict.get('Hora_Fin'):
                    hora_val = asignacion_dict['Hora_Fin']
                    if isinstance(hora_val, timedelta):
                        total_seconds = int(hora_val.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        asignacion_dict['Hora_Fin_fmt'] = f"{hours:02d}:{minutes:02d}"
                    elif isinstance(hora_val, time):
                        asignacion_dict['Hora_Fin_fmt'] = hora_val.strftime('%H:%M')
                    else:
                        # Si es string, extraer solo la parte de tiempo
                        hora_str = str(hora_val)
                        if ':' in hora_str:
                            asignacion_dict['Hora_Fin_fmt'] = hora_str[:5]
                        else:
                            asignacion_dict['Hora_Fin_fmt'] = hora_str
                else:
                    asignacion_dict['Hora_Fin_fmt'] = None
                
                asignaciones.append(asignacion_dict)
            
            # Obtener vendedores disponibles
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND u.Estado = 'ACTIVO'
                AND rol.Nombre_Rol LIKE '%%Vendedor%%'
                AND NOT EXISTS (
                    SELECT 1 
                    FROM asignacion_vendedores av
                    WHERE av.ID_Usuario = u.ID_Usuario 
                    AND av.Estado = 'Activa'
                    AND av.ID_Empresa = %s
                )
                ORDER BY u.NombreUsuario
            """, (empresa_id, empresa_id))
            
            vendedores = cursor.fetchall()
            
            # Obtener rutas activas
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta
                FROM rutas
                WHERE ID_Empresa = %s AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (empresa_id,))
            rutas = cursor.fetchall()
            
            # Obtener vehículos disponibles
            cursor.execute("""
                SELECT 
                    ID_Vehiculo, 
                    Placa,
                    Marca,
                    Modelo,
                    CONCAT(Placa, ' - ', Marca, ' ', Modelo) AS Descripcion
                FROM vehiculos
                WHERE ID_Empresa = %s 
                AND Estado = 'Disponible'
                AND NOT EXISTS (
                    SELECT 1 
                    FROM asignacion_vendedores av 
                    WHERE av.ID_Vehiculo = vehiculos.ID_Vehiculo 
                    AND av.Estado = 'Activa' 
                    AND av.ID_Empresa = %s
                )
                ORDER BY Placa
            """, (empresa_id, empresa_id))
            vehiculos = cursor.fetchall()
            
            # Obtener usuarios que pueden asignar
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND u.Estado = 'ACTIVO'
                AND rol.Nombre_Rol IN ('Administrador', 'Supervisor', 'ADMINISTRADOR', 'SUPERVISOR')
                ORDER BY u.NombreUsuario
            """, (empresa_id,))
            asignadores = cursor.fetchall()
            
            # Obtener asignaciones activas de fechas anteriores (Alertas de Rutas Sin Liquidar)
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    u.NombreUsuario AS Vendedor,
                    r.Nombre_Ruta,
                    a.Fecha_Asignacion
                FROM asignacion_vendedores a
                LEFT JOIN usuarios u ON a.ID_Usuario = u.ID_Usuario
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                WHERE a.ID_Empresa = %s
                  AND a.Estado = 'Activa'
                  AND DATE(a.Fecha_Asignacion) < CURDATE()
                ORDER BY a.Fecha_Asignacion ASC
            """, (empresa_id,))
            alertas_sin_liquidar = cursor.fetchall()

            return render_template(
                'admin/catalog/rutas/asignacion.html',
                asignaciones=asignaciones,
                vendedores=vendedores,
                rutas=rutas,
                vehiculos=vehiculos,
                asignadores=asignadores,
                alertas_sin_liquidar=alertas_sin_liquidar,
                hoy=datetime.now().strftime('%Y-%m-%d')
            )
        
    except Exception as e:
        flash(f'Error al cargar asignación de rutas: {str(e)}', 'error')
        error_details = traceback.format_exc()
        print(f"ERROR DETALLADO: {error_details}")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/catalogos/rutas/asignacion/crear', methods=['POST'])
@admin_required
def crear_asignacion_ruta():
    """Crear nueva asignación de ruta"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        # Obtener datos del formulario
        id_vendedor = request.form.get('id_usuario')
        id_ruta = request.form.get('id_ruta')
        id_vehiculo = request.form.get('id_vehiculo')
        fecha_asignacion = request.form.get('fecha_asignacion')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        id_asignador = current_user.id

        # Validaciones básicas
        if not id_vendedor or id_vendedor == '':
            flash('Debe seleccionar un vendedor', 'error')
            return redirect(url_for('admin.admin_asignacion_rutas'))
            
        if not id_ruta or id_ruta == '':
            flash('Debe seleccionar una ruta', 'error')
            return redirect(url_for('admin.admin_asignacion_rutas'))
            
        if not fecha_asignacion or fecha_asignacion == '':
            flash('Debe seleccionar una fecha', 'error')
            return redirect(url_for('admin.admin_asignacion_rutas'))
        
        # Convertir valores vacíos a None
        if id_vehiculo == '':
            id_vehiculo = None
        if hora_inicio == '':
            hora_inicio = None
        if hora_fin == '':
            hora_fin = None
        
        # Validar que el vendedor no tenga asignación activa en la misma fecha
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT ID_Asignacion 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s 
                AND Fecha_Asignacion = %s 
                AND Estado = 'Activa'
                AND ID_Empresa = %s
            """, (id_vendedor, fecha_asignacion, empresa_id))
            
            if cursor.fetchone():
                flash('El vendedor ya tiene una asignación activa para esta fecha', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
        
        # Crear la asignación en transacción separada
        with get_db_cursor(commit=True) as cursor:
            # Si se asignó vehículo, verificar disponibilidad
            if id_vehiculo:
                cursor.execute("""
                    SELECT Estado FROM vehiculos 
                    WHERE ID_Vehiculo = %s AND ID_Empresa = %s
                """, (id_vehiculo, empresa_id))
                vehiculo = cursor.fetchone()
                
                if not vehiculo or vehiculo['Estado'] != 'Disponible':
                    flash('El vehículo seleccionado no está disponible', 'error')
                    return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Crear la asignación CON NUEVOS CAMPOS
            cursor.execute("""
                INSERT INTO asignacion_vendedores 
                (ID_Usuario, ID_Ruta, ID_Vehiculo, Fecha_Asignacion, 
                 Estado, ID_Empresa, ID_Usuario_Asigna, Hora_Inicio, Hora_Fin)
                VALUES (%s, %s, %s, %s, 'Activa', %s, %s, %s, %s)
            """, (id_vendedor, id_ruta, id_vehiculo, 
                  fecha_asignacion, empresa_id, id_asignador,
                  hora_inicio, hora_fin))
            
            # Si se asignó vehículo, cambiar su estado
            if id_vehiculo:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'En Ruta' 
                    WHERE ID_Vehiculo = %s
                """, (id_vehiculo,))
            
        flash('Asignación creada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al crear asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))


@admin_bp.route('/admin/catalogos/rutas/asignacion/editar/<int:id>')
@admin_required
def editar_asignacion_ruta(id):
    """Vista para editar una asignación existente"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener la asignación específica - YA INCLUYE LOS NUEVOS CAMPOS EN a.*
            cursor.execute("""
                SELECT 
                    a.*,
                    u.ID_Usuario,
                    u.NombreUsuario AS Nombre_Vendedor,
                    r.Nombre_Ruta,
                    r.ID_Ruta,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    v.ID_Vehiculo,
                    rol.Nombre_Rol AS Rol_Vendedor
                FROM asignacion_vendedores a
                LEFT JOIN usuarios u ON a.ID_Usuario = u.ID_Usuario
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                WHERE a.ID_Asignacion = %s AND a.ID_Empresa = %s
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Obtener datos para el formulario
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta
                FROM rutas
                WHERE ID_Empresa = %s AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (empresa_id,))
            rutas = cursor.fetchall()
            
            # Obtener vehículos disponibles + el vehículo actual
            cursor.execute("""
                SELECT 
                    ID_Vehiculo, 
                    Placa,
                    Marca,
                    Modelo,
                    CONCAT(Placa, ' - ', Marca, ' ', Modelo) AS Descripcion,
                    Estado
                FROM vehiculos
                WHERE ID_Empresa = %s 
                AND (Estado = 'Disponible' OR ID_Vehiculo = %s)
                ORDER BY Placa
            """, (empresa_id, asignacion['ID_Vehiculo']))
            vehiculos = cursor.fetchall()
            
            # Obtener usuarios que pueden asignar
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND rol.Nombre_Rol IN ('Administrador', 'Supervisor', 'ADMINISTRADOR', 'SUPERVISOR')
                AND u.Estado = 'ACTIVO'
                ORDER BY u.NombreUsuario
            """, (empresa_id,))
            asignadores = cursor.fetchall()
            
            # Obtener vendedores disponibles + vendedor actual
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND u.Estado = 'ACTIVO'
                AND (
                    rol.Nombre_Rol LIKE '%%Vendedor%%' 
                    AND NOT EXISTS (
                        SELECT 1 
                        FROM asignacion_vendedores av
                        WHERE av.ID_Usuario = u.ID_Usuario 
                        AND av.Estado = 'Activa'
                        AND av.ID_Empresa = %s
                    )
                    OR u.ID_Usuario = %s
                )
                ORDER BY u.NombreUsuario
            """, (empresa_id, empresa_id, asignacion['ID_Usuario']))
            vendedores = cursor.fetchall()
            
        return render_template(
            'admin/catalog/rutas/editar_asignacion.html',
            asignacion=asignacion,
            rutas=rutas,
            vehiculos=vehiculos,
            asignadores=asignadores,
            vendedores=vendedores
        )
        
    except Exception as e:
        flash(f'Error al cargar asignación para editar: {str(e)}', 'error')
        return redirect(url_for('admin.admin_asignacion_rutas'))


@admin_bp.route('/admin/catalogos/rutas/asignacion/actualizar/<int:id>', methods=['POST'])
@admin_required
def actualizar_asignacion_ruta(id):
    """Actualizar una asignación existente"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        # Obtener datos del formulario
        id_ruta = request.form.get('id_ruta')
        id_vehiculo = request.form.get('id_vehiculo')
        fecha_asignacion = request.form.get('fecha_asignacion')
        fecha_finalizacion = request.form.get('fecha_finalizacion')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        estado = request.form.get('estado')
        
        if not all([id_ruta, fecha_asignacion, estado]):
            flash('Los campos ruta, fecha y estado son requeridos', 'error')
            return redirect(url_for('admin.editar_asignacion_ruta', id=id))
        
        # Convertir valores vacíos a None
        if hora_inicio == '':
            hora_inicio = None
        if hora_fin == '':
            hora_fin = None
        
        with get_db_cursor(commit=True) as cursor:
            # Obtener asignación actual para comparar vehículo
            cursor.execute("""
                SELECT ID_Vehiculo, Estado 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
            asignacion_actual = cursor.fetchone()
            
            if not asignacion_actual:
                flash('Asignación no encontrada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Manejar cambio de vehículo
            vehiculo_actual = asignacion_actual['ID_Vehiculo']
            nuevo_vehiculo = id_vehiculo if id_vehiculo and id_vehiculo != '' else None
            
            if vehiculo_actual != nuevo_vehiculo:
                # Liberar vehículo anterior si existe
                if vehiculo_actual:
                    cursor.execute("""
                        UPDATE vehiculos 
                        SET Estado = 'Disponible' 
                        WHERE ID_Vehiculo = %s
                    """, (vehiculo_actual,))
                
                # Asignar nuevo vehículo
                if nuevo_vehiculo:
                    # Verificar que el nuevo vehículo esté disponible
                    cursor.execute("""
                        SELECT Estado FROM vehiculos 
                        WHERE ID_Vehiculo = %s AND ID_Empresa = %s
                    """, (nuevo_vehiculo, empresa_id))
                    vehiculo_nuevo = cursor.fetchone()
                    
                    if not vehiculo_nuevo or vehiculo_nuevo['Estado'] != 'Disponible':
                        flash('El vehículo seleccionado no está disponible', 'error')
                        return redirect(url_for('admin.editar_asignacion_ruta', id=id))
                    
                    cursor.execute("""
                        UPDATE vehiculos 
                        SET Estado = 'En Ruta' 
                        WHERE ID_Vehiculo = %s
                    """, (nuevo_vehiculo,))
            
            # Actualizar la asignación CON NUEVOS CAMPOS
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET ID_Ruta = %s,
                    ID_Vehiculo = %s,
                    Fecha_Asignacion = %s,
                    Fecha_Finalizacion = %s,
                    Estado = %s,
                    Hora_Inicio = %s,
                    Hora_Fin = %s
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id_ruta, nuevo_vehiculo, fecha_asignacion, 
                  fecha_finalizacion if fecha_finalizacion and fecha_finalizacion != '' else None, 
                  estado, hora_inicio, hora_fin, id, empresa_id))
            
            # Si se finaliza la asignación, liberar el vehículo si existe
            if estado == 'Finalizada' and nuevo_vehiculo:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (nuevo_vehiculo,))
            
        flash('Asignación actualizada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al actualizar asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))


@admin_bp.route('/admin/catalogos/rutas/asignacion/finalizar/<int:id>')
@admin_required
def finalizar_asignacion_ruta(id):
    """Finalizar una asignación activa"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=True) as cursor:
            # Obtener el vehículo asignado y detalles de la ruta
            cursor.execute("""
                SELECT av.ID_Vehiculo, r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Asignacion = %s 
                AND av.ID_Empresa = %s 
                AND av.Estado = 'Activa'
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o ya finalizada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # 1. Calcular Ventas en Efectivo de la Ruta (Facturación)
            cursor.execute("""
                SELECT COALESCE(SUM(dfr.Total), 0) as total_ventas
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Asignacion = %s AND fr.Estado = 'Activa' AND fr.Credito_Contado = 1
            """, (id,))
            ventas_efectivo = float(cursor.fetchone()['total_ventas'] or 0)
            
            # 2. Calcular Abonos en Efectivo de la Ruta
            cursor.execute("""
                SELECT COALESCE(SUM(ad.Monto_Aplicado), 0) as total_abonos
                FROM abonos_detalle ad
                LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN movimientos_caja_ruta mcr ON ad.ID_Movimiento_Caja = mcr.ID_Movimiento
                WHERE ad.ID_Asignacion = %s 
                  AND (mp.Nombre = 'Efectivo' OR mp.Nombre = 'CONTADO' OR ad.ID_MetodoPago IS NULL)
                  AND (ad.ID_Movimiento_Caja IS NULL OR mcr.Estado = 'ACTIVO')
            """, (id,))
            abonos_efectivo = float(cursor.fetchone()['total_abonos'] or 0)
            
            # 3. Calcular Gastos en Efectivo de la Ruta
            cursor.execute("""
                SELECT COALESCE(SUM(Monto), 0) as total_gastos
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Tipo = 'GASTO'
                  AND Estado = 'ACTIVO'
            """, (id,))
            gastos = float(cursor.fetchone()['total_gastos'] or 0)
            
            # 4. Calcular Apertura de la Ruta
            cursor.execute("""
                SELECT COALESCE(SUM(Monto), 0) as total_apertura
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Tipo = 'APERTURA'
                  AND Estado = 'ACTIVO'
            """, (id,))
            apertura = float(cursor.fetchone()['total_apertura'] or 0)
            
            total_consolidado = apertura + ventas_efectivo + abonos_efectivo - gastos
            
            # Actualizar estado de la asignación CON HORA_FIN
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Estado = 'Finalizada',
                    Fecha_Finalizacion = CURDATE(),
                    Hora_Fin = CURTIME()
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
            # Registrar el movimiento consolidado en caja_movimientos si hay algo que reportar
            if total_consolidado > 0:
                nombre_ruta = asignacion.get('Nombre_Ruta') or f"Asignación {id}"
                descripcion = f"Liquidación Ruta {nombre_ruta} - (Apertura: C${apertura:.2f} + Ventas: C${ventas_efectivo:.2f} + Abonos: C${abonos_efectivo:.2f} - Gastos: C${gastos:.2f})"
                
                cursor.execute("""
                    INSERT INTO caja_movimientos 
                    (Fecha, Tipo_Movimiento, Descripcion, Monto, Referencia_Documento, ID_Usuario, Estado)
                    VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, 'ACTIVO')
                """, (descripcion, total_consolidado, f"RUT-LIQ-{id}", current_user.id))
            
            # Liberar el vehículo si existe
            if asignacion['ID_Vehiculo']:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (asignacion['ID_Vehiculo'],))
            
        flash('Asignación finalizada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al finalizar asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))


@admin_bp.route('/admin/catalogos/rutas/asignacion/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_asignacion_ruta(id):
    """Eliminar una asignación (solo si está en estado Finalizada o Suspendida)"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar que la asignación exista y no esté activa
            cursor.execute("""
                SELECT ID_Vehiculo, Estado 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Empresa = %s
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            if asignacion['Estado'] == 'Activa':
                flash('No se puede eliminar una asignación activa', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Liberar vehículo si existe
            if asignacion['ID_Vehiculo']:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (asignacion['ID_Vehiculo'],))
            
            # Eliminar la asignación
            cursor.execute("""
                DELETE FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
        flash('Asignación eliminada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al eliminar asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))


@admin_bp.route('/api/asignaciones/disponibilidad')
@admin_required
def api_disponibilidad_asignaciones():
    """API para verificar disponibilidad de vendedores y vehículos en una fecha"""
    try:
        empresa_id = session.get('id_empresa', 1)
        fecha = request.args.get('fecha')
        
        if not fecha:
            return jsonify({'error': 'Fecha requerida'}), 400
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener vendedores disponibles en esa fecha - CORREGIDA
            cursor.execute("""
            SELECT 
                u.ID_Usuario, 
                u.NombreUsuario AS Nombre,
                rol.Nombre_Rol AS Rol
            FROM usuarios u
            LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
            WHERE u.ID_Empresa = %s 
            AND u.Estado = 'ACTIVO'
            AND u.ID_Rol = 4  -- Solo vendedores
            AND u.ID_Usuario NOT IN (
                SELECT ID_Usuario 
                FROM asignacion_vendedores 
                WHERE Fecha_Asignacion = %s 
                AND Estado = 'Activa'
                AND ID_Empresa = %s
            )
            ORDER BY u.NombreUsuario
            """, (empresa_id, fecha, empresa_id))
            
            vendedores = cursor.fetchall()
            
            # Obtener vehículos disponibles en esa fecha - CORREGIDA
            cursor.execute("""
                SELECT 
                    v.ID_Vehiculo, 
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    CONCAT(v.Placa, ' - ', v.Marca, ' ', v.Modelo) AS Descripcion
                FROM vehiculos v
                WHERE v.ID_Empresa = %s 
                AND v.Estado = 'Disponible'
                AND v.ID_Vehiculo NOT IN (
                    SELECT ID_Vehiculo 
                    FROM asignacion_vendedores 
                    WHERE Fecha_Asignacion = %s 
                    AND Estado = 'Activa'
                    AND ID_Empresa = %s
                )
                ORDER BY v.Placa
            """, (empresa_id, fecha, empresa_id))
            
            vehiculos = cursor.fetchall()
            
        return jsonify({
            'vendedores': vendedores,
            'vehiculos': vehiculos
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/asignaciones/vendedor/<int:id_vendedor>')
@admin_required
def api_asignaciones_vendedor(id_vendedor):
    """API para obtener asignaciones de un vendedor específico"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    r.Nombre_Ruta,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado,
                    v.Placa,
                    v.Marca,
                    v.Modelo
                FROM asignacion_vendedores a
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                WHERE a.ID_Usuario = %s 
                AND a.ID_Empresa = %s
                ORDER BY a.Fecha_Asignacion DESC
                LIMIT 10
            """, (id_vendedor, empresa_id))
            
            asignaciones = cursor.fetchall()
            
        return jsonify(asignaciones)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/rutas/<int:id_ruta>/vendedores-activos')
@login_required
def api_vendedores_activos(id_ruta):
    """
    API para obtener vendedores activos de una ruta en la fecha actual
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    u.ID_Usuario,
                    u.NombreUsuario
                FROM asignacion_vendedores av
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE av.ID_Ruta = %s
                AND av.Estado = 'Activa'
                ORDER BY u.NombreUsuario
            """, (id_ruta,))
            
            vendedores = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': vendedores
            })
    except Exception as e:
        print(f"Error API vendedores: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'data': []
        }), 500


