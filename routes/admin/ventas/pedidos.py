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

@admin_bp.route('/admin/ventas/nuevo-pedido')
@admin_required
@bitacora_decorator("NUEVO_PEDIDO")
def nuevo_pedido():
    """
    Formulario para crear un nuevo pedido individual
    Los precios se muestran según el perfil del cliente seleccionado
    """
    try:
        cliente_id = request.args.get('cliente')
        
        with get_db_cursor(True) as cursor:
            # Obtener clientes activos con su perfil
            sql_clientes = """
            SELECT 
                ID_Cliente, 
                Nombre, 
                Telefono, 
                Direccion, 
                RUC_CEDULA, 
                tipo_cliente, 
                perfil_cliente,
                ID_Ruta
            FROM clientes 
            WHERE Estado = 'ACTIVO'
            ORDER BY Nombre
            """
            cursor.execute(sql_clientes)
            clientes = cursor.fetchall()
            
            # Obtener empresas
            sql_empresas = "SELECT ID_Empresa, Nombre_Empresa FROM empresa ORDER BY Nombre_Empresa"
            cursor.execute(sql_empresas)
            empresas = cursor.fetchall()
            
            # Obtener perfiles disponibles para mostrar en el selector si es necesario
            perfiles = ['Ruta', 'Mayorista', 'Mercado', 'Especial']
            
            # Si se pasa un cliente específico, obtener sus datos
            cliente_seleccionado = None
            if cliente_id:
                sql_cliente = """
                SELECT 
                    ID_Cliente, 
                    Nombre, 
                    Telefono, 
                    Direccion, 
                    RUC_CEDULA, 
                    tipo_cliente, 
                    perfil_cliente,
                    ID_Ruta
                FROM clientes 
                WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
                """
                cursor.execute(sql_cliente, (cliente_id,))
                cliente_seleccionado = cursor.fetchone()

            # Definir opciones de prioridad
            prioridades = ['Urgente', 'Normal', 'Bajo']
            
            return render_template('admin/ventas/pedidos/nuevo_pedido.html',
                                 clientes=clientes,
                                 empresas=empresas,
                                 cliente_seleccionado=cliente_seleccionado,
                                 prioridades=prioridades,
                                 perfiles=perfiles,
                                 now=datetime.now().date())
            
    except Exception as e:
        flash(f"Error al cargar formulario de pedido: {e}", "error")
        return redirect(url_for('admin.admin_pedidos_venta'))


