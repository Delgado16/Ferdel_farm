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

@admin_bp.route('/admin/ventas/anticipos/clientes-anticipos')
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS")   
def admin_clientes_anticipos():
    try:
        id_empresa = session.get('id_empresa', 1)
        if not id_empresa:
            flash('No se encontró información de la empresa', 'error')
            return redirect(url_for('admin_dashboard'))
            
        with get_db_cursor(True) as cursor:
            # Como anticipos_clientes no tiene ID_Empresa, debemos unir con clientes
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.Fecha_Anticipo as Fecha,
                    a.Monto_Pagado as Monto,
                    a.Saldo_Restante,
                    a.Cantidad_Cajas,
                    a.Cajas_Consumidas,
                    a.Estado,
                    a.Notas as Observacion,
                    c.Nombre as NombreCliente,
                    c.RUC_CEDULA as RUCCliente,
                    c.ID_Empresa,
                    c.Saldo_Anticipos,
                    c.Anticipo_Activo,
                    c.Limite_Anticipo_Cajas,
                    c.Cajas_Consumidas_Anticipo,
                    p.Descripcion as NombreProducto,
                    p.COD_Producto,
                    e.Nombre_Empresa,
                    DATEDIFF(NOW(), a.Fecha_Anticipo) as Dias_Transcurridos
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Empresa = %s
                ORDER BY a.Fecha_Anticipo DESC, a.ID_Anticipo DESC
                LIMIT 10
            """, (id_empresa,))
            anticipos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/clientes_anticipos.html', 
                                 anticipos=anticipos)
    except Exception as e:
        print(f" Error obteniendo anticipos de clientes: {str(e)}")
        traceback.print_exc()
        flash('Error interno al obtener anticipos de clientes', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/ventas/anticipos/nuevo', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-NUEVO")
def admin_anticipo_nuevo():
    id_empresa = session.get('id_empresa', 1)
    if not id_empresa:
        flash('No se encontró información de la empresa', 'error')
        return redirect(url_for('admin.admin_dashboard'))
    
    if request.method == 'POST':
        try:
            id_cliente = request.form.get('id_cliente')
            id_producto = request.form.get('id_producto')
            cantidad_cajas = int(request.form.get('cantidad_cajas', 0))
            monto_pagado = float(request.form.get('monto_pagado', 0))
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            notas = request.form.get('notas', '')
            precio_especial = request.form.get('precio_especial', '').strip()
            calcular_precio_auto = request.form.get('calcular_precio_auto')
            
            # Validaciones
            if not id_cliente or not id_producto:
                flash('Cliente y producto son requeridos', 'error')
                return redirect(url_for('admin.admin_anticipo_nuevo'))
            
            if cantidad_cajas <= 0:
                flash('La cantidad de cajas debe ser mayor a 0', 'error')
                return redirect(url_for('admin.admin_anticipo_nuevo'))
            
            if monto_pagado <= 0:
                flash('El monto pagado debe ser mayor a 0', 'error')
                return redirect(url_for('admin.admin_anticipo_nuevo'))
            
            with get_db_cursor() as cursor:
                # Verificar que el cliente pertenece a la empresa
                cursor.execute("""
                    SELECT ID_Cliente, perfil_cliente, tipo_cliente, Anticipo_Activo
                    FROM clientes 
                    WHERE ID_Cliente = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'
                """, (id_cliente, id_empresa))
                
                cliente = cursor.fetchone()
                if not cliente:
                    flash('Cliente no encontrado o no pertenece a su empresa', 'error')
                    return redirect(url_for('admin.admin_anticipo_nuevo'))
                
                # Obtener información del producto (solo para descripción, NO para el precio)
                cursor.execute("""
                    SELECT 
                        p.ID_Producto,
                        p.Descripcion,
                        p.COD_Producto
                    FROM productos p
                    WHERE p.ID_Producto = %s AND p.ID_Empresa = %s AND p.Estado = 'activo'
                """, (id_producto, id_empresa))
                
                producto = cursor.fetchone()
                if not producto:
                    flash('Producto no encontrado o no pertenece a su empresa', 'error')
                    return redirect(url_for('admin.admin_anticipo_nuevo'))
                
                # Determinar precio unitario según el perfil del cliente
                precio_unitario = 0
                perfil_cliente = cliente['perfil_cliente']
                
                # LÓGICA PRINCIPAL: Según el perfil del cliente
                if perfil_cliente == 'Especial':
                    # CLIENTE PERFIL ESPECIAL: El usuario ingresa el precio
                    if calcular_precio_auto == 'on':
                        # Calcular precio automáticamente: monto_pagado / cantidad_cajas
                        precio_unitario = monto_pagado / cantidad_cajas
                        flash(f'💰 Precio calculado automáticamente: ${precio_unitario:.2f} por caja (${monto_pagado:,.2f} / {cantidad_cajas} cajas)', 'info')
                    elif precio_especial and float(precio_especial) > 0:
                        # Usar precio especial ingresado manualmente
                        precio_unitario = float(precio_especial)
                        flash(f'💰 Precio especial ingresado: ${precio_unitario:.2f} por caja', 'info')
                    else:
                        # Si no hay precio especial, calcular automáticamente como fallback
                        precio_unitario = monto_pagado / cantidad_cajas
                        flash(f'💰 Precio calculado automáticamente: ${precio_unitario:.2f} por caja', 'info')
                    
                    # Validar que el precio sea positivo
                    if precio_unitario <= 0:
                        flash('El precio por caja debe ser mayor a 0', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                        
                elif perfil_cliente == 'Mayorista':
                    # Obtener precio mayorista del producto
                    cursor.execute("SELECT Precio_Mayorista FROM productos WHERE ID_Producto = %s", (id_producto,))
                    precio_data = cursor.fetchone()
                    precio_unitario = float(precio_data['Precio_Mayorista']) if precio_data and precio_data['Precio_Mayorista'] else 0
                    
                    if precio_unitario <= 0:
                        flash('El producto no tiene precio mayorista configurado', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                    
                    # Verificar que el monto corresponda
                    monto_esperado = cantidad_cajas * precio_unitario
                    if abs(monto_pagado - monto_esperado) > 0.01:
                        flash(f'⚠️ Atención: El monto pagado (${monto_pagado:,.2f}) no corresponde con el precio mayorista (${monto_esperado:,.2f}). Se usará el monto ingresado.', 'warning')
                        
                elif perfil_cliente == 'Ruta':
                    # Obtener precio ruta del producto
                    cursor.execute("SELECT Precio_Ruta FROM productos WHERE ID_Producto = %s", (id_producto,))
                    precio_data = cursor.fetchone()
                    precio_unitario = float(precio_data['Precio_Ruta']) if precio_data and precio_data['Precio_Ruta'] else 0
                    
                    if precio_unitario <= 0:
                        flash('El producto no tiene precio ruta configurado', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                    
                    # Verificar que el monto corresponda
                    monto_esperado = cantidad_cajas * precio_unitario
                    if abs(monto_pagado - monto_esperado) > 0.01:
                        flash(f'⚠️ Atención: El monto pagado (${monto_pagado:,.2f}) no corresponde con el precio ruta (${monto_esperado:,.2f}). Se usará el monto ingresado.', 'warning')
                        
                else:  # perfil_cliente == 'Mercado' o cualquier otro
                    # Obtener precio mercado del producto
                    cursor.execute("SELECT Precio_Mercado FROM productos WHERE ID_Producto = %s", (id_producto,))
                    precio_data = cursor.fetchone()
                    precio_unitario = float(precio_data['Precio_Mercado']) if precio_data and precio_data['Precio_Mercado'] else 0
                    
                    if precio_unitario <= 0:
                        flash('El producto no tiene precio mercado configurado', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                    
                    # Verificar que el monto corresponda
                    monto_esperado = cantidad_cajas * precio_unitario
                    if abs(monto_pagado - monto_esperado) > 0.01:
                        flash(f'⚠️ Atención: El monto pagado (${monto_pagado:,.2f}) no corresponde con el precio mercado (${monto_esperado:,.2f}). Se usará el monto ingresado.', 'warning')
                
                # Calcular saldo restante
                saldo_restante = monto_pagado
                
                # Insertar anticipo con el precio unitario determinado
                cursor.execute("""
                    INSERT INTO anticipos_clientes 
                    (ID_Cliente, ID_Producto, Cantidad_Cajas, Cajas_Consumidas, 
                     Monto_Pagado, Saldo_Restante, Precio_Unitario, Fecha_Anticipo, 
                     Fecha_Vencimiento, Estado, Notas)
                    VALUES (%s, %s, %s, 0, %s, %s, %s, NOW(), %s, 'ACTIVO', %s)
                """, (id_cliente, id_producto, cantidad_cajas, monto_pagado, 
                      saldo_restante, precio_unitario, fecha_vencimiento or None, notas))
                
                id_anticipo = cursor.lastrowid
                
                # Actualizar datos del cliente
                cursor.execute("""
                    UPDATE clientes 
                    SET Anticipo_Activo = 1,
                        Limite_Anticipo_Cajas = COALESCE(Limite_Anticipo_Cajas, 0) + %s,
                        Saldo_Anticipos = COALESCE(Saldo_Anticipos, 0) + %s,
                        Producto_Anticipado = %s
                    WHERE ID_Cliente = %s
                """, (cantidad_cajas, monto_pagado, id_producto, id_cliente))
                
                flash(f'✅ Anticipo registrado exitosamente. ID: {id_anticipo} - Precio por caja: ${precio_unitario:.2f}', 'success')
                return redirect(url_for('admin.admin_clientes_anticipos'))
                
        except Exception as e:
            print(f" Error registrando anticipo: {str(e)}")
            traceback.print_exc()
            flash('Error interno al registrar el anticipo', 'error')
            return redirect(url_for('admin.admin_anticipo_nuevo'))
    
    # GET - Mostrar formulario
    try:
        with get_db_cursor(True) as cursor:
            # Obtener clientes activos de la empresa
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA, perfil_cliente, tipo_cliente,
                       COALESCE(Saldo_Anticipos, 0) as Saldo_Anticipos, 
                       COALESCE(Limite_Anticipo_Cajas, 0) as Limite_Anticipo_Cajas
                FROM clientes 
                WHERE ID_Empresa = %s AND Estado = 'ACTIVO'
                ORDER BY Nombre
            """, (id_empresa,))
            clientes = cursor.fetchall()
            
            # Obtener productos activos de la empresa
            cursor.execute("""
                SELECT ID_Producto, Descripcion, COD_Producto, 
                       COALESCE(Precio_Mercado, 0) as Precio_Mercado, 
                       COALESCE(Precio_Mayorista, 0) as Precio_Mayorista, 
                       COALESCE(Precio_Ruta, 0) as Precio_Ruta
                FROM productos 
                WHERE ID_Empresa = %s AND Estado = 'activo'
                ORDER BY Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/nuevo_anticipo.html',
                                 clientes=clientes, productos=productos)
    except Exception as e:
        print(f" Error cargando formulario: {str(e)}")
        traceback.print_exc()
        flash('Error cargando el formulario', 'error')
        return redirect(url_for('admin.admin_clientes_anticipos'))


@admin_bp.route('/admin/ventas/anticipos/detalle/<int:id_anticipo>')
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-DETALLE")
def admin_anticipo_detalle(id_anticipo):
    try:
        id_empresa = session.get('id_empresa',1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    a.*,
                    c.Nombre as NombreCliente,
                    c.RUC_CEDULA,
                    c.Telefono,
                    c.Direccion,
                    c.perfil_cliente,
                    c.Saldo_Anticipos as Cliente_Saldo_Anticipos,
                    c.Limite_Anticipo_Cajas,
                    c.Cajas_Consumidas_Anticipo,
                    p.Descripcion as NombreProducto,
                    p.COD_Producto,
                    CASE 
                        WHEN c.perfil_cliente = 'Mayorista' THEN p.Precio_Mayorista
                        WHEN c.perfil_cliente = 'Ruta' THEN p.Precio_Ruta
                        ELSE p.Precio_Mercado
                    END as Precio_Actual
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Anticipo = %s AND c.ID_Empresa = %s
            """, (id_anticipo, id_empresa))
            
            anticipo = cursor.fetchone()
            
            if not anticipo:
                flash('Anticipo no encontrado', 'error')
                return redirect(url_for('admin.admin_clientes_anticipos'))
            
            return render_template('admin/ventas/anticipos/detalle_anticipo.html',
                                 anticipo=anticipo)
    except Exception as e:
        print(f" Error obteniendo detalle: {str(e)}")
        traceback.print_exc()
        flash('Error al obtener el detalle del anticipo', 'error')
        return redirect(url_for('admin.admin_clientes_anticipos'))


