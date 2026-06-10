from decimal import Decimal
import traceback
from venv import logger
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator

@admin_bp.route('/admin/compras/compras-entradas', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS")
def admin_compras_entradas():
    # ========== EXTRAER FILTROS DEL REQUEST ==========
    fecha_str = request.args.get('fecha')
    estado_filtro = request.args.get('estado', 'todas').upper()
    tipo_filtro = request.args.get('tipo', '').upper()
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else None
        
        with get_db_cursor() as cursor:
            # ========== CONSTRUIR CONDICIONES WHERE DINÁMICAMENTE ==========
            where_conditions = []
            params = []
            
            # *** CAMBIO PRINCIPAL: Condición para identificar COMPRAS por su ID_TipoMovimiento = 1 ***
            # Ya no se usan las condiciones basadas en texto (Adicion, Letra, Descripcion)
            where_conditions.append("mi.ID_TipoMovimiento = 1")
            
            # EXCLUIR registros que tienen ID_Factura_venta (son ventas, no compras)
            where_conditions.append("(mi.ID_Factura_venta IS NULL OR mi.ID_Factura_venta = '')")
            
            # Filtro por estado
            if estado_filtro == 'ACTIVAS':
                where_conditions.append("mi.Estado = 'Activa'")
            elif estado_filtro == 'ANULADAS':
                where_conditions.append("mi.Estado = 'Anulada'")
            elif estado_filtro == 'TODAS':
                # No aplicar filtro de estado específico
                pass
            else:
                # Por defecto, mostrar solo activas
                where_conditions.append("mi.Estado = 'Activa'")
            
            # Filtro por tipo de compra (Contado/Crédito)
            if tipo_filtro == 'CONTADO':
                where_conditions.append("mi.Tipo_Compra = 'CONTADO'")
            elif tipo_filtro == 'CREDITO':
                where_conditions.append("mi.Tipo_Compra = 'CREDITO'")
            
            # Filtro por fecha (opcional)
            if fecha and fecha_str:
                where_conditions.append("DATE(mi.Fecha) = %s")
                params.append(fecha)
            
            # Construir WHERE clause
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # ========== CONSULTA 1: Obtener entradas con filtros ==========
            query = f"""
                SELECT 
                    mi.ID_Movimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    mi.Fecha_Creacion,
                    p.Nombre as Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Estado,
                    COALESCE(detalle.Total_Productos, 0) as Total_Productos,
                    COALESCE(detalle.Total_Compra, 0) as Total_Compra,
                    -- Campos formateados para mostrar en la tabla
                    DATE_FORMAT(mi.Fecha, '%%d/%%m/%%Y') as Fecha_Formateada,
                    DATE_FORMAT(mi.Fecha_Creacion, '%%H:%%i') as Hora_Formateada,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'ACTIVA'
                        WHEN mi.Estado = 'Anulada' THEN 'ANULADA'
                        ELSE UPPER(mi.Estado)
                    END as Estado_Formateado,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'badge-success'
                        WHEN mi.Estado = 'Anulada' THEN 'badge-danger'
                        ELSE 'badge-secondary'
                    END as Estado_Clase,
                    CASE 
                        WHEN mi.Tipo_Compra = 'CONTADO' THEN 'CONTADO'
                        WHEN mi.Tipo_Compra = 'CREDITO' THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Compra_Formateado
                FROM movimientos_inventario mi
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN (
                    SELECT 
                        ID_Movimiento,
                        COUNT(*) as Total_Productos,
                        SUM(COALESCE(Subtotal, 0)) as Total_Compra
                    FROM detalle_movimientos_inventario
                    GROUP BY ID_Movimiento
                ) detalle ON mi.ID_Movimiento = detalle.ID_Movimiento
                {where_clause}
                ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
                LIMIT 30
            """
            
            print("SQL Query:", query)  # Para depuración
            print("Params:", params)     # Para depuración
            
            cursor.execute(query, tuple(params))
            compras = cursor.fetchall()
            
            # Procesar resultados para convertir a diccionario y asegurar valores
            compras_procesadas = []
            for compra in compras:
                compra_dict = dict(compra)
                # Asegurar que los campos tengan valores por defecto
                compra_dict['Fecha_Formateada'] = compra_dict.get('Fecha_Formateada', 'N/A')
                compra_dict['Hora_Formateada'] = compra_dict.get('Hora_Formateada', '')
                compra_dict['Total_Productos'] = compra_dict.get('Total_Productos') or 0
                compra_dict['Total_Compra'] = float(compra_dict.get('Total_Compra') or 0)
                compras_procesadas.append(compra_dict)
            
            # ========== CONSULTAS DE RESUMEN FINANCIERO (TODAS ACTIVAS) ==========
            # *** MODIFICADAS: Ahora usan ID_TipoMovimiento = 1 ***
            
            # **CONSULTA 2: Capital Invertido TOTAL (Contado + Crédito) - SOLO ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Total
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.ID_TipoMovimiento = 1
                    AND (mi.ID_Factura_venta IS NULL OR mi.ID_Factura_venta = '')
            """)
            resultado_total = cursor.fetchone()
            capital_total = float(resultado_total['Capital_Total']) if resultado_total and resultado_total['Capital_Total'] else 0.0
            
            # **CONSULTA 3: Capital Invertido SOLO AL CONTADO - SOLO ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Contado
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Tipo_Compra = 'CONTADO'
                    AND mi.ID_TipoMovimiento = 1
                    AND (mi.ID_Factura_venta IS NULL OR mi.ID_Factura_venta = '')
            """)
            resultado_contado = cursor.fetchone()
            capital_contado = float(resultado_contado['Capital_Contado']) if resultado_contado and resultado_contado['Capital_Contado'] else 0.0
            
            # **CONSULTA 4: Capital en CRÉDITO (deudas pendientes) - SOLO ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Credito
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Tipo_Compra = 'CREDITO'
                    AND mi.ID_TipoMovimiento = 1
                    AND (mi.ID_Factura_venta IS NULL OR mi.ID_Factura_venta = '')
            """)
            resultado_credito = cursor.fetchone()
            capital_credito = float(resultado_credito['Capital_Credito']) if resultado_credito and resultado_credito['Capital_Credito'] else 0.0
            
            # Validar consistencia
            capital_total_calculado = capital_contado + capital_credito
            diferencia = abs(capital_total - capital_total_calculado)
            
            if diferencia > 0.01:
                print(f"⚠️ ADVERTENCIA: Discrepancia detectada en compras")
                print(f"   Total BD: {capital_total}, Contado: {capital_contado}, Crédito: {capital_credito}")
                print(f"   Suma manual: {capital_total_calculado}, Diferencia: {diferencia}")
                capital_total = capital_total_calculado
            
            # ========== ESTADÍSTICAS PARA LOS FILTROS ==========
            # *** MODIFICADAS: Ahora usan ID_TipoMovimiento = 1 ***
            
            # Obtener estadísticas por estado
            cursor.execute("""
                SELECT 
                    mi.Estado,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(dmi.Subtotal), 0) as total_monto
                FROM movimientos_inventario mi
                LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.ID_TipoMovimiento = 1
                    AND (mi.ID_Factura_venta IS NULL OR mi.ID_Factura_venta = '')
                GROUP BY mi.Estado
            """)
            estadisticas_estado = cursor.fetchall()
            
            # Obtener estadísticas por tipo de compra
            cursor.execute("""
                SELECT 
                    mi.Tipo_Compra,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(dmi.Subtotal), 0) as total_monto
                FROM movimientos_inventario mi
                LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.ID_TipoMovimiento = 1
                    AND mi.Estado = 'Activa'
                    AND (mi.ID_Factura_venta IS NULL OR mi.ID_Factura_venta = '')
                GROUP BY mi.Tipo_Compra
            """)
            estadisticas_tipo = cursor.fetchall()
            
            # ========== ESTADÍSTICAS PARA LAS ENTRADAS MOSTRADAS ==========
            total_compras = len(compras_procesadas)
            total_invertido_lista = sum(float(compra.get('Total_Compra') or 0) for compra in compras_procesadas)
            total_productos_mostrados = sum(int(compra.get('Total_Productos') or 0) for compra in compras_procesadas)
            contado_mostradas = sum(1 for compra in compras_procesadas if compra.get('Tipo_Compra') == 'CONTADO')
            credito_mostradas = sum(1 for compra in compras_procesadas if compra.get('Tipo_Compra') == 'CREDITO')
            activas_mostradas = sum(1 for compra in compras_procesadas if compra.get('Estado') == 'Activa')
            anuladas_mostradas = sum(1 for compra in compras_procesadas if compra.get('Estado') == 'Anulada')
            
            return render_template('admin/compras/compras_entradas.html',
                                 # Datos de la tabla
                                 compras=compras_procesadas,
                                 
                                 # Estadísticas de las compras MOSTRADAS
                                 total_compras=total_compras,
                                 total_invertido=total_invertido_lista,
                                 total_productos=total_productos_mostrados,
                                 compras_contado=contado_mostradas,
                                 compras_credito=credito_mostradas,
                                 compras_activas=activas_mostradas,
                                 compras_anuladas=anuladas_mostradas,
                                 
                                 # Resumen financiero TOTAL
                                 capital_total=capital_total,
                                 capital_contado=capital_contado,
                                 capital_credito=capital_credito,
                                 
                                 # Filtros actuales
                                 fecha_filtro=fecha,
                                 estado_filtro=estado_filtro,
                                 tipo_filtro=tipo_filtro,
                                 
                                 # Estadísticas para mostrar en los filtros
                                 estadisticas_estado=estadisticas_estado,
                                 estadisticas_tipo=estadisticas_tipo)
                                 
    except Exception as e:
        flash(f'Error al cargar entradas de compras: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/compras/compras-entradas/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-CREAR")
def admin_crear_compra():
    try:
        if request.method == 'GET':
            id_empresa = session.get('id_empresa', 1)
            
            with get_db_cursor(True) as cursor:  
                cursor.execute("SELECT ID_Proveedor, Nombre FROM proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
                proveedores = cursor.fetchall()
                
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.ID_Categoria, 
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    WHERE p.Estado = 'activo'
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_empresa,))
                productos = cursor.fetchall()
                
                return render_template('admin/compras/crear_compra.html',
                                    proveedores=proveedores,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias)
        
        elif request.method == 'POST':
            # Obtener datos del formulario
            id_usuario_creacion = current_user.id
            id_tipo_movimiento = 1
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            costos_unitarios = request.form.getlist('costos_unitarios[]')
            
            print(f"Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_creacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin.admin_crear_compra'))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin.admin_crear_compra'))
            
            # Construir lista de productos
            for i in range(len(producto_ids)):
                if producto_ids[i] and cantidades[i] and costos_unitarios[i]:
                    cantidad = round(float(cantidades[i]), 2)
                    costo_unitario = round(float(costos_unitarios[i]), 2)
                    
                    precio_unitario = costo_unitario
                    
                    productos.append({
                        'id_producto': producto_ids[i],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'precio_unitario': precio_unitario
                    })
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_creacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin.admin_crear_compra'))
            
            # USAR TRANSACCIÓN CON COMMIT
            with get_db_cursor(commit=True) as cursor:
                # Calcular total de la compra
                total_compra = sum(
                    producto['cantidad'] * producto['costo_unitario'] 
                    for producto in productos
                )
                
                # Insertar movimiento principal
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        ID_TipoMovimiento, N_Factura_Externa, Fecha, ID_Proveedor, 
                        Tipo_Compra, Observacion, ID_Empresa, ID_Bodega, 
                        ID_Usuario_Creacion, ID_Usuario_Modificacion, Estado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_proveedor if id_proveedor else None,
                    tipo_compra,
                    observacion,
                    session.get('id_empresa', 1),
                    id_bodega,
                    id_usuario,
                    id_usuario,
                    1  # Estado activo/completado
                ))
                
                id_movimiento = cursor.lastrowid
                print(f"Movimiento creado con ID: {id_movimiento}")
                
                # Insertar detalles del movimiento
                for producto in productos:
                    subtotal = round(producto['cantidad'] * producto['costo_unitario'], 2)
                    
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                            Precio_Unitario, Subtotal, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['costo_unitario'],
                        producto['precio_unitario'],
                        subtotal,
                        id_usuario
                    ))
                    
                    # Actualizar inventario_bodega
                    cursor.execute("""
                        SELECT ID_Producto FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega, producto['id_producto']))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = Existencias + %s 
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (producto['cantidad'], id_bodega, producto['id_producto']))
                    else:
                        cursor.execute("""
                            INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                        """, (id_bodega, producto['id_producto'], producto['cantidad']))
                
                # CREAR CUENTA POR PAGAR Y ACTUALIZAR SALDO DEL PROVEEDOR SI ES CRÉDITO
                if tipo_compra == 'CREDITO' and id_proveedor:
                    if not fecha_vencimiento:
                        from datetime import datetime, timedelta
                        fecha_compra = datetime.strptime(fecha, '%Y-%m-%d')
                        fecha_vencimiento = (fecha_compra + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    # Insertar en cuentas_por_pagar
                    cursor.execute("""
                        INSERT INTO cuentas_por_pagar (
                            ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                            Saldo_Pendiente, ID_Usuario_Creacion, Estado
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        fecha,
                        id_proveedor,
                        n_factura_externa or '',
                        observacion or 'Compra a crédito',
                        fecha_vencimiento,
                        id_tipo_movimiento,
                        total_compra,
                        session.get('id_empresa', 1),
                        total_compra,  # Saldo pendiente de esta factura
                        id_usuario,
                        'Pendiente'
                    ))
                    
                    # ACTUALIZAR SALDO PENDIENTE DEL PROVEEDOR
                    cursor.execute("""
                        UPDATE proveedores 
                        SET Saldo_Pendiente = COALESCE(Saldo_Pendiente, 0) + %s
                        WHERE ID_Proveedor = %s
                    """, (total_compra, id_proveedor))
                    
                    print(f"Saldo del proveedor {id_proveedor} actualizado. Monto sumado: {total_compra}")
                
                flash(f'Compra creada exitosamente', 'success')
                return redirect(url_for('admin.admin_compras_entradas'))
                
    except Exception as e:
        print(f"Error completo al crear compra: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Error al crear compra: {str(e)}', 'error')
        return redirect(url_for('admin.admin_crear_compra'))

@admin_bp.route('/compras/productos-por-categoria/<int:id_categoria>')
@admin_required
def obtener_productos_por_categoria_compra(id_categoria):
    """
    Obtiene productos filtrados por categoría usando inventario_bodega
    RUTA FUNCIONANDO: ✅ (MODIFICADA: SIN PRECIO_VENTA)
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener bodega de la empresa
            cursor.execute("""
                SELECT ID_Bodega FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 1 LIMIT 1
            """, (id_empresa,))
            bodega_result = cursor.fetchone()
            
            if not bodega_result:
                return jsonify({'error': 'No se encontró bodega para la empresa'}), 404
            
            id_bodega = bodega_result['ID_Bodega']
            
            if id_categoria == 0:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.ID_Categoria,
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                        AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo'
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_bodega, id_empresa))
            else:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.ID_Categoria,
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                        AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo'
                    AND p.ID_Categoria = %s 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY p.Descripcion
                """, (id_bodega, id_categoria, id_empresa))
            
            productos = cursor.fetchall()
            productos_list = [{
                'id': p['ID_Producto'],
                'codigo': p['COD_Producto'],
                'descripcion': p['Descripcion'],
                'existencias': float(p['Existencias']),
                'id_categoria': p['ID_Categoria'],
                'categoria': p['Categoria'],
                'unidad_medida': p['Unidad_Medida'],
                'simbolo_medida': p['Simbolo_Medida']
            } for p in productos]
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener productos: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/compras/verificar-existencias/<int:id_producto>')
@admin_required
def verificar_existencias_producto(id_producto):
    """
    Verifica existencias de un producto usando inventario_bodega
    RUTA FUNCIONANDO: ✅
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener bodega de la empresa
            cursor.execute("""
                SELECT ID_Bodega FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 1 LIMIT 1
            """, (id_empresa,))
            bodega_result = cursor.fetchone()
            
            if not bodega_result:
                return jsonify({'error': 'No se encontró bodega'}), 404
            
            id_bodega = bodega_result['ID_Bodega']
            
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion,
                    COALESCE(p.Precio_Mercado, 0) as Precio_Venta,
                    um.Descripcion as Unidad_Medida,
                    COALESCE(ib.Existencias, 0) as Existencias
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE p.ID_Producto = %s 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND p.Estado = 'activo'
            """, (id_bodega, id_producto, id_empresa))
            
            producto = cursor.fetchone()
            
            if producto:
                return jsonify({
                    'id_producto': producto['ID_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']),
                    'precio_venta': float(producto['Precio_Venta']),
                    'unidad_medida': producto['Unidad_Medida']
                })
            else:
                return jsonify({'error': 'Producto no encontrado'}), 404
                
    except Exception as e:
        print(f"❌ Error al verificar existencias: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/compras/categorias-productos')
@admin_required
def obtener_categorias_productos_compra():
    """
    Obtiene todas las categorías de productos
    RUTA FUNCIONANDO: ✅
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            categorias_list = [{
                'id': c['ID_Categoria'],
                'descripcion': c['Descripcion']
            } for c in categorias]
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f"❌ Error al obtener categorías: {str(e)}")
        return jsonify({'error': str(e)}), 500