@admin_bp.route('/admin/ventas/crear-pedido', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PEDIDO")
def crear_pedido():
    """
    Crear un nuevo pedido individual
    Aplica el precio según el perfil_cliente del cliente:
    - perfil_cliente = 'Ruta' → Precio_Ruta
    - perfil_cliente = 'Mayorista' → Precio_Mayorista  
    - perfil_cliente = 'Mercado' → Precio_Mercado
    - perfil_cliente = 'Especial' → Precio_Mercado (por defecto)
    """
    try:
        data = request.get_json()
        user = current_user.id
        
        # Validar datos requeridos
        if not data.get('cliente_id'):
            return jsonify({'success': False, 'message': 'Se requiere un cliente'}), 400
        
        if not data.get('empresa_id'):
            return jsonify({'success': False, 'message': 'Se requiere una empresa'}), 400
        
        if not data.get('productos') or len(data['productos']) == 0:
            return jsonify({'success': False, 'message': 'Se requiere al menos un producto'}), 400
        
        fecha = data.get('fecha')
        tipo_entrega = data.get('tipo_entrega', 'Retiro en local')
        prioridad = data.get('prioridad', 'Normal')
        observacion = data.get('observacion', '')
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente existe y está activo (obtener perfil)
            sql_cliente = """
            SELECT 
                ID_Cliente, 
                tipo_cliente, 
                perfil_cliente 
            FROM clientes 
            WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
            """
            cursor.execute(sql_cliente, (data['cliente_id'],))
            cliente = cursor.fetchone()
            
            if not cliente:
                return jsonify({'success': False, 'message': 'Cliente no encontrado o inactivo'}), 400
            
            perfil_cliente = cliente['perfil_cliente']  # 'Ruta', 'Mayorista', 'Mercado', 'Especial'
            
            # Verificar que la empresa existe
            sql_empresa = "SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s"
            cursor.execute(sql_empresa, (data['empresa_id'],))
            empresa = cursor.fetchone()
            
            if not empresa:
                return jsonify({'success': False, 'message': 'Empresa no encontrada'}), 400
            
            # Crear el pedido
            sql_pedido = """
            INSERT INTO pedidos (
                Fecha, ID_Cliente, ID_Empresa, ID_Usuario_Creacion, 
                Estado, Observacion, Tipo_Entrega, Prioridad
            )
            VALUES (%s, %s, %s, %s, 'Pendiente', %s, %s, %s)
            """
            
            cursor.execute(sql_pedido, (
                fecha,
                data['cliente_id'],
                data['empresa_id'],
                user,
                observacion,
                tipo_entrega,
                prioridad
            ))
            
            pedido_id = cursor.lastrowid
            
            # Agregar productos al detalle del pedido
            for producto in data['productos']:
                # Verificar stock total disponible en inventario_bodega
                sql_stock_total = """
                SELECT COALESCE(SUM(Existencias), 0) as Stock_Total
                FROM inventario_bodega 
                WHERE ID_Producto = %s
                """
                cursor.execute(sql_stock_total, (producto['id'],))
                stock_total_result = cursor.fetchone()
                stock_total = stock_total_result['Stock_Total'] if stock_total_result else 0
                
                if stock_total < producto['cantidad']:
                    return jsonify({
                        'success': False, 
                        'message': f"Stock insuficiente para {producto['nombre']}. Disponible: {stock_total}"
                    }), 400
                
                # Obtener los tres precios del producto
                sql_precio = """
                SELECT 
                    Precio_Mercado,
                    Precio_Mayorista,
                    Precio_Ruta
                FROM productos 
                WHERE ID_Producto = %s AND Estado = 'activo'
                """
                cursor.execute(sql_precio, (producto['id'],))
                producto_info = cursor.fetchone()
                
                if not producto_info:
                    return jsonify({
                        'success': False, 
                        'message': f"Producto ID {producto['id']} no encontrado o inactivo"
                    }), 400
                
                # Determinar qué precio usar según el perfil del cliente
                if perfil_cliente == 'Ruta':
                    precio_unitario = producto_info['Precio_Ruta'] or 0
                elif perfil_cliente == 'Mayorista':
                    precio_unitario = producto_info['Precio_Mayorista'] or 0
                elif perfil_cliente == 'Mercado':
                    precio_unitario = producto_info['Precio_Mercado'] or 0
                elif perfil_cliente == 'Especial':
                    # Para clientes especiales, usamos precio de mercado por defecto
                    # pero podría ser un precio personalizado si se implementa después
                    precio_unitario = producto_info['Precio_Mercado'] or 0
                else:
                    # Por defecto, precio de mercado
                    precio_unitario = producto_info['Precio_Mercado'] or 0
                
                # Validar que el precio sea mayor a 0
                if precio_unitario <= 0:
                    return jsonify({
                        'success': False,
                        'message': f"El producto {producto['nombre']} no tiene precio válido para el perfil {perfil_cliente}"
                    }), 400
                
                # Calcular subtotal
                subtotal = precio_unitario * producto['cantidad']
                
                # Insertar detalle del pedido
                sql_detalle = """
                INSERT INTO detalle_pedidos (
                    ID_Pedido, ID_Producto, Precio_Unitario, 
                    Cantidad, Subtotal
                )
                VALUES (%s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql_detalle, (
                    pedido_id,
                    producto['id'],
                    precio_unitario,
                    producto['cantidad'],
                    subtotal
                ))
                
                # Descontar stock de las bodegas (FIFO)
                cantidad_a_descontar = producto['cantidad']
                
                sql_bodegas_stock = """
                SELECT ID_Bodega, Existencias 
                FROM inventario_bodega 
                WHERE ID_Producto = %s AND Existencias > 0
                ORDER BY ID_Bodega
                """
                cursor.execute(sql_bodegas_stock, (producto['id'],))
                bodegas_stock = cursor.fetchall()
                
                for bodega in bodegas_stock:
                    if cantidad_a_descontar <= 0:
                        break
                    
                    stock_disponible = bodega['Existencias']
                    id_bodega = bodega['ID_Bodega']
                    
                    if stock_disponible >= cantidad_a_descontar:
                        sql_update = """
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                        """
                        cursor.execute(sql_update, (cantidad_a_descontar, id_bodega, producto['id']))
                        cantidad_a_descontar = 0
                    else:
                        sql_update = """
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                        """
                        cursor.execute(sql_update, (stock_disponible, id_bodega, producto['id']))
                        cantidad_a_descontar -= stock_disponible
                
                if cantidad_a_descontar > 0:
                    raise Exception(f"No se pudo descontar todo el stock para el producto {producto['id']}")
            
            # Generar la URL para redirigir al detalle del pedido
            redirect_url = url_for('admin.ver_pedido', id_pedido=pedido_id)
            
            # Log para debugging
            print(f"✅ Pedido #{pedido_id} creado exitosamente con perfil {perfil_cliente}")
            print(f"   Redirigiendo a: {redirect_url}")
            
            return jsonify({
                'success': True, 
                'message': 'Pedido creado exitosamente',
                'pedido_id': pedido_id,
                'redirect_url': redirect_url,
                'perfil_cliente': perfil_cliente
            })
            
    except Exception as e:
        print(f" Error al crear pedido: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/ventas/nuevo-pedido-consolidado', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("NUEVO_PEDIDO_CONSOLIDADO")
def nuevo_pedido_consolidado():
    """
    Crear un pedido consolidado - Carga total para una ruta específica
    Los consolidados SIEMPRE usan Precio_Ruta de los productos
    Independientemente del perfil del cliente (no aplica porque no hay cliente)
    """
    try:
        if request.method == 'POST':
            data = request.get_json()
            user = current_user.id
            
            # Validar datos requeridos
            if not data.get('empresa_id'):
                return jsonify({'success': False, 'message': 'Se requiere una empresa'}), 400
            
            if not data.get('id_ruta'):
                return jsonify({'success': False, 'message': 'Se requiere una ruta para el pedido consolidado'}), 400
            
            if not data.get('productos') or len(data['productos']) == 0:
                return jsonify({'success': False, 'message': 'Se requiere al menos un producto'}), 400
            
            fecha = data.get('fecha')
            observacion = data.get('observacion', '')
            prioridad = data.get('prioridad', 'Normal')
            id_ruta = data.get('id_ruta')
            
            with get_db_cursor() as cursor:
                # Verificar que la ruta existe y está activa
                cursor.execute("""
                    SELECT ID_Ruta, Nombre_Ruta, Descripcion 
                    FROM rutas 
                    WHERE ID_Ruta = %s AND Estado = 'Activa'
                """, (id_ruta,))
                ruta = cursor.fetchone()
                
                if not ruta:
                    return jsonify({'success': False, 'message': 'Ruta no encontrada o inactiva'}), 400
                
                # Crear el pedido consolidado - SIN CLIENTE, CON RUTA OBLIGATORIA
                sql_pedido = """
                INSERT INTO pedidos (
                    Fecha, ID_Cliente, ID_Empresa, ID_Ruta,
                    ID_Usuario_Creacion, Estado, Observacion, 
                    Tipo_Entrega, Prioridad, Tipo_Pedido, Es_Pedido_Ruta
                )
                VALUES (%s, NULL, %s, %s, %s, 'Pendiente', %s, 'Entrega a domicilio', %s, 'Consolidado', 'SI')
                """
                
                cursor.execute(sql_pedido, (
                    fecha,
                    data['empresa_id'],
                    id_ruta,
                    user,
                    observacion,
                    prioridad
                ))
                
                pedido_id = cursor.lastrowid
                
                # Agregar productos consolidados
                for producto in data['productos']:
                    if producto['cantidad'] <= 0:
                        return jsonify({
                            'success': False, 
                            'message': f"La cantidad para {producto['nombre']} debe ser mayor a 0"
                        }), 400
                    
                    # Verificar que el producto existe y tiene precio de ruta
                    cursor.execute("""
                        SELECT Precio_Ruta 
                        FROM productos 
                        WHERE ID_Producto = %s AND Estado = 'activo'
                    """, (producto['id'],))
                    
                    producto_info = cursor.fetchone()
                    if not producto_info:
                        return jsonify({
                            'success': False,
                            'message': f"Producto {producto['nombre']} no encontrado o inactivo"
                        }), 400
                    
                    if producto_info['Precio_Ruta'] is None or producto_info['Precio_Ruta'] <= 0:
                        return jsonify({
                            'success': False,
                            'message': f"Producto {producto['nombre']} no tiene precio de ruta definido"
                        }), 400
                    
                    # Insertar en pedidos_consolidados_productos
                    sql_consolidado = """
                    INSERT INTO pedidos_consolidados_productos (
                        ID_Pedido, ID_Producto, Cantidad_Total, ID_Usuario_Creacion
                    )
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        Cantidad_Total = Cantidad_Total + VALUES(Cantidad_Total)
                    """
                    
                    cursor.execute(sql_consolidado, (
                        pedido_id,
                        producto['id'],
                        producto['cantidad'],
                        user
                    ))
                
                return jsonify({
                    'success': True,
                    'message': f'Pedido consolidado creado para ruta: {ruta["Nombre_Ruta"]}',
                    'pedido_id': pedido_id,
                    'redirect_url': url_for('admin.ver_pedido', id_pedido=pedido_id)
                })
        
        # GET: Mostrar formulario
        with get_db_cursor(True) as cursor:
            # Obtener empresas
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa 
                FROM empresa 
                ORDER BY Nombre_Empresa
            """)
            empresas = cursor.fetchall()
            
            # Obtener rutas activas
            cursor.execute("""
                SELECT 
                    r.ID_Ruta,
                    r.Nombre_Ruta,
                    r.Descripcion,
                    COUNT(c.ID_Cliente) as Total_clientes
                FROM rutas r
                LEFT JOIN clientes c ON r.ID_Ruta = c.ID_Ruta AND c.Estado = 'ACTIVO'
                WHERE r.Estado = 'Activa'
                GROUP BY r.ID_Ruta, r.Nombre_Ruta, r.Descripcion
                ORDER BY r.Nombre_Ruta
            """)
            rutas = cursor.fetchall()
            
            prioridades = ['Urgente', 'Normal', 'Bajo']
            
            return render_template('admin/ventas/pedidos/nuevo_pedido_consolidado.html',
                                 empresas=empresas,
                                 rutas=rutas,
                                 prioridades=prioridades,
                                 now=datetime.now().date())
            
    except Exception as e:
        print(f"Error en nuevo_pedido_consolidado: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if request.method == 'POST':
            return jsonify({'success': False, 'message': str(e)}), 500
        else:
            flash(f"Error al cargar formulario de pedido consolidado: {e}", "error")
            return redirect(url_for('admin.admin_pedidos_venta'))


@admin_bp.route('/admin/ventas/distribuir-carga/<int:id_pedido>')
@admin_or_bodega_required
def distribuir_carga(id_pedido):
    """
    Muestra el formulario de distribución de carga consolidada a vendedores
    Solo para pedidos consolidados en estado Pendiente
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Pedido,
                    p.Fecha,
                    p.Estado,
                    p.Tipo_Pedido,
                    p.ID_Ruta,
                    r.Nombre_Ruta,
                    e.ID_Empresa
                FROM pedidos p
                LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.ID_Pedido = %s AND p.Tipo_Pedido = 'Consolidado'
            """, (id_pedido,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            if not pedido['ID_Ruta']:
                flash('El pedido no tiene una ruta asignada', 'error')
                return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 2. OBTENER VENDEDORES ACTIVOS DE LA RUTA
            # ============================================
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
            """, (pedido['ID_Ruta'],))
            
            vendedores = cursor.fetchall()
            
            # ============================================
            # 3. OBTENER PRODUCTOS DEL CONSOLIDADO
            # ============================================
            cursor.execute("""
                SELECT 
                    pcp.ID_Producto,
                    pcp.Cantidad_Total,
                    pr.Descripcion as Nombre_Producto,
                    pr.COD_Producto,
                    pr.Precio_Ruta as Precio_Venta
                FROM pedidos_consolidados_productos pcp
                INNER JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                WHERE pcp.ID_Pedido = %s
                ORDER BY pr.Descripcion
            """, (id_pedido,))
            
            productos = cursor.fetchall()
            
            return render_template('admin/ventas/pedidos/distribuir_carga.html',
                                 pedido=pedido,
                                 vendedores=vendedores,
                                 productos=productos,
                                 now=datetime.now())
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar datos: {str(e)}', 'error')
        return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))


@admin_bp.route('/admin/ventas/procesar-carga-consolidada/<int:id_pedido>', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("PROCESAR_CARGA_CONSOLIDADA")
def procesar_carga_consolidada(id_pedido):
    """
    Procesa la distribución de carga consolidada a vendedores
    - Crea movimientos de salida de bodega principal
    - Crea movimientos de entrada en rutas de vendedores
    - Actualiza inventario de rutas
    - SOLO CAMBIA EL ESTADO, NO ELIMINA DATOS
    """
    try:
        distribucion = []
        index = 0
        
        while True:
            id_vendedor = request.form.get(f'distribucion[{index}][id_vendedor]')
            id_producto = request.form.get(f'distribucion[{index}][id_producto]')
            cantidad = request.form.get(f'distribucion[{index}][cantidad]')
            
            if id_vendedor is None or id_producto is None or cantidad is None:
                break
                
            if float(cantidad) > 0:
                distribucion.append({
                    'id_vendedor': int(id_vendedor),
                    'id_producto': int(id_producto),
                    'cantidad': float(cantidad)
                })
            index += 1
        
        if not distribucion:
            flash('Debe asignar al menos un producto a un vendedor', 'error')
            return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
        
        with get_db_cursor() as cursor:
            # ============================================
            # 2. VERIFICAR PEDIDO
            # ============================================
            cursor.execute("""
                SELECT 
                    p.ID_Pedido,
                    p.ID_Ruta,
                    p.Estado,
                    r.Nombre_Ruta,
                    e.ID_Empresa,
                    b.ID_Bodega as Bodega_Origen
                FROM pedidos p
                LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN bodegas b ON b.ID_Empresa = e.ID_Empresa AND b.Estado = 'activa'
                WHERE p.ID_Pedido = %s AND p.Tipo_Pedido = 'Consolidado'
                LIMIT 1
            """, (id_pedido,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            if pedido['Estado'] != 'Pendiente':
                flash(f'El pedido debe estar Pendiente, no {pedido["Estado"]}', 'error')
                return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            if not pedido['ID_Ruta']:
                flash('El pedido no tiene una ruta asignada', 'error')
                return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 3. VERIFICAR VENDEDORES
            # ============================================
            vendedores_ids = list(set([item['id_vendedor'] for item in distribucion]))
            placeholders = ','.join(['%s'] * len(vendedores_ids))
            
            query_vendedores = f"""
                SELECT ID_Asignacion, ID_Usuario
                FROM asignacion_vendedores
                WHERE ID_Asignacion IN ({placeholders})
                AND Estado = 'Activa'
                AND Fecha_Asignacion = CURDATE()
            """
            cursor.execute(query_vendedores, vendedores_ids)
            
            vendedores_validos = cursor.fetchall()
            vendedores_dict = {v['ID_Asignacion']: v for v in vendedores_validos}
            
            for item in distribucion:
                if item['id_vendedor'] not in vendedores_dict:
                    flash('Uno o más vendedores no tienen asignación activa hoy', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 4. VERIFICAR PRODUCTOS
            # ============================================
            productos_ids = list(set([item['id_producto'] for item in distribucion]))
            placeholders = ','.join(['%s'] * len(productos_ids))
            
            query_productos = f"""
                SELECT 
                    pcp.ID_Producto,
                    pcp.Cantidad_Total,
                    pr.Precio_Ruta as Precio_Venta,
                    COALESCE(ib.Existencias, 0) as Stock_Disponible
                FROM pedidos_consolidados_productos pcp
                JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                LEFT JOIN inventario_bodega ib ON ib.ID_Bodega = %s AND ib.ID_Producto = pcp.ID_Producto
                WHERE pcp.ID_Pedido = %s
                AND pcp.ID_Producto IN ({placeholders})
            """
            
            params = [pedido['Bodega_Origen'], id_pedido] + productos_ids
            cursor.execute(query_productos, params)
            
            productos_consolidados = cursor.fetchall()
            productos_dict = {}
            
            for p in productos_consolidados:
                productos_dict[p['ID_Producto']] = {
                    'ID_Producto': p['ID_Producto'],
                    'Cantidad_Total': float(p['Cantidad_Total']),
                    'Precio_Venta': float(p['Precio_Venta']),
                    'Stock_Disponible': float(p['Stock_Disponible'])
                }
            
            from collections import defaultdict
            total_por_producto = defaultdict(float)
            
            for item in distribucion:
                total_por_producto[item['id_producto']] += item['cantidad']
            
            for id_producto, cantidad_solicitada in total_por_producto.items():
                if id_producto not in productos_dict:
                    flash('Producto no válido', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
                
                producto = productos_dict[id_producto]
                
                if cantidad_solicitada > producto['Cantidad_Total']:
                    flash(f'Cantidad excede el consolidado', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
                
                if cantidad_solicitada > producto['Stock_Disponible']:
                    flash(f'Stock insuficiente en bodega', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 5. MOVIMIENTO DE SALIDA DE BODEGA PRINCIPAL
            # ============================================
            TRASLADO_SALIDA = 12
            TRASLADO_ENTRADA = 13
            
            cursor.execute("""
                INSERT INTO movimientos_inventario (
                    ID_TipoMovimiento, ID_Bodega, Fecha, Observacion,
                    ID_Empresa, ID_Usuario_Creacion, Estado, ID_Pedido_Origen
                )
                VALUES (%s, %s, CURDATE(), %s, %s, %s, 'Activa', %s)
            """, (
                TRASLADO_SALIDA,
                pedido['Bodega_Origen'],
                f'SALIDA POR CARGA #{id_pedido} - {pedido["Nombre_Ruta"]}',
                pedido['ID_Empresa'],
                current_user.id,
                id_pedido
            ))
            
            movimiento_salida_id = cursor.lastrowid
            
            for id_producto, cantidad_total in total_por_producto.items():
                producto = productos_dict[id_producto]
                
                cursor.execute("""
                    UPDATE inventario_bodega 
                    SET Existencias = Existencias - %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (cantidad_total, pedido['Bodega_Origen'], id_producto))
                
                subtotal = cantidad_total * producto['Precio_Venta']
                
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario (
                        ID_Movimiento, ID_Producto, Cantidad,
                        Costo_Unitario, Precio_Unitario, Subtotal,
                        ID_Usuario_Creacion
                    )
                    VALUES (%s, %s, %s, 0, %s, %s, %s)
                """, (
                    movimiento_salida_id,
                    id_producto,
                    cantidad_total,
                    producto['Precio_Venta'],
                    subtotal,
                    current_user.id
                ))
            
            # ============================================
            # 6. DISTRIBUIR A VENDEDORES
            # ============================================
            distribucion_por_vendedor = defaultdict(list)
            
            for item in distribucion:
                distribucion_por_vendedor[item['id_vendedor']].append({
                    'id_producto': item['id_producto'],
                    'cantidad': item['cantidad'],
                    'precio': productos_dict[item['id_producto']]['Precio_Venta']
                })
            
            for id_vendedor, productos_vendedor in distribucion_por_vendedor.items():
                total_items = sum([p['cantidad'] for p in productos_vendedor])
                total_productos = len(productos_vendedor)
                total_subtotal = sum([p['cantidad'] * p['precio'] for p in productos_vendedor])
                
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera (
                        ID_Asignacion, 
                        ID_TipoMovimiento, 
                        Fecha_Movimiento,
                        ID_Usuario_Registra, 
                        Documento_Numero, 
                        ID_Pedido,
                        Total_Productos, 
                        Total_Items, 
                        Total_Subtotal,
                        ID_Empresa, 
                        Estado
                    )
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_vendedor,
                    TRASLADO_ENTRADA,
                    current_user.id,
                    f'CARGA-{id_pedido}',
                    id_pedido,
                    total_productos,
                    total_items,
                    total_subtotal,
                    pedido['ID_Empresa']
                ))
                
                movimiento_ruta_id = cursor.lastrowid
                
                for producto in productos_vendedor:
                    subtotal = producto['cantidad'] * producto['precio']
                    
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle (
                            ID_Movimiento, 
                            ID_Producto, 
                            Cantidad,
                            Precio_Unitario, 
                            Subtotal
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        movimiento_ruta_id,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['precio'],
                        subtotal
                    ))
                
                for producto in productos_vendedor:
                    cursor.execute("""
                        INSERT INTO inventario_ruta (
                            ID_Asignacion, 
                            ID_Producto, 
                            Cantidad, 
                            Fecha_Actualizacion
                        )
                        VALUES (%s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            Cantidad = Cantidad + VALUES(Cantidad),
                            Fecha_Actualizacion = NOW()
                    """, (
                        id_vendedor,
                        producto['id_producto'],
                        producto['cantidad']
                    ))
            
            # ============================================
            # 7. SOLO CAMBIAR EL ESTADO - NO ELIMINAR NADA
            # ============================================
            # Cambiar el estado del pedido a 'Entregado'
            cursor.execute("""
                UPDATE pedidos 
                SET Estado = 'Entregado'
                WHERE ID_Pedido = %s
            """, (id_pedido,))
            
            # ⚠️ IMPORTANTE: NO se elimina nada de pedidos_consolidados_productos
            # Los datos originales del consolidado permanecen intactos
            
            flash(f'✅ Carga #{id_pedido} procesada exitosamente - Pedido marcado como Entregado', 'success')
            
            return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))


@admin_bp.route('/admin/ventas/pedidos-venta')
@admin_or_bodega_required
@bitacora_decorator("PEDIDOS-VENTA")
def admin_pedidos_venta():
    """
    Listado principal de pedidos (individuales y consolidados)
    """
    try:
        with get_db_cursor(True) as cursor:
            # 🔑 OBTENER EL ROL DEL USUARIO ACTUAL DESDE LA BASE DE DATOS
            # Usar el ID correcto - normalmente es 'id' o 'get_id()'
            user_id = current_user.get_id() if hasattr(current_user, 'get_id') else current_user.id
            
            print(f"🔍 Debug - User ID: {user_id}")
            print(f"🔍 Debug - Current User atributos: {dir(current_user)}")
            
            cursor.execute("""
                SELECT r.Nombre_Rol 
                FROM usuarios u
                INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Usuario = %s
            """, (user_id,))
            
            rol_result = cursor.fetchone()
            
            if not rol_result:
                flash("Error: No se pudo determinar el rol del usuario", "error")
                return redirect(url_for('admin.admin_dashboard'))
            
            # Determinar si es Bodega
            es_rol_bodega = (rol_result['Nombre_Rol'] == 'Bodega')
            
            # DEBUG
            print(f"🔍 Usuario ID: {user_id}")
            print(f"🔍 Rol obtenido: {rol_result['Nombre_Rol']}")
            print(f"🔍 ¿Es rol bodega? {es_rol_bodega}")
            
            # CONSULTA PRINCIPAL
            sql = """
            SELECT 
                p.ID_Pedido,
                p.Fecha,
                p.Estado,
                p.Tipo_Entrega,
                p.Observacion,
                p.Fecha_Creacion,
                p.Prioridad,
                p.Tipo_Pedido,
                p.Es_Pedido_Ruta,
                p.ID_Ruta,
                r.Nombre_Ruta,
                r.Descripcion as Descripcion_Ruta,
                c.ID_Cliente,
                c.Nombre as Nombre_Cliente,
                c.Telefono as Telefono_Cliente,
                c.Direccion as Direccion_Cliente,
                c.RUC_CEDULA as Documento_Cliente,
                c.tipo_cliente as Tipo_Cliente,
                c.perfil_cliente as Perfil_Cliente,
                c.Estado as Estado_Cliente,
                e.Nombre_Empresa,
                u.NombreUsuario as Usuario_Creacion,
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        SELECT COALESCE(SUM(pcp.Cantidad_Total), 0)
                        FROM pedidos_consolidados_productos pcp
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(dp.Cantidad), 0)
                END as Total_Items,
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        SELECT COALESCE(SUM(pcp.Cantidad_Total * pr2.Precio_Ruta), 0)
                        FROM pedidos_consolidados_productos pcp
                        LEFT JOIN productos pr2 ON pcp.ID_Producto = pr2.ID_Producto
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(
                        dp.Cantidad * 
                        CASE c.perfil_cliente
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END
                    ), 0)
                END as Total_Pedido,
                COUNT(DISTINCT CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN pcp2.ID_Pedido_Consolidado_Producto 
                    ELSE dp.ID_Detalle_Pedido 
                END) as Numero_Items
            FROM pedidos p
            LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
            LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
            LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
            LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
            LEFT JOIN detalle_pedidos dp ON p.ID_Pedido = dp.ID_Pedido AND p.Tipo_Pedido != 'Consolidado'
            LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
            LEFT JOIN pedidos_consolidados_productos pcp2 ON p.ID_Pedido = pcp2.ID_Pedido AND p.Tipo_Pedido = 'Consolidado'
            WHERE 1=1
            """
            
            # Filtro para clientes activos
            sql += " AND (c.ID_Cliente IS NULL OR c.Estado = 'ACTIVO')"
            
            # 🎯 APLICAR FILTRO SEGÚN EL ROL
            if es_rol_bodega:
                # Mostrar pedidos de los últimos 7 días para Bodega
                sql += " AND DATE(p.Fecha) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
                print("⚠️ Aplicando filtro: Mostrando pedidos de los últimos 7 días para Bodega")
            
            # Group by y Order by
            sql += """
            GROUP BY 
                p.ID_Pedido, p.Fecha, p.Estado, p.Tipo_Entrega, p.Observacion,
                p.Fecha_Creacion, p.Prioridad, p.Tipo_Pedido, p.Es_Pedido_Ruta,
                p.ID_Ruta, r.Nombre_Ruta, r.Descripcion,
                c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                c.tipo_cliente, c.perfil_cliente, c.Estado, e.Nombre_Empresa, u.NombreUsuario
            ORDER BY 
                p.Fecha DESC,
                p.ID_Pedido DESC
            """
            
            cursor.execute(sql)
            pedidos = cursor.fetchall()
            
            # DEBUG
            print(f"📊 Total pedidos encontrados: {len(pedidos)}")
            if pedidos:
                for idx, pedido in enumerate(pedidos[:3]):
                    print(f"   Pedido {idx+1}: ID={pedido.get('ID_Pedido')}, Fecha={pedido.get('Fecha')}")
            
            # Obtener opciones de filtro
            estados = ['Pendiente', 'Aprobado', 'Entregado', 'Cancelado']
            if es_rol_bodega:
                estados.insert(2, 'En Proceso')
            
            tipos_entrega = ['Retiro en local', 'Entrega a domicilio']
            tipos_cliente = ['Comun', 'Especial']
            prioridades = ['Urgente', 'Normal', 'Bajo']
            tipos_pedido = ['Individual', 'Consolidado']
            opciones_ruta = ['SI', 'NO']
            perfiles_cliente = ['Ruta', 'Mayorista', 'Mercado', 'Especial']
            
            # Obtener lista de rutas
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE Estado = 'Activa' 
                ORDER BY Nombre_Ruta
            """)
            rutas = cursor.fetchall()
            
            # Estadísticas
            stats = None
            if es_rol_bodega and pedidos:
                fecha_hoy = datetime.now().strftime('%Y-%m-%d')
                pedidos_hoy = [p for p in pedidos if p.get('Fecha') and p['Fecha'].strftime('%Y-%m-%d') == fecha_hoy]
                stats = {
                    'total_hoy': len(pedidos_hoy),
                    'urgentes_hoy': len([p for p in pedidos_hoy if p.get('Prioridad') == 'Urgente']),
                    'aprobados_hoy': len([p for p in pedidos_hoy if p.get('Estado') == 'Aprobado']),
                    'pendientes_hoy': len([p for p in pedidos_hoy if p.get('Estado') == 'Pendiente']),
                    'consolidados_hoy': len([p for p in pedidos_hoy if p.get('Tipo_Pedido') == 'Consolidado']),
                    'fecha_hoy': fecha_hoy
                }
            
            return render_template('admin/ventas/pedidos/pedidos_venta.html',
                                 pedidos=pedidos,
                                 estados=estados,
                                 tipos_entrega=tipos_entrega,
                                 tipos_cliente=tipos_cliente,
                                 prioridades=prioridades,
                                 tipos_pedido=tipos_pedido,
                                 opciones_ruta=opciones_ruta,
                                 rutas=rutas,
                                 perfiles_cliente=perfiles_cliente,
                                 es_rol_bodega=es_rol_bodega,
                                 stats=stats,
                                 filtros_aplicados=None,
                                 now=datetime.now())
            
    except Exception as e:
        print(f" Error en admin_pedidos_venta: {str(e)}")
        traceback.print_exc()
        flash(f"Error al cargar pedidos de venta: {str(e)}", "error")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/ventas/pedidos-venta/filtrar', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("FILTRAR-PEDIDOS-VENTA")
