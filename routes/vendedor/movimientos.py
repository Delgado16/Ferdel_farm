# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import convertir_hora_db, procesar_asignacion, procesar_lista_asignaciones

@vendedor_bp.route('/vendedor/movimientos/entrada-bodega', methods=['GET', 'POST'])
@vendedor_required
def vendedor_movimiento_entrada_bodega():
    """
    Registra una entrada de inventario desde bodega central
    Usando ID_TipoMovimiento = 13 (Traslado Entrada)
    """

    id_empresa = session.get('id_empresa', 1)

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            documento = request.form.get('documento_numero', '')
            
            with get_db_cursor(True) as cursor:
                # ============================================
                # 1. VERIFICAR ASIGNACIÓN ACTIVA
                # ============================================
                cursor.execute("""
                    SELECT 
                        av.ID_Asignacion,
                        av.ID_Ruta,
                        r.Nombre_Ruta
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    WHERE av.ID_Usuario = %s
                    AND av.Estado = 'Activa'
                    ORDER BY av.Fecha_Asignacion DESC
                    LIMIT 1
                """, (current_user.id,))
                
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una asignación activa para hoy', 'error')
                    return redirect(url_for('vendedor.vendedor_inventario'))
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ============================================
                # 2. DEFINIR TIPO DE MOVIMIENTO (Traslado Entrada)
                # ============================================
                ID_TIPO_ENTRADA = 1  # Traslado Entrada
                
                # ============================================
                # 3. PROCESAR PRODUCTOS Y CALCULAR TOTALES
                # ============================================
                total_productos = 0
                total_items = 0
                total_subtotal = 0
                productos_procesar = []
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        
                        # Obtener precio del producto
                        cursor.execute("""
                            SELECT Precio_Ruta 
                            FROM productos 
                            WHERE ID_Producto = %s
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            continue
                            
                        precio = float(producto_info['Precio_Ruta'])
                        subtotal = cantidad * precio
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'precio': precio,
                            'subtotal': subtotal
                        })
                        
                        total_productos += 1
                        total_items += 1
                        total_subtotal += subtotal
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_movimiento_entrada_bodega'))
                
                # ============================================
                # 4. CREAR MOVIMIENTO CABECERA
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera 
                    (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                     Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                     ID_Empresa, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_asignacion, 
                    ID_TIPO_ENTRADA, 
                    current_user.id,
                    documento, 
                    total_productos, 
                    total_items, 
                    total_subtotal,
                    id_empresa
                ))
                
                id_movimiento = cursor.lastrowid
                
                # ============================================
                # 5. CREAR DETALLES Y ACTUALIZAR INVENTARIO
                # ============================================
                for prod in productos_procesar:
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        prod['id_producto'], 
                        prod['cantidad'], 
                        prod['precio'], 
                        prod['subtotal']
                    ))
                    
                    # Actualizar inventario (SUMAR cantidad)
                    cursor.execute("""
                        INSERT INTO inventario_ruta 
                        (ID_Asignacion, ID_Producto, Cantidad)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Cantidad = Cantidad + VALUES(Cantidad)
                    """, (id_asignacion, prod['id_producto'], prod['cantidad']))
                
                flash('Entrada de inventario registrada exitosamente', 'success')
                return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento))
                    
        except Exception as e:
            print(f"Error en movimiento entrada: {str(e)}")
            traceback.print_exc()
            flash(f'Error al registrar entrada: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # ============================================
    # MÉTODO GET - MOSTRAR FORMULARIO
    # ============================================
    try:
        with get_db_cursor(True) as cursor:
            # Verificar asignación
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener productos activos
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.Precio_Ruta,
                    um.Abreviatura as Unidad,
                    c.Descripcion as Categoria
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE p.Estado = 'activo'
                ORDER BY c.Descripcion, p.Descripcion
            """)
            
            productos = cursor.fetchall()
            
            return render_template('vendedor/inventario/movimiento_entrada_bodega.html',
                                 asignacion=asignacion,
                                 productos=productos,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))


