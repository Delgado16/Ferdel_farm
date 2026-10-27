from datetime import datetime
import traceback

from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator
from .utils import (
    safe_float,
    safe_int,
    obtener_catalogos_productos_admin,
    formatear_producto_para_listado
)

@admin_bp.route('/admin/bodega/productos', methods=['GET'])
@admin_required
@bitacora_decorator("PRODUCTOS")
def admin_productos():
    try:
        # Obtener parámetros de filtro
        categoria_filtro = request.args.get('categoria', 'todos')
        bodega_filtro = request.args.get('bodega', 'todas')
        stock_filtro = request.args.get('stock', 'todos')
        empresa_filtro = request.args.get('empresa', 'todas')
        estado_filtro = request.args.get('estado', 'activo')
        search_term = request.args.get('search', '')
        
        with get_db_cursor() as cursor:
            # Consulta optimizada
            query = """
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    COALESCE(um.Abreviatura, 'Und') as Unidad,
                    COALESCE(SUM(ib.Existencias), 0) as Stock,
                    (SELECT GROUP_CONCAT(CONCAT(b.Nombre, ': ', CAST(COALESCE(ib2.Existencias, 0) AS UNSIGNED)) SEPARATOR ' | ')
                     FROM inventario_bodega ib2
                     INNER JOIN bodegas b ON ib2.ID_Bodega = b.ID_Bodega
                     WHERE ib2.ID_Producto = p.ID_Producto AND ib2.Existencias > 0) as Desglose_Bodegas,
                    p.Estado,
                    COALESCE(cp.Descripcion, 'Sin categoría') as Categoria,
                    COALESCE(p.Precio_Mercado, 0) as Precio_Mercado,
                    COALESCE(p.Precio_Mayorista, 0) as Precio_Mayorista,
                    COALESCE(p.Precio_Ruta, 0) as Precio_Ruta,
                    COALESCE(e.Nombre_Empresa, 'Sin empresa') as Empresa,
                    COALESCE(p.Stock_Minimo, 5) as Stock_Minimo,
                    p.Unidad_Medida
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE 1=1
            """
            
            params = []
            
            # Filtro de Estado
            if estado_filtro != 'todos':
                query += " AND p.Estado = %s"
                params.append(estado_filtro)
            
            # Filtros
            if categoria_filtro != 'todos':
                query += " AND p.ID_Categoria = %s"
                params.append(categoria_filtro)
            
            if empresa_filtro != 'todas':
                query += " AND p.ID_Empresa = %s"
                params.append(empresa_filtro)
            
            if bodega_filtro != 'todas':
                query += " AND EXISTS (SELECT 1 FROM inventario_bodega ib2 WHERE ib2.ID_Producto = p.ID_Producto AND ib2.ID_Bodega = %s)"
                params.append(bodega_filtro)
            
            if search_term:
                query += " AND (p.COD_Producto LIKE %s OR p.Descripcion LIKE %s)"
                params.append(f'%{search_term}%')
                params.append(f'%{search_term}%')
            
            query += """
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, um.Abreviatura, 
                         p.Estado, cp.Descripcion, p.Precio_Mercado, p.Precio_Mayorista, 
                         p.Precio_Ruta, e.Nombre_Empresa, p.Stock_Minimo, p.Unidad_Medida
                ORDER BY p.ID_Producto DESC
            """
            
            cursor.execute(query, params)
            productos = cursor.fetchall()
            
            # Formatear productos y aplicar filtro de stock
            productos_list = []
            for p in productos:
                prod_dict = formatear_producto_para_listado(p)
                stock_actual = prod_dict['stock']
                stock_min = prod_dict['stock_minimo']
                
                if stock_filtro == 'critico' and not (0 < stock_actual <= stock_min):
                    continue
                elif stock_filtro == 'bajo' and not (stock_min < stock_actual <= stock_min * 2):
                    continue
                elif stock_filtro == 'normal' and not (stock_actual > stock_min * 2):
                    continue
                elif stock_filtro == 'sin_stock' and stock_actual != 0:
                    continue
                
                productos_list.append(prod_dict)
            
            # Catálogos para filtros
            catalogos = obtener_catalogos_productos_admin(cursor)
            
            # Contadores globales de estado
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN LOWER(Estado) = 'activo' THEN 1 ELSE 0 END), 0) as total_activos,
                    COALESCE(SUM(CASE WHEN LOWER(Estado) = 'inactivo' THEN 1 ELSE 0 END), 0) as total_inactivos
                FROM productos
            """)
            conteo_estados = cursor.fetchone() or {}
            total_activos = conteo_estados.get('total_activos') or 0
            total_inactivos = conteo_estados.get('total_inactivos') or 0

            # Estadísticas
            stats = {
                'total': len(productos_list),
                'critico': sum(1 for p in productos_list if 0 < p['stock'] <= p['stock_minimo']),
                'sin_stock': sum(1 for p in productos_list if p['stock'] == 0),
                'total_stock': sum(p['stock'] for p in productos_list),
                'total_activos': int(total_activos),
                'total_inactivos': int(total_inactivos)
            }
            
            return render_template('admin/bodega/producto/productos.html', 
                                 productos=productos_list,
                                 stats=stats,
                                 categorias=catalogos['categorias'],
                                 categoria_seleccionada=categoria_filtro,
                                 bodegas=catalogos['bodegas'],
                                 bodega_seleccionada=bodega_filtro,
                                 stock_seleccionado=stock_filtro,
                                 empresas=catalogos['empresas'],
                                 empresa_seleccionada=empresa_filtro,
                                 estado_seleccionado=estado_filtro,
                                 unidades=catalogos['unidades'],
                                 search_term=search_term)
                                 
    except Exception as e:
        import traceback
        print(f"Error: {traceback.format_exc()}")
        flash(f'Error al cargar productos: {str(e)}', 'error')
        return render_template('admin/bodega/producto/productos.html',
                                productos=[], 
                                stats={'total': 0, 'critico': 0, 'sin_stock': 0, 'total_stock': 0, 'total_activos': 0, 'total_inactivos': 0},
                                categorias=[], 
                                categoria_seleccionada='todos',
                                bodega_seleccionada='todas',
                                bodegas=[],
                                stock_seleccionado='todos',
                                empresas=[],
                                empresa_seleccionada='todas',
                                estado_seleccionado='activo',
                                unidades=[],
                                search_term='')

@admin_bp.route('/admin/bodega/productos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PRODUCTO")
def admin_crear_producto():
    try:
        cod_producto = request.form.get('COD_Producto', '').strip()
        descripcion = request.form.get('Descripcion', '').strip()
        id_unidad_medida = safe_int(request.form.get('Unidad_Medida'))
        id_categoria = safe_int(request.form.get('ID_Categoria'))
        id_bodega = safe_int(request.form.get('ID_Bodega'))
        id_empresa = safe_int(request.form.get('ID_Empresa', 1), 1)
        estado = request.form.get('Estado', 'activo')
        usuario_creador = current_user.id if (current_user and current_user.is_authenticated) else session.get('id_usuario', 1)

        if not all([descripcion, id_unidad_medida, id_categoria, id_bodega]):
            flash('Descripción, unidad de medida, categoría y bodega inicial son obligatorios', 'error')
            return redirect(url_for('admin.admin_productos'))

        raw_cantidad = safe_float(request.form.get('Cantidad_Inicial'), 0.0)
        if id_unidad_medida == 1 and raw_cantidad % 1 != 0:
            cajillas = int(raw_cantidad)
            unidades = int(round((raw_cantidad - cajillas) * 100))
            cantidad_inicial = cajillas + (unidades / 30.0)
        else:
            cantidad_inicial = raw_cantidad

        precio_mercado = safe_float(request.form.get('Precio_Mercado'), 0.0)
        precio_mayorista = safe_float(request.form.get('Precio_Mayorista'), 0.0)
        precio_ruta = safe_float(request.form.get('Precio_Ruta'), 0.0)
        stock_minimo = safe_float(request.form.get('Stock_Minimo'), 5.0)

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT ID_Bodega, ID_Empresa FROM bodegas WHERE ID_Bodega = %s AND Estado = 'activa'", (id_bodega,))
            bodega_data = cursor.fetchone()
            if not bodega_data:
                flash('La bodega seleccionada no es válida', 'error')
                return redirect(url_for('admin.admin_productos'))

            if bodega_data['ID_Empresa'] != id_empresa:
                flash('La bodega seleccionada no pertenece a la empresa del producto', 'error')
                return redirect(url_for('admin.admin_productos'))

            if cod_producto:
                cursor.execute("SELECT ID_Producto FROM productos WHERE COD_Producto = %s", (cod_producto,))
                if cursor.fetchone():
                    flash('El código de producto ya existe', 'error')
                    return redirect(url_for('admin.admin_productos'))
            else:
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(COD_Producto AS UNSIGNED)), 0) + 1 as max_cod 
                    FROM productos WHERE COD_Producto REGEXP '^[0-9]+$'
                """)
                cod_producto = str((cursor.fetchone() or {}).get('max_cod') or 1)

            cursor.execute("""
                INSERT INTO productos (
                    COD_Producto, Descripcion, Unidad_Medida, Estado,
                    ID_Categoria, Precio_Mercado, Precio_Mayorista, Precio_Ruta, 
                    ID_Empresa, Usuario_Creador, Stock_Minimo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (cod_producto, descripcion, id_unidad_medida, estado,
                  id_categoria, precio_mercado, precio_mayorista, precio_ruta, 
                  id_empresa, usuario_creador, stock_minimo))

            producto_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            """, (id_bodega, producto_id, cantidad_inicial))

        flash(f'Producto "{descripcion}" creado exitosamente con {cantidad_inicial} unidades en la bodega seleccionada', 'success')
    except Exception as e:
        flash(f'Error al crear producto: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_productos'))

