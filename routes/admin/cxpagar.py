from decimal import Decimal
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator

# ==========================================
# CUENTAS POR PAGAR (CxP) Y ABONOS
# ==========================================

@admin_bp.route('/admin/compras/cxpagar/cuentas-por-pagar', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-CUENTAS-POR-PAGAR")
def admin_cuentas_por_pagar():
    try:
        # Obtener todos los parámetros de filtro
        filtro_estado = request.args.get('estado', 'Pendiente')
        filtro_proveedor = request.args.get('proveedor', '')
        filtro_fecha_desde = request.args.get('fecha_desde', '')
        filtro_fecha_hasta = request.args.get('fecha_hasta', '')
        filtro_rango_dias = request.args.get('rango_dias', '')  # Vencidas, Proximas, etc.
        filtro_monto_min = request.args.get('monto_min', '')
        filtro_monto_max = request.args.get('monto_max', '')
        filtro_num_documento = request.args.get('num_documento', '')
        
        with get_db_cursor(True) as cursor:
            # Construir consulta dinámica
            query = """
                SELECT 
                    cpp.ID_Cuenta,
                    cpp.Fecha,
                    cpp.ID_Proveedor,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    cpp.Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    cpp.Estado,
                    u.NombreUsuario as Usuario_Creacion,
                    DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) as dias_vencimiento
                FROM cuentas_por_pagar cpp
                LEFT JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON cpp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE 1=1
            """
            
            params = []
            
            # Filtro por estado
            if filtro_estado == 'Pendiente':
                query += " AND cpp.Estado = 'Pendiente' AND cpp.Saldo_Pendiente > 0"
            elif filtro_estado == 'Pagada':
                query += " AND cpp.Estado = 'Pagada'"
            elif filtro_estado == 'Anulada':
                query += " AND cpp.Estado = 'Anulada'"
            elif filtro_estado == 'Todas':
                pass
                
            # Filtro por proveedor
            if filtro_proveedor:
                query += " AND cpp.ID_Proveedor = %s"
                params.append(filtro_proveedor)
            
            # Filtro por rango de fechas
            if filtro_fecha_desde:
                query += " AND cpp.Fecha_Vencimiento >= %s"
                params.append(filtro_fecha_desde)
            
            if filtro_fecha_hasta:
                query += " AND cpp.Fecha_Vencimiento <= %s"
                params.append(filtro_fecha_hasta)
            
            # Filtro por rango de días (vencidas, próximas, etc.)
            if filtro_rango_dias == 'vencidas':
                query += " AND DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) < 0"
            elif filtro_rango_dias == 'hoy':
                query += " AND DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) = 0"
            elif filtro_rango_dias == 'proximas_7':
                query += " AND DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) BETWEEN 1 AND 7"
            elif filtro_rango_dias == 'proximas_15':
                query += " AND DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) BETWEEN 8 AND 15"
            elif filtro_rango_dias == 'proximas_30':
                query += " AND DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) BETWEEN 16 AND 30"
            elif filtro_rango_dias == 'futuras':
                query += " AND DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) > 30"
            
            # Filtro por monto
            if filtro_monto_min:
                query += " AND cpp.Saldo_Pendiente >= %s"
                params.append(float(filtro_monto_min))
            
            if filtro_monto_max:
                query += " AND cpp.Saldo_Pendiente <= %s"
                params.append(float(filtro_monto_max))
            
            # Filtro por número de documento
            if filtro_num_documento:
                query += " AND cpp.Num_Documento LIKE %s"
                params.append(f"%{filtro_num_documento}%")
                
            query += " ORDER BY cpp.Fecha_Vencimiento ASC"
            
            cursor.execute(query, params)
            cuentas = cursor.fetchall()
            
            # Obtener lista de proveedores para el filtro
            cursor.execute("SELECT ID_Proveedor, Nombre FROM proveedores ORDER BY Nombre")
            proveedores = cursor.fetchall()
            
            # Calcular estadísticas
            cuentas_pendientes = [c for c in cuentas if c['Estado'] == 'Pendiente']
            total_pendiente = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas_pendientes if cuenta['Saldo_Pendiente'])
            cuentas_vencidas = sum(1 for cuenta in cuentas_pendientes if cuenta['dias_vencimiento'] and cuenta['dias_vencimiento'] < 0)
            
            total_monto = sum(cuenta['Monto_Movimiento'] for cuenta in cuentas if cuenta['Monto_Movimiento'])
            total_saldo = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas if cuenta['Saldo_Pendiente'])
            
            hoy = datetime.now()
            
            return render_template('admin/compras/cxpagar/cuentas_por_pagar.html', 
                                 cuentas=cuentas,
                                 proveedores=proveedores,
                                 total_pendiente=total_pendiente,
                                 cuentas_vencidas=cuentas_vencidas,
                                 filtro_estado=filtro_estado,
                                 filtro_proveedor=filtro_proveedor,
                                 filtro_fecha_desde=filtro_fecha_desde,
                                 filtro_fecha_hasta=filtro_fecha_hasta,
                                 filtro_rango_dias=filtro_rango_dias,
                                 filtro_monto_min=filtro_monto_min,
                                 filtro_monto_max=filtro_monto_max,
                                 filtro_num_documento=filtro_num_documento,
                                 total_cuentas=len(cuentas),
                                 total_monto=total_monto,
                                 total_saldo=total_saldo,
                                 hoy=hoy)
    except Exception as e:
        print(f"Error al cargar cuentas por pagar: {str(e)}")
        flash(f'Error al cargar cuentas por pagar: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/compras/cuentas-por-pagar/pagar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-REGISTRAR-PAGO")
def registrar_pago_cuenta():
    try:
        if request.method == 'GET':
            # Cargar métodos de pago para el formulario
            with get_db_cursor(True) as cursor:
                cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
                metodos_pago = cursor.fetchall()
                
                # Obtener información de la cuenta si se proporciona ID
                id_cuenta = request.args.get('id_cuenta')
                cuenta_info = None
                if id_cuenta:
                    cursor.execute("""
                        SELECT 
                            cpp.ID_Cuenta,
                            cpp.Saldo_Pendiente,
                            cpp.ID_Proveedor,
                            p.Nombre as Proveedor,
                            cpp.Num_Documento,
                            cpp.Monto_Movimiento,
                            cpp.Estado
                        FROM cuentas_por_pagar cpp
                        LEFT JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                        WHERE cpp.ID_Cuenta = %s
                        AND cpp.Estado = 'Pendiente'
                    """, (id_cuenta,))
                    cuenta_info = cursor.fetchone()
                    
                    # Validar que la cuenta existe y está pendiente
                    if not cuenta_info:
                        flash('Cuenta no encontrada o ya está pagada/anulada', 'error')
                        return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                return render_template('admin/compras/cxpagar/registrar_pago.html',
                                     metodos_pago=metodos_pago,
                                     cuenta_info=cuenta_info)
        
        elif request.method == 'POST':
            # Procesar el pago
            id_cuenta = request.form['id_cuenta']
            monto_pago = float(request.form['monto_pago'])
            fecha_pago = request.form['fecha_pago']
            id_metodo_pago = request.form['id_metodo_pago']
            detalles_metodo = request.form.get('detalles_metodo', '')
            comentarios = request.form.get('comentarios_pago', '')
            id_usuario = session.get('user_id', 1)
            
            with get_db_cursor() as cursor:
                # Obtener información completa de la cuenta
                cursor.execute("""
                    SELECT 
                        cpp.Saldo_Pendiente,
                        cpp.ID_Proveedor,
                        p.Nombre as Proveedor,
                        cpp.Num_Documento,
                        cpp.Monto_Movimiento,
                        cpp.Estado,
                        cpp.ID_Movimiento
                    FROM cuentas_por_pagar cpp
                    LEFT JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                    WHERE cpp.ID_Cuenta = %s
                """, (id_cuenta,))
                
                cuenta = cursor.fetchone()
                
                if not cuenta:
                    flash('Cuenta no encontrada', 'error')
                    return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                # Validar que la cuenta esté pendiente
                if cuenta['Estado'] != 'Pendiente':
                    flash(f'Esta cuenta ya está {cuenta["Estado"].lower()}. No se pueden registrar más pagos.', 'error')
                    return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                saldo_actual = float(cuenta['Saldo_Pendiente'])
                proveedor = cuenta['Proveedor']
                num_documento = cuenta['Num_Documento']
                monto_total = float(cuenta['Monto_Movimiento'])
                
                # Validaciones
                if monto_pago <= 0:
                    flash('El monto a pagar debe ser mayor a cero', 'error')
                    return redirect(url_for('admin.registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                if monto_pago > saldo_actual:
                    flash(f'El monto a pagar (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})', 'error')
                    return redirect(url_for('admin.registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                # Calcular nuevo saldo
                nuevo_saldo = saldo_actual - monto_pago
                
                # Determinar el nuevo estado
                nuevo_estado = 'Pagada' if nuevo_saldo == 0 else 'Pendiente'
                
                # Registrar el pago en la tabla pagos_cuentaspagar
                cursor.execute("""
                    INSERT INTO pagos_cuentaspagar 
                    (ID_Cuenta, Fecha, Monto, ID_MetodoPago, Detalles_Metodo, Comentarios, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_cuenta, f"{fecha_pago} 00:00:00", monto_pago, id_metodo_pago, 
                      detalles_metodo, comentarios, id_usuario))
                
                # Actualizar saldo pendiente y estado en la cuenta
                cursor.execute("""
                    UPDATE cuentas_por_pagar 
                    SET Saldo_Pendiente = %s,
                        Estado = %s
                    WHERE ID_Cuenta = %s
                """, (nuevo_saldo, nuevo_estado, id_cuenta))

                # ACTUALIZAR SALDO PENDIENTE DEL PROVEEDOR
                cursor.execute("""
                    UPDATE proveedores 
                    SET Saldo_Pendiente = COALESCE(Saldo_Pendiente, 0) - %s
                    WHERE ID_Proveedor = %s
                """, (monto_pago, cuenta['ID_Proveedor']))
                
                # Mensaje de éxito
                if nuevo_saldo == 0:
                    mensaje = f'¡Cuenta completamente pagada! Se registró pago de ${monto_pago:,.2f} para {proveedor}.'
                else:
                    mensaje = f'Pago de ${monto_pago:,.2f} registrado correctamente para {proveedor}. Saldo restante: ${nuevo_saldo:,.2f}'
                
                flash(mensaje, 'success')
                return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
    except Exception as e:
        print(f"Error al registrar pago: {str(e)}")
        flash(f'Error al registrar pago: {str(e)}', 'error')
        return redirect(url_for('admin.admin_cuentas_por_pagar'))

@admin_bp.route('/admin/compras/cuentas-por-pagar/<int:id_cuenta>/pagos', methods=['GET'])
@admin_required
def historial_pagos_cuenta(id_cuenta):
    """Muestra el historial de pagos de una cuenta específica"""
    try:
        with get_db_cursor(True) as cursor:
            # 1. Obtener información básica de la cuenta
            cursor.execute("""
                SELECT 
                    cpp.ID_Cuenta,
                    DATE(cpp.Fecha) as Fecha,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    DATE(cpp.Fecha_Vencimiento) as Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    cpp.Estado
                FROM cuentas_por_pagar cpp
                LEFT JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                WHERE cpp.ID_Cuenta = %s
            """, (id_cuenta,))
            
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash('Cuenta no encontrada', 'error')
                return redirect(url_for('admin.admin_cuentas_por_pagar'))
            
            # 2. Obtener historial de pagos
            cursor.execute("""
                SELECT 
                    'directo' as Tipo_Pago_Origen,
                    pcp.ID_Pago,
                    DATE(pcp.Fecha) as Fecha_Pago,
                    TIME(pcp.Fecha) as Hora_Pago,
                    pcp.Monto,
                    mp.Nombre as Metodo_Pago,
                    pcp.Detalles_Metodo,
                    pcp.Comentarios,
                    u.NombreUsuario as Usuario_Registro,
                    pcp.Fecha as Fecha_Orden
                FROM pagos_cuentaspagar pcp
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE pcp.ID_Cuenta = %s
                
                UNION ALL
                
                SELECT 
                    'abono_global' as Tipo_Pago_Origen,
                    apd.ID_Detalle as ID_Pago,
                    DATE(apd.Fecha) as Fecha_Pago,
                    TIME(apd.Fecha) as Hora_Pago,
                    apd.Monto_Aplicado as Monto,
                    mp.Nombre as Metodo_Pago,
                    CONCAT('Saldo anterior: C$', FORMAT(apd.Saldo_Anterior, 2), ' | Saldo nuevo: C$', FORMAT(apd.Saldo_Nuevo, 2)) as Detalles_Metodo,
                    'Abono global aplicado en cascada' as Comentarios,
                    u.NombreUsuario as Usuario_Registro,
                    apd.Fecha as Fecha_Orden
                FROM abonos_proveedores_detalle apd
                LEFT JOIN metodos_pago mp ON apd.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON apd.ID_Usuario = u.ID_Usuario
                WHERE apd.ID_CuentaPagar = %s
                
                ORDER BY Fecha_Orden DESC
            """, (id_cuenta, id_cuenta))
            
            pagos = cursor.fetchall()
            
            # 3. Calcular total pagado
            total_pagado = 0.0
            for pago in pagos:
                if pago['Monto']:
                    total_pagado += float(pago['Monto'])
            
            # 4. Renderizar template
            return render_template('admin/compras/cxpagar/historial_pagos.html', 
                                cuenta=cuenta,
                                pagos=pagos,
                                total_pagado=total_pagado,
                                total_cuenta=float(cuenta['Monto_Movimiento']) if cuenta['Monto_Movimiento'] else 0.0)
            
    except Exception as e:
        print(f"Error al cargar historial de pagos (ID: {id_cuenta}): {str(e)}")
        flash(f'Error al cargar historial de pagos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_cuentas_por_pagar'))

@admin_bp.route('/admin/compras/cxpagar/abono-global', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-REGISTRAR-ABONO-GLOBAL")
def registrar_abono_proveedor_global():
    try:
        id_empresa = session.get('id_empresa', 1)
        if request.method == 'GET':
            with get_db_cursor(True) as cursor:
                # Obtener todos los proveedores activos de la empresa
                cursor.execute("""
                    SELECT ID_Proveedor, Nombre, COALESCE(Saldo_Pendiente, 0) as Saldo_Pendiente
                    FROM proveedores
                    WHERE ID_Empresa = %s AND Estado = 'ACTIVO'
                    ORDER BY Nombre
                """, (id_empresa,))
                proveedores = cursor.fetchall()
                
                # Obtener métodos de pago
                cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
                metodos_pago = cursor.fetchall()
                
                today = datetime.now().strftime('%Y-%m-%d')
                
                return render_template('admin/compras/cxpagar/registrar_abono_global.html',
                                     proveedores=proveedores,
                                     metodos_pago=metodos_pago,
                                     today=today)
                                     
        elif request.method == 'POST':
            id_proveedor = int(request.form['id_proveedor'])
            monto_abono = Decimal(str(request.form['monto_abono']))
            fecha_pago = request.form['fecha_pago']
            id_metodo_pago = int(request.form['id_metodo_pago'])
            detalles_metodo = request.form.get('detalles_metodo', '')
            comentarios = request.form.get('comentarios_pago', '')
            id_usuario = session.get('user_id', current_user.id if current_user.is_authenticated else 1)
            
            if monto_abono <= Decimal('0'):
                flash('El monto del abono debe ser mayor a cero', 'error')
                return redirect(url_for('admin.registrar_abono_proveedor_global'))
                
            with get_db_cursor(True) as cursor:
                # Obtener cuentas por pagar pendientes
                cursor.execute("""
                    SELECT ID_Cuenta, Saldo_Pendiente, Num_Documento
                    FROM cuentas_por_pagar
                    WHERE ID_Proveedor = %s AND Estado IN ('Pendiente', 'Parcial', 'Vencida') AND Saldo_Pendiente > 0
                    ORDER BY Fecha_Vencimiento ASC, Fecha ASC
                """, (id_proveedor,))
                cuentas = cursor.fetchall()
                
                saldo_disponible = monto_abono
                detalles_aplicados = []
                
                # 1. Aplicar en cascada a facturas existentes
                for cuenta in cuentas:
                    if saldo_disponible <= Decimal('0'):
                        break
                        
                    id_cuenta = cuenta['ID_Cuenta']
                    saldo_pendiente = Decimal(str(cuenta['Saldo_Pendiente']))
                    
                    monto_aplicado = min(saldo_disponible, saldo_pendiente)
                    saldo_nuevo = saldo_pendiente - monto_aplicado
                    estado_nuevo = 'Pagada' if saldo_nuevo == Decimal('0') else 'Parcial'
                    
                    # Registrar el detalle del abono
                    cursor.execute("""
                        INSERT INTO abonos_proveedores_detalle 
                        (ID_Usuario, ID_Proveedor, ID_CuentaPagar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo, Fecha, ID_MetodoPago, Detalles_Metodo, Comentarios)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (id_usuario, id_proveedor, id_cuenta, float(monto_aplicado), float(saldo_pendiente), float(saldo_nuevo), f"{fecha_pago} 00:00:00", id_metodo_pago, detalles_metodo, comentarios))
                    
                    # Actualizar la cuenta por pagar
                    cursor.execute("""
                        UPDATE cuentas_por_pagar 
                        SET Saldo_Pendiente = %s, Estado = %s
                        WHERE ID_Cuenta = %s
                    """, (float(saldo_nuevo), estado_nuevo, id_cuenta))
                    
                    saldo_disponible -= monto_aplicado
                    detalles_aplicados.append(f"Doc #{cuenta['Num_Documento'] or id_cuenta}: C${monto_aplicado:,.2f}")
                
                # 2. Si queda excedente
                if saldo_disponible > Decimal('0'):
                    cursor.execute("""
                        INSERT INTO cuentas_por_pagar (
                            Fecha, ID_Proveedor, Num_Documento, Observacion, Fecha_Vencimiento,
                            Tipo_Movimiento, Monto_Movimiento, ID_Empresa, Saldo_Pendiente,
                            ID_Usuario_Creacion, Estado
                        ) VALUES (%s, %s, 'ABONO-GLOBAL', %s, %s, 1, 0.00, %s, 0.00, %s, 'Pagada')
                    """, (
                        fecha_pago,
                        id_proveedor,
                        f"Excedente de abono global: C${saldo_disponible:,.2f}",
                        fecha_pago,
                        id_empresa,
                        id_usuario
                    ))
                    
                    id_cuenta_comodin = cursor.lastrowid
                    
                    cursor.execute("""
                        INSERT INTO abonos_proveedores_detalle 
                        (ID_Usuario, ID_Proveedor, ID_CuentaPagar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo, Fecha, ID_MetodoPago, Detalles_Metodo, Comentarios)
                        VALUES (%s, %s, %s, %s, 0.00, 0.00, %s, %s, %s, %s)
                    """, (id_usuario, id_proveedor, id_cuenta_comodin, float(saldo_disponible), f"{fecha_pago} 00:00:00", id_metodo_pago, detalles_metodo, comentarios))
                    
                    detalles_aplicados.append(f"Abono directo / Excedente: C${saldo_disponible:,.2f}")
                
                # 3. Actualizar el saldo pendiente total del proveedor
                cursor.execute("""
                    UPDATE proveedores 
                    SET Saldo_Pendiente = COALESCE(Saldo_Pendiente, 0) - %s
                    WHERE ID_Proveedor = %s
                """, (float(monto_abono), id_proveedor))
                
                cursor.execute("SELECT Nombre FROM proveedores WHERE ID_Proveedor = %s", (id_proveedor,))
                prov_nombre = cursor.fetchone()['Nombre']
                
                detalle_msg = ", ".join(detalles_aplicados)
                flash(f'¡Abono global a {prov_nombre} registrado correctamente! Monto total: C${monto_abono:,.2f}. Aplicado a: {detalle_msg}', 'success')
                return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
    except Exception as e:
        print(f"Error al registrar abono global: {str(e)}")
        flash(f'Error al registrar abono global: {str(e)}', 'error')
        return redirect(url_for('admin.admin_cuentas_por_pagar'))


@admin_bp.route('/admin/compras/cxpagar/historial-abonos')
@admin_required
def admin_historial_abonos_proveedores():
    """Muestra el historial de pagos y abonos realizados a proveedores del día con filtros."""
    try:
        from datetime import date, datetime
        
        # Filtros de fecha (por defecto: HOY)
        hoy = date.today().strftime('%Y-%m-%d')
        fecha_inicio = request.args.get('fecha_inicio', hoy)
        fecha_fin = request.args.get('fecha_fin', hoy)
        id_proveedor = request.args.get('id_proveedor', '')
        
        # Limpiar si el usuario seleccionó "Todos"
        if id_proveedor == 'todos' or id_proveedor == '':
            id_proveedor = None
            
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # 1. Obtener lista de proveedores para el filtro dropdown
            cursor.execute("""
                SELECT ID_Proveedor, Nombre 
                FROM proveedores 
                WHERE ID_Empresa = %s AND Estado = 'ACTIVO' 
                ORDER BY Nombre
            """, (id_empresa,))
            proveedores = cursor.fetchall()
            
            # 2. Armar la consulta base de pagos y abonos unificados para proveedores
            query = """
                SELECT 
                    'pago' as tipo_registro,
                    pcp.ID_Pago as id_registro,
                    pcp.Monto as monto,
                    pcp.Fecha,
                    pcp.Comentarios as descripcion,
                    COALESCE(mp.Nombre, 'No especificado') as metodo_pago,
                    u.NombreUsuario as usuario_registro,
                    prov.Nombre as proveedor_nombre,
                    cpp.Num_Documento as documento_afectado,
                    prov.ID_Proveedor
                FROM pagos_cuentaspagar pcp
                INNER JOIN cuentas_por_pagar cpp ON pcp.ID_Cuenta = cpp.ID_Cuenta
                INNER JOIN proveedores prov ON cpp.ID_Proveedor = prov.ID_Proveedor
                INNER JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                WHERE cpp.ID_Empresa = %s
            """
            params_pago = [id_empresa]
            
            if fecha_inicio:
                query += " AND DATE(pcp.Fecha) >= %s"
                params_pago.append(fecha_inicio)
            if fecha_fin:
                query += " AND DATE(pcp.Fecha) <= %s"
                params_pago.append(fecha_fin)
            if id_proveedor:
                query += " AND prov.ID_Proveedor = %s"
                params_pago.append(id_proveedor)
                
            query += """
                UNION ALL
                
                SELECT 
                    'abono' as tipo_registro,
                    apd.ID_Detalle as id_registro,
                    apd.Monto_Aplicado as monto,
                    apd.Fecha,
                    CASE 
                        WHEN cpp2.Num_Documento = 'ABONO-GLOBAL' THEN 'Abono directo / Excedente a cuenta'
                        ELSE CONCAT('Abono en cascada a Doc: ', cpp2.Num_Documento)
                    END as descripcion,
                    COALESCE(mp2.Nombre, 'No especificado') as metodo_pago,
                    u2.NombreUsuario as usuario_registro,
                    prov2.Nombre as proveedor_nombre,
                    cpp2.Num_Documento as documento_afectado,
                    prov2.ID_Proveedor
                FROM abonos_proveedores_detalle apd
                INNER JOIN proveedores prov2 ON apd.ID_Proveedor = prov2.ID_Proveedor
                INNER JOIN usuarios u2 ON apd.ID_Usuario = u2.ID_Usuario
                LEFT JOIN metodos_pago mp2 ON apd.ID_MetodoPago = mp2.ID_MetodoPago
                LEFT JOIN cuentas_por_pagar cpp2 ON apd.ID_CuentaPagar = cpp2.ID_Cuenta
                WHERE prov2.ID_Empresa = %s
            """
            params_abono = [id_empresa]
            
            if fecha_inicio:
                query += " AND DATE(apd.Fecha) >= %s"
                params_abono.append(fecha_inicio)
            if fecha_fin:
                query += " AND DATE(apd.Fecha) <= %s"
                params_abono.append(fecha_fin)
            if id_proveedor:
                query += " AND prov2.ID_Proveedor = %s"
                params_abono.append(id_proveedor)
                
            query += " ORDER BY Fecha DESC"
            
            all_params = params_pago + params_abono
            cursor.execute(query, all_params)
            registros_raw = cursor.fetchall()
            
            # Formatear datos para el template
            registros = []
            total_egresado = Decimal('0')
            total_cash = Decimal('0')
            total_transfer = Decimal('0')
            total_other = Decimal('0')
            
            for reg in registros_raw:
                reg_dict = dict(reg)
                monto = Decimal(str(reg_dict['monto']))
                total_egresado += monto
                
                # Clasificar por método de pago para resúmenes
                mp_upper = reg_dict['metodo_pago'].upper()
                if 'EFECTIVO' in mp_upper or 'CASH' in mp_upper:
                    total_cash += monto
                elif 'TRANSFERENCIA' in mp_upper or 'DEPOSITO' in mp_upper:
                    total_transfer += monto
                else:
                    total_other += monto
                
                # Formatear fecha
                if reg_dict['Fecha'] and hasattr(reg_dict['Fecha'], 'strftime'):
                    reg_dict['FechaFormateada'] = reg_dict['Fecha'].strftime('%d/%m/%Y %H:%M:%S')
                else:
                    reg_dict['FechaFormateada'] = str(reg_dict['Fecha'])
                    
                registros.append(reg_dict)
                
            return render_template('admin/compras/cxpagar/historial_abonos.html',
                                 registros=registros,
                                 proveedores=proveedores,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 id_proveedor_sel=id_proveedor or 'todos',
                                 total_egresado=float(total_egresado),
                                 total_cash=float(total_cash),
                                 total_transfer=float(total_transfer),
                                 total_other=float(total_other),
                                 hoy=hoy)
                                 
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error al cargar historial de pagos a proveedores: {e}", "danger")
        return redirect(url_for('admin.admin_cuentas_por_pagar'))