@admin_bp.route('/admin/ventas/anticipos/cancelar/<int:id_anticipo>', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-CANCELAR")
def admin_anticipo_cancelar(id_anticipo):
    try:
        id_empresa = session.get('id_empresa', 1)
        motivo = request.form.get('motivo', 'Cancelado por usuario')
        
        with get_db_cursor() as cursor:
            # Obtener información del anticipo verificando empresa a través del cliente
            cursor.execute("""
                SELECT a.ID_Cliente, a.Cantidad_Cajas, a.Cajas_Consumidas, 
                       a.Monto_Pagado, a.Saldo_Restante, a.Estado
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                WHERE a.ID_Anticipo = %s AND c.ID_Empresa = %s AND a.Estado = 'ACTIVO'
            """, (id_anticipo, id_empresa))
            
            anticipo = cursor.fetchone()
            
            if not anticipo:
                flash('Anticipo no encontrado o ya está cancelado/completado', 'error')
                return redirect(url_for('admin.admin_clientes_anticipos'))
            
            # Cancelar anticipo
            cursor.execute("""
                UPDATE anticipos_clientes 
                SET Estado = 'CANCELADO', 
                    Notas = CONCAT(COALESCE(Notas, ''), '\n[', NOW(), '] Cancelado: ', %s)
                WHERE ID_Anticipo = %s
            """, (motivo, id_anticipo))
            
            # Calcular cajas no consumidas
            cajas_no_consumidas = anticipo['Cantidad_Cajas'] - anticipo['Cajas_Consumidas']
            
            # Actualizar datos del cliente (restar solo lo no consumido)
            cursor.execute("""
                UPDATE clientes 
                SET Limite_Anticipo_Cajas = COALESCE(Limite_Anticipo_Cajas, 0) - %s,
                    Saldo_Anticipos = COALESCE(Saldo_Anticipos, 0) - %s,
                    Anticipo_Activo = CASE 
                        WHEN (COALESCE(Limite_Anticipo_Cajas, 0) - %s) <= 0 THEN 0 
                        ELSE 1 
                    END
                WHERE ID_Cliente = %s
            """, (cajas_no_consumidas, anticipo['Monto_Pagado'], 
                  cajas_no_consumidas, anticipo['ID_Cliente']))
            
            flash('Anticipo cancelado exitosamente', 'success')
            return redirect(url_for('admin.admin_clientes_anticipos'))
            
    except Exception as e:
        print(f" Error cancelando anticipo: {str(e)}")
        traceback.print_exc()
        flash('Error al cancelar el anticipo', 'error')
        return redirect(url_for('admin.admin_clientes_anticipos'))


@admin_bp.route('/admin/ventas/anticipos/entregas', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-ENTREGAS")
def admin_anticipo_entregas():
    """Visualizar y realizar entregas de productos con anticipos (múltiples sucursales)"""
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            id_anticipo = request.form.get('id_anticipo')
            id_bodega = request.form.get('id_bodega')
            notas = request.form.get('notas', '')
            
            # Obtener arreglos de sucursales y cantidades
            sucursales = request.form.getlist('sucursales[]')
            cantidades = request.form.getlist('cantidades[]')
            
            # Validar datos básicos
            if not id_anticipo:
                flash(' Por favor seleccione un anticipo', 'error')
                return redirect(request.url)
            
            if not id_bodega:
                flash(' Por favor seleccione una bodega', 'error')
                return redirect(request.url)
            
            if not sucursales or not cantidades:
                flash(' Debe agregar al menos una entrega', 'error')
                return redirect(request.url)
            
            # Validar que los arreglos tengan la misma longitud
            if len(sucursales) != len(cantidades):
                flash(' Error en los datos de entregas', 'error')
                return redirect(request.url)
            
            # Validar que haya al menos una entrega válida
            entregas_validas = []
            for i in range(len(sucursales)):
                sucursal_id = sucursales[i]
                cantidad_str = cantidades[i]
                
                if not sucursal_id or not cantidad_str:
                    continue
                
                try:
                    cantidad = int(cantidad_str)
                    if cantidad > 0:
                        entregas_validas.append({
                            'sucursal_id': int(sucursal_id),
                            'cantidad': cantidad
                        })
                except ValueError:
                    continue
            
            if len(entregas_validas) == 0:
                flash(' No hay entregas válidas para procesar', 'error')
                return redirect(request.url)
            
            # Calcular total de cajas
            total_cajas = sum(e['cantidad'] for e in entregas_validas)
            
            # Obtener el ID del usuario actual
            id_usuario = current_user.id
            
            with get_db_cursor() as cursor:
                # 1. Obtener información completa del anticipo y cliente
                cursor.execute("""
                    SELECT 
                        a.ID_Anticipo, 
                        a.ID_Cliente, 
                        a.ID_Producto, 
                        a.Cantidad_Cajas as Anticipo_Total_Cajas,
                        a.Cajas_Consumidas as Anticipo_Cajas_Consumidas,
                        a.Precio_Unitario,
                        a.Monto_Pagado,
                        a.Saldo_Restante,
                        p.Descripcion as Nombre_Producto,
                        c.Nombre as Nombre_Cliente,
                        c.Telefono,
                        c.Saldo_Anticipos as Cliente_Saldo_Anticipos,
                        c.Cajas_Consumidas_Anticipo as Cliente_Cajas_Consumidas,
                        c.Anticipo_Activo,
                        c.Producto_Anticipado,
                        c.ID_Empresa
                    FROM anticipos_clientes a
                    INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                    INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                    WHERE a.ID_Anticipo = %s AND a.Estado = 'ACTIVO'
                """, (id_anticipo,))
                anticipo = cursor.fetchone()
                
                if not anticipo:
                    flash(' Anticipo no encontrado o inactivo', 'error')
                    return redirect(request.url)
                
                # 2. Verificar que la bodega existe y está activa
                cursor.execute("""
                    SELECT ID_Bodega, Nombre
                    FROM bodegas
                    WHERE ID_Bodega = %s AND Estado = 'activa'
                """, (id_bodega,))
                bodega = cursor.fetchone()
                
                if not bodega:
                    flash(' Bodega no encontrada o inactiva', 'error')
                    return redirect(request.url)
                
                # 3. Verificar cajas disponibles en el anticipo
                cajas_disponibles_antes = anticipo['Anticipo_Total_Cajas'] - anticipo['Anticipo_Cajas_Consumidas']
                
                if total_cajas > cajas_disponibles_antes:
                    flash(f'⚠️ Cajas insuficientes en el anticipo. Disponibles: {cajas_disponibles_antes}, Solicitadas: {total_cajas}', 'error')
                    return redirect(request.url)
                
                # 4. Verificar inventario en bodega
                cursor.execute("""
                    SELECT Existencias
                    FROM inventario_bodega
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega, anticipo['ID_Producto']))
                inventario = cursor.fetchone()
                
                if not inventario:
                    flash(f'⚠️ El producto {anticipo["Nombre_Producto"]} no tiene inventario en la bodega {bodega["Nombre"]}', 'error')
                    return redirect(request.url)
                
                existencias_actuales = float(inventario['Existencias'])
                
                if total_cajas > existencias_actuales:
                    flash(f'⚠️ Existencias insuficientes. Disponibles: {existencias_actuales} cajas', 'error')
                    return redirect(request.url)
                
                # 5. Calcular precio y total
                precio_unitario = float(anticipo['Precio_Unitario'])
                total_monto = total_cajas * precio_unitario
                
                # 6. REGISTRAR MOVIMIENTO DE INVENTARIO
                id_tipo_movimiento = 14  # Salida por Anticipo Cliente
                observacion_movimiento = f"Salida por anticipo - Cliente: {anticipo['Nombre_Cliente']} - Anticipo #{id_anticipo} - Bodega: {bodega['Nombre']} - Producto: {anticipo['Nombre_Producto']} - Total Cajas: {total_cajas}"
                if notas:
                    observacion_movimiento += f" - Notas: {notas}"
                
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (ID_TipoMovimiento, Fecha, Observacion, ID_Empresa, ID_Bodega, 
                     ID_Usuario_Creacion, Fecha_Creacion, Estado)
                    VALUES (%s, CURDATE(), %s, %s, %s, %s, NOW(), 'Activa')
                """, (id_tipo_movimiento, observacion_movimiento,
                      anticipo['ID_Empresa'], id_bodega, id_usuario))
                
                id_movimiento = cursor.lastrowid
                
                # 7. REGISTRAR DETALLE DEL MOVIMIENTO DE INVENTARIO
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario 
                    (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, 
                     Subtotal, ID_Usuario_Creacion, Fecha_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (id_movimiento, anticipo['ID_Producto'], total_cajas, 
                      precio_unitario, total_monto, id_usuario))
                
                # 8. REGISTRAR CADA ENTREGA POR SUCURSAL
                ids_entregas = []
                for entrega in entregas_validas:
                    cursor.execute("""
                        INSERT INTO entregas 
                        (ID_Cliente, ID_Sucursal, ID_Producto, Cantidad_Cajas, 
                         Precio_Unitario, Total, Usa_Anticipo, ID_Anticipo, 
                         ID_Usuario, Notas, Fecha_Entrega)
                        VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, NOW())
                    """, (anticipo['ID_Cliente'], entrega['sucursal_id'], anticipo['ID_Producto'], 
                          entrega['cantidad'], precio_unitario, entrega['cantidad'] * precio_unitario, 
                          id_anticipo, id_usuario, notas))
                    
                    id_entrega = cursor.lastrowid
                    ids_entregas.append(id_entrega)
                    
                    # Registrar detalle de cada entrega
                    cursor.execute("""
                        INSERT INTO detalle_entregas 
                        (ID_Entrega, ID_Producto, Cantidad_Cajas, Precio_Unitario, 
                         Total, Usa_Anticipo, ID_Anticipo)
                        VALUES (%s, %s, %s, %s, %s, 1, %s)
                    """, (id_entrega, anticipo['ID_Producto'], entrega['cantidad'], 
                          precio_unitario, entrega['cantidad'] * precio_unitario, id_anticipo))
                
                # 9. ACTUALIZAR EL ANTICIPO
                nuevas_cajas_consumidas = anticipo['Anticipo_Cajas_Consumidas'] + total_cajas
                cajas_restantes = anticipo['Anticipo_Total_Cajas'] - nuevas_cajas_consumidas
                nuevo_saldo_restante = cajas_restantes * precio_unitario
                
                nuevo_estado = 'COMPLETADO' if nuevas_cajas_consumidas >= anticipo['Anticipo_Total_Cajas'] else 'ACTIVO'
                
                cursor.execute("""
                    UPDATE anticipos_clientes 
                    SET Cajas_Consumidas = %s, 
                        Estado = %s,
                        Saldo_Restante = %s
                    WHERE ID_Anticipo = %s
                """, (nuevas_cajas_consumidas, nuevo_estado, nuevo_saldo_restante, id_anticipo))
                
                # 10. ACTUALIZAR DATOS DEL CLIENTE
                nuevas_cajas_consumidas_cliente = anticipo['Cliente_Cajas_Consumidas'] + total_cajas
                nuevo_saldo_anticipos_cliente = float(anticipo['Cliente_Saldo_Anticipos']) - total_monto
                
                anticipo_cliente_completado = nuevas_cajas_consumidas_cliente >= anticipo['Anticipo_Total_Cajas']
                nuevo_anticipo_activo = 0 if anticipo_cliente_completado else 1
                
                cursor.execute("""
                    UPDATE clientes 
                    SET Cajas_Consumidas_Anticipo = %s,
                        Saldo_Anticipos = %s,
                        Anticipo_Activo = %s,
                        Fecha_Ultimo_Movimiento = NOW()
                    WHERE ID_Cliente = %s
                """, (nuevas_cajas_consumidas_cliente, nuevo_saldo_anticipos_cliente, 
                      nuevo_anticipo_activo, anticipo['ID_Cliente']))
                
                # 11. DESCOTAR INVENTARIO DE LA BODEGA
                nuevas_existencias = existencias_actuales - total_cajas
                cursor.execute("""
                    UPDATE inventario_bodega 
                    SET Existencias = %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (nuevas_existencias, id_bodega, anticipo['ID_Producto']))
                
                # 12. Si el anticipo se completó, registrar en bitácora (CORREGIDO)
                if anticipo_cliente_completado:
                    # Obtener la IP del usuario
                    ip_acceso = request.remote_addr or '0.0.0.0'
                    
                    cursor.execute("""
                        INSERT INTO bitacora (ID_Usuario, Modulo, Accion, IP_Acceso, Fecha)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (id_usuario, 
                          'CLIENTES-ANTICIPOS-ENTREGAS', 
                          f'ANTICIPO_COMPLETADO - Cliente: {anticipo["Nombre_Cliente"]} (ID: {anticipo["ID_Cliente"]}) - Total cajas consumidas: {nuevas_cajas_consumidas_cliente} - Anticipo #{id_anticipo}',
                          ip_acceso))
                
                # Commit implícito por el context manager
                
                # Redirigir al ticket con auto-impresión
                flash(f'✅ {len(ids_entregas)} entregas registradas exitosamente!', 'success')
                return redirect(url_for('admin.ticket_entregas', id_anticipo=id_anticipo, autoPrint=1))
                
        except ValueError as e:
            flash(f' Error en el formato de los datos: {str(e)}', 'error')
            return redirect(request.url)
        except Exception as e:
            flash(f' Error al registrar la entrega: {str(e)}', 'error')
            return redirect(request.url)
    
    # Método GET - Mostrar la página con datos
    try:
        with get_db_cursor() as cursor:
            # Obtener ID de la empresa del usuario actual
            cursor.execute("SELECT ID_Empresa FROM usuarios WHERE ID_Usuario = %s", (current_user.id,))
            usuario = cursor.fetchone()
            empresa_id = usuario['ID_Empresa'] if usuario else None
            
            # 1. Obtener anticipos activos disponibles - VERSIÓN CORREGIDA
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.ID_Cliente,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    c.RUC_CEDULA,
                    c.perfil_cliente,
                    c.Saldo_Anticipos as Cliente_Saldo_Anticipos,
                    c.Cajas_Consumidas_Anticipo as Cliente_Cajas_Consumidas,
                    c.Anticipo_Activo,
                    c.Limite_Anticipo_Cajas,
                    a.ID_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    a.Cantidad_Cajas as Total_Cajas_Anticipo,
                    a.Cajas_Consumidas as Cajas_Consumidas_Anticipo,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Disponibles,
                    a.Precio_Unitario,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    DATE_FORMAT(a.Fecha_Anticipo, '%d/%m/%Y') as Fecha_Anticipo_Formato,
                    DATE_FORMAT(a.Fecha_Vencimiento, '%d/%m/%Y') as Fecha_Vencimiento_Formato,
                    DATEDIFF(a.Fecha_Vencimiento, CURDATE()) as Dias_Vencimiento,
                    CASE 
                        WHEN a.Fecha_Vencimiento < NOW() AND a.Estado = 'ACTIVO' THEN 'VENCIDO'
                        WHEN a.Fecha_Vencimiento IS NOT NULL AND a.Fecha_Vencimiento < DATE_ADD(NOW(), INTERVAL 7 DAY) THEN 'PRÓXIMO_A_VENCER'
                        ELSE 'VIGENTE'
                    END as Estado_Vencimiento
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.Estado = 'ACTIVO' 
                  AND (a.Cantidad_Cajas - a.Cajas_Consumidas) > 0
                ORDER BY c.Nombre, a.Fecha_Anticipo ASC
            """)
            anticipos_disponibles = cursor.fetchall()
            
            # 2. Obtener sucursales
            cursor.execute("""
                SELECT s.ID_Sucursal, s.Nombre_Sucursal, s.Direccion, s.Encargado,
                       c.Nombre as Nombre_Cliente, c.ID_Cliente
                FROM sucursales s
                INNER JOIN clientes c ON s.ID_Cliente = c.ID_Cliente
                WHERE s.Estado = 'ACTIVO' AND c.Estado = 'ACTIVO'
                ORDER BY c.Nombre, s.Nombre_Sucursal
            """)
            sucursales = cursor.fetchall()
            
            # 3. Obtener bodegas activas
            if empresa_id:
                cursor.execute("""
                    SELECT ID_Bodega, Nombre, Ubicacion, Estado
                    FROM bodegas
                    WHERE ID_Empresa = %s AND Estado = 'activa'
                    ORDER BY Nombre
                """, (empresa_id,))
            else:
                cursor.execute("""
                    SELECT ID_Bodega, Nombre, Ubicacion, Estado
                    FROM bodegas
                    WHERE Estado = 'activa'
                    ORDER BY Nombre
                """)
            bodegas = cursor.fetchall()
            
            if not bodegas:
                flash('⚠️ No hay bodegas activas configuradas para su empresa', 'warning')
            
            # 4. Obtener historial de entregas
            cursor.execute("""
                SELECT 
                    e.ID_Entrega,
                    DATE_FORMAT(e.Fecha_Entrega, '%d/%m/%Y %H:%i') as Fecha_Entrega_Formato,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono as Cliente_Telefono,
                    p.Descripcion as Nombre_Producto,
                    e.Cantidad_Cajas,
                    e.Precio_Unitario,
                    e.Total,
                    s.Nombre_Sucursal,
                    e.Notas,
                    e.Usa_Anticipo,
                    a.ID_Anticipo,
                    a.Saldo_Restante as Saldo_Restante_Anticipo,
                    u.NombreUsuario,
                    c.Saldo_Anticipos as Cliente_Saldo_Actual
                FROM entregas e
                INNER JOIN clientes c ON e.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON e.ID_Producto = p.ID_Producto
                INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                LEFT JOIN anticipos_clientes a ON e.ID_Anticipo = a.ID_Anticipo
                LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                WHERE e.Usa_Anticipo = 1
                ORDER BY e.Fecha_Entrega DESC
                LIMIT 10
            """)
            entregas_recientes = cursor.fetchall()
            
            # 5. Estadísticas
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT e.ID_Entrega) as Total_Entregas_Hoy,
                    COALESCE(SUM(e.Total), 0) as Monto_Total_Entregado_Hoy,
                    COUNT(DISTINCT a.ID_Anticipo) as Anticipos_Activos,
                    COALESCE(SUM(a.Cantidad_Cajas - a.Cajas_Consumidas), 0) as Cajas_Disponibles_Total,
                    COUNT(DISTINCT c.ID_Cliente) as Clientes_Con_Anticipos,
                    COALESCE(SUM(c.Saldo_Anticipos), 0) as Saldo_Total_Anticipos
                FROM entregas e
                RIGHT JOIN anticipos_clientes a ON e.ID_Anticipo = a.ID_Anticipo AND DATE(e.Fecha_Entrega) = CURDATE()
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                WHERE a.Estado = 'ACTIVO'
            """)
            estadisticas = cursor.fetchone()
            
            # Si estadisticas es None, inicializar con ceros
            if not estadisticas:
                estadisticas = {
                    'Total_Entregas_Hoy': 0,
                    'Monto_Total_Entregado_Hoy': 0,
                    'Anticipos_Activos': 0,
                    'Cajas_Disponibles_Total': 0,
                    'Clientes_Con_Anticipos': 0,
                    'Saldo_Total_Anticipos': 0
                }
            
            # 6. Anticipos casi agotados
            cursor.execute("""
                SELECT 
                    c.ID_Cliente,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    a.ID_Anticipo,
                    p.Descripcion as Nombre_Producto,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Restantes,
                    a.Precio_Unitario,
                    a.Saldo_Restante,
                    c.perfil_cliente
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.Estado = 'ACTIVO'
                  AND (a.Cantidad_Cajas - a.Cajas_Consumidas) <= 5
                  AND (a.Cantidad_Cajas - a.Cajas_Consumidas) > 0
                ORDER BY Cajas_Restantes ASC
                LIMIT 10
            """)
            anticipos_bajos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/anticipos_entregas.html',
                                 anticipos=anticipos_disponibles,
                                 sucursales=sucursales,
                                 bodegas=bodegas,
                                 entregas=entregas_recientes,
                                 estadisticas=estadisticas,
                                 anticipos_bajos=anticipos_bajos)
                                 
    except Exception as e:
        flash(f' Error al cargar los datos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/ventas/anticipos/entregas/ticket/<int:id_anticipo>')
