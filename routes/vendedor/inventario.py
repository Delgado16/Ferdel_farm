# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import convertir_hora_db, procesar_asignacion, procesar_lista_asignaciones

@vendedor_bp.route('/vendedor/inventario')
@vendedor_required
def vendedor_inventario():
    """
    Muestra el inventario actual del vendedor basado en su asignación activa de hoy
    """
    try:
        with get_db_cursor(True) as cursor:
            # ============================================
            # 1. OBTENER ASIGNACIÓN ACTIVA DEL VENDEDOR HOY
            # ============================================
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    av.ID_Ruta,
                    r.Nombre_Ruta,
                    av.Fecha_Asignacion,
                    av.Hora_Inicio,
                    av.Hora_Fin,
                    v.Marca as Vehiculo,
                    v.Placa
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return render_template('vendedor/inventario/inventario.html', 
                                     asignacion=None,
                                     inventario=[],
                                     totales={})
            
            # ============================================
            # 2. OBTENER INVENTARIO DEL VENDEDOR
            # ============================================
            cursor.execute("""
                SELECT 
                    ir.ID_Inventario_Ruta,
                    ir.ID_Producto,
                    ir.Cantidad,
                    ir.Fecha_Actualizacion,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    p.Precio_Ruta as Precio_Venta,
                    p.Stock_Minimo,
                    um.Descripcion as Unidad,
                    um.Abreviatura as Unidad_Abrev,
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
            
            # ============================================
            # 3. CALCULAR TOTALES
            # ============================================
            total_productos = len(inventario)
            total_unidades = sum(float(item['Cantidad']) for item in inventario)
            total_valor = sum(float(item['Cantidad']) * float(item['Precio_Venta']) for item in inventario)
            
            # Productos con stock bajo (menor al mínimo)
            stock_bajo = []
            for item in inventario:
                if float(item['Cantidad']) <= float(item['Stock_Minimo'] or 0):
                    stock_bajo.append(item)
            
            # ============================================
            # 4. OBTENER VENTAS DEL DÍA USANDO movimientos_ruta_cabecera (CORREGIDO)
            # ============================================
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(Total_Subtotal), 0) as total_vendido,
                    COALESCE(SUM(Total_Items), 0) as total_items,
                    COALESCE(SUM(Total_Productos), 0) as total_productos_vendidos
                FROM movimientos_ruta_cabecera
                WHERE ID_Asignacion = %s
                AND ID_TipoMovimiento = 3  -- Tipo Venta
                AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            ventas_hoy = cursor.fetchone()
            
            totales = {
                'total_productos': total_productos,
                'total_unidades': total_unidades,
                'total_valor': total_valor,
                'stock_bajo': len(stock_bajo),
                'ventas_hoy': ventas_hoy['total_ventas'] if ventas_hoy else 0,
                'vendido_hoy': float(ventas_hoy['total_vendido']) if ventas_hoy else 0,
                'items_vendidos': int(ventas_hoy['total_items']) if ventas_hoy else 0,
                'productos_vendidos': int(ventas_hoy['total_productos_vendidos']) if ventas_hoy else 0
            }
            
            return render_template('vendedor/inventario/inventario.html',
                                 asignacion=asignacion,
                                 inventario=inventario,
                                 stock_bajo=stock_bajo,
                                 totales=totales,
                                 now=datetime.now())
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar inventario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))


@vendedor_bp.route('/api/vendedor/inventario')
@login_required
def api_vendedor_inventario():
    """
    API para consultar inventario del vendedor (formato JSON)
    Utiliza current_user.id para identificar al vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener asignación activa del usuario actual
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s
                AND Estado = 'Activa'
                ORDER BY Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({
                    'success': False,
                    'message': 'No tienes asignación activa hoy',
                    'data': []
                })
            
            # Obtener inventario
            cursor.execute("""
                SELECT 
                    ir.ID_Producto,
                    ir.Cantidad,
                    p.Descripcion as producto,
                    p.COD_Producto as codigo,
                    p.Precio_Ruta as precio,
                    um.Abreviatura as unidad
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': inventario
            })
            
    except Exception as e:
        print(f"Error en API inventario: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'data': []
        }), 500


@vendedor_bp.route('/vendedor/producto/<int:id_producto>')
@login_required
def vendedor_producto_detalle(id_producto):
    """
    Muestra el detalle de un producto específico en el inventario del vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener asignación activa del usuario actual
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s
                AND Estado = 'Activa'
                ORDER BY Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener detalle del producto
            cursor.execute("""
                SELECT 
                    ir.ID_Inventario_Ruta,
                    ir.ID_Producto,
                    ir.Cantidad as Stock_Actual,
                    ir.Fecha_Actualizacion,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    p.Precio_Ruta as Precio_Venta,
                    p.Stock_Minimo,
                    um.Descripcion as Unidad,
                    um.Abreviatura as Unidad_Abrev,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.ID_Producto = %s
                LIMIT 1
            """, (asignacion['ID_Asignacion'], id_producto))
            
            producto = cursor.fetchone()
            
            if not producto:
                flash('Producto no encontrado en tu inventario', 'error')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener historial de movimientos de este producto (CORREGIDO)
            cursor.execute("""
                SELECT 
                    mrc.ID_Movimiento,
                    mrc.Fecha_Movimiento,
                    mrc.Documento_Numero,
                    mrc.Total_Subtotal,
                    mrd.Cantidad,
                    mrd.Precio_Unitario,
                    mrd.Subtotal,
                    cm.Descripcion as Tipo_Movimiento
                FROM movimientos_ruta_detalle mrd
                INNER JOIN movimientos_ruta_cabecera mrc ON mrd.ID_Movimiento = mrc.ID_Movimiento
                INNER JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mrc.ID_Asignacion = %s
                AND mrd.ID_Producto = %s
                ORDER BY mrc.Fecha_Movimiento DESC
                LIMIT 20
            """, (asignacion['ID_Asignacion'], id_producto))
            
            historial = cursor.fetchall()
            
            return render_template('vendedor/inventario/producto_detalle.html',
                                 producto=producto,
                                 historial=historial,
                                 now=datetime.now(),
                                 current_user=current_user)
            
    except Exception as e:
        print(f"Error en vendedor_producto_detalle: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))


@vendedor_bp.route('/vendedor/refrescar-inventario', methods=['POST'])
@login_required
def vendedor_refrescar_inventario():
    """
    Refresca el inventario del vendedor (útil después de una venta)
    Utiliza current_user.id para identificar al vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener asignación activa del usuario actual
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s
                AND Estado = 'Activa'
                ORDER BY Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({
                    'success': False,
                    'message': 'No tienes asignación activa hoy'
                })
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_productos,
                    COALESCE(SUM(Cantidad), 0) as total_unidades,
                    COALESCE(SUM(Cantidad * p.Precio_Ruta), 0) as total_valor
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                WHERE ir.ID_Asignacion = %s
            """, (asignacion['ID_Asignacion'],))
            
            totales = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'data': {
                    'total_productos': int(totales['total_productos']),
                    'total_unidades': float(totales['total_unidades']),
                    'total_valor': float(totales['total_valor'])
                }
            })
            
    except Exception as e:
        print(f"Error en refrescar inventario: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@vendedor_bp.route('/api/vendedor/sincronizar_inventario', methods=['GET'])
@vendedor_required
def api_sincronizar_inventario():
    """Sincronizar inventario de la ruta (solo cambios recientes)"""
    try:
        id_vendedor = int(current_user.id)
        ultima_sincronizacion = request.args.get('ultima_sincronizacion')
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta, ID_Empresa
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
            
            # Construir consulta según si hay última sincronización
            if ultima_sincronizacion:
                # Solo productos con cambios desde la última sincronización
                cursor.execute("""
                    SELECT ir.ID_Producto, p.COD_Producto, p.Descripcion as Nombre,
                           p.Precio_Ruta, ir.Cantidad as Stock_Disponible,
                           um.Descripcion as Unidad_Medida, um.Abreviatura,
                           p.ID_Categoria, c.Descripcion as Categoria,
                           p.Estado as Producto_Estado,
                           ir.Fecha_Actualizacion
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE ir.ID_Asignacion = %s 
                      AND ir.Fecha_Actualizacion > %s
                    ORDER BY p.Descripcion
                """, (asignacion['ID_Asignacion'], ultima_sincronizacion))
            else:
                # Primera sincronización: todos los productos
                cursor.execute("""
                    SELECT ir.ID_Producto, p.COD_Producto, p.Descripcion as Nombre,
                           p.Precio_Ruta, ir.Cantidad as Stock_Disponible,
                           um.Descripcion as Unidad_Medida, um.Abreviatura,
                           p.ID_Categoria, c.Descripcion as Categoria,
                           p.Estado as Producto_Estado,
                           ir.Fecha_Actualizacion
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE ir.ID_Asignacion = %s 
                      AND p.Estado = 'activo'
                    ORDER BY p.Descripcion
                """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            # Obtener la fecha de la última modificación para próxima sincronización
            cursor.execute("""
                SELECT MAX(Fecha_Actualizacion) as ultima_modificacion
                FROM inventario_ruta
                WHERE ID_Asignacion = %s
            """, (asignacion['ID_Asignacion'],))
            
            ultima_modificacion = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'inventario': inventario,
                'ultima_modificacion': ultima_modificacion['ultima_modificacion'] if ultima_modificacion else None,
                'asignacion_id': asignacion['ID_Asignacion'],
                'ruta_id': asignacion['ID_Ruta']
            })
            
    except Exception as e:
        print(f"Error en api_sincronizar_inventario: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