def filtrar_pedidos():
    """
    Filtro avanzado para el listado de pedidos
    """
    try:
        with get_db_cursor(True) as cursor:
            # 🔑 OBTENER EL ROL DEL USUARIO ACTUAL
            # Usar el ID correcto
            user_id = current_user.get_id() if hasattr(current_user, 'get_id') else current_user.id
            
            cursor.execute("""
                SELECT r.Nombre_Rol 
                FROM usuarios u
                INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Usuario = %s
            """, (user_id,))
            
            rol_result = cursor.fetchone()
            
            if not rol_result:
                flash("Error: No se pudo determinar el rol del usuario", "error")
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            es_rol_bodega = (rol_result['Nombre_Rol'] == 'Bodega')
            
            # Obtener parámetros del formulario
            estado = request.form.get('estado', 'todos')
            fecha_inicio = request.form.get('fecha_inicio')
            fecha_fin = request.form.get('fecha_fin')
            tipo_entrega = request.form.get('tipo_entrega', 'todos')
            tipo_cliente = request.form.get('tipo_cliente', 'todos')
            prioridad = request.form.get('prioridad', 'todos')
            tipo_pedido = request.form.get('tipo_pedido', 'todos')
            es_pedido_ruta = request.form.get('es_pedido_ruta', 'todos')
            id_ruta = request.form.get('id_ruta', 'todos')
            perfil_cliente = request.form.get('perfil_cliente', 'todos')
            documento_cliente = request.form.get('documento_cliente', '').strip()
            nombre_cliente = request.form.get('nombre_cliente', '').strip()
            
            # Construir condiciones
            condiciones = ["(c.ID_Cliente IS NULL OR c.Estado = 'ACTIVO')"]
            parametros = []
            
            # Si es rol Bodega y NO se aplicaron filtros de fecha, filtrar últimos 7 días
            if es_rol_bodega and not fecha_inicio and not fecha_fin:
                condiciones.append("DATE(p.Fecha) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)")
            
            # Aplicar filtros
            if estado != 'todos':
                condiciones.append("p.Estado = %s")
                parametros.append(estado)
            
            if fecha_inicio:
                condiciones.append("DATE(p.Fecha) >= %s")
                parametros.append(fecha_inicio)
            
            if fecha_fin:
                condiciones.append("DATE(p.Fecha) <= %s")
                parametros.append(fecha_fin)
            
            if tipo_entrega != 'todos':
                condiciones.append("p.Tipo_Entrega = %s")
                parametros.append(tipo_entrega)
            
            if tipo_cliente != 'todos':
                condiciones.append("c.tipo_cliente = %s")
                parametros.append(tipo_cliente)
            
            if perfil_cliente != 'todos':
                condiciones.append("c.perfil_cliente = %s")
                parametros.append(perfil_cliente)
            
            if prioridad != 'todos':
                condiciones.append("p.Prioridad = %s")
                parametros.append(prioridad)
            
            if tipo_pedido != 'todos':
                condiciones.append("p.Tipo_Pedido = %s")
                parametros.append(tipo_pedido)
            
            if es_pedido_ruta != 'todos':
                condiciones.append("p.Es_Pedido_Ruta = %s")
                parametros.append(es_pedido_ruta)
            
            if id_ruta != 'todos' and id_ruta.isdigit():
                condiciones.append("p.ID_Ruta = %s")
                parametros.append(int(id_ruta))
            
            if documento_cliente:
                condiciones.append("c.RUC_CEDULA LIKE %s")
                parametros.append(f"%{documento_cliente}%")
            
            if nombre_cliente:
                condiciones.append("c.Nombre LIKE %s")
                parametros.append(f"%{nombre_cliente}%")
            
            # Construir consulta SQL (la misma que en admin_pedidos_venta)
            sql = """
            SELECT 
                p.ID_Pedido,
                p.Fecha,
                p.Estado,
                p.Tipo_Entrega,
                p.Observacion,
                p.Fecha_Creacion,
                p.Prioridad,
                p.Tipo_Pedido,
                p.Es_Pedido_Ruta,
                p.ID_Ruta,
                r.Nombre_Ruta,
                r.Descripcion as Descripcion_Ruta,
                c.ID_Cliente,
                c.Nombre as Nombre_Cliente,
                c.Telefono as Telefono_Cliente,
                c.Direccion as Direccion_Cliente,
                c.RUC_CEDULA as Documento_Cliente,
                c.tipo_cliente as Tipo_Cliente,
                c.perfil_cliente as Perfil_Cliente,
                c.Estado as Estado_Cliente,
                e.Nombre_Empresa,
                u.NombreUsuario as Usuario_Creacion,
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        SELECT COALESCE(SUM(pcp.Cantidad_Total), 0)
                        FROM pedidos_consolidados_productos pcp
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(dp.Cantidad), 0)
                END as Total_Items,
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        SELECT COALESCE(SUM(pcp.Cantidad_Total * pr2.Precio_Ruta), 0)
                        FROM pedidos_consolidados_productos pcp
                        LEFT JOIN productos pr2 ON pcp.ID_Producto = pr2.ID_Producto
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(
                        dp.Cantidad * 
                        CASE c.perfil_cliente
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END
                    ), 0)
                END as Total_Pedido,
                COUNT(DISTINCT CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN pcp2.ID_Pedido_Consolidado_Producto 
                    ELSE dp.ID_Detalle_Pedido 
                END) as Numero_Items
            FROM pedidos p
            LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
            LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
            LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
            LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
            LEFT JOIN detalle_pedidos dp ON p.ID_Pedido = dp.ID_Pedido AND p.Tipo_Pedido != 'Consolidado'
            LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
            LEFT JOIN pedidos_consolidados_productos pcp2 ON p.ID_Pedido = pcp2.ID_Pedido AND p.Tipo_Pedido = 'Consolidado'
            WHERE 1=1
            """
            
            if condiciones:
                sql += " AND " + " AND ".join(condiciones)
            
            sql += """
            GROUP BY 
                p.ID_Pedido, p.Fecha, p.Estado, p.Tipo_Entrega, p.Observacion,
                p.Fecha_Creacion, p.Prioridad, p.Tipo_Pedido, p.Es_Pedido_Ruta,
                p.ID_Ruta, r.Nombre_Ruta, r.Descripcion,
                c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                c.tipo_cliente, c.perfil_cliente, c.Estado, e.Nombre_Empresa, u.NombreUsuario
            ORDER BY 
                p.Fecha DESC,
                p.ID_Pedido DESC
            """
            
            cursor.execute(sql, tuple(parametros))
            pedidos = cursor.fetchall()
            
            # Obtener opciones de filtro
            estados = ['Pendiente', 'Aprobado', 'Entregado', 'Cancelado']
            if es_rol_bodega:
                estados.insert(2, 'En Proceso')
            
            tipos_entrega = ['Retiro en local', 'Entrega a domicilio']
            tipos_cliente = ['Comun', 'Especial']
            prioridades = ['Urgente', 'Normal', 'Bajo']
            tipos_pedido = ['Individual', 'Consolidado']
            opciones_ruta = ['SI', 'NO']
            perfiles_cliente = ['Ruta', 'Mayorista', 'Mercado', 'Especial']
            
            # Obtener rutas
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE Estado = 'Activa' 
                ORDER BY Nombre_Ruta
            """)
            rutas = cursor.fetchall()
            
            # Estadísticas
            stats = None
            if es_rol_bodega and pedidos:
                fecha_hoy = datetime.now().strftime('%Y-%m-%d')
                pedidos_hoy = [p for p in pedidos if p.get('Fecha') and p['Fecha'].strftime('%Y-%m-%d') == fecha_hoy]
                stats = {
                    'total_hoy': len(pedidos_hoy),
                    'urgentes_hoy': len([p for p in pedidos_hoy if p.get('Prioridad') == 'Urgente']),
                    'aprobados_hoy': len([p for p in pedidos_hoy if p.get('Estado') == 'Aprobado']),
                    'pendientes_hoy': len([p for p in pedidos_hoy if p.get('Estado') == 'Pendiente']),
                    'consolidados_hoy': len([p for p in pedidos_hoy if p.get('Tipo_Pedido') == 'Consolidado']),
                    'fecha_hoy': fecha_hoy
                }
            
            filtros_aplicados = {
                'estado': estado if estado != 'todos' else None,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'tipo_entrega': tipo_entrega if tipo_entrega != 'todos' else None,
                'tipo_cliente': tipo_cliente if tipo_cliente != 'todos' else None,
                'perfil_cliente': perfil_cliente if perfil_cliente != 'todos' else None,
                'prioridad': prioridad if prioridad != 'todos' else None,
                'tipo_pedido': tipo_pedido if tipo_pedido != 'todos' else None,
                'es_pedido_ruta': es_pedido_ruta if es_pedido_ruta != 'todos' else None,
                'id_ruta': id_ruta if id_ruta != 'todos' else None,
                'documento_cliente': documento_cliente if documento_cliente else None,
                'nombre_cliente': nombre_cliente if nombre_cliente else None
            }
            
            return render_template('admin/ventas/pedidos/pedidos_venta.html',
                                 pedidos=pedidos,
                                 estados=estados,
                                 tipos_entrega=tipos_entrega,
                                 tipos_cliente=tipos_cliente,
                                 prioridades=prioridades,
                                 tipos_pedido=tipos_pedido,
                                 opciones_ruta=opciones_ruta,
                                 rutas=rutas,
                                 perfiles_cliente=perfiles_cliente,
                                 es_rol_bodega=es_rol_bodega,
                                 stats=stats,
                                 filtros_aplicados=filtros_aplicados,
                                 now=datetime.now())
            
    except Exception as e:
        print(f" Error en filtrar_pedidos: {str(e)}")
        traceback.print_exc()
        flash(f"Error al filtrar pedidos: {str(e)}", "error")
        return redirect(url_for('admin.admin_pedidos_venta'))


@admin_bp.route('/ventas/pedido-venta/<int:id_pedido>')
@admin_or_bodega_required
def ver_pedido(id_pedido):
    """
    Ver detalle completo de un pedido
    - Individuales: muestra el precio según perfil_cliente del cliente
    - Consolidados: siempre muestra Precio_Ruta
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener información del pedido
            sql_pedido = """
            SELECT 
                p.*,
                c.ID_Cliente,
                c.Nombre as Nombre_Cliente,
                c.Telefono as Telefono_Cliente,
                c.Direccion as Direccion_Cliente,
                c.RUC_CEDULA as Documento_Cliente,
                c.tipo_cliente as Tipo_Cliente,
                c.perfil_cliente as Perfil_Cliente,
                c.Estado as Estado_Cliente,
                e.Nombre_Empresa,
                e.Direccion as Direccion_Empresa,
                e.Telefono as Telefono_Empresa,
                e.RUC as RUC_Empresa,
                u.NombreUsuario as Usuario_Creacion,
                r.Nombre_Ruta,
                r.Descripcion as Descripcion_Ruta
            FROM pedidos p
            LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
            LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
            LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
            LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
            WHERE p.ID_Pedido = %s
            """
            
            cursor.execute(sql_pedido, (id_pedido,))
            pedido = cursor.fetchone()
            
            if not pedido:
                flash("Pedido no encontrado", "error")
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            # Obtener detalles según tipo de pedido
            if pedido['Tipo_Pedido'] == 'Consolidado':
                # PARA CONSOLIDADOS: SIEMPRE usar Precio_Ruta
                cursor.execute("""
                    SELECT 
                        pcp.ID_Pedido_Consolidado_Producto,
                        pcp.ID_Producto,
                        pcp.Cantidad_Total as Cantidad,
                        pcp.Fecha_Creacion,
                        u.NombreUsuario as Usuario_Creacion,
                        pr.COD_Producto,
                        pr.Descripcion as Nombre_Producto,
                        pr.Precio_Ruta as Precio_Unitario,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        pr.Unidad_Medida,
                        um.Descripcion as Unidad_Nombre,
                        um.Abreviatura as Unidad_Abreviatura,
                        cat.Descripcion as Categoria,
                        (pcp.Cantidad_Total * pr.Precio_Ruta) as Subtotal
                    FROM pedidos_consolidados_productos pcp
                    LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                    LEFT JOIN unidades_medida um ON pr.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cat ON pr.ID_Categoria = cat.ID_Categoria
                    LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                    WHERE pcp.ID_Pedido = %s
                    ORDER BY pr.Descripcion
                """, (id_pedido,))
                detalles = cursor.fetchall()
                
                # Calcular totales
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(pcp.Cantidad_Total), 0) as Total_Cantidad,
                        COALESCE(SUM(pcp.Cantidad_Total * pr.Precio_Ruta), 0) as Total_General,
                        COUNT(DISTINCT pcp.ID_Producto) as Total_Productos
                    FROM pedidos_consolidados_productos pcp
                    LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                    WHERE pcp.ID_Pedido = %s
                """, (id_pedido,))
                totales = cursor.fetchone()
                
            else:
                # PARA INDIVIDUALES: usar precio según perfil_cliente
                perfil_cliente = pedido.get('Perfil_Cliente', 'Mercado')
                
                cursor.execute("""
                    SELECT 
                        dp.*,
                        pr.COD_Producto,
                        pr.Descripcion as Nombre_Producto,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        pr.Unidad_Medida,
                        um.Descripcion as Unidad_Nombre,
                        um.Abreviatura as Unidad_Abreviatura,
                        cat.Descripcion as Categoria,
                        -- Mostrar el precio según el perfil del cliente
                        CASE %s
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END as Precio_Segun_Perfil,
                        -- Calcular subtotal según el perfil
                        COALESCE(dp.Subtotal, dp.Cantidad * 
                            CASE %s
                                WHEN 'Ruta' THEN pr.Precio_Ruta
                                WHEN 'Mayorista' THEN pr.Precio_Mayorista
                                WHEN 'Mercado' THEN pr.Precio_Mercado
                                WHEN 'Especial' THEN pr.Precio_Mercado
                                ELSE pr.Precio_Mercado
                            END) as Subtotal
                    FROM detalle_pedidos dp
                    LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
                    LEFT JOIN unidades_medida um ON pr.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cat ON pr.ID_Categoria = cat.ID_Categoria
                    WHERE dp.ID_Pedido = %s
                    ORDER BY dp.ID_Detalle_Pedido
                """, (perfil_cliente, perfil_cliente, id_pedido))
                detalles = cursor.fetchall()
                
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(dp.Cantidad), 0) as Total_Cantidad,
                        COALESCE(SUM(COALESCE(dp.Subtotal, 
                            dp.Cantidad * 
                            CASE %s
                                WHEN 'Ruta' THEN pr.Precio_Ruta
                                WHEN 'Mayorista' THEN pr.Precio_Mayorista
                                WHEN 'Mercado' THEN pr.Precio_Mercado
                                WHEN 'Especial' THEN pr.Precio_Mercado
                                ELSE pr.Precio_Mercado
                            END)), 0) as Total_General,
                        COUNT(DISTINCT dp.ID_Producto) as Total_Productos
                    FROM detalle_pedidos dp
                    LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
                    WHERE dp.ID_Pedido = %s
                """, (perfil_cliente, id_pedido))
                totales = cursor.fetchone()
            
            return render_template('admin/ventas/pedidos/detalle_pedido.html',
                                 pedido=pedido,
                                 detalles=detalles,
                                 totales=totales)
            
    except Exception as e:
        flash(f"Error al cargar el pedido: {str(e)}", "error")
        print(f"Error detallado: {traceback.format_exc()}")
        return redirect(url_for('admin.admin_pedidos_venta'))


