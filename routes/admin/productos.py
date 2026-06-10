from datetime import datetime
import traceback

from flask import render_template, redirect, session, url_for, request, flash, jsonify
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator

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
                    p.Estado,
                    COALESCE(cp.Descripcion, 'Sin categoría') as Categoria,
                    COALESCE(p.Precio_Mercado, 0) as Precio_Mercado,
                    COALESCE(p.Precio_Mayorista, 0) as Precio_Mayorista,
                    COALESCE(p.Precio_Ruta, 0) as Precio_Ruta,
                    COALESCE(e.Nombre_Empresa, 'Sin empresa') as Empresa,
                    COALESCE(p.Stock_Minimo, 5) as Stock_Minimo
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE p.Estado = 'activo'
            """
            
            params = []
            
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
                         p.Precio_Ruta, e.Nombre_Empresa, p.Stock_Minimo
                ORDER BY p.ID_Producto DESC
            """
            
            cursor.execute(query, params)
            productos = cursor.fetchall()
            
            # Procesar productos manejando NULL correctamente
            productos_list = []
            for producto in productos:
                if isinstance(producto, dict):
                    # Manejo para diccionario
                    codigo = producto.get('COD_Producto')
                    if codigo is None:
                        codigo = 'N/A'
                    
                    stock_val = producto.get('Stock')
                    if stock_val is None:
                        stock_val = 0
                    
                    precio_mercado = producto.get('Precio_Mercado')
                    if precio_mercado is None:
                        precio_mercado = 0
                    
                    stock_minimo = producto.get('Stock_Minimo')
                    if stock_minimo is None:
                        stock_minimo = 5
                    
                    prod_dict = {
                        'id': producto.get('ID_Producto'),
                        'codigo': codigo,
                        'nombre': producto.get('Descripcion', ''),
                        'unidad': producto.get('Unidad', 'Und'),
                        'stock': float(stock_val),
                        'estado': producto.get('Estado', 'activo'),
                        'categoria': producto.get('Categoria', 'Sin categoría'),
                        'precio_mercado': float(precio_mercado),
                        'precio_mayorista': float(producto.get('Precio_Mayorista') or 0),
                        'precio_ruta': float(producto.get('Precio_Ruta') or 0),
                        'empresa': producto.get('Empresa', 'Sin empresa'),
                        'stock_minimo': float(stock_minimo)
                    }
                else:
                    # Manejo para tupla
                    def safe_float(val, default=0):
                        if val is None:
                            return float(default)
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return float(default)
                    
                    def safe_str(val, default=''):
                        if val is None:
                            return default
                        return str(val)
                    
                    codigo = producto[1] if producto[1] is not None else 'N/A'
                    
                    prod_dict = {
                        'id': producto[0],
                        'codigo': codigo,
                        'nombre': safe_str(producto[2]),
                        'unidad': safe_str(producto[3], 'Und'),
                        'stock': safe_float(producto[4], 0),
                        'estado': safe_str(producto[5], 'activo'),
                        'categoria': safe_str(producto[6], 'Sin categoría'),
                        'precio_mercado': safe_float(producto[7], 0),
                        'precio_mayorista': safe_float(producto[8], 0),
                        'precio_ruta': safe_float(producto[9], 0),
                        'empresa': safe_str(producto[10], 'Sin empresa'),
                        'stock_minimo': safe_float(producto[11], 5)
                    }
                
                # Aplicar filtro de stock
                if stock_filtro != 'todos':
                    stock_actual = prod_dict['stock']
                    stock_min = prod_dict['stock_minimo']
                    
                    if stock_filtro == 'critico' and not (stock_actual > 0 and stock_actual <= stock_min):
                        continue
                    elif stock_filtro == 'bajo' and not (stock_actual > stock_min and stock_actual <= stock_min * 2):
                        continue
                    elif stock_filtro == 'normal' and not (stock_actual > stock_min * 2):
                        continue
                    elif stock_filtro == 'sin_stock' and stock_actual != 0:
                        continue
                
                productos_list.append(prod_dict)
            
            # Datos para filtros
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
            categorias_raw = cursor.fetchall()
            categorias = []
            for cat in categorias_raw:
                if isinstance(cat, dict):
                    categorias.append({'id': cat['ID_Categoria'], 'nombre': cat['Descripcion']})
                else:
                    categorias.append({'id': cat[0], 'nombre': cat[1] if cat[1] else 'Sin nombre'})
            
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas_raw = cursor.fetchall()
            empresas = []
            for emp in empresas_raw:
                if isinstance(emp, dict):
                    empresas.append({'id': emp['ID_Empresa'], 'nombre': emp['Nombre_Empresa']})
                else:
                    empresas.append({'id': emp[0], 'nombre': emp[1] if emp[1] else 'Sin nombre'})
            
            cursor.execute("""
                SELECT b.ID_Bodega, b.Nombre, b.ID_Empresa, e.Nombre_Empresa 
                FROM bodegas b 
                JOIN empresa e ON b.ID_Empresa = e.ID_Empresa 
                WHERE b.Estado = 'activa'
                ORDER BY e.Nombre_Empresa, b.Nombre
            """)
            bodegas_raw = cursor.fetchall()
            bodegas = []
            for bod in bodegas_raw:
                if isinstance(bod, dict):
                    bodegas.append({
                        'id': bod['ID_Bodega'],
                        'nombre': bod['Nombre'],
                        'id_empresa': bod['ID_Empresa'],
                        'empresa': bod['Nombre_Empresa']
                    })
                else:
                    bodegas.append({
                        'id': bod[0],
                        'nombre': bod[1] if bod[1] else 'Sin nombre',
                        'id_empresa': bod[2],
                        'empresa': bod[3] if bod[3] else 'Sin empresa'
                    })
            
            cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM unidades_medida")
            unidades_raw = cursor.fetchall()
            unidades = []
            for uni in unidades_raw:
                if isinstance(uni, dict):
                    unidades.append({
                        'id': uni['ID_Unidad'],
                        'nombre': uni['Descripcion'],
                        'abreviatura': uni['Abreviatura'] or ''
                    })
                else:
                    unidades.append({
                        'id': uni[0],
                        'nombre': uni[1] if uni[1] else 'Sin nombre',
                        'abreviatura': uni[2] if uni[2] else ''
                    })
            
            # Estadísticas
            stats = {
                'total': len(productos_list),
                'critico': sum(1 for p in productos_list if 0 < p['stock'] <= p['stock_minimo']),
                'sin_stock': sum(1 for p in productos_list if p['stock'] == 0),
                'total_stock': sum(p['stock'] for p in productos_list)
            }
            
            return render_template('admin/bodega/producto/productos.html', 
                                 productos=productos_list,
                                 stats=stats,
                                 categorias=categorias,
                                 categoria_seleccionada=categoria_filtro,
                                 bodegas=bodegas,
                                 bodega_seleccionada=bodega_filtro,
                                 stock_seleccionado=stock_filtro,
                                 empresas=empresas,
                                 empresa_seleccionada=empresa_filtro,
                                 unidades=unidades,
                                 search_term=search_term)
                                 
    except Exception as e:
        import traceback
        print(f"Error: {traceback.format_exc()}")
        flash(f'Error al cargar productos: {str(e)}', 'error')
        return render_template('admin/bodega/producto/productos.html',
                                productos=[], 
                                stats={'total': 0, 'critico': 0, 'sin_stock': 0, 'total_stock': 0},
                                categorias=[], 
                                categoria_seleccionada='todos',
                                bodegas=[],
                                bodega_seleccionada='todas',
                                stock_seleccionado='todos',
                                empresas=[],
                                empresa_seleccionada='todas',
                                unidades=[],
                                search_term='')

