# -*- coding: utf-8 -*-
from flask import json
from decimal import Decimal
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import date, datetime, time, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator
from .. import admin_bp

@admin_bp.route('/admin/ventas/cxcobrar/cuentas-por-cobrar')
@admin_required
@bitacora_decorator("CUENTAS-POR-COBRAR")
def admin_cuentascobrar():
    try:
        # Obtener parámetro de filtro de la URL
        filtro_estado = request.args.get('estado', 'pendientes')
        
        # Definir hoy al principio
        hoy = datetime.now().date()
        
        with get_db_cursor(True) as cursor:
            # Construir la consulta base con ambos tipos de documentos
            query = """
                SELECT 
                    c.ID_Movimiento,
                    c.Fecha,
                    cl.Nombre as NombreCliente,
                    cl.Telefono as TelefonoCliente,
                    c.Observacion,
                    c.Fecha_Vencimiento,
                    c.Monto_Movimiento,
                    c.Saldo_Pendiente,
                    c.ID_Factura,
                    c.ID_FacturaRuta,
                    -- Número de documento según el tipo
                    CASE 
                        WHEN c.ID_Factura IS NOT NULL THEN CONCAT('FAC-', LPAD(f.ID_Factura, 5, '0'))
                        WHEN c.ID_FacturaRuta IS NOT NULL THEN CONCAT('RUTA-', LPAD(fr.ID_FacturaRuta, 5, '0'))
                        ELSE 'S/D'
                    END as NumeroDocumento,
                    -- Tipo de documento
                    CASE 
                        WHEN c.ID_Factura IS NOT NULL THEN 'Factura'
                        WHEN c.ID_FacturaRuta IS NOT NULL THEN 'Factura Ruta'
                        ELSE 'Sin documento'
                    END as TipoDocumento,
                    e.Nombre_Empresa,
                    c.Estado as EstadoDB,
                    -- Calcular estado actual basado en saldo y fecha
                    CASE 
                        WHEN c.Saldo_Pendiente = 0 THEN 'Pagado'
                        WHEN c.Fecha_Vencimiento < CURDATE() AND c.Saldo_Pendiente > 0 THEN 'Vencido'
                        WHEN c.Saldo_Pendiente > 0 THEN 'Pendiente'
                        ELSE 'Desconocido'
                    END as EstadoCalculado,
                    DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as DiasVencido,
                    DATEDIFF(c.Fecha_Vencimiento, CURDATE()) as DiasRestantes,
                    -- Información adicional de factura de ruta
                    fr.Credito_Contado,
                    fr.Observacion as ObservacionRuta,
                    fr.Saldo_Anterior_Cliente
                FROM cuentas_por_cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN facturacion f ON c.ID_Factura = f.ID_Factura
                LEFT JOIN facturacion_ruta fr ON c.ID_FacturaRuta = fr.ID_FacturaRuta
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado != 'Anulada'  -- Excluir anuladas siempre
            """
            
            params = []
            
            # Aplicar filtros según el parámetro
            if filtro_estado == 'pagados':
                query += " AND c.Saldo_Pendiente = 0"
            elif filtro_estado == 'vencidos':
                query += " AND c.Fecha_Vencimiento < CURDATE() AND c.Saldo_Pendiente > 0"
            elif filtro_estado == 'pendientes':
                query += " AND c.Saldo_Pendiente > 0 AND c.Estado != 'Pagada'"
            # 'todos' no necesita filtro adicional
            
            # Ordenar según el filtro
            if filtro_estado == 'pendientes':
                query += """
                    ORDER BY 
                        CASE 
                            WHEN c.Fecha_Vencimiento >= CURDATE() THEN 1  -- Pendientes normales
                            WHEN c.Fecha_Vencimiento < CURDATE() THEN 2   -- Vencidas
                            ELSE 3
                        END,
                        c.Fecha_Vencimiento ASC,
                        c.Fecha DESC
                """
            elif filtro_estado == 'vencidos':
                query += """
                    ORDER BY 
                        c.Fecha_Vencimiento ASC,
                        DATEDIFF(CURDATE(), c.Fecha_Vencimiento) DESC
                """
            elif filtro_estado == 'pagados':
                query += """
                    ORDER BY 
                        c.Fecha DESC,
                        c.ID_Movimiento DESC
                """
            else:  # 'todos'
                query += """
                    ORDER BY 
                        CASE 
                            WHEN c.Saldo_Pendiente > 0 AND c.Fecha_Vencimiento >= CURDATE() THEN 1
                            WHEN c.Saldo_Pendiente > 0 AND c.Fecha_Vencimiento < CURDATE() THEN 2
                            WHEN c.Saldo_Pendiente = 0 THEN 3
                            ELSE 4
                        END,
                        c.Fecha_Vencimiento ASC,
                        c.Fecha DESC
                """
            
            cursor.execute(query, params)
            cuentas = cursor.fetchall()
            
            # Calcular totales
            total_pendiente = sum(cuenta['Monto_Movimiento'] for cuenta in cuentas)  # Monto original
            total_saldo = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas)      # Saldo actual
            
            # Calcular estadísticas basadas en datos reales
            cuentas_pagadas = [c for c in cuentas if c['Saldo_Pendiente'] == 0]
            cuentas_vencidas = [c for c in cuentas if c['Fecha_Vencimiento'] and 
                                c['Fecha_Vencimiento'] < hoy and 
                                c['Saldo_Pendiente'] > 0]
            cuentas_pendientes = [c for c in cuentas if c['Saldo_Pendiente'] > 0 and 
                                  c['Fecha_Vencimiento'] and 
                                  c['Fecha_Vencimiento'] >= hoy]
            
            # Obtener clientes con saldo pendiente
            cursor.execute("""
                SELECT 
                    c.ID_Cliente, 
                    c.Nombre, 
                    SUM(cc.Saldo_Pendiente) as Saldo_Total 
                FROM clientes c
                JOIN cuentas_por_cobrar cc ON c.ID_Cliente = cc.ID_Cliente
                WHERE cc.Saldo_Pendiente > 0 
                  AND cc.Estado IN ('Pendiente', 'Vencida')
                GROUP BY c.ID_Cliente, c.Nombre
                ORDER BY c.Nombre
            """)
            clientes_pendientes = cursor.fetchall()
            
            return render_template('admin/ventas/cxcobrar/cuentas_cobrar.html',
                                 cuentas=cuentas,
                                 total_pendiente=total_pendiente,
                                 total_saldo=total_saldo,
                                 hoy=hoy,
                                 filtro_actual=filtro_estado,
                                 total_pagadas=len(cuentas_pagadas),
                                 total_vencidas=len(cuentas_vencidas),
                                 total_pendientes=len(cuentas_pendientes),
                                 clientes_pendientes=clientes_pendientes)
    except Exception as e:
        flash(f"Error al cargar cuentas por cobrar: {e}")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/ventas/cxcobrar/registrar-pago/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("REGISTRAR-PAGO-CXC")