@admin_bp.route('/admin/ventas/cambiar-estado/<int:id_pedido>', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("CAMBIAR_ESTADO_PEDIDO")
def cambiar_estado_pedido(id_pedido):
    """
    Cambiar estado de un pedido (Pendiente, Aprobado, Entregado, Cancelado)
    Registra el cambio en historial si la tabla existe
    """
    try:
        data = request.get_json()
        nuevo_estado = data.get('estado')
        
        if nuevo_estado not in ['Pendiente', 'Aprobado', 'Entregado', 'Cancelado']:
            return jsonify({'success': False, 'message': 'Estado inválido'}), 400
        
        with get_db_cursor() as cursor:
            # Verificar que el pedido existe
            cursor.execute("SELECT Estado, Tipo_Pedido FROM pedidos WHERE ID_Pedido = %s", (id_pedido,))
            pedido = cursor.fetchone()
            
            if not pedido:
                return jsonify({'success': False, 'message': 'Pedido no encontrado'}), 404
            
            # Actualizar estado
            sql = """
            UPDATE pedidos 
            SET Estado = %s,
                Fecha_Creacion = CASE 
                    WHEN %s = 'Entregado' THEN CURRENT_TIMESTAMP 
                    ELSE Fecha_Creacion 
                END
            WHERE ID_Pedido = %s
            """
            
            cursor.execute(sql, (nuevo_estado, nuevo_estado, id_pedido))
            
            # Registrar en historial (si existe tabla)
            try:
                cursor.execute("""
                    INSERT INTO pedidos_historial_estados 
                    (ID_Pedido, Estado_Anterior, Estado_Nuevo, ID_Usuario)
                    VALUES (%s, %s, %s, %s)
                """, (id_pedido, pedido['Estado'], nuevo_estado, current_user.id))
            except:
                pass  # La tabla puede no existir
            
            return jsonify({'success': True, 'message': 'Estado actualizado correctamente'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/ventas/cancelar-pedido/<int:pedido_id>', methods=['POST'])
@admin_required
@bitacora_decorator("CANCELAR_PEDIDO")
def cancelar_pedido(pedido_id):
    """
    Cancelar un pedido y devolver el stock a inventario
    Solo aplica para pedidos en estado Pendiente o Aprobado
    """
    try:
        with get_db_cursor() as cursor:
            # Verificar que el pedido existe y está pendiente o aprobado
            sql_verificar = """
            SELECT Estado FROM pedidos 
            WHERE ID_Pedido = %s AND Estado IN ('Pendiente', 'Aprobado')
            """
            cursor.execute(sql_verificar, (pedido_id,))
            pedido = cursor.fetchone()
            
            if not pedido:
                return jsonify({'success': False, 'message': 'Pedido no encontrado o no se puede cancelar'}), 400
            
            # Obtener productos del pedido para devolver al stock
            sql_productos = """
            SELECT dp.ID_Producto, dp.Cantidad 
            FROM detalle_pedidos dp
            WHERE dp.ID_Pedido = %s
            """
            cursor.execute(sql_productos, (pedido_id,))
            productos = cursor.fetchall()
            
            # Devolver stock a las bodegas (se devuelve a la primera bodega disponible)
            for producto in productos:
                # Obtener bodegas de la empresa del pedido
                sql_bodegas = """
                SELECT b.ID_Bodega 
                FROM pedidos p
                JOIN bodegas b ON p.ID_Empresa = b.ID_Empresa
                WHERE p.ID_Pedido = %s AND b.Estado = 'ACTIVO'
                ORDER BY b.ID_Bodega
                LIMIT 1
                """
                cursor.execute(sql_bodegas, (pedido_id,))
                bodega = cursor.fetchone()
                
                if bodega:
                    # Actualizar inventario_bodega
                    sql_update = """
                    INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
                    """
                    cursor.execute(sql_update, (bodega['ID_Bodega'], producto['ID_Producto'], producto['Cantidad']))
            
            # Actualizar estado del pedido
            sql_actualizar = """
            UPDATE pedidos 
            SET Estado = 'Cancelado' 
            WHERE ID_Pedido = %s
            """
            cursor.execute(sql_actualizar, (pedido_id,))
            
            # Registrar en bitácora
            cursor.execute("""
                INSERT INTO bitacora (ID_Usuario, Accion, Descripcion, Fecha)
                VALUES (%s, 'CANCELAR_PEDIDO', %s, NOW())
            """, (session.get('user_id'), f'Pedido #{pedido_id} cancelado'))
            
            return jsonify({
                'success': True, 
                'message': 'Pedido cancelado exitosamente'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/ventas/procesar-pedido/<int:id_pedido>', methods=['GET', 'POST'])
@admin_or_bodega_required
@bitacora_decorator("PROCESAR_VENTA_PEDIDO")
def admin_procesar_venta_pedido(id_pedido):
    """
    Procesar venta desde un pedido aprobado
    Respeta el perfil_cliente para elegir el precio correcto en individuales
    VERSIÓN MEJORADA CON VERIFICACIÓN DE STOCK ROBUSTA
    """
    try:
        # Obtener ID de empresa y usuario desde la sesión
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        if not id_empresa:
            flash('No se pudo determinar la empresa', 'error')
            return redirect(url_for('admin.admin_pedidos_venta'))
        
        if not id_usuario:
            flash('Usuario no autenticado', 'error')
            return redirect(url_for('admin.admin_pedidos_venta'))

        with get_db_cursor(True) as cursor:
            # Obtener información del pedido con perfil_cliente
            cursor.execute("""
                SELECT 
                    p.ID_Pedido,
                    p.Fecha,
                    p.Estado,
                    p.Tipo_Entrega,
                    p.Observacion,
                    p.Prioridad,
                    p.ID_Cliente,
                    p.ID_Empresa,
                    p.Tipo_Pedido,
                    c.Nombre as Nombre_Cliente,
                    c.RUC_CEDULA as Documento_Cliente,
                    c.tipo_cliente as Tipo_Cliente,
                    c.perfil_cliente as Perfil_Cliente,
                    c.Direccion as Direccion_Cliente,
                    c.Telefono as Telefono_Cliente,
                    e.Nombre_Empresa,
                    e.RUC as RUC_Empresa,
                    e.Direccion as Direccion_Empresa,
                    e.Telefono as Telefono_Empresa
                FROM pedidos p
                LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.ID_Pedido = %s
            """, (id_pedido,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            # Validar que el pedido esté aprobado
            if pedido['Estado'] != 'Aprobado':
                flash('Solo se pueden procesar ventas de pedidos aprobados', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            perfil_cliente = pedido.get('Perfil_Cliente', 'Mercado')
            tipo_pedido = pedido.get('Tipo_Pedido')
            
            # Obtener los detalles del pedido según el tipo
            if tipo_pedido == 'Consolidado':
                # Para consolidados: obtener detalles con Precio_Ruta
                cursor.execute("""
                    SELECT 
                        pcp.ID_Pedido_Consolidado_Producto as ID_Detalle_Pedido,
                        pcp.ID_Producto,
                        pcp.Cantidad_Total as Cantidad,
                        pr.Precio_Ruta as Precio_Unitario,
                        (pcp.Cantidad_Total * pr.Precio_Ruta) as Subtotal,
                        pr.COD_Producto,
                        pr.Descripcion,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        cp.Descripcion as Categoria
                    FROM pedidos_consolidados_productos pcp
                    LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                    LEFT JOIN categorias_producto cp ON pr.ID_Categoria = cp.ID_Categoria
                    WHERE pcp.ID_Pedido = %s
                    ORDER BY pr.Descripcion
                """, (id_pedido,))
            else:
                # Para individuales: obtener detalles con precio según perfil
                cursor.execute("""
                    SELECT 
                        dp.ID_Detalle_Pedido,
                        dp.ID_Producto,
                        dp.Cantidad,
                        dp.Precio_Unitario,
                        dp.Subtotal,
                        pr.COD_Producto,
                        pr.Descripcion,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        cp.Descripcion as Categoria,
                        CASE %s
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END as Precio_Segun_Perfil
                    FROM detalle_pedidos dp
                    LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
                    LEFT JOIN categorias_producto cp ON pr.ID_Categoria = cp.ID_Categoria
                    WHERE dp.ID_Pedido = %s
                    ORDER BY dp.ID_Detalle_Pedido
                """, (perfil_cliente, id_pedido))
            
            detalles_pedido = cursor.fetchall()
            
            if not detalles_pedido:
                flash('El pedido no tiene productos', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            # Obtener el ID_TipoMovimiento para VENTAS
            cursor.execute("""
                SELECT ID_TipoMovimiento, Descripcion, Letra 
                FROM catalogo_movimientos 
                WHERE Descripcion LIKE '%Venta%' OR Letra = 'S' 
                LIMIT 1
            """)
            tipo_movimiento = cursor.fetchone()
            
            if not tipo_movimiento:
                flash('Error: No se encontró el tipo de movimiento para ventas', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            id_tipo_movimiento = tipo_movimiento['ID_TipoMovimiento']
            
            # Obtener bodega principal
            cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_principal = cursor.fetchone()
            if not bodega_principal:
                flash('Error: No hay bodegas activas en el sistema', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            id_bodega_principal = bodega_principal['ID_Bodega']
            
            # ============================================
            # VERIFICACIÓN DE STOCK MEJORADA
            # ============================================
            productos_sin_stock = []
            productos_sin_registro = []
            total_pedido = 0
            total_cajillas_huevos = 0
            ID_CATEGORIA_HUEVOS = 1  # AJUSTAR según tu sistema
            
            print(f"\n📦 INICIANDO VERIFICACIÓN DE STOCK")
            print(f"📦 Bodega: {bodega_principal['Nombre']} (ID: {id_bodega_principal})")
            print("="*60)
            
            for detalle in detalles_pedido:
                id_producto = detalle['ID_Producto']
                cantidad = float(detalle['Cantidad'])
                precio = float(detalle['Precio_Unitario'])
                nombre_producto = detalle.get('Descripcion', f'Producto ID:{id_producto}')
                
                # Verificar si existe registro de inventario y obtener stock
                cursor.execute("""
                    SELECT 
                        COALESCE(Existencias, 0) as Stock,
                        CASE 
                            WHEN ID_Producto IS NOT NULL THEN 1 
                            ELSE 0 
                        END as ExisteRegistro
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega_principal, id_producto))
                
                stock_info = cursor.fetchone()
                
                print(f"\n🔍 Producto: {nombre_producto} (ID:{id_producto})")
                print(f"   Cantidad solicitada: {cantidad}")
                
                if not stock_info or stock_info['ExisteRegistro'] == 0:
                    # No existe registro en inventario_bodega
                    print(f"    ERROR CRÍTICO: No hay registro de inventario para este producto")
                    productos_sin_registro.append({
                        'producto': nombre_producto,
                        'id_producto': id_producto,
                        'cantidad_solicitada': cantidad,
                        'motivo': 'Producto no registrado en inventario_bodega'
                    })
                    productos_sin_stock.append({
                        'producto': nombre_producto,
                        'stock_actual': 0,
                        'cantidad_solicitada': cantidad,
                        'motivo': 'Sin registro en inventario'
                    })
                else:
                    stock_actual = float(stock_info['Stock'])
                    
                    print(f"   Stock actual en sistema: {stock_actual}")
                    
                    # Comparación con tolerancia para decimales
                    if (stock_actual + 0.001) < cantidad:
                        print(f"    STOCK INSUFICIENTE!")
                        productos_sin_stock.append({
                            'producto': nombre_producto,
                            'stock_actual': stock_actual,
                            'cantidad_solicitada': cantidad,
                            'motivo': f'Stock insuficiente (disponible: {stock_actual}, necesita: {cantidad})'
                        })
                    else:
                        print(f"   ✅ Stock suficiente")
                
                # Calcular total del pedido
                total_pedido += cantidad * precio
                
                # Verificar si es producto de huevos
                cursor.execute("""
                    SELECT ID_Categoria 
                    FROM productos 
                    WHERE ID_Producto = %s
                """, (id_producto,))
                
                producto_data = cursor.fetchone()
                if producto_data and producto_data['ID_Categoria'] == ID_CATEGORIA_HUEVOS:
                    total_cajillas_huevos += cantidad
            
            print("\n" + "="*60)
            
            # Si hay productos sin stock, mostrar error detallado
            if productos_sin_stock:
                print(f" VERIFICACIÓN DE STOCK FALLIDA")
                print(f"   Total de productos con problemas: {len(productos_sin_stock)}")
                
                # Crear mensaje de error detallado
                error_detalles = []
                for ps in productos_sin_stock:
                    error_detalles.append(f"{ps['producto']}: {ps['motivo']}")
                
                error_msg = f"No se puede procesar el pedido. Problemas de inventario:\n" + "\n".join(error_detalles)
                
                # Si es GET, mostrar en el template
                if request.method == 'GET':
                    return render_template('admin/ventas/pedidos/procesar_pedido.html',
                                        pedido=pedido,
                                        detalles_pedido=detalles_pedido,
                                        productos_sin_stock=productos_sin_stock,
                                        productos_sin_registro=productos_sin_registro,
                                        total_pedido=total_pedido,
                                        total_cajillas_huevos=total_cajillas_huevos,
                                        bodega_principal=bodega_principal,
                                        perfil_cliente=perfil_cliente,
                                        now=datetime.now(),
                                        current_user=current_user,
                                        error_stock=True)
                else:
                    flash(error_msg, 'error')
                    return redirect(url_for('admin.admin_procesar_venta_pedido', id_pedido=id_pedido))
            
            print(f"✅ VERIFICACIÓN DE STOCK EXITOSA")
            print(f"   Total productos: {len(detalles_pedido)}")
            print(f"   Total pedido: C${total_pedido:,.2f}")
            if total_cajillas_huevos > 0:
                print(f"   Cajillas de huevos: {total_cajillas_huevos}")
            print("="*60)
        
        # Si es GET, mostrar formulario de procesamiento
        if request.method == 'GET':
            return render_template('admin/ventas/pedidos/procesar_pedido.html',
                                pedido=pedido,
                                detalles_pedido=detalles_pedido,
                                productos_sin_stock=productos_sin_stock,
                                total_pedido=total_pedido,
                                total_cajillas_huevos=total_cajillas_huevos,
                                bodega_principal=bodega_principal,
                                perfil_cliente=perfil_cliente,
                                now=datetime.now(),
                                current_user=current_user)
        
        # Si es POST, procesar la venta
        if request.method == 'POST':
            print(f"\n📨 PROCESANDO VENTA DESDE PEDIDO #{id_pedido}...")
            print("="*60)
            
            tipo_venta = request.form.get('tipo_venta', 'contado')
            observacion_adicional = request.form.get('observacion_adicional', '')
            
            with get_db_cursor(True) as cursor:
                # VALIDACIÓN DE VISIBILIDAD DE PRODUCTOS
                print("🔍 Validando visibilidad de productos para el cliente...")
                
                # Obtener tipo de cliente
                cursor.execute("""
                    SELECT tipo_cliente 
                    FROM clientes 
                    WHERE ID_Cliente = %s
                """, (pedido['ID_Cliente'],))
                
                cliente_data = cursor.fetchone()
                if not cliente_data:
                    flash('Cliente no encontrado', 'error')
                    return redirect(url_for('admin.admin_pedidos_venta'))
                
                tipo_cliente = cliente_data['tipo_cliente']
                print(f"👤 Tipo de cliente: {tipo_cliente}")
                
                # Validar cada producto contra la visibilidad del cliente
                productos_invalidos = []
                for detalle in detalles_pedido:
                    producto_id = detalle['ID_Producto']
                    
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as valido,
                            p.Descripcion,
                            c.Descripcion as categoria_nombre
                        FROM productos p
                        INNER JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                        INNER JOIN config_visibilidad_categorias cfg ON c.ID_Categoria = cfg.ID_Categoria
                        WHERE p.ID_Producto = %s
                          AND cfg.tipo_cliente = %s
                          AND cfg.visible = 1
                          AND p.Estado = 'activo'
                    """, (producto_id, tipo_cliente))
                    
                    resultado = cursor.fetchone()
                    if not resultado or resultado['valido'] == 0:
                        productos_invalidos.append({
                            'id': producto_id,
                            'nombre': resultado['Descripcion'] if resultado else f"ID:{producto_id}",
                            'categoria': resultado['categoria_nombre'] if resultado else 'Desconocida'
                        })
                
                # Si hay productos no visibles, mostrar error
                if productos_invalidos:
                    productos_error = ", ".join([f"{p['nombre']} ({p['categoria']})" for p in productos_invalidos])
                    error_msg = f"Los siguientes productos no están disponibles para este cliente ({tipo_cliente}): {productos_error}"
                    print(f" {error_msg}")
                    flash(error_msg, 'error')
                    return redirect(url_for('admin.admin_procesar_venta_pedido', id_pedido=id_pedido))
                
                print("✅ Validación de visibilidad completada")
                
                # VOLVER A VERIFICAR STOCK ANTES DE PROCESAR (por si acaso)
                print("🔍 Verificando stock nuevamente antes de procesar...")
                for detalle in detalles_pedido:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega_principal, id_producto))
                    
                    stock_data = cursor.fetchone()
                    if not stock_data or float(stock_data['Stock']) < cantidad - 0.001:
                        flash(f'Stock insuficiente para {detalle["Descripcion"]}. Por favor, verifique el inventario.', 'error')
                        return redirect(url_for('admin.admin_procesar_venta_pedido', id_pedido=id_pedido))
                
                print("✅ Verificación de stock final exitosa")
                
                # 1. Crear factura
                observacion_completa = f"Pedido #{id_pedido} - {pedido['Observacion'] or 'Sin observación'}"
                if observacion_adicional:
                    observacion_completa += f" | {observacion_adicional}"
                
                cursor.execute("""
                    INSERT INTO facturacion (
                        Fecha, IDCliente, Credito_Contado, Observacion, 
                        ID_Empresa, ID_Usuario_Creacion
                    )
                    VALUES (CURDATE(), %s, %s, %s, %s, %s)
                """, (
                    pedido['ID_Cliente'],
                    1 if tipo_venta == 'credito' else 0,
                    observacion_completa,
                    id_empresa,
                    id_usuario
                ))
                
                # Obtener el ID de la factura
                cursor.execute("SELECT LAST_INSERT_ID() as id_factura")
                id_factura = cursor.fetchone()['id_factura']
                print(f"🧾 Factura creada: #{id_factura}")
                
                # CONSTANTES
                ID_SEPARADOR = 11          # ID_Producto del separador
                ID_BODEGA_EMPAQUE = 1      # Bodega de donde se descuentan separadores
                
                total_venta = 0
                
                # 2. Procesar productos y crear detalles de facturación
                print("\n📝 Procesando productos...")
                for detalle in detalles_pedido:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    precio = float(detalle['Precio_Unitario'])
                    total_linea = cantidad * precio
                    total_venta += total_linea
                    
                    # Insertar detalle de facturación
                    cursor.execute("""
                        INSERT INTO detalle_facturacion (
                            ID_Factura, ID_Producto, Cantidad, Costo, Total
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, id_producto, cantidad, precio, total_linea))
                    
                    # Actualizar inventario del producto
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega_principal, id_producto))
                    
                    # Verificar que la actualización fue exitosa
                    if cursor.rowcount == 0:
                        raise Exception(f"No se pudo actualizar el inventario para el producto {detalle['Descripcion']} (ID: {id_producto})")
                    
                    print(f"  ✅ {detalle['Descripcion']}: {cantidad} x C${precio:,.2f} = C${total_linea:,.2f}")
                
                print(f"\n📊 Total venta: C${total_venta:,.2f}")
                
                # 3. CALCULAR SEPARADORES NECESARIOS
                separadores_totales = 0
                if total_cajillas_huevos > 0:
                    separadores_entre_cajillas = total_cajillas_huevos
                    separadores_base_extra = total_cajillas_huevos // 10
                    separadores_totales = separadores_entre_cajillas + separadores_base_extra
                    
                    print(f"\n🔢 CÁLCULO DE SEPARADORES:")
                    print(f"  Cajillas de huevos: {total_cajillas_huevos}")
                    print(f"  Separadores necesarios: {separadores_totales}")
                
                # 4. DESCONTAR SEPARADORES SI HAY PRODUCTOS DE HUEVOS
                if separadores_totales > 0:
                    print(f"\n🔧 Procesando separadores...")
                    
                    # Verificar stock de separadores
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                    
                    stock_separadores = cursor.fetchone()
                    stock_actual_separadores = float(stock_separadores['Stock']) if stock_separadores else 0
                    
                    if stock_actual_separadores >= separadores_totales:
                        # Restar separadores del inventario
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = Existencias - %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (separadores_totales, ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                        
                        # Registrar separador en detalle de factura (costo 0)
                        cursor.execute("""
                            INSERT INTO detalle_facturacion (
                                ID_Factura, ID_Producto, Cantidad, Costo, Total
                            )
                            VALUES (%s, %s, %s, 0, 0)
                        """, (id_factura, ID_SEPARADOR, separadores_totales))
                        
                        print(f"  ✅ Separadores descontados: {separadores_totales}")
                    else:
                        warning_msg = f'Stock insuficiente de separadores. Necesarios: {separadores_totales}, Disponibles: {stock_actual_separadores}'
                        print(f"  ⚠️ {warning_msg}")
                        observacion_completa += f" | [ADVERTENCIA: {warning_msg}]"
                
                # 5. Actualizar observación de factura si hubo advertencia
                cursor.execute("""
                    UPDATE facturacion 
                    SET Observacion = %s
                    WHERE ID_Factura = %s
                """, (observacion_completa, id_factura))
                
                # 6. Registrar movimiento de inventario (VENTA)
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        ID_TipoMovimiento, ID_Bodega, Fecha, Tipo_Compra,
                        Observacion, ID_Empresa, ID_Usuario_Creacion, Estado,
                        ID_Factura_Venta
                    )
                    VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, 1, %s)
                """, (
                    id_tipo_movimiento,
                    id_bodega_principal,
                    'CREDITO' if tipo_venta == 'credito' else 'CONTADO',
                    observacion_completa,
                    id_empresa,
                    id_usuario,
                    id_factura
                ))
                
                # Obtener el ID del movimiento de inventario
                cursor.execute("SELECT LAST_INSERT_ID() as id_movimiento")
                id_movimiento = cursor.fetchone()['id_movimiento']
                
                # 7. Insertar detalles del movimiento de inventario
                for detalle in detalles_pedido:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    precio = float(detalle['Precio_Unitario'])
                    subtotal = cantidad * precio
                    
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        id_producto,
                        cantidad,
                        precio,
                        precio,
                        subtotal,
                        id_usuario
                    ))
                
                # 8. Insertar detalle del movimiento para el separador
                if separadores_totales > 0:
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, 0, 0, 0, %s)
                    """, (
                        id_movimiento,
                        ID_SEPARADOR,
                        separadores_totales,
                        id_usuario
                    ))
                
                # 9. Si es crédito, crear cuenta por cobrar
                if tipo_venta == 'credito':
                    cursor.execute("""
                        INSERT INTO cuentas_por_cobrar (
                            Fecha, ID_Cliente, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                            ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion
                        )
                        VALUES (CURDATE(), %s, %s, %s, DATE_ADD(CURDATE(), INTERVAL 30 DAY), 
                                1, %s, %s, %s, %s, %s)
                    """, (
                        pedido['ID_Cliente'],
                        f'FAC-{id_factura:05d}',
                        observacion_completa,
                        total_venta,
                        id_empresa,
                        total_venta,
                        id_factura,
                        id_usuario
                    ))
                    print(f"💰 Cuenta por cobrar creada: FAC-{id_factura:05d}")
                
                # 10. Si es CONTADO, registrar entrada en caja
                if tipo_venta == 'contado':
                    cursor.execute("""
                        INSERT INTO caja_movimientos (
                            Fecha, Tipo_Movimiento, Descripcion, Monto, 
                            ID_Factura, ID_Usuario, Referencia_Documento
                        )
                        VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                    """, (
                        f'Venta desde pedido #{id_pedido} - Factura #{id_factura} - Cliente: {pedido["Nombre_Cliente"]}',
                        total_venta,
                        id_factura,
                        id_usuario,
                        f'FAC-{id_factura:05d}'
                    ))
                    print(f"💰 Movimiento de caja registrado: C${total_venta:,.2f}")
                
                # 11. Actualizar el estado del pedido a "Entregado"
                cursor.execute("""
                    UPDATE pedidos 
                    SET Estado = 'Entregado'
                    WHERE ID_Pedido = %s
                """, (id_pedido,))
                
                print(f"\n✅ Pedido #{id_pedido} actualizado a estado: Entregado")
                
                # 12. Guardar datos de la venta en la sesión para mostrarlos en el ticket
                session['venta_procesada'] = {
                    'id_factura': id_factura,
                    'id_pedido': id_pedido,
                    'total_venta': total_venta,
                    'tipo_venta': tipo_venta,
                    'nombre_cliente': pedido['Nombre_Cliente'],
                    'fecha': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                }
                
                print("="*60)
                print(f"🎯 Venta procesada exitosamente!")
                print(f"   Factura: #{id_factura}")
                print(f"   Total: C${total_venta:,.2f}")
                print("="*60)
                
                # 13. Redirigir directamente al ticket
                return redirect(url_for('admin.admin_generar_ticket', id_factura=id_factura))
                
    except Exception as e:
        error_msg = f' Error al procesar venta desde pedido: {str(e)}'
        print(f"\n{error_msg}")
        import traceback
        print(f"Traceback completo:")
        print(traceback.format_exc())
        
        flash(error_msg, 'error')
        return redirect(url_for('admin.admin_pedidos_venta'))


@admin_bp.route('/api/pedidos/<int:id_pedido>/productos-consolidados')
@login_required
def api_productos_consolidados(id_pedido):
    """
    API para obtener productos de un pedido consolidado
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    pcp.ID_Producto,
                    pcp.Cantidad_Total,
                    pr.Descripcion as Nombre_Producto,
                    pr.COD_Producto,
                    pr.Precio_Mercado as Precio_Venta
                FROM pedidos_consolidados_productos pcp
                INNER JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                WHERE pcp.ID_Pedido = %s
                ORDER BY pr.Descripcion
            """, (id_pedido,))
            
            productos = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': productos
            })
    except Exception as e:
        print(f"Error API productos: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'data': []
        }), 500