@admin_bp.route('/admin/bodegas/por-empresa/<int:id_empresa>')
@admin_required
def obtener_bodegas_por_empresa(id_empresa):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 'activa'
                ORDER BY Nombre
            """, (id_empresa,))
            bodegas = cursor.fetchall()
        
        return jsonify({
            'bodegas': bodegas
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/bodega/productos/editar/<int:id_producto>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_PRODUCTO")
def admin_editar_producto(id_producto):
    try:
        if request.method == 'POST':
            cod_producto = request.form.get('COD_Producto', '').strip()
            descripcion = request.form.get('Descripcion', '').strip()
            unidad_medida = safe_int(request.form.get('Unidad_Medida'))
            id_categoria = safe_int(request.form.get('ID_Categoria'))
            id_empresa = safe_int(request.form.get('ID_Empresa'))
            estado = 'activo' if request.form.get('Estado') == 'activo' else 'inactivo'

            if not all([descripcion, unidad_medida, id_categoria, id_empresa]):
                flash('Descripción, unidad, categoría y empresa son obligatorios', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            precio_mercado = safe_float(request.form.get('Precio_Mercado'), 0.0)
            precio_mayorista = safe_float(request.form.get('Precio_Mayorista'), 0.0)
            precio_ruta = safe_float(request.form.get('Precio_Ruta'), 0.0)
            stock_minimo = safe_float(request.form.get('Stock_Minimo'), 5.0)

            if precio_mercado < 0 or precio_mayorista < 0 or precio_ruta < 0 or stock_minimo < 0:
                flash('Los precios y el stock mínimo no pueden ser negativos', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            with get_db_cursor(commit=True) as cursor:
                if cod_producto:
                    cursor.execute("SELECT ID_Producto FROM productos WHERE COD_Producto = %s AND ID_Producto != %s", (cod_producto, id_producto))
                    if cursor.fetchone():
                        flash('El código de producto ya existe en otro producto', 'error')
                        return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                cursor.execute("""
                    UPDATE productos SET
                        COD_Producto = %s, Descripcion = %s, Unidad_Medida = %s,
                        ID_Categoria = %s, Precio_Mercado = %s, Precio_Mayorista = %s,
                        Precio_Ruta = %s, ID_Empresa = %s, Stock_Minimo = %s, Estado = %s
                    WHERE ID_Producto = %s
                """, (cod_producto or None, descripcion, unidad_medida, id_categoria,
                      precio_mercado, precio_mayorista, precio_ruta, id_empresa,
                      stock_minimo, estado, id_producto))

            flash('Producto actualizado exitosamente', 'success')
            return redirect(url_for('admin.admin_productos'))

        else:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, p.COD_Producto, p.Descripcion, p.Unidad_Medida,
                        um.Descripcion as Nombre_Unidad, um.Abreviatura, p.Estado, p.ID_Categoria,
                        cp.Descripcion as Nombre_Categoria, p.Precio_Mercado, p.Precio_Mayorista,
                        p.Precio_Ruta, p.ID_Empresa, e.Nombre_Empresa, p.Fecha_Creacion,
                        p.Usuario_Creador, u.NombreUsuario as Usuario_Creador_Nombre, p.Stock_Minimo,
                        COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales
                    FROM productos p
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                    LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                    LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                    WHERE p.ID_Producto = %s
                    GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, p.Unidad_Medida,
                             um.Descripcion, um.Abreviatura, p.Estado, p.ID_Categoria,
                             cp.Descripcion, p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,
                             p.ID_Empresa, e.Nombre_Empresa, p.Fecha_Creacion, p.Usuario_Creador, 
                             u.NombreUsuario, p.Stock_Minimo
                """, (id_producto,))
                producto = cursor.fetchone()
                
                if not producto:
                    flash('Producto no encontrado', 'error')
                    return redirect(url_for('admin.admin_productos'))

                catalogos = obtener_catalogos_productos_admin(cursor)

                cursor.execute("""
                    SELECT b.ID_Bodega, b.Nombre as Nombre_Bodega, e.Nombre_Empresa, ib.Existencias
                    FROM inventario_bodega ib
                    JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                    JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                    WHERE ib.ID_Producto = %s AND b.Estado = 'activa'
                    ORDER BY e.Nombre_Empresa, b.Nombre
                """, (id_producto,))
                inventario_bodegas = cursor.fetchall() or []

                cursor.execute("SELECT ID_Bodega, Nombre as Nombre_Bodega FROM bodegas WHERE Estado = 'activa' ORDER BY Nombre")
                todas_bodegas = cursor.fetchall() or []

                return render_template('admin/bodega/producto/editar_producto.html', 
                                     producto=producto,
                                     categorias=catalogos['categorias'],
                                     unidades=catalogos['unidades'],
                                     empresas=catalogos['empresas'],
                                     inventario_bodegas=inventario_bodegas,
                                     todas_bodegas=todas_bodegas,
                                     fecha_actual=datetime.now().strftime('%d/%m/%Y %H:%M'))

    except Exception as e:
        flash(f'Error al procesar producto: {str(e)}', 'error')
        return redirect(url_for('admin.admin_productos'))
    
