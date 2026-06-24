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
                
                # Obtener asignación activa del vendedor
                cursor.execute("""
                    SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Vehiculo, 
                           r.Nombre_Ruta, r.Descripcion,
                           av.Fecha_Asignacion, av.Hora_Inicio, av.Hora_Fin,
                           v.Placa as VehiculoPlaca
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                    WHERE av.ID_Usuario = %s 
                      AND av.Estado = 'Activa'
                      AND av.Fecha_Asignacion <= %s
                    ORDER BY av.Fecha_Asignacion DESC
                    LIMIT 1
                """, (vendedor_id, fecha_consulta))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    return jsonify({
                        'success': False, 
                        'error': 'El vendedor no tiene una ruta activa asignada en esta fecha'
                    }), 404
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ABONOS EN EFECTIVO (solo de la tabla abonos_detalle)
                cursor.execute("""
                    SELECT COALESCE(SUM(ad.Monto_Aplicado), 0) as total_abonos_efectivo
                    FROM abonos_detalle ad
                    LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE ad.ID_Asignacion = %s 
                      AND DATE(ad.Fecha) = %s
                      AND (mp.Nombre = 'Efectivo' OR mp.Nombre = 'CONTADO' OR ad.ID_MetodoPago IS NULL)
                """, (id_asignacion, fecha_consulta))
                abonos_efectivo = cursor.fetchone()['total_abonos_efectivo']
                abonos_efectivo = float(abonos_efectivo) if abonos_efectivo else 0.0
                
                # Ventas en efectivo
                cursor.execute("""
                    SELECT COALESCE(SUM(mrc.Monto_Efectivo), 0) as total_ventas_efectivo
                    FROM movimientos_ruta_cabecera mrc
                    WHERE mrc.ID_Asignacion = %s 
                      AND DATE(mrc.Fecha_Movimiento) = %s
                      AND mrc.Estado = 'ACTIVO'
                """, (id_asignacion, fecha_consulta))
                ventas_efectivo = cursor.fetchone()['total_ventas_efectivo']
                ventas_efectivo = float(ventas_efectivo) if ventas_efectivo else 0.0
                
                # GASTOS del día (¡NUEVO!)
                cursor.execute("""
                    SELECT COALESCE(SUM(Monto), 0) as total_gastos
                    FROM movimientos_caja_ruta
                    WHERE ID_Asignacion = %s 
                      AND DATE(Fecha) = %s
                      AND Tipo = 'GASTO'
                      AND Estado = 'ACTIVO'
                """, (id_asignacion, fecha_consulta))
                gastos = cursor.fetchone()['total_gastos']
                gastos = float(gastos) if gastos else 0.0
                
                # Total de efectivo en caja = ventas + abonos - gastos
                caja_total = ventas_efectivo + abonos_efectivo - gastos
                
                # LISTA DE ABONOS EN EFECTIVO (para mostrar en la tabla)
                cursor.execute("""
                    SELECT 
                        ad.Monto_Aplicado as monto,
                        ad.Fecha as fecha,
                        c.Nombre as cliente,
                        COALESCE(mp.Nombre, 'Efectivo') as metodo_pago
                    FROM abonos_detalle ad
                    JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                    LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE ad.ID_Asignacion = %s 
                      AND DATE(ad.Fecha) = %s
                      AND (mp.Nombre = 'Efectivo' OR mp.Nombre = 'CONTADO' OR ad.ID_MetodoPago IS NULL)
                    ORDER BY ad.Fecha DESC
                """, (id_asignacion, fecha_consulta))
                abonos_hoy = cursor.fetchall()
                
                # LISTA DE GASTOS DEL DÍA (para mostrar)
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
                gastos_hoy = cursor.fetchall()
                
                # Inventario
                cursor.execute("""
                    SELECT ir.ID_Producto, p.Descripcion as NombreProducto, ir.Cantidad, p.Precio_Ruta as PrecioVenta
                    FROM inventario_ruta ir
                    JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    WHERE ir.ID_Asignacion = %s AND ir.Cantidad > 0
                """, (id_asignacion,))
                inventario = cursor.fetchall()
                
                # Facturas pendientes
                cursor.execute("""
                    SELECT fr.ID_FacturaRuta, c.Nombre as NombreCliente, fr.Observacion,
                           COALESCE(SUM(dfr.Cantidad * dfr.Precio), 0) as Total
                    FROM facturacion_ruta fr
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    LEFT JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    WHERE fr.ID_Asignacion = %s 
                      AND fr.Estado = 'Activa' 
                      AND fr.Credito_Contado = 2
                    GROUP BY fr.ID_FacturaRuta, c.Nombre, fr.Observacion
                    HAVING Total > 0
                """, (id_asignacion,))
                facturas_pendientes = cursor.fetchall()
                
                # Resumen
                cursor.execute("""
                    SELECT COUNT(*) as total_facturas,
                           COALESCE(SUM(dfr.Cantidad * dfr.Precio), 0) as total_vendido
                    FROM facturacion_ruta fr
                    JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE fr.ID_Asignacion = %s AND DATE(fr.Fecha) = %s
                """, (id_asignacion, fecha_consulta))
                resumen = cursor.fetchone()
                
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
                        'hora_fin': str(asignacion['Hora_Fin']) if asignacion['Hora_Fin'] else None
                    },
                    'caja': {
                        'ventas_efectivo': ventas_efectivo,
                        'abonos_efectivo': abonos_efectivo,
                        'gastos': gastos,
                        'total': caja_total
                    },
                    'inventario': [{
                        'nombre': i['NombreProducto'],
                        'cantidad': float(i['Cantidad']),
                        'precio': float(i['PrecioVenta'])
                    } for i in inventario],
                    'facturas_pendientes': [{
                        'cliente': f['NombreCliente'],
                        'total': float(f['Total'])
                    } for f in facturas_pendientes],
                    'abonos_hoy': [{
                        'cliente': a['cliente'],
                        'monto': float(a['monto']),
                        'metodo_pago': a['metodo_pago']
                    } for a in abonos_hoy],
                    'gastos_hoy': [{
                        'concepto': g['Concepto'],
                        'monto': float(g['Monto']),
                        'fecha': g['Fecha'].isoformat() if g['Fecha'] else None
                    } for g in gastos_hoy],
                    'resumen': {
                        'total_facturas': resumen['total_facturas'] or 0,
                        'total_vendido': float(resumen['total_vendido'] or 0),
                        'total_abonos': len(abonos_hoy),
                        'total_abonos_monto': sum(float(a['monto']) for a in abonos_hoy),
                        'total_gastos': gastos,
                        'total_gastos_cantidad': len(gastos_hoy)
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
            """, (session.get('empresa_id', 1),))
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
            print(f"DEBUG: Tipo de asignaciones_raw: {type(asignaciones_raw)}")
            if asignaciones_raw:
                print(f"DEBUG: Primer elemento tipo: {type(asignaciones_raw[0])}")
                print(f"DEBUG: Claves del primer elemento (si es dict): {list(asignaciones_raw[0].keys()) if isinstance(asignaciones_raw[0], dict) else 'No es dict'}")
            
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
            
        return render_template(
            'admin/catalog/rutas/asignacion.html',
            asignaciones=asignaciones,
            vendedores=vendedores,
            rutas=rutas,
            vehiculos=vehiculos,
            asignadores=asignadores,
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
            
        return render_template(
            'admin/catalog/rutas/editar_asignacion.html',
            asignacion=asignacion,
            rutas=rutas,
            vehiculos=vehiculos,
            asignadores=asignadores
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
            # Obtener el vehículo asignado
            cursor.execute("""
                SELECT ID_Vehiculo 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Empresa = %s 
                AND Estado = 'Activa'
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o ya finalizada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Actualizar estado de la asignación CON HORA_FIN
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Estado = 'Finalizada',
                    Fecha_Finalizacion = CURDATE(),
                    Hora_Fin = CURTIME()
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
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
        empresa_id = session.get('id_empresa')
        fecha = request.args.get('fecha')
        
        if not fecha:
            return jsonify({'error': 'Fecha requerida'}), 400
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener vendedores disponibles en esa fecha - CORREGIDA
            cursor.execute("""
            SELECT 
                u.ID_Usuario, 
                u.NombreUsuario AS Nombre,  -- ← Esto ya es el nombre del usuario
                rol.Nombre_Rol AS Rol
            FROM usuarios u
            LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
            WHERE u.ID_Empresa = %s 
            AND u.Estado = 'ACTIVO'
            AND u.ID_Rol = 4  -- Solo vendedores
            ORDER BY u.NombreUsuario
            """, (empresa_id, empresa_id, fecha, fecha))
            
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
                AND av.Fecha_Asignacion = CURDATE()
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