@admin_required
def ticket_entregas(id_anticipo):
    """Generar ticket SOLO con las entregas del día actual"""
    try:
        from datetime import datetime
        
        with get_db_cursor(True) as cursor:
            # Obtener información del anticipo y cliente
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.ID_Cliente,
                    a.ID_Producto,
                    a.Cantidad_Cajas as Total_Cajas_Anticipo,
                    a.Cajas_Consumidas as Cajas_Consumidas,
                    a.Precio_Unitario,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    a.Fecha_Anticipo,
                    a.Notas as Anticipo_Notas,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    c.Direccion as Direccion_Cliente,
                    c.RUC_CEDULA,
                    c.perfil_cliente,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Anticipo = %s
            """, (id_anticipo,))
            anticipo = cursor.fetchone()
            
            if not anticipo:
                flash('Anticipo no encontrado', 'error')
                return redirect(url_for('admin.admin_anticipo_entregas'))
            
            # Obtener SOLO las entregas de HOY
            cursor.execute("""
                SELECT 
                    e.ID_Entrega,
                    e.Cantidad_Cajas,
                    e.Fecha_Entrega,
                    e.Notas,
                    s.Nombre_Sucursal,
                    s.Direccion as Direccion_Sucursal,
                    u.NombreUsuario as Registrado_Por,
                    DATE_FORMAT(e.Fecha_Entrega, '%%d/%%m/%%Y') as Fecha_Entrega_Formato,
                    DATE_FORMAT(e.Fecha_Entrega, '%%H:%%i') as Hora_Entrega
                FROM entregas e
                INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                WHERE e.ID_Anticipo = %s AND DATE(e.Fecha_Entrega) = CURDATE()
                ORDER BY e.Fecha_Entrega ASC
            """, (id_anticipo,))
            entregas_hoy = cursor.fetchall()
            
            if not entregas_hoy:
                flash('No hay entregas registradas hoy para este anticipo', 'warning')
                return redirect(url_for('admin.admin_anticipo_entregas'))
            
            # Agrupar entregas por fecha (para el detalle)
            entregas_por_fecha = {}
            for e in entregas_hoy:
                fecha = e['Fecha_Entrega_Formato']
                if fecha not in entregas_por_fecha:
                    entregas_por_fecha[fecha] = []
                entregas_por_fecha[fecha].append(e)
            
            # Consolidar por sucursal
            sucursales_consolidadas = {}
            for e in entregas_hoy:
                nombre_sucursal = e['Nombre_Sucursal']
                if nombre_sucursal not in sucursales_consolidadas:
                    sucursales_consolidadas[nombre_sucursal] = {
                        'nombre': nombre_sucursal,
                        'total': 0
                    }
                sucursales_consolidadas[nombre_sucursal]['total'] += e['Cantidad_Cajas']
            
            sucursales_consolidadas = sorted(sucursales_consolidadas.values(), key=lambda x: x['nombre'])
            
            total_cajas_hoy = sum(e['Cantidad_Cajas'] for e in entregas_hoy)
            cajas_pendientes = anticipo['Total_Cajas_Anticipo'] - anticipo['Cajas_Consumidas']
            
            # Obtener bodega
            bodega_nombre = None
            cursor.execute("""
                SELECT b.Nombre
                FROM movimientos_inventario m
                INNER JOIN bodegas b ON m.ID_Bodega = b.ID_Bodega
                WHERE m.Observacion LIKE %s AND DATE(m.Fecha_Creacion) = CURDATE()
                LIMIT 1
            """, (f'%Anticipo #{id_anticipo}%',))
            bodega = cursor.fetchone()
            if bodega:
                bodega_nombre = bodega['Nombre']
            
            # Datos de la empresa
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, RUC, Direccion, Telefono
                FROM empresa
                LIMIT 1
            """)
            empresa = cursor.fetchone()
            
            # Notas combinadas
            notas_entregas = ' | '.join([e['Notas'] for e in entregas_hoy if e['Notas']]) if entregas_hoy else None
            
            return render_template('admin/ventas/anticipos/ticket_entregas.html',
                                 anticipo=anticipo,
                                 entregas=entregas_hoy,
                                 entregas_por_fecha=entregas_por_fecha,
                                 sucursales_consolidadas=sucursales_consolidadas,
                                 total_cajas_rango=total_cajas_hoy,
                                 cajas_pendientes=cajas_pendientes,
                                 empresa=empresa,
                                 bodega_nombre=bodega_nombre,
                                 notas_entregas=notas_entregas,
                                 titulo_rango=f"Hoy - {datetime.now().strftime('%d/%m/%Y')}",
                                 mostrar_detalle=False,
                                 fecha_actual=datetime.now())
                                 
    except Exception as e:
        flash(f'Error al generar ticket: {str(e)}', 'error')
        return redirect(url_for('admin.admin_anticipo_entregas'))