def obtener_id_bodega_empresa(id_empresa=None):
    """
    Obtiene el ID de la bodega principal de una empresa
    FUNCIÓN AUXILIAR: ✅
    """
    if id_empresa is None:
        id_empresa = session.get('id_empresa', 1)
    
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Bodega 
                FROM bodegas 
                WHERE ID_Empresa = %s 
                AND Estado = 1
                LIMIT 1
            """, (id_empresa,))
            
            result = cursor.fetchone()
            return result['ID_Bodega'] if result else None
    except Exception as e:
        print(f"❌ Error al obtener bodega: {str(e)}")
        return None

@admin_bp.route('/compras/compras-entradas/anular/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-ANULAR")
def admin_anular_compra(id_movimiento):
    """Anular una compra existente - REVIERTE INVENTARIO COMPLETAMENTE"""
    
    # Si es GET, mostrar información de la compra
    if request.method == 'GET':
        try:
            with get_db_cursor(commit=False) as cursor:
                # ✅ CORREGIDO: Incluir ID_Bodega en la consulta
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.N_Factura_Externa,
                        mi.Fecha,
                        mi.Tipo_Compra,
                        mi.Estado,
                        mi.ID_Bodega,  # ← AGREGADO: necesario para consultar inventario
                        p.Nombre as Proveedor,
                        b.Nombre as Bodega,
                        COALESCE((
                            SELECT COUNT(*) 
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ), 0) as Total_Productos,
                        COALESCE((
                            SELECT SUM(COALESCE(Subtotal, 0))
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ), 0) as Total_Compra
                    FROM movimientos_inventario mi
                    LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    WHERE mi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                compra = cursor.fetchone()
                
                if not compra:
                    return jsonify({'success': False, 'error': 'Compra no encontrada'}), 404
                
                if compra['Estado'] != 'Activa':
                    estado_texto = "anulada" if compra['Estado'] == 'Anulada' else compra['Estado'].lower()
                    return jsonify({'success': False, 'error': f'La compra #{id_movimiento} ya está {estado_texto}'}), 400
                
                carga_completa = request.args.get('completa', '0') == '1'
                total_compra = float(compra['Total_Compra'] or 0)
                
                # ✅ CORREGIDO: Usar Existencias en lugar de Stock_Actual
                cursor.execute("""
                    SELECT 
                        dmi.ID_Producto,
                        dmi.Cantidad,
                        p.Descripcion,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM detalle_movimientos_inventario dmi
                    INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                    LEFT JOIN inventario_bodega ib ON ib.ID_Producto = dmi.ID_Producto AND ib.ID_Bodega = %s
                    WHERE dmi.ID_Movimiento = %s
                """, (compra['ID_Bodega'], id_movimiento))
                
                productos_stock = cursor.fetchall()
                stock_suficiente = True
                productos_sin_stock = []
                
                for ps in productos_stock:
                    existencias = float(ps['Existencias'] or 0)
                    cantidad_a_retirar = float(ps['Cantidad'] or 0)
                    if existencias < cantidad_a_retirar:
                        stock_suficiente = False
                        productos_sin_stock.append({
                            'producto': ps['Descripcion'],
                            'existencias': existencias,
                            'necesita': cantidad_a_retirar
                        })
                
                datos_respuesta = {
                    'success': True,
                    'compra': {
                        'id': compra['ID_Movimiento'],
                        'factura': compra['N_Factura_Externa'] or 'Sin factura',
                        'tipo_compra': compra['Tipo_Compra'],
                        'fecha': compra['Fecha'].strftime('%d/%m/%Y') if compra['Fecha'] else 'N/A',
                        'total_compra': total_compra,
                        'total_formateado': f"C${total_compra:,.2f}",
                        'proveedor': compra['Proveedor'] or 'Proveedor General',
                        'bodega': compra['Bodega'] or 'N/A',
                        'id_bodega': compra['ID_Bodega'],  # ← AGREGADO
                        'estado': compra['Estado'],
                        'total_productos': compra['Total_Productos'] or 0,
                        'carga_completa': carga_completa,
                        'stock_suficiente': stock_suficiente,
                        'productos_sin_stock': productos_sin_stock
                    }
                }
                
                if carga_completa:
                    # ✅ CORREGIDO: Usar Existencias
                    cursor.execute("""
                        SELECT 
                            p.COD_Producto,
                            p.Descripcion,
                            p.Unidad_Medida,
                            dmi.Cantidad,
                            dmi.Costo_Unitario,
                            dmi.Subtotal,
                            COALESCE(ib.Existencias, 0) as Existencias
                        FROM detalle_movimientos_inventario dmi
                        INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                        LEFT JOIN inventario_bodega ib ON ib.ID_Producto = dmi.ID_Producto AND ib.ID_Bodega = %s
                        WHERE dmi.ID_Movimiento = %s
                        ORDER BY p.Descripcion
                    """, (compra['ID_Bodega'], id_movimiento))
                    
                    productos = cursor.fetchall()
                    
                    if productos:
                        productos_formateados = []
                        total_cantidad = 0
                        
                        for producto in productos:
                            cantidad = float(producto['Cantidad'] or 0)
                            existencias = float(producto['Existencias'] or 0)
                            
                            productos_formateados.append({
                                'codigo': producto['COD_Producto'],
                                'descripcion': producto['Descripcion'],
                                'unidad': producto['Unidad_Medida'],
                                'cantidad': cantidad,
                                'costo_unitario': float(producto['Costo_Unitario'] or 0),
                                'subtotal': float(producto['Subtotal'] or 0),
                                'existencias': existencias,
                                'suficiente_stock': existencias >= cantidad
                            })
                            total_cantidad += cantidad
                        
                        datos_respuesta['compra']['productos'] = productos_formateados
                        datos_respuesta['compra']['total_cantidad'] = total_cantidad
                        datos_respuesta['compra']['stock_suficiente'] = all(p['suficiente_stock'] for p in productos_formateados)
                
                return jsonify(datos_respuesta)
                
        except Exception as e:
            print(f"Error en GET anular compra {id_movimiento}: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Error al obtener datos: {str(e)}'}), 500
    
    # Si es POST, procesar la anulación CON REVERSIÓN DE INVENTARIO
    elif request.method == 'POST':
        try:
            # Obtener datos del formulario
            id_usuario_anulacion = current_user.id
            motivo_anulacion = request.form.get('motivo_anulacion', '').strip()
            
            # Validaciones básicas
            if not id_usuario_anulacion:
                flash('Error: No se especificó el usuario que realiza la anulación', 'error')
                return redirect(url_for('admin.admin_compras_entradas'))
            
            try:
                id_usuario = int(id_usuario_anulacion)
            except (ValueError, TypeError):
                flash('Error: ID de usuario inválido', 'error')
                return redirect(url_for('admin.admin_compras_entradas'))
            
            if not motivo_anulacion:
                motivo_anulacion = f"Compra anulada por usuario ID {id_usuario}"
            
            # 🔥 TRANSACCIÓN COMPLETA - Modifica inventario_bodega (campo Existencias)
            with get_db_cursor(commit=True) as cursor:
                # 1. Verificar que el movimiento existe, está activo y obtener datos
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.Estado,
                        mi.N_Factura_Externa,
                        mi.Observacion,
                        mi.ID_Bodega,
                        COALESCE((
                            SELECT SUM(Subtotal) 
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ), 0) as Total_Compra
                    FROM movimientos_inventario mi
                    WHERE mi.ID_Movimiento = %s
                    FOR UPDATE
                """, (id_movimiento,))
                
                movimiento = cursor.fetchone()
                
                if not movimiento:
                    flash('Error: Compra no encontrada', 'error')
                    return redirect(url_for('admin.admin_compras_entradas'))
                
                if movimiento['Estado'] != 'Activa':
                    flash(f'Error: La compra ya está {movimiento["Estado"].lower()}', 'error')
                    return redirect(url_for('admin.admin_compras_entradas'))
                
                n_factura_externa = movimiento['N_Factura_Externa']
                total_compra = float(movimiento['Total_Compra'] or 0)
                id_bodega = movimiento['ID_Bodega']
                
                # 2. Obtener los detalles de la compra (productos y cantidades)
                cursor.execute("""
                    SELECT 
                        dmi.ID_Producto,
                        dmi.Cantidad,
                        dmi.Costo_Unitario,
                        dmi.Subtotal,
                        p.Descripcion
                    FROM detalle_movimientos_inventario dmi
                    INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE dmi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                detalles = cursor.fetchall()
                
                if not detalles:
                    flash('Error: No se encontraron productos en esta compra', 'error')
                    return redirect(url_for('admin.admin_compras_entradas'))
                
                # 3. 🔥 REVERTIR EL INVENTARIO - ACTUALIZAR Existencias en inventario_bodega
                productos_actualizados = []
                
                for detalle in detalles:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    nombre_producto = detalle['Descripcion']
                    
                    # Obtener existencias actuales del producto en la bodega (con lock)
                    cursor.execute("""
                        SELECT Existencias 
                        FROM inventario_bodega 
                        WHERE ID_Producto = %s AND ID_Bodega = %s
                        FOR UPDATE
                    """, (id_producto, id_bodega))
                    
                    inventario = cursor.fetchone()
                    
                    if not inventario:
                        # Si no existe registro, significa que el producto no tiene existencias
                        raise Exception(
                            f"No se puede anular la compra. El producto '{nombre_producto}' "
                            f"no tiene registro de inventario en la bodega. "
                            f"Debe tener existencias para poder retirar {cantidad} unidades."
                        )
                    else:
                        existencias_actuales = float(inventario['Existencias'])
                    
                    # 🔥 RESTAR la cantidad (esto es lo que QUITA del inventario)
                    nuevas_existencias = existencias_actuales - cantidad
                    
                    # Validar que no quede existencias negativo
                    if nuevas_existencias < 0:
                        raise Exception(
                            f"⚠️ Existencias insuficientes para anular la compra.\n"
                            f"Producto: {nombre_producto}\n"
                            f"Existencias actuales en bodega: {existencias_actuales}\n"
                            f"Cantidad a retirar (por la anulación): {cantidad}\n"
                            f"Resultaría en existencias negativas: {nuevas_existencias}\n\n"
                            f"Sugerencia: Revise si este producto ya fue vendido o movido."
                        )
                    
                    # 🔥 ACTUALIZAR inventario_bodega (RESTAR las existencias)
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = %s
                        WHERE ID_Producto = %s AND ID_Bodega = %s
                    """, (nuevas_existencias, id_producto, id_bodega))
                    
                    productos_actualizados.append({
                        'producto': nombre_producto,
                        'existencias_anteriores': existencias_actuales,
                        'cantidad_retirada': cantidad,
                        'existencias_nuevas': nuevas_existencias
                    })
                    
                    # Opcional: Registrar en tabla de auditoría de inventario si existe
                    try:
                        # Verificar si existe la tabla auditoria_inventario
                        cursor.execute("""
                            SELECT COUNT(*) as existe 
                            FROM information_schema.tables 
                            WHERE table_name = 'auditoria_inventario'
                        """)
                        if cursor.fetchone()['existe'] > 0:
                            cursor.execute("""
                                INSERT INTO auditoria_inventario 
                                (ID_Producto, ID_Bodega, Tipo_Movimiento, Cantidad, Existencias_Anterior, Existencias_Nueva, 
                                 Referencia, ID_Usuario, Fecha_Movimiento)
                                VALUES (%s, %s, 'ANULACION_COMPRA', %s, %s, %s, %s, %s, NOW())
                            """, (id_producto, id_bodega, -cantidad, existencias_actuales, nuevas_existencias, 
                                  f"Anulación compra #{id_movimiento}", id_usuario))
                    except Exception as e:
                        print(f"Nota: No se pudo registrar en auditoría: {e}")
                
                # 4. Actualizar observación con el motivo de anulación y detalle de inventario
                resumen_inventario = "\n".join([
                    f"  • {p['producto']}: se retiraron {p['cantidad_retirada']} unidades (existencias: {p['existencias_anteriores']} → {p['existencias_nuevas']})"
                    for p in productos_actualizados
                ])
                
                nueva_observacion = (
                    f"{movimiento['Observacion'] or ''}\n"
                    f"{'='*60}\n"
                    f"[ANULACIÓN] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Usuario: {id_usuario}\n"
                    f"Motivo: {motivo_anulacion}\n"
                    f"INVENTARIO MODIFICADO (productos retirados):\n"
                    f"{resumen_inventario}\n"
                    f"{'='*60}"
                )
                
                if len(nueva_observacion) > 65535:
                    nueva_observacion = nueva_observacion[:65530] + "..."
                
                # 5. Cambiar el estado a 'Anulada'
                cursor.execute("""
                    UPDATE movimientos_inventario 
                    SET Estado = 'Anulada',
                        ID_Usuario_Modificacion = %s,
                        Fecha_Modificacion = NOW(),
                        Observacion = %s
                    WHERE ID_Movimiento = %s
                """, (id_usuario, nueva_observacion, id_movimiento))
                
                # 6. Registrar en bitácora
                try:
                    cursor.execute("""
                        INSERT INTO bitacora 
                        (ID_Usuario, Fecha, Modulo, Accion, IP_Acceso, Detalle)
                        VALUES (%s, NOW(), 'COMPRAS', 'ANULACION_COMPRA', %s, %s)
                    """, (id_usuario, request.remote_addr or '127.0.0.1', 
                          f"Compra #{id_movimiento} anulada. Se retiraron {len(detalles)} productos del inventario_bodega"))
                except Exception as e:
                    print(f"Nota: No se pudo registrar en bitácora: {e}")
                
                # 7. Mensaje de éxito DETALLADO
                resumen_html = "<br>".join([
                    f"• {p['producto']}: {p['cantidad_retirada']} unidades (existencias: {p['existencias_anteriores']} → {p['existencias_nuevas']})"
                    for p in productos_actualizados
                ])
                
                from markupsafe import Markup
                mensaje = Markup(
                    f"✅ <strong>Compra anulada exitosamente</strong><br>"
                    f"• Número de compra: #{id_movimiento}<br>"
                    f"• Factura: {n_factura_externa or 'N/A'}<br>"
                    f"• Total compra: C${total_compra:,.2f}<br>"
                    f"• Productos retirados del inventario: {len(detalles)}<br>"
                    f"• Motivo: {motivo_anulacion[:100]}<br><br>"
                    f"<strong>📦 Detalle de inventario actualizado (tabla inventario_bodega):</strong><br>"
                    f"{resumen_html}<br>"
                    f"<span class='text-success'>✓ Se ha actualizado correctamente el campo Existencias en inventario_bodega</span>"
                )
                
                flash(mensaje, 'success')
            
            return redirect(url_for('admin.admin_compras_entradas'))
            
        except Exception as e:
            print(f"Error al anular compra {id_movimiento}: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'❌ Error al anular compra: {str(e)}', 'error')
            return redirect(url_for('admin.admin_compras_entradas'))

@admin_bp.route('/admin/compras/detalle-completo/<int:id_movimiento>', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-DETALLE-COMPLETO")
def admin_detalle_compra_completo(id_movimiento):
    try:
        # Obtener ID de empresa desde la sesión
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # 1. Obtener información general del movimiento de compra
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    DATE_FORMAT(mi.Fecha, '%%d/%%m/%%Y') as Fecha_Formateada,
                    mi.Fecha as Fecha_Original,
                    mi.N_Factura_Externa,
                    mi.Observacion,
                    mi.ID_Usuario_Creacion,
                    mi.ID_Usuario_Modificacion,
                    mi.Fecha_Creacion,
                    mi.Fecha_Modificacion,
                    mi.Estado as Estado_Movimiento,
                    mi.Tipo_Compra,
                    mi.ID_Bodega,
                    mi.ID_Proveedor,
                    -- Datos del proveedor
                    p.Nombre as Proveedor,
                    p.RUC_CEDULA as RUC_Proveedor,
                    p.Direccion as Direccion_Proveedor,
                    p.Telefono as Telefono_Proveedor,
                    -- Datos de la bodega
                    b.Nombre as Bodega,
                    b.Ubicacion as Direccion_Bodega,
                    -- Datos de usuarios
                    u.NombreUsuario as Usuario_Creacion,
                    u_mod.NombreUsuario as Usuario_Modificacion,
                    -- Datos de la empresa
                    e.Nombre_Empresa,
                    e.RUC as RUC_Empresa,
                    e.Direccion as Direccion_Empresa,
                    e.Telefono as Telefono_Empresa,
                    -- Formatear tipo de compra
                    CASE 
                        WHEN mi.Tipo_Compra = 'Crédito' THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Compra_Formateado,
                    -- Estado formateado
                    UPPER(mi.Estado) as Estado_Formateado,
                    -- Calcular total de la compra
                    COALESCE(
                        (SELECT SUM(Subtotal) 
                         FROM detalle_movimientos_inventario 
                         WHERE ID_Movimiento = mi.ID_Movimiento), 
                        0
                    ) as Total_Compra,
                    -- Total de productos
                    COALESCE(
                        (SELECT COUNT(*) 
                         FROM detalle_movimientos_inventario 
                         WHERE ID_Movimiento = mi.ID_Movimiento), 
                        0
                    ) as Total_Productos
                FROM movimientos_inventario mi
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN usuarios u_mod ON mi.ID_Usuario_Modificacion = u_mod.ID_Usuario
                LEFT JOIN empresa e ON mi.ID_Empresa = e.ID_Empresa
                WHERE mi.ID_Movimiento = %s 
                  AND mi.ID_Empresa = %s
                LIMIT 1
            """, (id_movimiento, id_empresa))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash('Compra no encontrada o no pertenece a su empresa', 'error')
                return redirect(url_for('admin.admin_compras_entradas'))
            
            # 2. Obtener detalles de los productos comprados
            cursor.execute("""
                SELECT 
                    dmi.ID_Detalle_Movimiento,
                    dmi.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto_Desc,
                    COALESCE(ib.Existencias, 0) as Existencias_Actuales,
                    dmi.Cantidad,
                    dmi.Costo_Unitario,
                    dmi.Precio_Unitario,
                    dmi.Subtotal,
                    um.Descripcion as Unidad_Medida,
                    um.Abreviatura as Simbolo_Medida
                FROM detalle_movimientos_inventario dmi
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON dmi.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (movimiento['ID_Bodega'], id_movimiento))
            
            detalles = cursor.fetchall()
            
            # 3. Obtener información de cuenta por pagar
            cursor.execute("""
                SELECT 
                    ID_Cuenta,
                    Fecha_Vencimiento,
                    Monto_Movimiento,
                    Saldo_Pendiente
                FROM cuentas_por_pagar 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta_por_pagar = cursor.fetchone()
            
            # 4. Calcular totales
            total_productos = len(detalles)
            total_cantidad = sum([detalle['Cantidad'] for detalle in detalles]) if detalles else 0
            
            # 5. Calcular estadísticas de pago
            total_pagado = 0
            if cuenta_por_pagar:
                total_pagado = cuenta_por_pagar['Monto_Movimiento'] - cuenta_por_pagar['Saldo_Pendiente']
            
            return render_template(
                'admin/compras/detalle_compra.html',
                movimiento=movimiento,
                detalles=detalles,
                cuenta_por_pagar=cuenta_por_pagar,
                total_productos=total_productos,
                total_cantidad=total_cantidad,
                total_compra=movimiento['Total_Compra'],
                total_pagado=total_pagado,
                now=datetime.now().date()
            )
            
    except Exception as e:
        print(f"Error al cargar detalle completo de compra: {str(e)}")
        print(f"Error detallado: {traceback.format_exc()}")
        flash(f'Error al cargar detalles: {str(e)}', 'error')
        return redirect(url_for('admin.admin_compras_entradas'))

# CUENTAS POR PAGAR 
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
                            cpp.Estado  -- NUEVO: Incluir el campo Estado
                        FROM cuentas_por_pagar cpp
                        LEFT JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                        WHERE cpp.ID_Cuenta = %s
                        AND cpp.Estado = 'Pendiente'  -- NUEVO: Solo cuentas pendientes
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
                        cpp.Estado,  -- NUEVO: Incluir el campo Estado
                        cpp.ID_Movimiento  -- Para referencia
                    FROM cuentas_por_pagar cpp
                    LEFT JOIN proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                    WHERE cpp.ID_Cuenta = %s
                """, (id_cuenta,))
                
                cuenta = cursor.fetchone()
                
                if not cuenta:
                    flash('Cuenta no encontrada', 'error')
                    return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                # NUEVO: Validar que la cuenta esté pendiente
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
                        Estado = %s  -- NUEVO: Actualizar el estado
                    WHERE ID_Cuenta = %s
                """, (nuevo_saldo, nuevo_estado, id_cuenta))
                
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
            
            # 2. Obtener historial de pagos (ajustado a tu estructura)
            cursor.execute("""
                SELECT 
                    pcp.ID_Pago,
                    DATE(pcp.Fecha) as Fecha_Pago,
                    TIME(pcp.Fecha) as Hora_Pago,
                    pcp.Monto,
                    mp.Nombre as Metodo_Pago,
                    pcp.Detalles_Metodo,
                    pcp.Comentarios,
                    u.NombreUsuario as Usuario_Registro
                FROM pagos_cuentaspagar pcp
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE pcp.ID_Cuenta = %s
                ORDER BY pcp.Fecha DESC
            """, (id_cuenta,))
            
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

##GASTOS
@admin_bp.route('/admin/gastos-operativos', methods=['GET'])
@admin_required
@bitacora_decorator("GASTOS")
def admin_gastos_operativos():
    try:
        # ========== PARÁMETROS DE FILTRO ==========
        filtro_periodo = request.args.get('filtro_periodo', 'dia')
        fecha_especifica = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        semana_num = request.args.get('semana', str(datetime.now().isocalendar()[1]))
        anio_semana = request.args.get('anio_semana', datetime.now().strftime('%Y'))
        mes_filtro = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        anio_filtro = request.args.get('anio', datetime.now().strftime('%Y'))
        
        # Filtros adicionales
        tipo_gasto_id = request.args.get('tipo_gasto', '')
        origen = request.args.get('origen', '')
        proveedor_id = request.args.get('proveedor', '')
        
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            
            # ========== 1. VERIFICAR QUÉ CAMPOS EXISTEN EN LA VISTA ==========
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'vista_gastos_unificados'
            """)
            columnas_existentes = [row['COLUMN_NAME'] for row in cursor.fetchall()]
            
            # Construir SELECT dinámicamente
            select_fields = ['origen', 'tipo_gasto', 'subcategoria', 'fecha', 'monto', 'factura', 'proveedor', 'vehiculo', 'id_gasto']
            
            if 'id_proveedor' in columnas_existentes:
                select_fields.append('id_proveedor')
            else:
                select_fields.append('NULL as id_proveedor')
            
            if 'id_categoria_inv' in columnas_existentes:
                select_fields.append('id_categoria_inv')
            
            query_base = f"""
            SELECT {', '.join(select_fields)}
            FROM vista_gastos_unificados
            WHERE ID_Empresa = %s
            """
            
            params = [id_empresa]
            fecha_inicio_semana = None
            fecha_fin_semana = None
            
            # Filtro de período
            if filtro_periodo == 'dia':
                query_base += " AND fecha = %s"
                params.append(fecha_especifica)
                titulo_periodo = f"Gastos del día {datetime.strptime(fecha_especifica, '%Y-%m-%d').strftime('%d/%m/%Y')}"
                
            elif filtro_periodo == 'semana':
                año = int(anio_semana)
                semana = int(semana_num)
                fecha_inicio_semana = datetime.strptime(f'{año}-W{semana}-1', '%Y-W%W-%w').date()
                fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
                query_base += " AND fecha BETWEEN %s AND %s"
                params.extend([fecha_inicio_semana, fecha_fin_semana])
                titulo_periodo = f"Gastos de la semana {semana_num} ({fecha_inicio_semana.strftime('%d/%m')} - {fecha_fin_semana.strftime('%d/%m/%Y')})"
                
            elif filtro_periodo == 'mes':
                año, mes = mes_filtro.split('-')
                query_base += " AND YEAR(fecha) = %s AND MONTH(fecha) = %s"
                params.extend([año, mes])
                nombre_mes = datetime(int(año), int(mes), 1).strftime('%B %Y')
                titulo_periodo = f"Gastos de {nombre_mes}"
                
            elif filtro_periodo == 'acumulado':
                query_base += " AND YEAR(fecha) = %s AND fecha <= CURDATE()"
                params.append(anio_filtro)
                titulo_periodo = f"Gastos Acumulados {anio_filtro} (Enero - {datetime.now().strftime('%B')})"
                
            elif filtro_periodo == 'anual':
                query_base += " AND YEAR(fecha) = %s"
                params.append(anio_filtro)
                titulo_periodo = f"Gastos del año {anio_filtro}"
                
            elif filtro_periodo == 'todo':
                query_base += " AND fecha >= '2020-01-01'"
                titulo_periodo = "TODOS LOS GASTOS (Histórico completo)"
            
            # Filtros adicionales
            if tipo_gasto_id and tipo_gasto_id.isdigit():
                query_base += " AND id_tipo = %s"
                params.append(int(tipo_gasto_id))
            
            if origen:
                query_base += " AND origen = %s"
                params.append(origen)
            
            if proveedor_id and proveedor_id.isdigit() and 'id_proveedor' in columnas_existentes:
                query_base += " AND id_proveedor = %s"
                params.append(int(proveedor_id))
            
            # Orden
            query_base += " ORDER BY fecha DESC, monto DESC"
            
            cursor.execute(query_base, params)
            resultados = cursor.fetchall()
            
            # Calcular total del período
            total_periodo = sum(float(r['monto'] or 0) for r in resultados)
            
            # ========== 2. TOTALES ACUMULADOS ==========
            query_totales = """
            SELECT 
                'total_compras' AS concepto,
                COALESCE(SUM(dmi.Cantidad * dmi.Costo_Unitario), 0) AS total
            FROM movimientos_inventario mi
            LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
            WHERE mi.Estado = 'Activa' AND mi.ID_TipoMovimiento = 1 AND mi.ID_Empresa = %s
            
            UNION ALL
            
            SELECT 
                'total_gastos' AS concepto,
                COALESCE(SUM(gg.Monto), 0) AS total
            FROM gastos_generales gg
            WHERE gg.Estado = 'Activo' AND gg.ID_Empresa = %s
            """
            cursor.execute(query_totales, [id_empresa, id_empresa])
            totales_acumulados = {row['concepto']: float(row['total'] or 0) for row in cursor.fetchall()}
            
            # ========== 3. LISTAS PARA FILTROS ==========
            
            # Tipos de gasto disponibles
            cursor.execute("""
                SELECT DISTINCT id_tipo, tipo_gasto 
                FROM vista_gastos_unificados 
                WHERE ID_Empresa = %s AND tipo_gasto IS NOT NULL
                ORDER BY tipo_gasto
            """, [id_empresa])
            tipos_gasto_disponibles = cursor.fetchall()
            
            # Proveedores disponibles
            if 'id_proveedor' in columnas_existentes:
                cursor.execute("""
                    SELECT DISTINCT id_proveedor, proveedor 
                    FROM vista_gastos_unificados 
                    WHERE ID_Empresa = %s AND proveedor IS NOT NULL
                    ORDER BY proveedor
                """, [id_empresa])
                proveedores_lista = cursor.fetchall()
            else:
                proveedores_lista = []
            
            años_disponibles = range(2020, datetime.now().year + 2)
            semanas_disponibles = range(1, 54)
            
            return render_template(
                'admin/gastos/gastos_operativos.html',
                # Filtros actuales
                filtro_periodo=filtro_periodo,
                fecha_especifica=fecha_especifica,
                semana_num=semana_num,
                anio_semana=anio_semana,
                mes_filtro=mes_filtro,
                anio_filtro=anio_filtro,
                tipo_gasto_id=tipo_gasto_id,
                origen=origen,
                proveedor_id=proveedor_id,
                # Datos principales
                resultados=resultados,
                total_periodo=total_periodo,
                titulo_periodo=titulo_periodo,
                totales_acumulados=totales_acumulados,
                # Listas para filtros
                tipos_gasto_disponibles=tipos_gasto_disponibles,
                proveedores_lista=proveedores_lista,
                años_disponibles=años_disponibles,
                semanas_disponibles=semanas_disponibles,
                titulo="Control de Gastos - Compras + Gastos Generales"
            )
            
    except Exception as e:
        logger.error(f"Error en gastos operativos: {str(e)}")
        flash(f'Error al cargar los gastos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/gastos/registrar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("REGISTRO_GASTO")
def registrar_gasto():
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Obtener listas para selects
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE Estado = 'Activo' AND ID_Empresa = %s
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Proveedor, Nombre 
                FROM proveedores 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            proveedores = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Vehiculo, Placa, Marca, Modelo 
                FROM vehiculos 
                WHERE ID_Empresa = %s AND Estado != 'Inactivo'
                ORDER BY Placa
            """, [id_empresa])
            vehiculos = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                id_subcategoria = request.form.get('id_subcategoria') or None
                fecha = request.form.get('fecha')
                monto = request.form.get('monto')
                descripcion = request.form.get('descripcion')
                n_factura = request.form.get('n_factura') or None
                id_proveedor = request.form.get('id_proveedor') or None
                id_vehiculo = request.form.get('id_vehiculo') or None
                metodo_pago = request.form.get('metodo_pago')
                # observaciones = request.form.get('observaciones') or None  # ELIMINADO
                
                # Validaciones
                if not id_tipo_gasto:
                    flash('Debe seleccionar un tipo de gasto', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                if not fecha:
                    flash('Debe ingresar una fecha', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                if not monto or float(monto) <= 0:
                    flash('Debe ingresar un monto válido', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                # Insertar gasto (SIN Observaciones)
                cursor.execute("""
                    INSERT INTO gastos_generales (
                        ID_Tipo_Gasto, ID_Subcategoria, Fecha, Monto, Descripcion,
                        N_Factura, ID_Proveedor, ID_Vehiculo, Metodo_Pago, 
                        ID_Empresa, ID_Usuario_Registro
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_gasto, id_subcategoria, fecha, monto, descripcion,
                    n_factura, id_proveedor, id_vehiculo, metodo_pago,
                    id_empresa, id_usuario
                ))
                
                id_gasto = cursor.lastrowid
                
                # Si es gasto de vehículo, registrar detalle adicional
                if id_vehiculo:
                    kilometraje = request.form.get('kilometraje') or None
                    tipo_mantenimiento = request.form.get('tipo_mantenimiento') or None
                    taller = request.form.get('taller') or None
                    
                    cursor.execute("""
                        INSERT INTO gastos_vehiculo_detalle (
                            ID_Gasto, ID_Vehiculo, Kilometraje, Tipo_Mantenimiento, Taller
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (id_gasto, id_vehiculo, kilometraje, tipo_mantenimiento, taller))
                
                flash(f'Gasto registrado exitosamente. Total: C${float(monto):,.2f}', 'success')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            return render_template(
                'admin/gastos/registrar_gastos.html',
                tipos_gasto=tipos_gasto,
                proveedores=proveedores,
                vehiculos=vehiculos,
                hoy=datetime.now().strftime('%Y-%m-%d'),
                titulo="Registrar Nuevo Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al registrar gasto: {str(e)}")
        flash(f'Error al registrar gasto: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

@admin_bp.route('/gastos/get_subcategorias', methods=['GET'])
@admin_required
def get_subcategorias():
    try:
        id_tipo_gasto = request.args.get('id_tipo_gasto')
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Subcategoria, Nombre 
                FROM subcategorias_gasto 
                WHERE ID_Tipo_Gasto = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_tipo_gasto])
            subcategorias = cursor.fetchall()
            
        return jsonify({'success': True, 'subcategorias': subcategorias})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/admin/gastos/ver/<int:id_gasto>', methods=['GET'])
@admin_required
def ver_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    gg.*,
                    tg.Nombre AS tipo_gasto_nombre,
                    sg.Nombre AS subcategoria_nombre,
                    pr.Nombre AS proveedor_nombre,
                    v.Placa AS vehiculo_placa,
                    u.NombreUsuario AS usuario_registro_nombre
                FROM gastos_generales gg
                LEFT JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                LEFT JOIN subcategorias_gasto sg ON gg.ID_Subcategoria = sg.ID_Subcategoria
                LEFT JOIN proveedores pr ON gg.ID_Proveedor = pr.ID_Proveedor
                LEFT JOIN vehiculos v ON gg.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios u ON gg.ID_Usuario_Registro = u.ID_Usuario
                WHERE gg.ID_Gasto = %s AND gg.ID_Empresa = %s
            """, [id_gasto, id_empresa])
            gasto = cursor.fetchone()
            
            if not gasto:
                flash('Gasto no encontrado', 'error')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            # Obtener detalle de vehículo si aplica
            detalle_vehiculo = None
            if gasto['ID_Vehiculo']:
                cursor.execute("""
                    SELECT * FROM gastos_vehiculo_detalle WHERE ID_Gasto = %s
                """, [id_gasto])
                detalle_vehiculo = cursor.fetchone()
            
            return render_template(
                'admin/gastos/ver_gasto.html',
                gasto=gasto,
                detalle_vehiculo=detalle_vehiculo,
                titulo="Detalle del Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al ver gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

@admin_bp.route('/admin/gastos/anular/<int:id_gasto>', methods=['POST'])
@admin_required
@bitacora_decorator("ANULAR_GASTO")
def anular_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                UPDATE gastos_generales 
                SET Estado = 'Anulado', 
                    ID_Usuario_Registro = %s,
                    Observaciones = CONCAT(IFNULL(Observaciones, ''), ' [ANULADO por usuario ', %s, ']')
                WHERE ID_Gasto = %s AND ID_Empresa = %s
            """, [id_usuario, id_usuario, id_gasto, id_empresa])
            
            if cursor.rowcount == 0:
                flash('No se pudo anular el gasto', 'error')
            else:
                flash('Gasto anulado correctamente', 'success')
                
    except Exception as e:
        logger.error(f"Error al anular gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_gastos_operativos'))