@vendedor_bp.route('/vendedor/movimientos/devolucion-bodega', methods=['GET', 'POST'])
@vendedor_required
def vendedor_movimiento_devolucion_bodega():
    """
    Registra una devolución de productos no vendidos a bodega central
    Usando ID_TipoMovimiento = 11 (Devolucion Ruta)
    """

    id_empresa = session.get('id_empresa', 1)

    if request.method == 'POST':
        try:
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            observacion = request.form.get('observacion', '')
            documento = request.form.get('documento_numero', '')
            
            with get_db_cursor(True) as cursor:
                # ============================================
                # 1. VERIFICAR ASIGNACIÓN ACTIVA
                # ============================================
                cursor.execute("""
                    SELECT 
                        av.ID_Asignacion,
                        av.ID_Ruta,
                        r.Nombre_Ruta
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    WHERE av.ID_Usuario = %s
                    AND av.Estado = 'Activa'
                    ORDER BY av.Fecha_Asignacion DESC
                    LIMIT 1
                """, (current_user.id,))
                
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una asignación activa para hoy', 'error')
                    return redirect(url_for('vendedor.vendedor_inventario'))
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ============================================
                # 2. DEFINIR TIPOS DE MOVIMIENTO
                # ============================================
                ID_TIPO_DEVOLUCION_RUTA = 11  # Devolucion Ruta (para tabla de rutas)
                ID_TIPO_ENTRADA_BODEGA = 11    # Entrada a bodega por devolución (ajusta según tu catálogo)
                ID_BODEGA_CENTRAL = 1          # ID de la bodega central según tu tabla bodegas
                
                # ============================================
                # 3. VALIDAR STOCK Y CALCULAR TOTALES
                # ============================================
                productos_procesar = []
                total_productos = 0
                total_items = 0
                total_subtotal = 0
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        
                        # Verificar stock actual en ruta
                        cursor.execute("""
                            SELECT Cantidad 
                            FROM inventario_ruta 
                            WHERE ID_Asignacion = %s AND ID_Producto = %s
                        """, (id_asignacion, id_producto))
                        
                        stock = cursor.fetchone()
                        if not stock or float(stock['Cantidad']) < cantidad:
                            flash(f'Stock insuficiente para devolución. Stock actual: {float(stock["Cantidad"]) if stock else 0}', 'error')
                            return redirect(url_for('vendedor.vendedor_movimiento_devolucion_bodega'))
                        
                        # Obtener precio del producto (Precio_Ruta)
                        cursor.execute("""
                            SELECT Precio_Ruta 
                            FROM productos 
                            WHERE ID_Producto = %s
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            continue
                            
                        precio_ruta = float(producto_info['Precio_Ruta'])
                        subtotal = cantidad * precio_ruta
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'precio_ruta': precio_ruta,
                            'subtotal': subtotal
                        })
                        
                        total_productos += 1
                        total_items += 1
                        total_subtotal += subtotal
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_movimiento_devolucion_bodega'))
                
                # ============================================
                # 4. CREAR MOVIMIENTO EN movimientos_ruta_cabecera
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera 
                    (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                     Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                     ID_Empresa, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_asignacion, 
                    ID_TIPO_DEVOLUCION_RUTA, 
                    current_user.id,
                    documento, 
                    total_productos, 
                    total_items, 
                    total_subtotal,
                    id_empresa
                ))
                
                id_movimiento_ruta = cursor.lastrowid
                
                # ============================================
                # 5. CREAR MOVIMIENTO EN movimientos_inventario (TABLA GENERAL)
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (ID_TipoMovimiento, N_Factura_Externa, Fecha, Observacion, 
                     ID_Empresa, ID_Bodega, ID_Usuario_Creacion, Estado)
                    VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, 'Activa')
                """, (
                    ID_TIPO_ENTRADA_BODEGA,
                    documento,
                    f"Devolución de ruta: {asignacion['Nombre_Ruta']} - {observacion}" if observacion else f"Devolución de ruta: {asignacion['Nombre_Ruta']}",
                    id_empresa,
                    ID_BODEGA_CENTRAL,
                    current_user.id
                ))
                
                id_movimiento_inventario = cursor.lastrowid
                
                # ============================================
                # 6. CREAR DETALLES Y ACTUALIZAR INVENTARIOS
                # ============================================
                for prod in productos_procesar:
                    # Insertar detalle en movimientos_ruta_detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_ruta, 
                        prod['id_producto'], 
                        prod['cantidad'], 
                        prod['precio_ruta'], 
                        prod['subtotal']
                    ))
                    
                    # Insertar detalle en detalle_movimientos_inventario (tabla general)
                    # Nota: Como no tenemos precio de costo, usamos Precio_Ruta como referencia
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_inventario,
                        prod['id_producto'],
                        prod['cantidad'],
                        prod['precio_ruta'],  # Precio_Unitario
                        prod['subtotal'],      # Subtotal
                        current_user.id
                    ))
                    
                    # Actualizar inventario_ruta (RESTAR cantidad)
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad - %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (prod['cantidad'], id_asignacion, prod['id_producto']))
                    
                    # Actualizar inventario_bodega (SUMAR cantidad)
                    cursor.execute("""
                        INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Existencias = Existencias + %s
                    """, (
                        ID_BODEGA_CENTRAL,
                        prod['id_producto'],
                        prod['cantidad'],
                        prod['cantidad']
                    ))
                
                flash('Devolución a bodega registrada exitosamente', 'success')
                return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento_ruta))
                    
        except Exception as e:
            print(f"Error en devolución: {str(e)}")
            traceback.print_exc()
            flash(f'Error al registrar devolución: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # ============================================
    # MÉTODO GET - MOSTRAR FORMULARIO
    # ============================================
    try:
        with get_db_cursor(True) as cursor:
            # Verificar asignación
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener inventario actual (solo productos con stock)
            cursor.execute("""
                SELECT 
                    ir.ID_Producto,
                    ir.Cantidad as Stock_Actual,
                    p.COD_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.Precio_Ruta,
                    um.Abreviatura as Unidad,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            return render_template('vendedor/inventario/movimiento_devolucion_bodega.html',
                                 asignacion=asignacion,
                                 inventario=inventario,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))


@vendedor_bp.route('/vendedor/movimientos/merma', methods=['GET', 'POST'])
@vendedor_required
def vendedor_movimiento_merma():
    """
    Registra una salida por merma/pérdida de productos
    Usando ID_TipoMovimiento = 7 (Merma)
    """
    id_empresa = session.get('id_empresa', 1)

    if request.method == 'POST':
        try:
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            documento = request.form.get('documento_numero', '')
            
            with get_db_cursor(True) as cursor:
                # ============================================
                # 1. VERIFICAR ASIGNACIÓN ACTIVA
                # ============================================
                cursor.execute("""
                    SELECT 
                        av.ID_Asignacion,
                        av.ID_Ruta,
                        r.Nombre_Ruta
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    WHERE av.ID_Usuario = %s
                    AND av.Estado = 'Activa'
                    ORDER BY av.Fecha_Asignacion DESC
                    LIMIT 1
                """, (current_user.id,))
                
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una asignación activa para hoy', 'error')
                    return redirect(url_for('vendedor.vendedor_inventario'))
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ============================================
                # 2. DEFINIR TIPO DE MOVIMIENTO (Merma)
                # ============================================
                ID_TIPO_MERMA = 7  # Merma
                
                # ============================================
                # 3. VALIDAR STOCK Y CALCULAR TOTALES
                # ============================================
                productos_procesar = []
                total_productos = 0
                total_items = 0
                total_subtotal = 0
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        
                        # Verificar stock actual
                        cursor.execute("""
                            SELECT Cantidad 
                            FROM inventario_ruta 
                            WHERE ID_Asignacion = %s AND ID_Producto = %s
                        """, (id_asignacion, id_producto))
                        
                        stock = cursor.fetchone()
                        if not stock or float(stock['Cantidad']) < cantidad:
                            flash(f'Stock insuficiente para merma. Stock actual: {float(stock["Cantidad"]) if stock else 0}', 'error')
                            return redirect(url_for('vendedor.vendedor_movimiento_merma'))
                        
                        # Obtener precio del producto
                        cursor.execute("""
                            SELECT Precio_Ruta 
                            FROM productos 
                            WHERE ID_Producto = %s
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            continue
                            
                        precio = float(producto_info['Precio_Ruta'])
                        subtotal = cantidad * precio
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'precio': precio,
                            'subtotal': subtotal
                        })
                        
                        total_productos += 1
                        total_items += 1
                        total_subtotal += subtotal
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_movimiento_merma'))
                
                # ============================================
                # 4. CREAR MOVIMIENTO CABECERA
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera 
                    (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                     Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                     ID_Empresa, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_asignacion, 
                    ID_TIPO_MERMA, 
                    current_user.id,
                    documento, 
                    total_productos, 
                    total_items, 
                    total_subtotal,
                    id_empresa, 
                ))
                
                id_movimiento = cursor.lastrowid
                
                # ============================================
                # 5. CREAR DETALLES Y ACTUALIZAR INVENTARIO
                # ============================================
                for prod in productos_procesar:
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        prod['id_producto'], 
                        prod['cantidad'], 
                        prod['precio'], 
                        prod['subtotal']
                    ))
                    
                    # Actualizar inventario (RESTAR cantidad)
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad - %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (prod['cantidad'], id_asignacion, prod['id_producto']))
                
                flash('Merma registrada exitosamente', 'success')
                return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento))
                    
        except Exception as e:
            print(f"Error en merma: {str(e)}")
            traceback.print_exc()
            flash(f'Error al registrar merma: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # ============================================
    # MÉTODO GET - MOSTRAR FORMULARIO
    # ============================================
    try:
        with get_db_cursor(True) as cursor:
            # Verificar asignación
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener inventario actual (solo productos con stock)
            cursor.execute("""
                SELECT 
                    ir.ID_Producto,
                    ir.Cantidad as Stock_Actual,
                    p.COD_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.Precio_Ruta,
                    um.Abreviatura as Unidad,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            return render_template('vendedor/inventario/movimiento_merma.html',
                                 asignacion=asignacion,
                                 inventario=inventario,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))


@vendedor_bp.route('/vendedor/movimientos/historial')
@vendedor_required
def vendedor_movimientos_historial():
    """
    Muestra el historial de movimientos de inventario del vendedor
    Incluye traslados de bodega central a ruta
    """
    try:
        with get_db_cursor(True) as cursor:
            # ============================================
            # 1. OBTENER ASIGNACION ACTIVA
            # ============================================
            from datetime import date
            hoy_local = date.today()
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    av.ID_Ruta,
                    r.Nombre_Ruta,
                    av.ID_Empresa,
                    av.Fecha_Asignacion,
                    av.Fecha_Finalizacion
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND %s BETWEEN av.Fecha_Asignacion AND COALESCE(av.Fecha_Finalizacion, %s)
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id, hoy_local, hoy_local))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignacion activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # ============================================
            # 2. OBTENER MOVIMIENTOS (INCLUYENDO TRASLADOS)
            # ============================================
            cursor.execute("""
                SELECT 
                    mrc.ID_Movimiento,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra as Tipo_Letra,
                    mrc.Fecha_Movimiento,
                    mrc.Documento_Numero,
                    CAST(COALESCE(mrc.Total_Productos, 0) AS DECIMAL(12,2)) as Total_Productos,
                    CAST(COALESCE(mrc.Total_Subtotal, 0) AS DECIMAL(12,2)) as Total_Subtotal,
                    COALESCE(mrc.Total_Items, 0) as Total_Items,
                    mrc.Estado,
                    u.NombreUsuario as Usuario_Registra,
                    CASE 
                        WHEN mrc.ID_TipoMovimiento = 13 THEN 'Traslado Entrada (Bodega -> Ruta)'
                        WHEN mrc.ID_TipoMovimiento = 12 THEN 'Traslado Salida (Bodega -> Ruta)'
                        WHEN mrc.ID_TipoMovimiento = 6 THEN 'Traslado Interno'
                        WHEN mrc.ID_TipoMovimiento = 15 THEN 'Entrada por Carga'
                        WHEN mrc.ID_TipoMovimiento = 7 THEN 'Merma'
                        WHEN mrc.ID_TipoMovimiento = 11 THEN 'Devolucion Ruta'
                        WHEN mrc.ID_TipoMovimiento = 1 THEN 'Compra'
                        WHEN mrc.ID_TipoMovimiento = 2 THEN 'Venta'
                        WHEN mrc.ID_TipoMovimiento = 3 THEN 'Produccion'
                        WHEN mrc.ID_TipoMovimiento = 4 THEN 'Consumo'
                        WHEN mrc.ID_TipoMovimiento = 5 THEN 'Ajuste Salida'
                        WHEN mrc.ID_TipoMovimiento = 8 THEN 'Ajuste Entrada'
                        WHEN mrc.ID_TipoMovimiento = 14 THEN 'Salida por Entrega'
                        ELSE cm.Descripcion
                    END as Descripcion_Detallada
                FROM movimientos_ruta_cabecera mrc
                INNER JOIN catalogo_movimientos cm 
                    ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN usuarios u 
                    ON mrc.ID_Usuario_Registra = u.ID_Usuario
                WHERE mrc.ID_Asignacion = %s
                    AND mrc.ID_TipoMovimiento IN (1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15)
                    AND mrc.Estado = 'ACTIVO'
                ORDER BY mrc.Fecha_Movimiento DESC
            """, (asignacion['ID_Asignacion'],))
            
            movimientos = cursor.fetchall()
            
            # Convertir valores numericos
            for mov in movimientos:
                if 'Total_Productos' in mov:
                    mov['Total_Productos'] = float(mov['Total_Productos']) if mov['Total_Productos'] else 0.0
                if 'Total_Subtotal' in mov:
                    mov['Total_Subtotal'] = float(mov['Total_Subtotal']) if mov['Total_Subtotal'] else 0.0
                if 'Total_Items' in mov:
                    mov['Total_Items'] = int(mov['Total_Items']) if mov['Total_Items'] else 0
            
            # ============================================
            # 3. RESUMEN SIMPLIFICADO
            # ============================================
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN mrc.ID_TipoMovimiento = 13 THEN 'Traslado Entrada (Bodega -> Ruta)'
                        WHEN mrc.ID_TipoMovimiento = 12 THEN 'Traslado Salida (Bodega -> Ruta)'
                        WHEN mrc.ID_TipoMovimiento = 6 THEN 'Traslado Interno'
                        WHEN mrc.ID_TipoMovimiento = 15 THEN 'Entrada por Carga'
                        WHEN mrc.ID_TipoMovimiento = 7 THEN 'Merma'
                        WHEN mrc.ID_TipoMovimiento = 11 THEN 'Devolucion Ruta'
                        WHEN mrc.ID_TipoMovimiento = 1 THEN 'Compra'
                        WHEN mrc.ID_TipoMovimiento = 2 THEN 'Venta'
                        WHEN mrc.ID_TipoMovimiento = 3 THEN 'Produccion'
                        WHEN mrc.ID_TipoMovimiento = 4 THEN 'Consumo'
                        WHEN mrc.ID_TipoMovimiento = 5 THEN 'Ajuste Salida'
                        WHEN mrc.ID_TipoMovimiento = 8 THEN 'Ajuste Entrada'
                        WHEN mrc.ID_TipoMovimiento = 14 THEN 'Salida por Entrega'
                        ELSE cm.Descripcion
                    END as Tipo_Movimiento,
                    COUNT(*) as Cantidad_Movimientos,
                    CAST(SUM(COALESCE(mrc.Total_Productos, 0)) AS DECIMAL(12,2)) as Total_Productos
                FROM movimientos_ruta_cabecera mrc
                INNER JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mrc.ID_Asignacion = %s
                AND mrc.ID_TipoMovimiento IN (1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15)
                AND mrc.Estado = 'ACTIVO'
                GROUP BY Tipo_Movimiento
                ORDER BY Cantidad_Movimientos DESC
            """, (asignacion['ID_Asignacion'],))
            
            resumen_movimientos = cursor.fetchall()
            
            # Convertir valores del resumen
            for res in resumen_movimientos:
                if 'Total_Productos' in res:
                    res['Total_Productos'] = float(res['Total_Productos']) if res['Total_Productos'] else 0.0
            
            return render_template('vendedor/inventario/historial_movimientos.html',
                                 movimientos=movimientos,
                                 resumen_movimientos=resumen_movimientos,
                                 asignacion=asignacion,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error en vendedor_movimientos_historial: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar historial: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))