@admin_bp.route('/admin/bodega/productos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PRODUCTO")
def admin_crear_producto():
    try:
        # Obtener datos del formulario - Actualizado con nuevos precios
        cod_producto = request.form.get('COD_Producto')
        descripcion = request.form.get('Descripcion')
        id_unidad_medida = request.form.get('Unidad_Medida')
        id_categoria = request.form.get('ID_Categoria')
        precio_mercado = request.form.get('Precio_Mercado', 0)      # Nuevo
        precio_mayorista = request.form.get('Precio_Mayorista', 0)  # Nuevo
        precio_ruta = request.form.get('Precio_Ruta', 0)            # Nuevo
        id_empresa = request.form.get('ID_Empresa', 1)
        stock_minimo = request.form.get('Stock_Minimo', 5)
        cantidad_inicial = request.form.get('Cantidad_Inicial')
        id_bodega = request.form.get('ID_Bodega')
        estado = request.form.get('Estado', 'activo')
        usuario_creador = session.get('id_usuario', 1)

        print(f"DEBUG: Datos recibidos - Descripcion: {descripcion}, Bodega: {id_bodega}, Empresa: {id_empresa}")

        # Validaciones básicas
        if not all([descripcion, id_unidad_medida, id_categoria]):
            flash('Descripción, unidad de medida y categoría son campos obligatorios', 'error')
            return redirect(url_for('admin.admin_productos'))

        if not id_bodega:
            flash('Debe seleccionar una bodega para el inventario inicial', 'error')
            return redirect(url_for('admin.admin_productos'))

        # Validar y convertir valores
        try:
            cantidad_inicial = float(cantidad_inicial) if cantidad_inicial else 0
        except (ValueError, TypeError):
            cantidad_inicial = 0
            
        # Convertir precios
        try:
            precio_mercado = float(precio_mercado) if precio_mercado else 0.0
        except (ValueError, TypeError):
            precio_mercado = 0.0
            
        try:
            precio_mayorista = float(precio_mayorista) if precio_mayorista else 0.0
        except (ValueError, TypeError):
            precio_mayorista = 0.0
            
        try:
            precio_ruta = float(precio_ruta) if precio_ruta else 0.0
        except (ValueError, TypeError):
            precio_ruta = 0.0
            
        try:
            stock_minimo = float(stock_minimo) if stock_minimo else 5.0
        except (ValueError, TypeError):
            stock_minimo = 5.0

        try:
            id_unidad_medida = int(id_unidad_medida)
        except (ValueError, TypeError):
            flash('Unidad de medida no válida', 'error')
            return redirect(url_for('admin.admin_productos'))
            
        try:
            id_categoria = int(id_categoria)
        except (ValueError, TypeError):
            flash('Categoría no válida', 'error')
            return redirect(url_for('admin.admin_productos'))
            
        try:
            id_empresa = int(id_empresa)
        except (ValueError, TypeError):
            id_empresa = 1
            
        try:
            id_bodega = int(id_bodega)
        except (ValueError, TypeError):
            flash('Bodega no válida', 'error')
            return redirect(url_for('admin.admin_productos'))

        with get_db_cursor(commit=True) as cursor:
            print(f"DEBUG: Verificando bodega ID: {id_bodega}")
            
            # Verificar que la bodega existe y está activa
            cursor.execute("""
                SELECT ID_Bodega, ID_Empresa FROM bodegas 
                WHERE ID_Bodega = %s AND Estado = 'activa'
            """, (id_bodega,))
            
            bodega_data = cursor.fetchone()
            print(f"DEBUG: Datos bodega obtenidos: {bodega_data}")
            
            if not bodega_data:
                flash('La bodega seleccionada no es válida', 'error')
                return redirect(url_for('admin.admin_productos'))
            
            # Manejar tanto diccionarios como tuplas
            if isinstance(bodega_data, dict):
                bodega_id = bodega_data.get('ID_Bodega')
                bodega_empresa_id = bodega_data.get('ID_Empresa')
            else:
                bodega_id = bodega_data[0]
                bodega_empresa_id = bodega_data[1]
            
            print(f"DEBUG: Bodega ID: {bodega_id}, Empresa Bodega: {bodega_empresa_id}, Empresa Form: {id_empresa}")
            
            # Verificar que la bodega pertenece a la empresa del producto
            if bodega_empresa_id != id_empresa:
                flash('La bodega seleccionada no pertenece a la empresa del producto', 'error')
                return redirect(url_for('admin.admin_productos'))

            # Verificar si el código de producto ya existe
            if cod_producto:
                cursor.execute("SELECT ID_Producto FROM productos WHERE COD_Producto = %s", (cod_producto,))
                if cursor.fetchone():
                    flash('El código de producto ya existe', 'error')
                    return redirect(url_for('admin.admin_productos'))
            else:
                # Generar código automático si no se proporciona
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(COD_Producto AS UNSIGNED)), 0) + 1 
                    FROM productos 
                    WHERE COD_Producto REGEXP '^[0-9]+$'
                """)
                result = cursor.fetchone()
                
                if isinstance(result, dict):
                    max_cod = result.get(list(result.keys())[0])
                else:
                    max_cod = result[0] if result else 0
                    
                cod_producto = str(max_cod + 1) if max_cod else "1"
                print(f"DEBUG: Código generado: {cod_producto}")

            # Insertar nuevo producto - Actualizado con los nuevos campos de precio
            print(f"DEBUG: Insertando producto...")
            cursor.execute("""
                INSERT INTO Productos (
                    COD_Producto, Descripcion, Unidad_Medida, Estado,
                    ID_Categoria, Precio_Mercado, Precio_Mayorista, Precio_Ruta, 
                    ID_Empresa, Usuario_Creador, Stock_Minimo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cod_producto, descripcion, id_unidad_medida, estado,
                id_categoria, precio_mercado, precio_mayorista, precio_ruta, 
                id_empresa, usuario_creador, stock_minimo
            ))

            producto_id = cursor.lastrowid
            print(f"DEBUG: Producto creado con ID: {producto_id}")

            # Insertar en inventario_bodega con la cantidad inicial
            cursor.execute("""
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            """, (id_bodega, producto_id, cantidad_inicial))

        flash(f'Producto "{descripcion}" creado exitosamente con {cantidad_inicial} unidades en la bodega seleccionada', 'success')
        
    except Exception as e:
        print(f"ERROR DETALLADO: {str(e)}")
        print(traceback.format_exc())
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
            # ========== PROCESAR FORMULARIO POST ==========
            # Obtener datos del formulario - Actualizado con nuevos precios
            cod_producto = request.form.get('COD_Producto', '').strip()
            descripcion = request.form.get('Descripcion', '').strip()
            unidad_medida = request.form.get('Unidad_Medida')
            id_categoria = request.form.get('ID_Categoria')
            precio_mercado = request.form.get('Precio_Mercado', 0)      # Nuevo
            precio_mayorista = request.form.get('Precio_Mayorista', 0)  # Nuevo
            precio_ruta = request.form.get('Precio_Ruta', 0)            # Nuevo
            id_empresa = request.form.get('ID_Empresa')
            stock_minimo = request.form.get('Stock_Minimo', 5)
            estado = request.form.get('Estado', 'activo')

            # Validaciones
            if not descripcion:
                flash('La descripción es obligatoria', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            if not unidad_medida or not id_categoria or not id_empresa:
                flash('Unidad de medida, categoría y empresa son campos obligatorios', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            # Validar estado
            if estado not in ['activo', 'inactivo']:
                estado = 'activo'

            # Convertir valores numéricos
            try:
                precio_mercado = float(precio_mercado) if precio_mercado else 0
                precio_mayorista = float(precio_mayorista) if precio_mayorista else 0
                precio_ruta = float(precio_ruta) if precio_ruta else 0
                stock_minimo = float(stock_minimo) if stock_minimo else 5
                
                # Validar valores positivos
                if precio_mercado < 0 or precio_mayorista < 0 or precio_ruta < 0:
                    flash('Los precios no pueden ser negativos', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                    
                if stock_minimo < 0:
                    flash('El stock mínimo no puede ser negativo', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                    
            except (ValueError, TypeError):
                flash('Error en los valores numéricos', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            with get_db_cursor(commit=True) as cursor:
                # Verificar si el código de producto ya existe en otro producto
                if cod_producto:
                    cursor.execute("""
                        SELECT ID_Producto FROM productos 
                        WHERE COD_Producto = %s AND ID_Producto != %s
                    """, (cod_producto, id_producto))
                    if cursor.fetchone():
                        flash('El código de producto ya existe en otro producto', 'error')
                        return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                # Verificar que las referencias existan
                cursor.execute("SELECT ID_Unidad FROM unidades_medida WHERE ID_Unidad = %s", (unidad_medida,))
                if not cursor.fetchone():
                    flash('La unidad de medida seleccionada no existe', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Categoria FROM categorias_producto WHERE ID_Categoria = %s", (id_categoria,))
                if not cursor.fetchone():
                    flash('La categoría seleccionada no existe', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", (id_empresa,))
                if not cursor.fetchone():
                    flash('La empresa seleccionada no existe o está inactiva', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                # Actualizar producto - Actualizado con nuevos precios
                cursor.execute("""
                    UPDATE productos SET
                        COD_Producto = %s,
                        Descripcion = %s,
                        Unidad_Medida = %s,
                        ID_Categoria = %s,
                        Precio_Mercado = %s,      -- Nuevo
                        Precio_Mayorista = %s,    -- Nuevo
                        Precio_Ruta = %s,          -- Nuevo
                        ID_Empresa = %s,
                        Stock_Minimo = %s,
                        Estado = %s
                    WHERE ID_Producto = %s
                """, (
                    cod_producto or None,
                    descripcion, 
                    unidad_medida, 
                    id_categoria,
                    precio_mercado, 
                    precio_mayorista,
                    precio_ruta,
                    id_empresa, 
                    stock_minimo, 
                    estado,
                    id_producto
                ))

                # Verificar si se actualizó algún registro
                if cursor.rowcount == 0:
                    flash('No se pudo actualizar el producto. Puede que no exista.', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            flash('Producto actualizado exitosamente', 'success')
            return redirect(url_for('admin.admin_productos'))

        else:
            # ========== CARGAR FORMULARIO GET ==========
            with get_db_cursor() as cursor:
                # Obtener el producto específico - Actualizado con nuevos precios
                cursor.execute("""
                    SELECT 
                        p.ID_Producto,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida,
                        um.Descripcion as Nombre_Unidad,
                        um.Abreviatura,
                        p.Estado,
                        p.ID_Categoria,
                        cp.Descripcion as Nombre_Categoria,
                        p.Precio_Mercado,      -- Nuevo
                        p.Precio_Mayorista,    -- Nuevo
                        p.Precio_Ruta,          -- Nuevo
                        p.ID_Empresa,
                        e.Nombre_Empresa,
                        p.Fecha_Creacion,
                        p.Usuario_Creador,
                        u.NombreUsuario as Usuario_Creador_Nombre,
                        p.Stock_Minimo,
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
                             cp.Descripcion, p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,  -- Actualizado
                             p.ID_Empresa, e.Nombre_Empresa, p.Fecha_Creacion, p.Usuario_Creador, 
                             u.NombreUsuario, p.Stock_Minimo
                """, (id_producto,))
                producto = cursor.fetchone()
                
                if not producto:
                    flash('Producto no encontrado', 'error')
                    return redirect(url_for('admin.admin_productos'))
                
                # Convertir a diccionario si es necesario
                if isinstance(producto, dict):
                    producto_data = producto
                else:
                    # Si es tupla, convertir a diccionario - Actualizado
                    producto_data = {
                        'ID_Producto': producto[0],
                        'COD_Producto': producto[1],
                        'Descripcion': producto[2],
                        'Unidad_Medida': producto[3],
                        'Nombre_Unidad': producto[4],
                        'Abreviatura': producto[5],
                        'Estado': producto[6],
                        'ID_Categoria': producto[7],
                        'Nombre_Categoria': producto[8],
                        'Precio_Mercado': producto[9],
                        'Precio_Mayorista': producto[10],
                        'Precio_Ruta': producto[11],
                        'ID_Empresa': producto[12],
                        'Nombre_Empresa': producto[13],
                        'Fecha_Creacion': producto[14],
                        'Usuario_Creador': producto[15],
                        'Usuario_Creador_Nombre': producto[16],
                        'Stock_Minimo': producto[17],
                        'Existencias_Totales': producto[18] or 0
                    }
                
                print(f"DEBUG - Estado del producto: {producto_data.get('Estado')}")
                print(f"DEBUG - Precios: Mercado={producto_data.get('Precio_Mercado')}, Mayorista={producto_data.get('Precio_Mayorista')}, Ruta={producto_data.get('Precio_Ruta')}")
                
                # Obtener datos para los dropdowns
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto")
                categorias = cursor.fetchall()
                
                cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM unidades_medida")
                unidades = cursor.fetchall()
                
                cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
                empresas = cursor.fetchall()
                
                # CONSULTA PARA INVENTARIO POR BODEGA
                cursor.execute("""
                    SELECT 
                        b.ID_Bodega, 
                        b.Nombre as Nombre_Bodega,
                        e.Nombre_Empresa,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM bodegas b
                    JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                    LEFT JOIN inventario_bodega ib ON b.ID_Bodega = ib.ID_Bodega AND ib.ID_Producto = %s
                    WHERE b.Estado = 'activa'
                    ORDER BY e.Nombre_Empresa, b.Nombre
                """, (id_producto,))
                inventario_bodegas = cursor.fetchall()
                
                fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
                
                return render_template('admin/bodega/producto/editar_producto.html', 
                                     producto=producto_data,
                                     categorias=categorias,
                                     unidades=unidades,
                                     empresas=empresas,
                                     inventario_bodegas=inventario_bodegas,
                                     fecha_actual=fecha_actual)
                
    except Exception as e:
        flash(f'Error al procesar producto: {str(e)}', 'error')
        traceback.print_exc()
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