def admin_registrar_pago(id_movimiento):
    if request.method == 'POST':
        try:
            # Convertir el monto del formulario a Decimal
            monto_pago_str = request.form['monto']
            monto_pago = Decimal(monto_pago_str)
            
            id_metodo_pago = request.form['metodo_pago']
            comentarios = request.form.get('comentarios', '')
            detalles_metodo = request.form.get('detalles_metodo', '')
            
            # Obtener el nombre del método de pago para validaciones
            metodo_pago_nombre = ''
            with get_db_cursor(True) as cursor:
                cursor.execute("SELECT Nombre FROM metodos_pago WHERE ID_MetodoPago = %s", (id_metodo_pago,))
                resultado = cursor.fetchone()
                if resultado:
                    metodo_pago_nombre = resultado['Nombre'].upper().strip()
                else:
                    flash(" Método de pago no válido")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            # Normalizar nombres para comparación (eliminar acentos y espacios)
            import unicodedata
            def normalize_text(text):
                text = text.upper().strip()
                # Eliminar acentos
                text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
                return text
            
            metodo_normalizado = normalize_text(metodo_pago_nombre)
            
            # Validar detalles según el método de pago
            # EFECTIVO o equivalentes
            if metodo_normalizado in ['EFECTIVO', 'CASH', 'CONTADO', 'EFECTIVO/CONTADO']:
                if detalles_metodo:
                    try:
                        # Extraer cantidad recibida del string
                        import re
                        recibido_match = re.search(r'recibido:\s*([\d,]+(?:\.\d+)?)', detalles_metodo.lower())
                        if recibido_match:
                            # Remover comas y convertir a Decimal
                            recibido_str = recibido_match.group(1).replace(',', '')
                            recibido = Decimal(recibido_str)
                            if recibido < monto_pago:
                                flash(" La cantidad recibida no puede ser menor al monto del pago")
                                return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
                    except Exception as e:
                        print(f"Error procesando detalles de efectivo: {e}")
                        # Continuar con el procesamiento aunque haya error en el parseo
            
            # TRANSFERENCIA o DEPÓSITO
            elif metodo_normalizado in ['TRANSFERENCIA', 'DEPOSITO', 'TRANSFERENCIA BANCARIA', 'DEPOSITO BANCARIO', 'TRANSFERENCIA/DEPOSITO']:
                if not detalles_metodo.strip():
                    flash(" Para pagos por transferencia/depósito debe proporcionar el número de transacción o referencia")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            # CHEQUE
            elif metodo_normalizado in ['CHEQUE', 'CHEQUES']:
                if not detalles_metodo.strip():
                    flash(" Para pagos con cheque debe proporcionar los detalles del cheque (número, banco, etc.)")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            # TARJETA (cualquier tipo)
            elif 'TARJETA' in metodo_normalizado or metodo_normalizado in ['CREDITO', 'DEBITO', 'VISA', 'MASTERCARD']:
                if not detalles_metodo.strip():
                    flash(" Para pagos con tarjeta debe proporcionar los detalles de la transacción (autorización, último dígitos, etc.)")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            with get_db_cursor(True) as cursor:
                # Verificar saldo pendiente y datos de la cuenta
                cursor.execute("""
                    SELECT c.Saldo_Pendiente, c.ID_Cliente, c.Monto_Movimiento, 
                           cl.Nombre as NombreCliente, c.Num_Documento,
                           c.ID_Factura, c.Estado
                    FROM cuentas_por_cobrar c
                    LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                    WHERE c.ID_Movimiento = %s
                """, (id_movimiento,))
                resultado = cursor.fetchone()
                
                if not resultado:
                    flash("Cuenta por cobrar no encontrada")
                    return redirect(url_for('admin.admin_cuentascobrar'))
                
                # Verificar si ya está pagada
                if resultado['Estado'] == 'Pagada':
                    flash(" Esta cuenta ya ha sido pagada completamente")
                    return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
                # Verificar si está anulada
                if resultado['Estado'] == 'Anulada':
                    flash(" No se puede registrar pago en una cuenta anulada")
                    return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
                # Asegurar que saldo_actual sea Decimal
                saldo_actual = Decimal(str(resultado['Saldo_Pendiente']))
                id_cliente = resultado['ID_Cliente']
                
                # Validaciones con Decimal
                if monto_pago <= Decimal('0'):
                    flash(" El monto del pago debe ser mayor a cero")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
                
                if monto_pago > saldo_actual:
                    flash(f" El monto del pago (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
                
                # Registrar pago - convertir a float para la base de datos
                cursor.execute("""
                    INSERT INTO pagos_cuentascobrar 
                    (ID_Movimiento, Monto, ID_MetodoPago, Comentarios, Detalles_Metodo, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_movimiento,
                    float(monto_pago),
                    id_metodo_pago,
                    comentarios,
                    detalles_metodo,
                    current_user.id
                ))
                
                # Obtener el ID del pago recién insertado
                cursor.execute("SELECT LAST_INSERT_ID() as id_pago")
                id_pago = cursor.fetchone()['id_pago']
                print(f"💰 Pago registrado: #{id_pago}")
                
                # Calcular nuevo saldo
                nuevo_saldo = saldo_actual - monto_pago
                
                # Determinar nuevo estado
                if nuevo_saldo == Decimal('0'):
                    nuevo_estado = "Pagada"
                else:
                    # Si hay saldo pendiente, verificar si está vencida
                    cursor.execute("""
                        SELECT Fecha_Vencimiento 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Movimiento = %s
                    """, (id_movimiento,))
                    fecha_vencimiento = cursor.fetchone()['Fecha_Vencimiento']
                    
                    from datetime import date
                    hoy = date.today()
                    
                    if fecha_vencimiento and fecha_vencimiento < hoy:
                        nuevo_estado = "Vencida"
                    else:
                        nuevo_estado = "Pendiente"
                
                # Actualizar saldo pendiente Y estado en la tabla cuentas_por_cobrar
                cursor.execute("""
                    UPDATE cuentas_por_cobrar 
                    SET Saldo_Pendiente = %s,
                        Estado = %s
                    WHERE ID_Movimiento = %s
                """, (float(nuevo_saldo), nuevo_estado, id_movimiento))
                
                # ==============================================
                # ACTUALIZAR SALDO PENDIENTE CONSOLIDADO DEL CLIENTE
                # ==============================================
                # Primero, obtener el saldo pendiente actual del cliente
                cursor.execute("""
                    SELECT Saldo_Pendiente_Total 
                    FROM clientes 
                    WHERE ID_Cliente = %s
                """, (id_cliente,))
                cliente_data = cursor.fetchone()
                
                if cliente_data:
                    saldo_cliente_actual = Decimal(str(cliente_data['Saldo_Pendiente_Total']))
                    nuevo_saldo_cliente = saldo_cliente_actual - monto_pago
                    
                    # Actualizar el saldo pendiente total del cliente
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = %s,
                            Fecha_Ultimo_Pago = NOW()
                        WHERE ID_Cliente = %s
                    """, (float(nuevo_saldo_cliente), id_cliente))
                    
                    print(f"💰 Saldo del cliente #{id_cliente} actualizado: {float(saldo_cliente_actual):,.2f} → {float(nuevo_saldo_cliente):,.2f}")
                    
                    # Verificar si el cliente quedó con saldo cero
                    if nuevo_saldo_cliente == Decimal('0'):
                        print(f"✅ Cliente #{id_cliente} ha cancelado todas sus deudas")
                        flash(f"🎉 ¡Excelente! El cliente {resultado['NombreCliente']} ha cancelado TODAS sus deudas pendientes.")
                else:
                    print(f"⚠️ Cliente #{id_cliente} no encontrado al actualizar saldo pendiente total")
                
                # Verificar si el método de pago es EFECTIVO y registrar en caja
                if metodo_normalizado in ['EFECTIVO', 'CASH', 'CONTADO', 'EFECTIVO/CONTADO']:
                    nombre_cliente = resultado['NombreCliente'] if resultado['NombreCliente'] else f'Cliente ID: {id_cliente}'
                    num_documento = resultado['Num_Documento'] if resultado['Num_Documento'] else f'CXC-{id_movimiento:05d}'
                    
                    cursor.execute("""
                        INSERT INTO caja_movimientos (
                            Fecha, Tipo_Movimiento, Descripcion, Monto, 
                            ID_Pagos_cxc, ID_Usuario, Referencia_Documento
                        )
                        VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                    """, (
                        f'Pago CxC - {nombre_cliente} - Documento: {num_documento} - {comentarios if comentarios else "Pago registrado"}',
                        float(monto_pago),
                        id_pago,
                        current_user.id,
                        f'PAGO-CXC-{id_pago:05d}'
                    ))
                    print(f"💰 Entrada en caja registrada por pago en efectivo: C${float(monto_pago):,.2f}")
                
                # Guardar detalles del método de pago en comentarios adicionales si existe
                if detalles_metodo.strip():
                    cursor.execute("""
                        UPDATE pagos_cuentascobrar 
                        SET Comentarios = CONCAT(COALESCE(Comentarios, ''), 
                            CASE WHEN COALESCE(Comentarios, '') != '' THEN ' | ' ELSE '' END,
                            'Detalles: ', %s)
                        WHERE ID_Pago = %s
                    """, (detalles_metodo[:200], id_pago))
                
                # Mensaje final según el estado
                if nuevo_estado == "Pagada":
                    flash(f"✅ PAGO COMPLETO REGISTRADO. La cuenta ha sido marcada como PAGADA. Monto: C${float(monto_pago):,.2f}")
                    if detalles_metodo:
                        flash(f"📝 Detalles del pago: {detalles_metodo}")
                else:
                    flash(f"✅ Pago de ${float(monto_pago):,.2f} registrado exitosamente. Saldo restante de esta cuenta: C${float(nuevo_saldo):,.2f} - Estado: {nuevo_estado}")
                    if detalles_metodo:
                        flash(f"📝 Detalles del pago: {detalles_metodo}")
                    
                return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
        except ValueError as e:
            flash(f" Error: El monto ingresado no es válido: {e}")
            return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
        except Exception as e:
            flash(f" Error al registrar pago: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
    
    # GET: Cargar datos para el formulario
    try:
        with get_db_cursor(True) as cursor:
            # Datos de la cuenta con estado calculado
            cursor.execute("""
                SELECT 
                    c.*, 
                    cl.Nombre as NombreCliente,
                    cl.Telefono as TelefonoCliente,
                    cl.Direccion as DireccionCliente,
                    cl.RUC_CEDULA,
                    cl.Saldo_Pendiente_Total as Saldo_Total_Cliente,
                    e.Nombre_Empresa
                FROM cuentas_por_cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Movimiento = %s
            """, (id_movimiento,))
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash("Cuenta por cobrar no encontrada")
                return redirect(url_for('admin.admin_cuentascobrar'))
            
            # Verificar si ya está pagada
            if cuenta['Estado'] == 'Pagada' and cuenta['Saldo_Pendiente'] == 0:
                flash("⚠️ Esta cuenta ya está completamente pagada")
                return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
            
            # Verificar si está anulada
            if cuenta['Estado'] == 'Anulada':
                flash("⚠️ Esta cuenta está anulada, no se pueden registrar pagos")
                return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
            
            # Convertir Decimal a float para el template
            if cuenta['Saldo_Pendiente']:
                cuenta['Saldo_Pendiente'] = float(cuenta['Saldo_Pendiente'])
            if cuenta['Monto_Movimiento']:
                cuenta['Monto_Movimiento'] = float(cuenta['Monto_Movimiento'])
            if cuenta.get('Saldo_Total_Cliente'):
                cuenta['Saldo_Total_Cliente'] = float(cuenta['Saldo_Total_Cliente'])
            
            # Métodos de pago disponibles
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
            metodos_pago = cursor.fetchall()
            
            # Pasar la fecha actual para comparar vencimientos
            from datetime import datetime
            today = datetime.now().date()
            
            return render_template('admin/ventas/cxcobrar/registrar_pago.html',
                                 cuenta=cuenta, 
                                 metodos_pago=metodos_pago,
                                 today=today)
                                 
    except Exception as e:
        flash(f" Error al cargar formulario de pago: {e}")
        import traceback
        print(traceback.format_exc())
        return redirect(url_for('admin.admin_cuentascobrar'))


@admin_bp.route('/admin/ventas/cxcobrar/detalle/<int:id_movimiento>')
@admin_required
@bitacora_decorator("DETALLE-CUENTA-COBRAR")
def admin_detalle_cuentacobrar(id_movimiento):
    try:
        with get_db_cursor(True) as cursor:
            # CONSULTA PRINCIPAL - TRAER FECHAS SIN FORMATEAR
            cursor.execute("""
                SELECT 
                    c.ID_Movimiento,
                    c.Fecha,  -- Fecha sin formatear
                    c.ID_Cliente,
                    c.Num_Documento,
                    c.Observacion,
                    c.Fecha_Vencimiento,  -- Fecha sin formatear
                    c.Tipo_Movimiento,
                    c.Monto_Movimiento,
                    c.ID_Empresa,
                    COALESCE(c.Saldo_Pendiente, 0) as Saldo_Pendiente,
                    c.ID_Factura,
                    c.ID_Usuario_Creacion,
                    COALESCE(cl.Nombre, 'Cliente no encontrado') as NombreCliente,
                    COALESCE(cl.RUC_CEDULA, 'N/A') as CedulaCliente,
                    COALESCE(cl.Telefono, 'N/A') as TelefonoCliente,
                    COALESCE(cl.Direccion, 'N/A') as DireccionCliente,
                    COALESCE(e.Nombre_Empresa, 'N/A') as Nombre_Empresa,
                    CASE 
                        WHEN f.ID_Factura IS NOT NULL THEN CONCAT('FAC-', LPAD(f.ID_Factura, 5, '0'))
                        ELSE 'N/A'
                    END as NumeroFactura,
                    f.Fecha as Fecha_Factura,  -- Fecha sin formatear
                    COALESCE(u.NombreUsuario, 'N/A') as UsuarioCreacion,
                    -- Estado de la cuenta
                    CASE 
                        WHEN COALESCE(c.Saldo_Pendiente, 0) = 0 THEN 'Cancelado'
                        WHEN c.Fecha_Vencimiento < CURDATE() AND COALESCE(c.Saldo_Pendiente, 0) > 0 THEN 'Vencido'
                        ELSE 'Pendiente'
                    END as Estado,
                    -- Días vencidos
                    CASE 
                        WHEN c.Fecha_Vencimiento IS NOT NULL 
                             AND c.Fecha_Vencimiento < CURDATE() 
                             AND COALESCE(c.Saldo_Pendiente, 0) > 0 
                        THEN DATEDIFF(CURDATE(), c.Fecha_Vencimiento)
                        ELSE 0
                    END as DiasVencido
                FROM cuentas_por_cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                LEFT JOIN facturacion f ON c.ID_Factura = f.ID_Factura
                LEFT JOIN usuarios u ON c.ID_Usuario_Creacion = u.ID_Usuario
                WHERE c.ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta_raw = cursor.fetchone()
            
            if not cuenta_raw:
                flash(" Error: Cuenta por cobrar no encontrada", "error")
                return redirect(url_for('admin.admin_cuentascobrar'))
            
            # FUNCIÓN PARA FORMATEAR FECHAS EN PYTHON (MÁS CONFIABLE)
            def formatear_fecha(fecha_input):
                if fecha_input is None:
                    return 'No especificada'
                
                try:
                    # Si es datetime de MySQL
                    if hasattr(fecha_input, 'strftime'):
                        return fecha_input.strftime('%d/%m/%Y')
                    
                    # Si es string
                    if isinstance(fecha_input, str):
                        # Intentar diferentes formatos
                        formatos = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y']
                        for formato in formatos:
                            try:
                                dt = datetime.strptime(fecha_input, formato)
                                return dt.strftime('%d/%m/%Y')
                            except ValueError:
                                continue
                    
                    # Si no se pudo formatear, devolver como string
                    return str(fecha_input)
                except Exception as e:
                    print(f"Error formateando fecha {fecha_input}: {e}")
                    return 'Formato inválido'
            
            # FUNCIÓN PARA FORMATEAR FECHAS EN FORMATO ISO (YYYY-MM-DD) PARA FORMULARIOS
            def formatear_fecha_iso(fecha_input):
                if fecha_input is None:
                    return ''
                
                try:
                    # Si es datetime de MySQL
                    if hasattr(fecha_input, 'strftime'):
                        return fecha_input.strftime('%Y-%m-%d')
                    
                    # Si es string
                    if isinstance(fecha_input, str):
                        # Intentar diferentes formatos
                        formatos = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y']
                        for formato in formatos:
                            try:
                                dt = datetime.strptime(fecha_input, formato)
                                return dt.strftime('%Y-%m-%d')
                            except ValueError:
                                continue
                    
                    # Si no se pudo formatear, devolver vacío
                    return ''
                except Exception as e:
                    print(f"Error formateando fecha ISO {fecha_input}: {e}")
                    return ''
            
            # CONVERTIR A DICCIONARIO Y AGREGAR FECHAS FORMATEADAS
            cuenta = dict(cuenta_raw)
            
            # Agregar campos formateados para display
            cuenta['Fecha_Formateada'] = formatear_fecha(cuenta['Fecha'])
            cuenta['Fecha_Vencimiento_Formateada'] = formatear_fecha(cuenta['Fecha_Vencimiento'])
            cuenta['FechaFactura_Formateada'] = formatear_fecha(cuenta['Fecha_Factura'])
            
            # Agregar campos ISO para formularios HTML (type="date")
            cuenta['Fecha_ISO'] = formatear_fecha_iso(cuenta['Fecha'])
            cuenta['Fecha_Vencimiento_ISO'] = formatear_fecha_iso(cuenta['Fecha_Vencimiento'])
            cuenta['FechaFactura_ISO'] = formatear_fecha_iso(cuenta['Fecha_Factura'])
            
            # DEBUG: Verificar datos
            print("=" * 60)
            print("DEBUG - INFORMACIÓN DE FECHAS:")
            print(f"ID Movimiento: {cuenta['ID_Movimiento']}")
            print(f"Fecha Original (DB): {cuenta['Fecha']} - Tipo: {type(cuenta['Fecha'])}")
            print(f"Fecha Formateada: {cuenta['Fecha_Formateada']}")
            print(f"Fecha Vencimiento Original: {cuenta['Fecha_Vencimiento']}")
            print(f"Fecha Vencimiento Formateada: {cuenta['Fecha_Vencimiento_Formateada']}")
            print(f"Fecha Factura Original: {cuenta['Fecha_Factura']}")
            print(f"Fecha Factura Formateada: {cuenta['FechaFactura_Formateada']}")
            print("=" * 60)
            
            # ==================================================
            # HISTORIAL UNIFICADO (PAGOS + ABONOS)
            # ==================================================
            cursor.execute("""
                SELECT 
                    'pago' as tipo_registro,
                    p.ID_Pago as id_registro,
                    p.ID_Movimiento,
                    p.Monto,
                    p.ID_MetodoPago,
                    p.Comentarios as Descripcion,
                    p.Detalles_Metodo,
                    p.ID_Usuario_Creacion,
                    p.Fecha,
                    COALESCE(mp.Nombre, 'Método no disponible') as MetodoPago,
                    COALESCE(u.NombreUsuario, 'Usuario no disponible') as UsuarioRegistro,
                    NULL as Saldo_Anterior,
                    NULL as Saldo_Nuevo,
                    NULL as ID_Movimiento_Caja,
                    NULL as ID_Asignacion,
                    NULL as ID_Cliente_Abono
                FROM pagos_cuentascobrar p
                LEFT JOIN metodos_pago mp ON p.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
                WHERE p.ID_Movimiento = %s
                
                UNION ALL
                
                SELECT 
                    'abono' as tipo_registro,
                    a.ID_Detalle as id_registro,
                    a.ID_CuentaCobrar as ID_Movimiento,
                    a.Monto_Aplicado as Monto,
                    NULL as ID_MetodoPago,
                    CONCAT('Abono registrado en caja/ruta. ID Mov Caja: ', COALESCE(a.ID_Movimiento_Caja, 0)) as Descripcion,
                    NULL as Detalles_Metodo,
                    a.ID_Usuario as ID_Usuario_Creacion,
                    a.Fecha,
                    'Abono en ruta' as MetodoPago,
                    COALESCE(u2.NombreUsuario, 'Usuario no disponible') as UsuarioRegistro,
                    a.Saldo_Anterior,
                    a.Saldo_Nuevo,
                    a.ID_Movimiento_Caja,
                    a.ID_Asignacion,
                    a.ID_Cliente
                FROM abonos_detalle a
                LEFT JOIN usuarios u2 ON a.ID_Usuario = u2.ID_Usuario
                WHERE a.ID_CuentaCobrar = %s
                
                ORDER BY Fecha DESC
            """, (id_movimiento, id_movimiento))
            
            historial_raw = cursor.fetchall()
            
            # FORMATEAR FECHAS Y PROCESAR HISTORIAL UNIFICADO
            historial = []
            for registro in historial_raw:
                registro_dict = dict(registro)
                fecha_reg = registro_dict['Fecha']
                
                # Formatear fecha
                if fecha_reg:
                    if hasattr(fecha_reg, 'strftime'):
                        registro_dict['FechaFormateada'] = fecha_reg.strftime('%d/%m/%Y %H:%M')
                        registro_dict['FechaSolo'] = fecha_reg.strftime('%d/%m/%Y')
                    else:
                        registro_dict['FechaFormateada'] = formatear_fecha(fecha_reg) + ' 00:00'
                        registro_dict['FechaSolo'] = formatear_fecha(fecha_reg)
                else:
                    registro_dict['FechaFormateada'] = 'Fecha no disponible'
                    registro_dict['FechaSolo'] = 'N/A'
                
                # Configurar tipo de registro para mostrar en template
                if registro_dict['tipo_registro'] == 'abono':
                    registro_dict['TipoDisplay'] = '💵 Abono en ruta'
                    registro_dict['MontoFormateado'] = f"{float(registro_dict['Monto']):,.2f}"
                    registro_dict['Icono'] = 'bi-cash-stack'
                    registro_dict['ColorBadge'] = 'success'
                else:
                    registro_dict['TipoDisplay'] = '💰 Pago registrado'
                    registro_dict['MontoFormateado'] = f"{float(registro_dict['Monto']):,.2f}"
                    registro_dict['Icono'] = 'bi-credit-card'
                    registro_dict['ColorBadge'] = 'primary'
                
                historial.append(registro_dict)
            
            # ==================================================
            # CÁLCULOS FINANCIEROS CON DATOS UNIFICADOS
            # ==================================================
            monto_movimiento = Decimal(str(cuenta['Monto_Movimiento'])) if cuenta['Monto_Movimiento'] else Decimal('0')
            saldo_pendiente = Decimal(str(cuenta['Saldo_Pendiente'])) if cuenta['Saldo_Pendiente'] else Decimal('0')
            
            # Sumar tanto pagos como abonos
            total_pagado = sum(Decimal(str(reg['Monto'])) for reg in historial) if historial else Decimal('0')
            
            # Validar consistencia
            saldo_teorico = monto_movimiento - total_pagado
            diferencia = abs(saldo_pendiente - saldo_teorico)
            tiene_inconsistencia = diferencia > Decimal('0.01')
            
            # Calcular estadísticas
            total_abonado = monto_movimiento - saldo_pendiente
            porcentaje_pagado = (total_abonado / monto_movimiento * 100) if monto_movimiento > 0 else 0
            
            # Obtener primer y último pago/abono
            primer_registro = historial[-1] if historial and len(historial) > 0 else None
            ultimo_registro = historial[0] if historial and len(historial) > 0 else None
            
            # Separar pagos y abonos para estadísticas específicas (opcional)
            solo_pagos = [reg for reg in historial if reg['tipo_registro'] == 'pago']
            solo_abonos = [reg for reg in historial if reg['tipo_registro'] == 'abono']
            
            total_pagos = sum(Decimal(str(reg['Monto'])) for reg in solo_pagos) if solo_pagos else Decimal('0')
            total_abonos = sum(Decimal(str(reg['Monto'])) for reg in solo_abonos) if solo_abonos else Decimal('0')
            
            # Preparar datos para template
            datos_template = {
                'cuenta': cuenta,
                'historial': historial,  # NUEVO: historial unificado
                'pagos': solo_pagos,  # Mantenido por compatibilidad
                'abonos': solo_abonos,  # NUEVO: solo abonos
                'total_pagado': float(total_pagado),
                'total_abonado': float(total_abonado),
                'total_pagos': float(total_pagos),
                'total_abonos': float(total_abonos),
                'porcentaje_pagado': round(float(porcentaje_pagado), 2),
                'tiene_inconsistencia': tiene_inconsistencia,
                'diferencia': float(diferencia),
                'primer_registro': primer_registro,
                'ultimo_registro': ultimo_registro,
                'primer_pago': primer_registro if primer_registro and primer_registro['tipo_registro'] == 'pago' else None,
                'ultimo_pago': ultimo_registro if ultimo_registro and ultimo_registro['tipo_registro'] == 'pago' else None,
                'monto_movimiento_formateado': float(monto_movimiento),
                'saldo_pendiente_formateado': float(saldo_pendiente),
                'saldo_teorico': float(saldo_teorico),
                'cantidad_pagos': len(solo_pagos),
                'cantidad_abonos': len(solo_abonos),
                'cantidad_total_movimientos': len(historial)
            }
            
            return render_template('admin/ventas/cxcobrar/detalle_cuenta.html', **datos_template)
                                 
    except Exception as e:
        flash(f" Error al cargar detalle de cuenta: {str(e)}", "error")
        traceback.print_exc()
        return redirect(url_for('admin.admin_cuentascobrar'))


@admin_bp.route('/api/facturas_pendientes_cliente/<int:id_cliente>', methods=['GET'])
@admin_or_bodega_required
def api_facturas_pendientes_cliente(id_cliente):
    """API para obtener las facturas pendientes de un cliente"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cxc.Num_Documento as documento,
                    DATE_FORMAT(cxc.Fecha, '%d/%m/%Y') as fecha,
                    DATE_FORMAT(cxc.Fecha_Vencimiento, '%d/%m/%Y') as vencimiento,
                    cxc.Monto_Movimiento as monto_original,
                    cxc.Saldo_Pendiente as saldo,
                    DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as dias_vencido
                FROM cuentas_por_cobrar cxc
                INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
                WHERE cxc.ID_Cliente = %s 
                AND c.ID_Empresa = %s
                AND cxc.Estado IN ('Pendiente', 'Vencida')
                AND cxc.Saldo_Pendiente > 0.01
                AND cxc.ID_Factura IS NOT NULL
                ORDER BY cxc.Fecha_Vencimiento ASC, cxc.Fecha ASC
            """, (id_cliente, id_empresa))
            
            facturas = cursor.fetchall()
            
            facturas_list = []
            for f in facturas:
                facturas_list.append({
                    'documento': f['documento'],
                    'fecha': f['fecha'],
                    'vencimiento': f['vencimiento'],
                    'monto_original': float(f['monto_original']),
                    'saldo': float(f['saldo']),
                    'dias_vencido': f['dias_vencido'] if f['dias_vencido'] else 0
                })
            
            return jsonify({
                'success': True,
                'facturas': facturas_list
            })
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/ventas/productos/cliente/<int:cliente_id>', methods=['GET'])
@admin_or_bodega_required
def api_productos_por_cliente(cliente_id):
    """API para obtener productos visibles para un cliente específico con los 3 tipos de precio"""
    
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        with get_db_cursor() as cursor:
            # 1. Obtener tipo y perfil del cliente
            cursor.execute("""
                SELECT tipo_cliente, perfil_cliente, Nombre 
                FROM clientes 
                WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
            """, (cliente_id,))
            
            cliente = cursor.fetchone()
            if not cliente:
                return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404
            
            tipo_cliente = cliente['tipo_cliente']
            perfil_cliente = cliente['perfil_cliente']
            
            # 2. Obtener productos visibles para ese tipo de cliente con los 3 precios
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    COALESCE(ib.Existencias, 0) as Existencias,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    p.ID_Categoria,
                    c.Descripcion as Categoria,
                    um.Descripcion as Unidad_Medida
                FROM productos p
                INNER JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                INNER JOIN config_visibilidad_categorias cfg 
                    ON c.ID_Categoria = cfg.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE cfg.tipo_cliente = %s
                  AND cfg.visible = 1
                  AND p.Estado = 'activo' 
                  AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                  AND COALESCE(ib.Existencias, 0) > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_bodega, tipo_cliente, id_empresa))
            
            productos = cursor.fetchall()
            
            # Contar productos por categoría
            cursor.execute("""
                SELECT c.Descripcion as categoria, COUNT(p.ID_Producto) as cantidad
                FROM productos p
                INNER JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                INNER JOIN config_visibilidad_categorias cfg 
                    ON c.ID_Categoria = cfg.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE cfg.tipo_cliente = %s
                  AND cfg.visible = 1
                  AND p.Estado = 'activo' 
                  AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                  AND COALESCE(ib.Existencias, 0) > 0
                GROUP BY c.ID_Categoria, c.Descripcion
            """, (id_bodega, tipo_cliente, id_empresa))
            
            categorias_count = cursor.fetchall()
            
            # Calcular el precio según el perfil para cada producto (para referencia)
            productos_con_precio_segun_perfil = []
            for producto in productos:
                producto_dict = dict(producto)
                # Determinar qué precio usar según el perfil
                if perfil_cliente == 'Ruta':
                    precio_aplicado = producto['Precio_Ruta'] or 0
                elif perfil_cliente == 'Mayorista':
                    precio_aplicado = producto['Precio_Mayorista'] or 0
                elif perfil_cliente == 'Mercado':
                    precio_aplicado = producto['Precio_Mercado'] or 0
                else:  # Especial u otros
                    precio_aplicado = producto['Precio_Mercado'] or 0
                
                producto_dict['Precio_Aplicado'] = float(precio_aplicado)
                producto_dict['Perfil_Aplicado'] = perfil_cliente
                productos_con_precio_segun_perfil.append(producto_dict)
            
            return jsonify({
                'success': True,
                'tipo_cliente': tipo_cliente,
                'perfil_cliente': perfil_cliente,
                'productos': productos_con_precio_segun_perfil,
                'categorias': categorias_count,
                'total': len(productos)
            })
            
    except Exception as e:
        print(f" Error en API productos por cliente: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/productos-por-cliente/<int:cliente_id>')
@login_required
def productos_por_cliente(cliente_id):
    """Obtener productos visibles para un cliente específico"""
    
    empresa_id = session.get('empresa_id',1)
    
    with get_db_cursor() as cursor:
        # 1. Obtener tipo de cliente
        cursor.execute("""
            SELECT tipo_cliente 
            FROM clientes 
            WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
        """, (cliente_id,))
        
        cliente = cursor.fetchone()
        if not cliente:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        tipo_cliente = cliente['tipo_cliente']
        
        # 2. Obtener productos visibles para ese tipo
        cursor.execute("""
            SELECT p.*, c.Descripcion as categoria
            FROM productos p
            INNER JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
            INNER JOIN config_visibilidad_categorias cfg 
                ON cat.ID_Categoria = cfg.ID_Categoria
            WHERE cfg.tipo_cliente = %s
              AND cfg.visible = 1
              AND p.Estado = 'activo'
              AND p.ID_Empresa = %s
            ORDER BY p.Descripcion
        """, (tipo_cliente, empresa_id))
        
        productos = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'tipo_cliente': tipo_cliente,
            'productos': productos
        })



@admin_bp.route('/admin/ventas/cxcobrar/abono', methods=['GET', 'POST'])
@admin_required
def admin_crear_abono():
    """Renderiza y procesa el formulario para crear un registro en abonos_general."""
    if request.method == 'POST':
        try:
            id_usuario = current_user.id
            id_cliente = request.form.get('id_cliente')
            monto_aplicado = request.form.get('monto_aplicado')
            id_metodo_pago = request.form.get('id_metodo_pago') or None

            monto_aplicado = float(monto_aplicado)
            if monto_aplicado <= 0:
                # Cambiado a JSON para mantener la consistencia en el Frontend
                return jsonify({'success': False, 'error': 'El monto del abono debe ser mayor a 0'}), 400

            if id_metodo_pago is not None:
                id_metodo_pago = int(id_metodo_pago)

            # Inicializamos variables para evitar UnboundLocalError
            caja_movimientos_json = None 
            id_movimiento_caja = None
            nuevo_saldo = None

            # TODO el proceso de DB envuelto en el bloque WITH
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                SELECT ID_MetodoPago, Nombre
                FROM metodos_pago
                WHERE ID_MetodoPago = %s
                """, (id_metodo_pago,))
                metodo = cursor.fetchone()

                if not metodo:
                    return jsonify({'success': False, 'error': 'Método de pago no válido'}), 400

                nombre_metodo = metodo['Nombre']

                # Facturas pendientes
                cursor.execute("""
                SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente,
                    Fecha_Vencimiento,
                    CASE
                        WHEN Fecha_Vencimiento < CURDATE() THEN 1
                        ELSE 2
                    END as Prioridad
                FROM cuentas_por_cobrar
                WHERE ID_Cliente = %s 
                    AND Estado IN ('Pendiente','Vencida')
                    AND Saldo_Pendiente > 0
                ORDER BY Prioridad ASC, Fecha_Vencimiento ASC
                """,(int(id_cliente),))

                facturas = cursor.fetchall()

                if not facturas:
                    return jsonify({'success': False, 'error': 'No hay facturas pendientes para este cliente'}), 400
            
                if id_metodo_pago == 1:
                    cursor.execute("""
                    SELECT COALESCE(SUM(CASE
                        WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto
                        ELSE -Monto
                    END), 0) as Saldo_Actual
                    FROM caja_movimientos
                    WHERE DATE(Fecha) = CURDATE()
                    AND Estado = 'ACTIVO'
                    """)

                    saldo_actual_caja = cursor.fetchone()
                    saldo_actual = float(saldo_actual_caja['Saldo_Actual'] if saldo_actual_caja else 0)
                    nuevo_saldo = saldo_actual + monto_aplicado

                    concepto_caja = f"Abono de Cliente - {nombre_metodo} - Monto: C${monto_aplicado:.2f}"

                    cursor.execute("""
                    INSERT INTO caja_movimientos 
                    (Fecha, Tipo_Movimiento, Descripcion, Monto, ID_Usuario, Estado, Referencia_Documento)
                    VALUES (NOW(), 'ENTRADA', %s, %s, %s, 'ACTIVO', %s)
                    """, (
                        concepto_caja,
                        monto_aplicado,
                        id_usuario,
                        f"Abono Cxc Cliente {id_cliente}"
                    ))

                    id_movimiento_caja = cursor.lastrowid
                    # La columna caja_movimientos es varchar(100), no podemos guardar un JSON largo.
                    # Guardaremos una referencia corta al ID del movimiento de caja.
                    caja_mov_ref = f"ADMIN-{id_movimiento_caja}" if id_movimiento_caja else "SIN_CAJA"

                # Distribución del abono entre las facturas
                monto_restante = monto_aplicado
                detalle_abono = []
                monto_aplicado_total = 0  # Usar una nueva variable en vez de sobreescribir 'monto_aplicado'
                ultimo_id_abono = None
                facturas_canceladas = []

                for factura in facturas: 
                    if monto_restante <= 0:
                        break

                    saldo_factura = float(factura['Saldo_Pendiente'])
                    monto_aplicar = min(monto_restante, saldo_factura)
                    nuevo_saldo_factura = saldo_factura - monto_aplicar
                    nuevo_estado = 'Pagada' if nuevo_saldo_factura == 0 else 'Pendiente'
                
                    if nuevo_saldo_factura <= 0.01:
                        facturas_canceladas.append({
                            'id_movimiento': factura['ID_Movimiento'],
                            'num_documento': factura['Num_Documento'],
                            'monto_pagado': monto_aplicar
                        })
                
                    cursor.execute("""
                    UPDATE cuentas_por_cobrar
                    SET Saldo_Pendiente = %s,
                        Estado = %s
                    WHERE ID_Movimiento = %s
                    """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))

                    saldo_anterior = float(factura['Saldo_Pendiente'])
                    saldo_nuevo = float(nuevo_saldo_factura)
                
                    cursor.execute("""
                        INSERT INTO abonos_general
                        (ID_Usuario, ID_Cliente, ID_CuentaCobrar, Monto_Aplicado, 
                        Saldo_Anterior, Saldo_Nuevo, Fecha, ID_MetodoPago, caja_movimientos)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                    """, (
                        id_usuario,
                        id_cliente,
                        factura['ID_Movimiento'],
                        monto_aplicar,
                        saldo_anterior,
                        saldo_nuevo,
                        id_metodo_pago,
                        caja_mov_ref
                    ))
                
                    detalle_abono.append({
                        'factura_id': factura['ID_Movimiento'],
                        'num_documento': factura['Num_Documento'],
                        'monto_aplicado': monto_aplicar,
                        'saldo_anterior': saldo_anterior,
                        'saldo_nuevo': saldo_nuevo
                    })
                
                    monto_restante -= monto_aplicar
                    monto_aplicado_total += monto_aplicar
                    ultimo_id_abono = cursor.lastrowid

                # Actualizar saldo del cliente
                cursor.execute("""
                UPDATE clientes
                SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total,0) - %s),
                    Fecha_ultimo_pago = NOW()
                WHERE ID_Cliente = %s
                """, (monto_aplicado_total, int(id_cliente)))

            # Preparamos la respuesta final fuera del WITH una vez cerrado y "commiteado"
            id_abono_para_recibo = ultimo_id_abono if ultimo_id_abono else (id_movimiento_caja if id_movimiento_caja else 0)

            respuesta ={
                'success': True,
                'mensaje': f'Abono de C${monto_aplicado_total:,.2f} registrado correctamente',
                'id_abono': id_abono_para_recibo,
                'monto_aplicado': monto_aplicado_total,
                'detalle': detalle_abono,
                'facturas_canceladas': facturas_canceladas
            }

            if id_metodo_pago == 1:
                respuesta['nuevo_saldo_caja'] = nuevo_saldo

            return jsonify(respuesta)

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f' Error al insertar abono: {e}')
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
            
    # Respuesta por si el método es GET
    try:
        with get_db_cursor(True) as cursor:
            # Obtener clientes con saldo pendiente
            cursor.execute("""
                SELECT ID_Cliente, Nombre, Saldo_Pendiente_Total as Saldo_Pendiente
                FROM clientes
                WHERE Estado = 'ACTIVO' AND Saldo_Pendiente_Total > 0
                ORDER BY Nombre
            """)
            clientes = cursor.fetchall()
            
            # Obtener métodos de pago
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
            metodos_pago = cursor.fetchall()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            return render_template('admin/ventas/cxcobrar/cxcobrar_abono.html',
                                 clientes=clientes,
                                 metodos_pago=metodos_pago,
                                 today=today)
    except Exception as e:
        print(f' Error al cargar formulario de abono: {e}')
        flash('Error al cargar el formulario', 'danger')
        return redirect(url_for('admin.admin_cuentascobrar'))