@vendedor_bp.route('/movimientos/detalle/<int:id_movimiento>')
@vendedor_required
def vendedor_movimiento_detalle(id_movimiento):
    """
    Muestra el detalle de un movimiento específico
    """
    try:
        print(f"\n=== DEPURACIÓN DETALLE MOVIMIENTO ===")
        print(f"ID Movimiento solicitado: {id_movimiento}")
        print(f"Usuario actual ID: {current_user.id if hasattr(current_user, 'id') else 'No ID'}")
        
        # Validar que el usuario tenga ID válido
        if not hasattr(current_user, 'id') or not current_user.id:
            flash('Sesión inválida o usuario no identificado', 'error')
            return redirect(url_for('vendedor.vendedor_movimientos_historial'))
        
        with get_db_cursor(True) as cursor:
            from datetime import date
            hoy_local = date.today()
            # Obtener asignación activa del vendedor primero
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s 
                AND Estado = 'Activa'
                AND %s BETWEEN Fecha_Asignacion AND COALESCE(Fecha_Finalizacion, %s)
                ORDER BY Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id, hoy_local, hoy_local))
            
            asignacion_activa = cursor.fetchone()
            id_asignacion_activa = asignacion_activa['ID_Asignacion'] if asignacion_activa else None
            
            print(f"Asignación activa encontrada: {id_asignacion_activa}")
            
            # CONSULTA PRINCIPAL CORREGIDA
            # Primero verificamos permisos sin LEFT JOIN problemáticos
            query_permiso = """
                SELECT 
                    mrc.ID_Movimiento,
                    mrc.ID_Asignacion,
                    mrc.ID_TipoMovimiento,
                    mrc.ID_Usuario_Registra
                FROM movimientos_ruta_cabecera mrc
                WHERE mrc.ID_Movimiento = %s
                AND mrc.Estado = 'ACTIVO'
            """
            
            cursor.execute(query_permiso, (id_movimiento,))
            movimiento_base = cursor.fetchone()
            
            if not movimiento_base:
                flash(f'Movimiento #{id_movimiento} no existe o está anulado', 'error')
                return redirect(url_for('vendedor.vendedor_movimientos_historial'))
            
            # Verificar permisos: 
            # 1. El movimiento pertenece a la asignación activa del vendedor
            # 2. O el vendedor fue quien registró el movimiento
            tiene_permiso = False
            
            if movimiento_base['ID_Asignacion'] == id_asignacion_activa:
                tiene_permiso = True
                print("Permiso concedido: Movimiento pertenece a asignación activa")
            elif movimiento_base['ID_Usuario_Registra'] == current_user.id:
                tiene_permiso = True
                print("Permiso concedido: Vendedor registró el movimiento")
            else:
                # Verificar si el movimiento pertenece a alguna asignación anterior del vendedor
                cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM asignacion_vendedores
                    WHERE ID_Asignacion = %s
                    AND ID_Usuario = %s
                """, (movimiento_base['ID_Asignacion'], current_user.id))
                
                asignacion_anterior = cursor.fetchone()
                if asignacion_anterior and asignacion_anterior['total'] > 0:
                    tiene_permiso = True
                    print("Permiso concedido: Movimiento pertenece a asignación anterior del vendedor")
            
            if not tiene_permiso:
                flash('No tienes permiso para ver este movimiento', 'error')
                return redirect(url_for('vendedor.vendedor_movimientos_historial'))
            
            # Ahora obtener todos los datos del movimiento con JOINs simplificados
            query = """
                SELECT 
                    mrc.ID_Movimiento,
                    mrc.ID_Asignacion,
                    mrc.ID_TipoMovimiento,
                    mrc.Fecha_Movimiento,
                    mrc.Documento_Numero,
                    mrc.Total_Productos,
                    mrc.Total_Items,
                    mrc.Total_Subtotal,
                    mrc.Estado,
                    mrc.ID_Cliente,
                    mrc.ID_Pedido,
                    cm.Descripcion as Tipo_Movimiento_Desc,
                    cm.Letra as Tipo_Letra,
                    u.NombreUsuario as Usuario_Registra,
                    r.Nombre_Ruta,
                    fr.Credito_Contado,
                    CASE 
                        WHEN mrc.ID_TipoMovimiento = 13 THEN 'Carga de Productos'
                        WHEN mrc.ID_TipoMovimiento = 1 THEN 'Compra'
                        WHEN mrc.ID_TipoMovimiento = 2 THEN 'Venta'
                        WHEN mrc.ID_TipoMovimiento = 7 THEN 'Merma'
                        WHEN mrc.ID_TipoMovimiento = 11 THEN 'Devolución'
                        ELSE cm.Descripcion
                    END as Descripcion_Detallada
                FROM movimientos_ruta_cabecera mrc
                INNER JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN usuarios u ON mrc.ID_Usuario_Registra = u.ID_Usuario
                LEFT JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN facturacion_ruta fr ON mrc.ID_Movimiento = fr.ID_Movimiento
                WHERE mrc.ID_Movimiento = %s
            """
            
            cursor.execute(query, (id_movimiento,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash('Error al cargar datos del movimiento', 'error')
                return redirect(url_for('vendedor.vendedor_movimientos_historial'))
            
            # Convertir valores numéricos
            movimiento['Total_Productos'] = float(movimiento.get('Total_Productos', 0) or 0)
            movimiento['Total_Subtotal'] = float(movimiento.get('Total_Subtotal', 0) or 0)
            
            # Obtener detalles del movimiento
            cursor.execute("""
                SELECT 
                    mrd.ID_Detalle,
                    mrd.Cantidad,
                    mrd.Precio_Unitario,
                    mrd.Subtotal,
                    mrd.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto_Nombre,
                    um.Abreviatura as Unidad_Medida
                FROM movimientos_ruta_detalle mrd
                INNER JOIN productos p ON mrd.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE mrd.ID_Movimiento = %s
                ORDER BY mrd.ID_Detalle ASC
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            
            # Convertir valores numéricos en detalles
            for detalle in detalles:
                detalle['Cantidad'] = float(detalle['Cantidad'] or 0)
                detalle['Precio_Unitario'] = float(detalle['Precio_Unitario'] or 0)
                detalle['Subtotal'] = float(detalle['Subtotal'] or 0)
            
            print(f"Detalles encontrados: {len(detalles)}")
            
            # Obtener información del cliente
            cliente_info = None
            if movimiento.get('ID_Cliente') and movimiento['ID_Cliente']:
                cursor.execute("""
                    SELECT ID_Cliente, Nombre, RUC_CEDULA as RUC, Direccion, Telefono
                    FROM clientes WHERE ID_Cliente = %s
                """, (movimiento['ID_Cliente'],))
                cliente_info = cursor.fetchone()
            
            # Obtener información de la asignación
            asignacion_info = None
            if movimiento.get('ID_Asignacion'):
                cursor.execute("""
                    SELECT av.ID_Asignacion, av.Fecha_Asignacion, av.Fecha_Finalizacion,
                           av.Estado as Estado_Asignacion, r.Nombre_Ruta, u.NombreUsuario as Vendedor_Nombre
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE av.ID_Asignacion = %s
                """, (movimiento['ID_Asignacion'],))
                asignacion_info = cursor.fetchone()
            
            return render_template('vendedor/inventario/detalle_movimiento.html',
                                 movimiento=movimiento,
                                 detalles=detalles,
                                 cliente_info=cliente_info,
                                 asignacion_info=asignacion_info,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error en vendedor_movimiento_detalle: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar detalle del movimiento: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_movimientos_historial'))


@vendedor_bp.route('/vendedor/movimientos/carga-directa-proveedor', methods=['GET', 'POST'])
@vendedor_required
def vendedor_carga_directa_proveedor():
    from datetime import datetime, timedelta
    import os
    from werkzeug.utils import secure_filename
    import traceback
    
    id_empresa = session.get('id_empresa', 1)
    id_usuario = current_user.id

    # Constantes
    ID_TIPO_COMPRA = 1
    ID_TIPO_TRASLADO = 6
    ID_TIPO_ENTRADA_CARGA = 15
    ID_BODEGA_CENTRAL = 1
    ID_TIPO_CUENTA_COMPRA = 1

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            costos_unitarios = request.form.getlist('costo_unitario[]')
            factura_proveedor = request.form.get('factura_proveedor', '').strip()
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            tipo_destino = request.form.get('tipo_destino')
            observacion = request.form.get('observacion', '')
            
            # Validaciones básicas
            if not factura_proveedor:
                flash('El número de factura del proveedor es obligatorio', 'error')
                return redirect(url_for('vendedor.vendedor_carga_directa_proveedor'))
            
            if not id_proveedor:
                flash('Debe seleccionar un proveedor', 'error')
                return redirect(url_for('vendedor.vendedor_carga_directa_proveedor'))
            
            if not tipo_destino or tipo_destino not in ['RUTA', 'BODEGA']:
                flash('Debe seleccionar el tipo de carga (Ruta o Local/Bodega)', 'error')
                return redirect(url_for('vendedor.vendedor_carga_directa_proveedor'))
            
            # Validar asignación para RUTA
            id_asignacion = None
            if tipo_destino == 'RUTA':
                with get_db_cursor(True) as cursor:
                    cursor.execute("""
                        SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta
                        FROM asignacion_vendedores av
                        LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                        WHERE av.ID_Usuario = %s
                        AND av.Estado = 'Activa'
                        ORDER BY av.Fecha_Asignacion DESC
                        LIMIT 1
                    """, (id_usuario,))
                    
                    asignacion = cursor.fetchone()
                    if not asignacion:
                        flash('No tienes una asignación activa para hoy. No puedes cargar mercancía a tu ruta.', 'error')
                        return redirect(url_for('vendedor.vendedor_inventario'))
                    id_asignacion = asignacion['ID_Asignacion']
            
            # Procesar productos primero (validaciones y cálculos)
            with get_db_cursor(True) as cursor:
                # Verificar factura duplicada
                cursor.execute("""
                    SELECT COUNT(*) as total 
                    FROM movimientos_inventario 
                    WHERE N_Factura_Externa = %s AND ID_Proveedor = %s AND Estado != 'Anulada'
                """, (factura_proveedor, id_proveedor))
                
                if cursor.fetchone()['total'] > 0:
                    flash(f'La factura {factura_proveedor} ya fue registrada anteriormente', 'error')
                    return redirect(url_for('vendedor.vendedor_carga_directa_proveedor'))
                
                # Preparar productos
                productos_procesar = []
                total_cantidad = 0
                total_items = 0
                total_costo_compra = 0
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        costo = float(costos_unitarios[i]) if i < len(costos_unitarios) and costos_unitarios[i] else 0
                        
                        cantidad = abs(cantidad)
                        costo = abs(costo)
                        
                        cursor.execute("""
                            SELECT ID_Producto, IFNULL(Precio_Ruta, 0) as Precio_Ruta, Descripcion 
                            FROM productos 
                            WHERE ID_Producto = %s AND Estado = 'activo'
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            flash(f'Producto ID {id_producto} no existe o está inactivo', 'error')
                            return redirect(url_for('vendedor.vendedor_carga_directa_proveedor'))
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'costo': costo,
                            'precio_ruta': float(producto_info['Precio_Ruta']),
                            'descripcion': producto_info['Descripcion']
                        })
                        total_cantidad += cantidad
                        total_items += 1
                        total_costo_compra += cantidad * costo
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_carga_directa_proveedor'))
            
            # ============================================
            # PASO 1: REGISTRAR COMPRA Y ACTUALIZAR INVENTARIO
            # ============================================
            id_movimiento_entrada = None
            with get_db_cursor(commit=True) as cursor:
                try:
                    estado_movimiento = 'Activa'
                    
                    # Insertar compra
                    cursor.execute("""
                        INSERT INTO movimientos_inventario 
                        (ID_TipoMovimiento, N_Factura_Externa, Fecha, ID_Proveedor, 
                         Tipo_Compra, Observacion, ID_Empresa, ID_Bodega, 
                         ID_Usuario_Creacion, Estado)
                        VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, %s, %s, %s)
                    """, (ID_TIPO_COMPRA, factura_proveedor, id_proveedor, tipo_compra,
                          f'CARGA DIRECTA - Tipo: {tipo_destino} - {observacion}'[:500],
                          id_empresa, ID_BODEGA_CENTRAL, id_usuario, estado_movimiento))
                    
                    id_movimiento_entrada = cursor.lastrowid
                    
                    # Detalle de compra
                    for prod in productos_procesar:
                        subtotal = prod['cantidad'] * prod['costo']
                        cursor.execute("""
                            INSERT INTO detalle_movimientos_inventario
                            (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, Subtotal, ID_Usuario_Creacion)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (id_movimiento_entrada, prod['id_producto'], prod['cantidad'], 
                              prod['costo'], subtotal, id_usuario))
                    
                    # ACTUALIZAR INVENTARIO DE BODEGA (SUMA)
                    for prod in productos_procesar:
                        cursor.execute("""
                            INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
                        """, (ID_BODEGA_CENTRAL, prod['id_producto'], prod['cantidad']))
                    
                    # Cuenta por pagar si es crédito
                    if tipo_compra == 'CREDITO':
                        cursor.execute("""
                            INSERT INTO cuentas_por_pagar 
                            (ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, 
                             Observacion, Fecha_Vencimiento, Tipo_Movimiento, 
                             Monto_Movimiento, ID_Empresa, Saldo_Pendiente, 
                             ID_Usuario_Creacion, Estado)
                            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente')
                        """, (
                            id_movimiento_entrada,
                            id_proveedor,
                            factura_proveedor,
                            f'Compra a crédito - Tipo: {tipo_destino} - Factura: {factura_proveedor}'[:500],
                            None,
                            ID_TIPO_CUENTA_COMPRA,
                            total_costo_compra,
                            id_empresa,
                            total_costo_compra,
                            id_usuario
                        ))
                        
                        cursor.execute("""
                            UPDATE proveedores 
                            SET Saldo_Pendiente = COALESCE(Saldo_Pendiente, 0) + %s
                            WHERE ID_Proveedor = %s
                        """, (total_costo_compra, id_proveedor))
                    
                    # Guardar foto de factura
                    if 'foto_factura' in request.files:
                        foto = request.files['foto_factura']
                        if foto and foto.filename != '':
                            upload_folder = os.path.join('static', 'uploads', 'facturas')
                            os.makedirs(upload_folder, exist_ok=True)
                            
                            extension = foto.filename.rsplit('.', 1)[1].lower() if '.' in foto.filename else 'jpg'
                            nombre_archivo = f"factura_{id_movimiento_entrada}_{factura_proveedor}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
                            nombre_archivo = secure_filename(nombre_archivo)
                            
                            ruta_completa = os.path.join(upload_folder, nombre_archivo)
                            foto.save(ruta_completa)
                            
                            ruta_factura = f'uploads/facturas/{nombre_archivo}'
                            
                            cursor.execute("""
                                UPDATE movimientos_inventario 
                                SET Observacion = CONCAT(Observacion, ' | Factura: ', %s)
                                WHERE ID_Movimiento = %s
                            """, (ruta_factura, id_movimiento_entrada))
                    
                    # Si es BODEGA, crear carga pendiente y terminar
                    if tipo_destino == 'BODEGA':
                        cursor.execute("""
                            INSERT INTO cargas_pendientes_recepcion
                            (ID_Movimiento, ID_Proveedor, Num_Factura, Fecha_Carga, 
                             ID_Usuario_Carga, Estado, Observaciones)
                            VALUES (%s, %s, %s, CURDATE(), %s, 'PENDIENTE', %s)
                        """, (id_movimiento_entrada, id_proveedor, factura_proveedor, 
                              id_usuario, f'Carga pendiente de recepción en bodega - {observacion}'[:500]))
                        
                        id_carga_pendiente = cursor.lastrowid
                        
                        for prod in productos_procesar:
                            cursor.execute("""
                                INSERT INTO cargas_pendientes_detalle
                                (ID_Carga, ID_Producto, Cantidad_Cargada, Costo_Unitario)
                                VALUES (%s, %s, %s, %s)
                            """, (id_carga_pendiente, prod['id_producto'], prod['cantidad'], prod['costo']))
                        
                        flash(f'✅ CARGA A BODEGA registrada. Pendiente de recepción por el encargado de bodega. Factura: {factura_proveedor}', 'success')
                        return redirect(url_for('vendedor.vendedor_inventario'))
                    
                except Exception as e:
                    print(f"❌ Error en compra: {str(e)}")
                    traceback.print_exc()
                    raise e
            
            # ============================================
            # PASO 2: PROCESAR TRASLADO A RUTA
            # ============================================
            if tipo_destino == 'RUTA':
                with get_db_cursor(commit=True) as cursor:
                    try:
                        # VERIFICAR STOCK DISPONIBLE (DESPUÉS DE LA COMPRA)
                        for prod in productos_procesar:
                            cursor.execute("""
                                SELECT Existencias FROM inventario_bodega 
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (ID_BODEGA_CENTRAL, prod['id_producto']))
                            existencias = cursor.fetchone()
                            
                            stock_actual = existencias['Existencias'] if existencias else 0
                            
                            if not existencias or existencias['Existencias'] < prod['cantidad']:
                                flash(f'⚠️ STOCK INSUFICIENTE en bodega para trasladar {prod["descripcion"]}. Disponible: {stock_actual}, Requerido: {prod["cantidad"]}', 'error')
                                return redirect(url_for('vendedor.vendedor_inventario'))
                        
                        # REGISTRAR TRASLADO (SALIDA DE BODEGA)
                        cursor.execute("""
                            INSERT INTO movimientos_inventario 
                            (ID_TipoMovimiento, Fecha, Observacion, ID_Empresa, ID_Bodega, 
                             ID_Bodega_Destino, ID_Pedido_Origen, ID_Usuario_Creacion, Estado)
                            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            ID_TIPO_TRASLADO,
                            f'TRASLADO A RUTA - Asignacion: {id_asignacion} - Factura: {factura_proveedor}'[:500],
                            id_empresa,
                            ID_BODEGA_CENTRAL,
                            None,
                            None,
                            id_usuario,
                            'Activa'
                        ))
                        
                        id_movimiento_salida = cursor.lastrowid
                        
                        # DETALLE DEL TRASLADO
                        for prod in productos_procesar:
                            subtotal_salida = prod['cantidad'] * prod['costo']
                            cursor.execute("""
                                INSERT INTO detalle_movimientos_inventario
                                (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, Subtotal, ID_Usuario_Creacion)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (id_movimiento_salida, prod['id_producto'], prod['cantidad'], 
                                  prod['costo'], subtotal_salida, id_usuario))
                        
                        # RESTAR DE BODEGA
                        for prod in productos_procesar:
                            cursor.execute("""
                                UPDATE inventario_bodega 
                                SET Existencias = Existencias - %s
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (prod['cantidad'], ID_BODEGA_CENTRAL, prod['id_producto']))
                            
                            # Verificar que no quede negativo
                            cursor.execute("""
                                SELECT Existencias FROM inventario_bodega 
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (ID_BODEGA_CENTRAL, prod['id_producto']))
                            existencias_final = cursor.fetchone()
                            
                            if existencias_final['Existencias'] < 0:
                                flash(f'ERROR CRÍTICO: Stock negativo en bodega para producto {prod["descripcion"]}', 'error')
                                return redirect(url_for('vendedor.vendedor_inventario'))
                        
                        # REGISTRAR ENTRADA A RUTA
                        total_subtotal_venta = sum(p['cantidad'] * p['precio_ruta'] for p in productos_procesar)
                        
                        cursor.execute("""
                            INSERT INTO movimientos_ruta_cabecera 
                            (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                             Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                             ID_Empresa, Estado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (id_asignacion, ID_TIPO_ENTRADA_CARGA, id_usuario, factura_proveedor,
                              total_cantidad, total_items, total_subtotal_venta, id_empresa, 'ACTIVO'))
                        
                        id_movimiento_ruta = cursor.lastrowid
                        
                        # DETALLE DE RUTA
                        for prod in productos_procesar:
                            subtotal = prod['cantidad'] * prod['precio_ruta']
                            cursor.execute("""
                                INSERT INTO movimientos_ruta_detalle
                                (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, 
                                 Subtotal, ID_Movimiento_Origen)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (id_movimiento_ruta, prod['id_producto'], prod['cantidad'],
                                  prod['precio_ruta'], subtotal, id_movimiento_salida))
                        
                        # ACTUALIZAR INVENTARIO DE RUTA
                        for prod in productos_procesar:
                            cursor.execute("""
                                INSERT INTO inventario_ruta (ID_Asignacion, ID_Producto, Cantidad)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE Cantidad = Cantidad + VALUES(Cantidad)
                            """, (id_asignacion, prod['id_producto'], prod['cantidad']))
                            
                            # VERIFICAR INVENTARIO DE RUTA
                            cursor.execute("""
                                SELECT Cantidad FROM inventario_ruta 
                                WHERE ID_Asignacion = %s AND ID_Producto = %s
                            """, (id_asignacion, prod['id_producto']))
                            ruta_inventario = cursor.fetchone()
                            
                            if ruta_inventario['Cantidad'] < 0:
                                flash(f'ERROR: Inventario de ruta negativo para producto {prod["descripcion"]}', 'error')
                                return redirect(url_for('vendedor.vendedor_inventario'))
                        
                        flash(f'✅ CARGA A RUTA registrada exitosamente. Stock disponible en tu ruta para venta inmediata. Factura: {factura_proveedor}', 'success')
                        return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento_ruta))
                        
                    except Exception as e:
                        print(f"❌ Error en traslado: {str(e)}")
                        traceback.print_exc()
                        # La compra YA está registrada, solo notificar
                        flash(f'⚠️ COMPRA REGISTRADA (ID: {id_movimiento_entrada}) pero el TRASLADO falló: {str(e)}. La compra queda registrada en bodega central.', 'warning')
                        return redirect(url_for('vendedor.vendedor_inventario'))
                    
        except Exception as e:
            print(f"Error en carga directa: {str(e)}")
            traceback.print_exc()
            flash(f'Error al procesar la carga directa: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # MÉTODO GET
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Proveedor, Nombre 
                FROM proveedores 
                WHERE Estado = 'ACTIVO' AND ID_Empresa = %s 
                ORDER BY Nombre
            """, (id_empresa,))
            proveedores = cursor.fetchall()
            
            cursor.execute("""
                SELECT 
                    p.ID_Producto as id,
                    p.COD_Producto as codigo,
                    p.Descripcion as nombre,
                    IFNULL(p.Precio_Ruta, 0) as precio_ruta,
                    IFNULL(um.Abreviatura, 'PZA') as unidad
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE p.Estado = 'activo' AND p.ID_Empresa = %s
                ORDER BY p.Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            """, (current_user.id,))
            tiene_asignacion = cursor.fetchone()['total'] > 0
            
            return render_template('vendedor/inventario/carga_directa_proveedor.html',
                                 proveedores=proveedores,
                                 productos=productos,
                                 tiene_asignacion=tiene_asignacion,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error en GET carga directa: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar el formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))