@admin_bp.route('/ventas/anticipos/proforma')
@admin_required
def proforma_anticipos_lista():
    """Lista de anticipos disponibles para ver proforma"""
    try:
        with get_db_cursor(True) as cursor:
            # Obtener todos los anticipos (activos, completados, cancelados)
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.Cantidad_Cajas as Total_Cajas,
                    a.Cajas_Consumidas,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Pendientes,
                    a.Fecha_Anticipo,
                    a.Estado,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    p.Descripcion as Nombre_Producto,
                    DATE_FORMAT(a.Fecha_Anticipo, '%d/%m/%Y') as Fecha_Formato
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                ORDER BY a.Fecha_Anticipo DESC
            """)
            anticipos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/proforma_lista.html',
                                 anticipos=anticipos,
                                 fecha_actual=datetime.now())
                                 
    except Exception as e:
        flash(f'Error al cargar anticipos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_anticipo_entregas'))


@admin_bp.route('/ventas/anticipos/proforma/api/<int:id_anticipo>')
@admin_required
def proforma_anticipo_api(id_anticipo):
    """API para obtener datos de la proforma en formato JSON"""
    try:
        
        # Obtener parámetros del filtro
        filtro = request.args.get('filtro', 'todas')
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        with get_db_cursor(True) as cursor:
            # 1. Obtener información del anticipo y cliente
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.ID_Cliente,
                    a.ID_Producto,
                    a.Cantidad_Cajas as Total_Cajas_Anticipo,
                    a.Cajas_Consumidas as Cajas_Consumidas,
                    a.Precio_Unitario,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    a.Fecha_Anticipo,
                    a.Notas as Anticipo_Notas,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    c.Direccion as Direccion_Cliente,
                    c.RUC_CEDULA,
                    c.perfil_cliente,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Anticipo = %s
            """, (id_anticipo,))
            anticipo = cursor.fetchone()
            
            if not anticipo:
                return jsonify({'error': 'Anticipo no encontrado'}), 404
            
            # 2. Determinar fechas según el filtro
            hoy = datetime.now().date()
            titulo_rango = ""
            
            if filtro == 'hoy':
                fecha_inicio = hoy.strftime('%Y-%m-%d')
                fecha_fin = hoy.strftime('%Y-%m-%d')
                titulo_rango = f"Hoy - {hoy.strftime('%d/%m/%Y')}"
            elif filtro == 'rango' and fecha_inicio and fecha_fin:
                fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
                titulo_rango = f"Del {fecha_inicio_obj.strftime('%d/%m/%Y')} al {fecha_fin_obj.strftime('%d/%m/%Y')}"
            else:
                fecha_inicio = None
                fecha_fin = None
                titulo_rango = "Historial Completo"
            
            # 3. Obtener entregas
            if fecha_inicio and fecha_fin:
                cursor.execute("""
                    SELECT 
                        e.ID_Entrega,
                        e.Cantidad_Cajas,
                        e.Fecha_Entrega,
                        e.Notas,
                        s.Nombre_Sucursal,
                        s.Direccion as Direccion_Sucursal,
                        u.NombreUsuario as Registrado_Por,
                        DATE_FORMAT(e.Fecha_Entrega, '%d/%m/%Y') as Fecha_Formato,
                        DATE_FORMAT(e.Fecha_Entrega, '%H:%i') as Hora_Entrega
                    FROM entregas e
                    INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                    LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                    WHERE e.ID_Anticipo = %s 
                      AND DATE(e.Fecha_Entrega) >= %s 
                      AND DATE(e.Fecha_Entrega) <= %s
                    ORDER BY e.Fecha_Entrega ASC
                """, (id_anticipo, fecha_inicio, fecha_fin))
            else:
                cursor.execute("""
                    SELECT 
                        e.ID_Entrega,
                        e.Cantidad_Cajas,
                        e.Fecha_Entrega,
                        e.Notas,
                        s.Nombre_Sucursal,
                        s.Direccion as Direccion_Sucursal,
                        u.NombreUsuario as Registrado_Por,
                        DATE_FORMAT(e.Fecha_Entrega, '%d/%m/%Y') as Fecha_Formato,
                        DATE_FORMAT(e.Fecha_Entrega, '%H:%i') as Hora_Entrega
                    FROM entregas e
                    INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                    LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                    WHERE e.ID_Anticipo = %s
                    ORDER BY e.Fecha_Entrega ASC
                """, (id_anticipo,))
            
            entregas = cursor.fetchall()
            
            # 4. Calcular totales
            total_cajas_entregadas = sum(e['Cantidad_Cajas'] for e in entregas) if entregas else 0
            cajas_pendientes = anticipo['Total_Cajas_Anticipo'] - anticipo['Cajas_Consumidas']
            
            # 5. Consolidar por sucursal
            sucursales_consolidadas = {}
            for e in entregas:
                nombre = e['Nombre_Sucursal']
                if nombre not in sucursales_consolidadas:
                    sucursales_consolidadas[nombre] = 0
                sucursales_consolidadas[nombre] += e['Cantidad_Cajas']
            
            sucursales_lista = [{'nombre': k, 'total': v} for k, v in sucursales_consolidadas.items()]
            sucursales_lista.sort(key=lambda x: x['nombre'])
            
            # 6. Agrupar entregas por fecha
            entregas_por_fecha = {}
            for e in entregas:
                fecha = e['Fecha_Formato']
                if fecha not in entregas_por_fecha:
                    entregas_por_fecha[fecha] = []
                entregas_por_fecha[fecha].append({
                    'hora': e['Hora_Entrega'],
                    'sucursal': e['Nombre_Sucursal'],
                    'cantidad': e['Cantidad_Cajas']
                })
            
            # 7. Calcular porcentaje
            porcentaje_avance = (anticipo['Cajas_Consumidas'] / anticipo['Total_Cajas_Anticipo'] * 100) if anticipo['Total_Cajas_Anticipo'] > 0 else 0
            
            # 8. Datos de la empresa
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, RUC, Direccion, Telefono
                FROM empresa
                LIMIT 1
            """)
            empresa = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'anticipo': {
                    'id': anticipo['ID_Anticipo'],
                    'cliente': anticipo['Nombre_Cliente'],
                    'ruc': anticipo['RUC_CEDULA'] or 'No registra',
                    'telefono': anticipo['Telefono'] or 'No registra',
                    'direccion': anticipo['Direccion_Cliente'] or 'No registra',
                    'perfil': anticipo['perfil_cliente'],
                    'producto': anticipo['Nombre_Producto'],
                    'codigo': anticipo['COD_Producto'] or 'N/A',
                    'total_contratado': anticipo['Total_Cajas_Anticipo'],
                    'total_entregado': anticipo['Cajas_Consumidas'],
                    'fecha_anticipo': anticipo['Fecha_Anticipo'].strftime('%d/%m/%Y') if anticipo['Fecha_Anticipo'] else 'N/A',
                    'pendiente': cajas_pendientes,
                    'porcentaje': round(porcentaje_avance, 1)
                },
                'entregas': [{
                    'fecha': e['Fecha_Formato'],
                    'hora': e['Hora_Entrega'],
                    'sucursal': e['Nombre_Sucursal'],
                    'direccion': e['Direccion_Sucursal'] or '-',
                    'cantidad': e['Cantidad_Cajas'],
                    'registrado_por': e['Registrado_Por'] or 'Sistema',
                    'notas': e['Notas'] or '-'
                } for e in entregas],
                'sucursales_consolidadas': sucursales_lista,
                'total_cajas': total_cajas_entregadas,
                'total_entregas': len(entregas),
                'titulo_rango': titulo_rango,
                'empresa': {
                    'nombre': empresa['Nombre_Empresa'] if empresa else 'SISTEMA DE VENTAS',
                    'ruc': empresa['RUC'] if empresa else '000-000-000',
                    'direccion': empresa['Direccion'] if empresa else '',
                    'telefono': empresa['Telefono'] if empresa else ''
                },
                'fecha_actual': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