@admin_bp.route('/admin/bodega/productos/activar/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("ACTIVAR_PRODUCTO")
def admin_activar_producto(id_producto):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE productos 
                SET Estado = 'activo'
                WHERE ID_Producto = %s
            """, (id_producto,))
            
            if cursor.rowcount > 0:
                flash('Producto activado exitosamente', 'success')
            else:
                flash('Producto no encontrado', 'error')
                
    except Exception as e:
        flash(f'Error al activar producto: {str(e)}', 'error')
        
    return redirect(url_for('admin.admin_productos'))

@admin_bp.route('/admin/bodega/productos/desactivar/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("DESACTIVAR_PRODUCTO")
def admin_desactivar_producto(id_producto):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE productos 
                SET Estado = 'inactivo'
                WHERE ID_Producto = %s
            """, (id_producto,))
            
            if cursor.rowcount > 0:
                flash('Producto desactivado exitosamente', 'success')
            else:
                flash('Producto no encontrado', 'error')
                
    except Exception as e:
        flash(f'Error al desactivar producto: {str(e)}', 'error')
        
    return redirect(url_for('admin.admin_productos'))

from decimal import Decimal

@admin_bp.route('/admin/bodega/productos/transferir/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("TRANSFERIR_PRODUCTO")
def admin_transferir_producto_bodega(id_producto):
    try:
        id_bodega_origen = request.form.get('id_bodega_origen')
        id_bodega_destino = request.form.get('id_bodega_destino')
        cantidad = request.form.get('cantidad')
        observacion = request.form.get('observacion', '').strip()
        
        if not all([id_bodega_origen, id_bodega_destino, cantidad]):
            flash("Todos los campos obligatorios deben ser completados", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        try:
            id_bodega_origen = int(id_bodega_origen)
            id_bodega_destino = int(id_bodega_destino)
            cantidad = Decimal(str(cantidad))
        except ValueError:
            flash("Valores inválidos", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        if id_bodega_origen == id_bodega_destino:
            flash("La bodega origen y destino no pueden ser la misma", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        if cantidad <= 0:
            flash("La cantidad debe ser mayor a 0", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        id_usuario = current_user.id if (current_user and current_user.is_authenticated) else session.get('id_usuario', 1)
        id_empresa = session.get('id_empresa', 1)
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        
        ID_TS = 12
        ID_TE = 13
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT Descripcion, Precio_Mercado, Unidad_Medida FROM productos WHERE ID_Producto = %s AND Estado = 'activo'", (id_producto,))
            prod_info = cursor.fetchone()
            if not prod_info:
                flash("Producto no encontrado o inactivo", "error")
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                
            es_caja = prod_info.get('Unidad_Medida') == 1

            # Lógica base 30
            raw_cantidad = float(cantidad)
            if es_caja and raw_cantidad % 1 != 0:
                cajillas = int(raw_cantidad)
                unidades = int(round((raw_cantidad - cajillas) * 100))
                cantidad = Decimal(str(cajillas + (unidades / 30.0)))
            
            cursor.execute("SELECT COALESCE(Existencias, 0) as Existencias FROM inventario_bodega WHERE ID_Bodega = %s AND ID_Producto = %s", (id_bodega_origen, id_producto))
            stock_info = cursor.fetchone()
            stock_disponible = Decimal(str(stock_info['Existencias'])) if stock_info else Decimal('0')
            
            if stock_disponible < cantidad:
                flash(f"Stock insuficiente en la bodega de origen. Disponible: {stock_disponible}", "error")
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                
            cursor.execute("SELECT Nombre FROM bodegas WHERE ID_Bodega = %s", (id_bodega_origen,))
            origen_res = cursor.fetchone()
            bodega_origen_nombre = origen_res['Nombre'] if origen_res else ''

            cursor.execute("SELECT Nombre FROM bodegas WHERE ID_Bodega = %s", (id_bodega_destino,))
            destino_res = cursor.fetchone()
            bodega_destino_nombre = destino_res['Nombre'] if destino_res else ''
            
            cursor.execute("""
                SELECT dmi.Costo_Unitario 
                FROM detalle_movimientos_inventario dmi
                JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE dmi.ID_Producto = %s 
                AND (cm.Letra = 'E' OR cm.Descripcion LIKE '%%entrada%%' OR cm.Descripcion LIKE '%%compra%%')
                AND mi.Estado = 'Activa'
                ORDER BY mi.Fecha DESC, dmi.ID_Detalle_Movimiento DESC
                LIMIT 1
            """, (id_producto,))
            costo_result = cursor.fetchone()
            costo_unitario = Decimal(str(costo_result['Costo_Unitario'])) if costo_result and costo_result.get('Costo_Unitario') is not None else Decimal('0')
            precio_venta = Decimal(str(prod_info['Precio_Mercado'])) if prod_info.get('Precio_Mercado') else Decimal('0')

            subtotal = cantidad * costo_unitario
            
            obs_salida = f"Salida por traslado a {bodega_destino_nombre}"
            if observacion: obs_salida += f" - {observacion}"
            obs_entrada = f"Entrada por traslado desde {bodega_origen_nombre}"
            if observacion: obs_entrada += f" - {observacion}"
            
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino, Observacion, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Activa')
            """, (ID_TS, fecha_actual, id_bodega_origen, id_bodega_destino, obs_salida, id_empresa, id_usuario))
            id_mov_salida = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino, Observacion, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Activa')
            """, (ID_TE, fecha_actual, id_bodega_destino, id_bodega_origen, obs_entrada, id_empresa, id_usuario))
            id_mov_entrada = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO detalle_movimientos_inventario
                (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (id_mov_salida, id_producto, cantidad, costo_unitario, precio_venta, subtotal, id_usuario))
            
            cursor.execute("""
                INSERT INTO detalle_movimientos_inventario
                (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (id_mov_entrada, id_producto, cantidad, costo_unitario, precio_venta, subtotal, id_usuario))
            
            cursor.execute("""
                UPDATE inventario_bodega 
                SET Existencias = Existencias - %s
                WHERE ID_Bodega = %s AND ID_Producto = %s
            """, (cantidad, id_bodega_origen, id_producto))
            
            cursor.execute("""
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            """, (id_bodega_destino, id_producto, cantidad))
            
        flash(f"Se transfirieron {cantidad} unidades exitosamente", "success")
        
    except Exception as e:
        flash(f'Error al transferir producto: {str(e)}', 'error')
        
    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))


@admin_bp.route('/admin/bodega/productos/asignar_bodega/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("ASIGNAR_BODEGA_PRODUCTO")
def admin_asignar_bodega_producto(id_producto):
    try:
        id_bodega = safe_int(request.form.get('id_bodega'))
        cantidad = safe_float(request.form.get('cantidad', 0))
        
        if not id_bodega:
            flash("Debe seleccionar una bodega", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT ID_Producto, Unidad_Medida FROM productos WHERE ID_Producto = %s AND Estado = 'activo'", (id_producto,))
            prod_info = cursor.fetchone()
            if not prod_info:
                flash("Producto no encontrado o inactivo", "error")
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                
            es_caja = prod_info.get('Unidad_Medida') == 1
            if es_caja and cantidad % 1 != 0:
                cajillas = int(cantidad)
                unidades = int(round((cantidad - cajillas) * 100))
                cantidad = cajillas + (unidades / 30.0)
                
            cursor.execute("""
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            """, (id_bodega, id_producto, cantidad))
            
        flash("Bodega asignada exitosamente", "success")
        
    except Exception as e:
        flash(f'Error al asignar bodega: {str(e)}', 'error')
        
    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))


@admin_bp.route('/admin/bodega/productos/pdf_existencias', methods=['GET'])
@admin_required
@bitacora_decorator("PDF_EXISTENCIAS_PRODUCTOS")
def admin_productos_pdf_existencias():
    try:
        categoria_filtro = request.args.get('categoria', 'todos')
        bodega_filtro = request.args.get('bodega', 'todas')
        empresa_filtro = request.args.get('empresa', 'todas')
        estado_filtro = request.args.get('estado', 'activo')
        stock_filtro = request.args.get('stock', 'todos')
        search_term = request.args.get('search', '')

        with get_db_cursor() as cursor:
            query = """
                SELECT 
                    b.Nombre as Bodega,
                    p.COD_Producto as Codigo,
                    p.Descripcion as Producto,
                    COALESCE(um.Abreviatura, 'Und') as Unidad,
                    CAST(ib.Existencias AS DECIMAL(10,2)) as Existencias,
                    p.Unidad_Medida,
                    p.Stock_Minimo,
                    (SELECT SUM(Existencias) FROM inventario_bodega WHERE ID_Producto = p.ID_Producto) as Stock_Global
                FROM inventario_bodega ib
                JOIN productos p ON ib.ID_Producto = p.ID_Producto
                JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE ib.Existencias > 0 AND b.Estado = 'activa'
            """
            params = []
            
            if estado_filtro != 'todos':
                query += " AND p.Estado = %s"
                params.append(estado_filtro)
                
            if categoria_filtro != 'todos':
                query += " AND p.ID_Categoria = %s"
                params.append(categoria_filtro)
                
            if empresa_filtro != 'todas':
                query += " AND p.ID_Empresa = %s"
                params.append(empresa_filtro)
                
            if bodega_filtro != 'todas':
                query += " AND b.ID_Bodega = %s"
                params.append(bodega_filtro)
                
            if search_term:
                query += " AND (p.COD_Producto LIKE %s OR p.Descripcion LIKE %s)"
                params.append(f'%{search_term}%')
                params.append(f'%{search_term}%')

            query += " ORDER BY b.Nombre, p.Descripcion"
            
            cursor.execute(query, params)
            resultados = cursor.fetchall()

            if not resultados:
                flash('No hay productos con existencias para generar el reporte.', 'warning')
                return redirect(url_for('admin.admin_productos'))
                
            datos_por_bodega = {}
            for row in resultados:
                bodega = row.get('Bodega', '')
                existencias_raw = float(row.get('Existencias', 0))
                es_caja = row.get('Unidad_Medida') == 1
                stock_min = float(row.get('Stock_Minimo', 5))
                stock_actual = float(row.get('Stock_Global', 0))

                # Aplicar filtro de stock global
                if stock_filtro != 'todos':
                    if stock_filtro == 'critico' and not (0 < stock_actual <= stock_min):
                        continue
                    elif stock_filtro == 'bajo' and not (stock_min < stock_actual <= stock_min * 2):
                        continue
                    elif stock_filtro == 'normal' and not (stock_actual > stock_min * 2):
                        continue
                    elif stock_filtro == 'sin_stock' and stock_actual != 0:
                        continue

                if es_caja:
                    cajillas = int(existencias_raw)
                    unidades = int(round((existencias_raw - cajillas) * 100))
                    existencias_str = f"{cajillas}.{unidades:02d}"
                else:
                    existencias_str = f"{existencias_raw:g}"

                item = {
                    'Código': row.get('Codigo', ''),
                    'Producto': row.get('Producto', ''),
                    'Unidad': row.get('Unidad', ''),
                    'Existencias': existencias_str
                }
                    
                if bodega not in datos_por_bodega:
                    datos_por_bodega[bodega] = []
                datos_por_bodega[bodega].append(item)

            from helpers.export import exportar_pdf_existencias_por_bodega
            return exportar_pdf_existencias_por_bodega(datos_por_bodega, "Reporte_Existencias_Bodegas")
            
    except Exception as e:
        flash(f'Error al generar PDF: {str(e)}', 'error')
        return redirect(url_for('admin.admin_productos'))

