"""
Blueprint de rutas del personal de bodega (dashboard, inventario, movimientos)
"""
from datetime import datetime, timedelta
from decimal import Decimal
import json
import traceback

from flask import Blueprint, jsonify, render_template, flash, redirect, request, session, url_for
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import bodega_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator

bodega_bp = Blueprint('bodega', __name__, url_prefix='/bodega')


@bodega_bp.route('/bodega/dashboard')
@admin_or_bodega_required
def bodega_dashboard():

    try:
        with get_db_cursor() as cursor:
            # 1. Productos que han salido hoy
            cursor.execute("""
                SELECT 
                    p.Descripcion AS Producto,
                    um.Abreviatura AS Unidad,
                    SUM(dmi.Cantidad) AS Cantidad_Salida,
                    b.Nombre AS Bodega
                FROM productos p
                INNER JOIN detalle_movimientos_inventario dmi ON p.ID_Producto = dmi.ID_Producto
                INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                INNER JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                WHERE mi.Estado = 'Activa'
                    AND mi.Fecha = CURDATE()
                    AND (cm.Adicion = 'RESTA' OR cm.Letra = 'S')
                GROUP BY p.ID_Producto, p.Descripcion, um.Abreviatura, b.Nombre
                HAVING SUM(dmi.Cantidad) > 0
                ORDER BY SUM(dmi.Cantidad) DESC
                LIMIT 20
            """)
            productos_salidas_hoy = cursor.fetchall()
            
            # 2. Kardex de hoy completo
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(mi.Fecha, '%H:%i:%s') AS Hora,
                    mi.ID_Movimiento,
                    cm.Descripcion AS Tipo_Movimiento,
                    p.Descripcion AS Producto,
                    um.Abreviatura AS Unidad,
                    dmi.Cantidad,
                    CASE 
                        WHEN cm.Adicion = 'SUMA' OR cm.Letra = 'E' OR cm.Letra = 'TE'
                        THEN 'ENTRADA' 
                        ELSE 'SALIDA' 
                    END AS Tipo,
                    b.Nombre AS Bodega
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                INNER JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                WHERE mi.Estado = 'Activa'
                    AND mi.Fecha = CURDATE()
                ORDER BY dmi.Fecha_Creacion DESC
                LIMIT 100
            """)
            kardex_hoy = cursor.fetchall()
            
            # 3. Resumen de movimientos del día por bodega
            cursor.execute("""
                SELECT 
                    b.Nombre AS Bodega,
                    COUNT(DISTINCT mi.ID_Movimiento) AS total_movimientos,
                    COUNT(DISTINCT dmi.ID_Producto) AS total_productos_movidos,
                    SUM(CASE 
                        WHEN cm.Adicion = 'SUMA' OR cm.Letra = 'E' 
                        THEN dmi.Cantidad 
                        ELSE 0 
                    END) AS total_entradas,
                    SUM(CASE 
                        WHEN cm.Adicion = 'RESTA' OR cm.Letra = 'S' 
                        THEN dmi.Cantidad 
                        ELSE 0 
                    END) AS total_salidas
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                WHERE mi.Estado = 'Activa'
                    AND mi.Fecha = CURDATE()
                GROUP BY b.Nombre
                ORDER BY total_movimientos DESC
            """)
            resumen_por_bodega = cursor.fetchall()
            
            # Resumen total del día
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT mi.ID_Movimiento) AS total_movimientos,
                    COUNT(DISTINCT dmi.ID_Producto) AS total_productos_movidos,
                    SUM(CASE 
                        WHEN cm.Adicion = 'SUMA' OR cm.Letra = 'E' 
                        THEN dmi.Cantidad 
                        ELSE 0 
                    END) AS total_entradas,
                    SUM(CASE 
                        WHEN cm.Adicion = 'RESTA' OR cm.Letra = 'S' 
                        THEN dmi.Cantidad 
                        ELSE 0 
                    END) AS total_salidas
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Fecha = CURDATE()
            """)
            resumen_dia_total = cursor.fetchone()
            
            # 4. Productos con stock bajo (menor al mínimo) - TODAS las bodegas
            cursor.execute("""
                SELECT 
                    p.Descripcion AS Producto,
                    um.Abreviatura AS Unidad,
                    ib.Existencias AS Stock_Actual,
                    p.Stock_Minimo AS Stock_Minimo,
                    b.Nombre AS Bodega,
                    CONCAT(FORMAT(ib.Existencias, 2), ' ', um.Abreviatura) AS Stock_Actual_Formateado,
                    ROUND((ib.Existencias / p.Stock_Minimo) * 100, 2) AS Porcentaje_Stock,
                    CASE 
                        WHEN ib.Existencias <= p.Stock_Minimo * 0.5 THEN 'CRÍTICO'
                        WHEN ib.Existencias <= p.Stock_Minimo THEN 'BAJO'
                        ELSE 'NORMAL'
                    END AS Nivel_Alerta
                FROM productos p
                INNER JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                INNER JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                INNER JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                WHERE p.Estado = 'activo'
                    AND ib.Existencias <= p.Stock_Minimo
                ORDER BY Porcentaje_Stock ASC, b.Nombre
                LIMIT 30
            """)
            productos_stock_bajo = cursor.fetchall()
            
            # 5. Top 10 productos más vendidos hoy - SIN PRECIOS
            cursor.execute("""
                SELECT 
                    p.Descripcion AS Producto,
                    um.Abreviatura AS Unidad,
                    b.Nombre AS Bodega,
                    SUM(dmi.Cantidad) AS Total_Salidas
                FROM productos p
                INNER JOIN detalle_movimientos_inventario dmi ON p.ID_Producto = dmi.ID_Producto
                INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                INNER JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                WHERE mi.Estado = 'Activa'
                    AND mi.Fecha = CURDATE()
                    AND (cm.Adicion = 'RESTA' OR cm.Letra = 'S')
                GROUP BY p.ID_Producto, p.Descripcion, um.Abreviatura, b.Nombre
                HAVING SUM(dmi.Cantidad) > 0
                ORDER BY SUM(dmi.Cantidad) DESC
                LIMIT 20
            """)
            top_productos_hoy = cursor.fetchall()
            
            # 6. Información de TODAS las bodegas - SIN VALORES MONETARIOS
            cursor.execute("""
                SELECT 
                    b.Nombre,
                    b.Ubicacion,
                    COUNT(DISTINCT ib.ID_Producto) AS total_productos,
                    COALESCE(SUM(ib.Existencias), 0) AS total_existencias,
                    COUNT(DISTINCT CASE WHEN ib.Existencias <= p.Stock_Minimo THEN ib.ID_Producto END) AS productos_criticos
                FROM bodegas b
                LEFT JOIN inventario_bodega ib ON b.ID_Bodega = ib.ID_Bodega
                LEFT JOIN productos p ON ib.ID_Producto = p.ID_Producto AND p.Estado = 'activo'
                WHERE b.Estado = 'activa'
                GROUP BY b.ID_Bodega, b.Nombre, b.Ubicacion
                ORDER BY b.Nombre
            """)
            info_bodegas = cursor.fetchall()
            
            # 7. Productos por categoría - SIN PRECIOS NI VALORES TOTALES
            cursor.execute("""
                SELECT 
                    b.Nombre AS Bodega,
                    cp.Descripcion AS Categoria,
                    p.Descripcion AS Producto,
                    um.Abreviatura AS Unidad,
                    p.COD_Producto AS Codigo,
                    ib.Existencias AS Stock_Actual,
                    p.Stock_Minimo AS Stock_Minimo,
                    CASE 
                        WHEN ib.Existencias <= p.Stock_Minimo THEN 'CRITICO'
                        WHEN ib.Existencias <= (p.Stock_Minimo * 1.5) THEN 'BAJO'
                        ELSE 'NORMAL'
                    END AS Estado_Stock
                FROM productos p
                INNER JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                INNER JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                INNER JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                INNER JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                WHERE p.Estado = 'activo'
                ORDER BY b.Nombre, cp.Descripcion, p.Descripcion
                LIMIT 500
            """)
            productos_categorias = cursor.fetchall()
            
            # 8. Resumen por bodega y categoría - SIN VALORES MONETARIOS
            cursor.execute("""
                SELECT 
                    b.Nombre AS Bodega,
                    cp.Descripcion AS Categoria,
                    COUNT(p.ID_Producto) AS Total_Productos,
                    COALESCE(SUM(ib.Existencias), 0) AS Stock_Total,
                    COUNT(CASE WHEN ib.Existencias <= p.Stock_Minimo THEN 1 END) AS Productos_Criticos,
                    COUNT(CASE WHEN ib.Existencias <= (p.Stock_Minimo * 1.5) AND ib.Existencias > p.Stock_Minimo THEN 1 END) AS Productos_Bajos
                FROM bodegas b
                CROSS JOIN categorias_producto cp
                LEFT JOIN productos p ON p.ID_Categoria = cp.ID_Categoria AND p.Estado = 'activo'
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = b.ID_Bodega
                WHERE b.Estado = 'activa'
                GROUP BY b.Nombre, cp.Descripcion
                HAVING Total_Productos > 0
                ORDER BY b.Nombre, cp.Descripcion
            """)
            resumen_categorias = cursor.fetchall()
            
            # 9. Información adicional del sistema
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM productos WHERE Estado = 'activo') as total_productos_sistema,
                    (SELECT COUNT(*) FROM bodegas WHERE Estado = 'activa') as total_bodegas_sistema,
                    (SELECT COUNT(*) FROM movimientos_inventario WHERE Fecha = CURDATE()) as movimientos_hoy_sistema
            """)
            sistema_info = cursor.fetchone()
            
            # Formatear fecha actual para mostrar
            fecha_hoy = datetime.now().strftime("%d/%m/%Y")
            
            return render_template('bodega/dashboard.html',
                                 productos_salidas_hoy=productos_salidas_hoy,
                                 kardex_hoy=kardex_hoy,
                                 resumen_por_bodega=resumen_por_bodega,
                                 resumen_dia_total=resumen_dia_total,
                                 productos_stock_bajo=productos_stock_bajo,
                                 top_productos_hoy=top_productos_hoy,
                                 info_bodegas=info_bodegas,
                                 productos_categorias=productos_categorias,
                                 resumen_categorias=resumen_categorias,
                                 sistema_info=sistema_info,
                                 fecha_hoy=fecha_hoy,
                                 current_user=current_user)
                             
    except Exception as e:
        flash(f'Error al cargar el dashboard: {str(e)}', 'error')
        print(f"ERROR en bodega_dashboard: {str(e)}")
        traceback.print_exc()
        return render_template('bodega/dashboard.html',
                             productos_salidas_hoy=[],
                             kardex_hoy=[],
                             resumen_por_bodega=[],
                             resumen_dia_total={},
                             productos_stock_bajo=[],
                             top_productos_hoy=[],
                             info_bodegas=[],
                             productos_categorias=[],
                             resumen_categorias=[],
                             sistema_info={},
                             fecha_hoy=datetime.now().strftime("%d/%m/%Y"),
                             current_user=current_user)

TIPO_COMPRA = 1
TIPO_VENTA = 2
TIPO_PRODUCCION = 3
TIPO_CONSUMO = 4
TIPO_AJUSTE = 5
TIPO_TRASLADO = 6

# 1. LISTADO MEJORADO CON FILTROS
@bodega_bp.route('/bodega/movimientos/listado')
@admin_or_bodega_required
@bitacora_decorator("HISTORIAL-MOVIMIENTOS")
def bodega_historial_movimientos():
    """Historial completo de movimientos con filtros"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Filtros
        tipo_filtro = request.args.get('tipo', 'todos')
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        
        with get_db_cursor(True) as cursor:
            # Construir consulta base CORREGIDA
            query = """
                SELECT mi.*, 
                       cm.Descripcion as Tipo_Movimiento_Descripcion,
                       cm.Letra,
                       bo.Nombre as Bodega_Origen_Nombre,
                       bd.Nombre as Bodega_Destino_Nombre,
                       p.Nombre as Proveedor_Nombre,
                       u.NombreUsuario as Usuario_Creacion_Nombre,
                       (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Cantidad_Productos,
                       (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Costo
                FROM movimientos_inventario mi
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor 
                    AND p.ID_Empresa = mi.ID_Empresa  -- IMPORTANTE: filtrar por misma empresa
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE mi.Estado = 1
            """
            
            count_query = """
                SELECT COUNT(*) as total
                FROM movimientos_inventario mi
                WHERE mi.Estado = 1
            """
            
            params = []
            count_params = []
            
            # Aplicar filtros
            if tipo_filtro != 'todos':
                query += " AND mi.ID_TipoMovimiento = %s"
                count_query += " AND mi.ID_TipoMovimiento = %s"
                params.append(tipo_filtro)
                count_params.append(tipo_filtro)
            
            if fecha_inicio:
                query += " AND mi.Fecha >= %s"
                count_query += " AND mi.Fecha >= %s"
                params.append(fecha_inicio)
                count_params.append(fecha_inicio)
            
            if fecha_fin:
                query += " AND mi.Fecha <= %s"
                count_query += " AND mi.Fecha <= %s"
                params.append(fecha_fin)
                count_params.append(fecha_fin)
            
            # Ordenar y paginar
            query += " ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            # Ejecutar consulta de conteo
            cursor.execute(count_query, tuple(count_params))
            total = cursor.fetchone()['total']
            
            # Ejecutar consulta principal
            cursor.execute(query, tuple(params))
            movimientos = cursor.fetchall()
            
            # Obtener tipos de movimiento para filtro
            cursor.execute("SELECT * FROM catalogo_movimientos ORDER BY Descripcion")
            tipos_movimiento = cursor.fetchall()
            
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('bodega/movimientos/historial_movimientos.html',
                                 movimientos=movimientos,
                                 tipos_movimiento=tipos_movimiento,
                                 tipo_filtro=tipo_filtro,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 page=page,
                                 total_pages=total_pages,
                                 total=total)
    except Exception as e:
        flash(f"Error al cargar historial: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_dashboard'))

# 2. NUEVA ENTRADA (Compra/Producción)
@bodega_bp.route('/bodega/movimientos/entrada/nueva')
@admin_or_bodega_required
def bodega_nueva_entrada_form():

    print(f"DEBUG - current_user: {current_user}")
    print(f"DEBUG - current_user.is_authenticated: {current_user.is_authenticated}")
    print(f"DEBUG - current_user.id: {getattr(current_user, 'id', 'NO ID ATTRIBUTE')}")
    print(f"DEBUG - current_user.__dict__: {current_user.__dict__}")

    """Mostrar formulario para nueva entrada (compra/producción)"""
    try:
        with get_db_cursor(True) as cursor:
            # Solo mostrar tipos de entrada (Letra = 'E')
            cursor.execute("""
                SELECT * FROM catalogo_movimientos 
                WHERE Letra = 'E'
                ORDER BY Descripcion
            """)  # Ajuste también puede ser entrada
            
            tipos_movimiento = cursor.fetchall()
            
            # Obtener proveedores
            cursor.execute("""
                SELECT * FROM proveedores 
                WHERE Estado = 'ACTIVO' 
                ORDER BY Nombre
            """)
            proveedores = cursor.fetchall()
            
            # Obtener bodegas
            cursor.execute("""
                SELECT * FROM bodegas 
                WHERE Estado = 1 
                ORDER BY Nombre
            """)
            bodegas = cursor.fetchall()
            
            # Obtener productos activos
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    p.Unidad_Medida, 
                    um.Descripcion as Unidad_Descripcion,
                    p.Precio_Mercado as Precio_Venta, 
                    p.Stock_Minimo,
                    cp.Descripcion as Categoria_Descripcion,
                    COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE p.Estado = 'activo'
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, 
                         p.Unidad_Medida, Precio_Venta, p.Stock_Minimo,
                         um.Descripcion, cp.Descripcion
                ORDER BY p.Descripcion
                LIMIT 100
            """)
            productos = cursor.fetchall()
            
            # Obtener también el stock por bodega para cada producto
            productos_con_stock = []
            for producto in productos:
                producto_dict = dict(producto)
                
                # Consultar stock por bodega
                cursor.execute("""
                    SELECT 
                        b.ID_Bodega,
                        b.Nombre as Bodega,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM bodegas b
                    LEFT JOIN inventario_bodega ib ON b.ID_Bodega = ib.ID_Bodega 
                        AND ib.ID_Producto = %s
                    WHERE b.Estado = 1
                    ORDER BY b.Nombre
                """, (producto['ID_Producto'],))
                
                stock_bodegas = cursor.fetchall()
                producto_dict['stock_bodegas'] = stock_bodegas
                
                productos_con_stock.append(producto_dict)

            fecha_hoy = datetime.now().strftime('%Y-%m-%d')
            
            return render_template('bodega/movimientos/nueva_entrada.html',
                                 tipos_movimiento=tipos_movimiento,
                                 proveedores=proveedores,
                                 bodegas=bodegas,
                                 productos=productos_con_stock,
                                 fecha_hoy=fecha_hoy)
    except Exception as e:
        flash(f"Error al cargar formulario: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_historial_movimientos'))

# 3. PROCESAR ENTRADA
@bodega_bp.route('/bodega/movimientos/entrada/procesar', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("PROCESAR-ENTRADA")
def bodega_procesar_entrada():
    """Procesar nueva entrada (compra/producción/ajuste positivo)"""
    try:
        # Obtener user_id desde current_user (Flask-Login)
        if not current_user.is_authenticated:
            flash("Debe iniciar sesión para realizar esta acción", 'error')
            return redirect(url_for('auth.login'))
        
        user_id = current_user.id
        print(f"DEBUG - User ID from current_user: {user_id}")
        
        # Validar datos básicos
        fecha = request.form.get('fecha')
        id_tipo_movimiento = request.form.get('id_tipo_movimiento')
        id_bodega = request.form.get('id_bodega')
        
        if not all([fecha, id_tipo_movimiento, id_bodega]):
            flash("Fecha, tipo de movimiento y bodega son requeridos", 'error')
            return redirect(url_for('bodega.bodega_nueva_entrada_form'))
        
        # Convertir valores
        try:
            id_tipo_movimiento = int(id_tipo_movimiento)
            id_bodega = int(id_bodega)
        except ValueError:
            flash("ID de tipo de movimiento o bodega no válido", 'error')
            return redirect(url_for('bodega.bodega_nueva_entrada_form'))
        
        # Validar que sea tipo de entrada
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT Letra FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = %s
            """, (id_tipo_movimiento,))
            
            tipo_mov = cursor.fetchone()
            if not tipo_mov or tipo_mov['Letra'] not in ['E', 'A']:
                flash("Tipo de movimiento no válido para entrada", 'error')
                return redirect(url_for('bodega.bodega_nueva_entrada_form'))
        
        # Obtener productos
        productos_json = request.form.get('productos')
        if not productos_json:
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('bodega.bodega_nueva_entrada_form'))
        
        try:
            productos = json.loads(productos_json)
        except json.JSONDecodeError:
            flash("Formato de productos no válido", 'error')
            return redirect(url_for('bodega.bodega_nueva_entrada_form'))
        
        with get_db_cursor() as cursor:
            # Obtener ID de empresa del usuario o usar valor por defecto
            cursor.execute("""
                SELECT ID_Empresa FROM usuarios WHERE ID_Usuario = %s
            """, (user_id,))
            
            usuario_data = cursor.fetchone()
            id_empresa = usuario_data['ID_Empresa'] if usuario_data else 1
            
            # Insertar movimiento principal
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Proveedor, Tipo_Compra, 
                 ID_Bodega, N_Factura_Externa, Observacion, 
                 ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id_tipo_movimiento, 
                fecha,
                request.form.get('id_proveedor') or None,
                request.form.get('tipo_compra') or None,
                id_bodega,
                request.form.get('n_factura_externa') or None,
                request.form.get('observacion') or None,
                id_empresa,
                user_id
            ))
            
            id_movimiento = cursor.lastrowid
            
            # Procesar cada producto
            for prod in productos:
                try:
                    # Validar campos requeridos
                    if 'id_producto' not in prod or not prod['id_producto']:
                        continue
                    
                    if 'cantidad' not in prod or not prod['cantidad']:
                        continue
                    
                    # Convertir valores
                    id_producto = int(prod['id_producto'])
                    cantidad = Decimal(str(prod.get('cantidad', 0)))
                    costo_unitario = Decimal(str(prod.get('costo_unitario', 0)))
                    precio_unitario = Decimal(str(prod.get('precio_unitario', 0)))
                    subtotal = cantidad * costo_unitario
                    
                    # Validar valores positivos
                    if cantidad <= 0:
                        continue
                    
                    # Validar que el producto existe
                    cursor.execute("""
                        SELECT ID_Producto FROM productos 
                        WHERE ID_Producto = %s AND Estado = 'activo'
                    """, (id_producto,))
                    
                    if not cursor.fetchone():
                        continue
                    
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario
                        (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                         Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        id_producto, 
                        cantidad,
                        costo_unitario, 
                        precio_unitario, 
                        subtotal,
                        user_id
                    ))
                    
                    # ACTUALIZAR inventario_bodega
                    cursor.execute("""
                        INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Existencias = Existencias + VALUES(Existencias)
                    """, (id_bodega, id_producto, cantidad))
                    
                except Exception as prod_error:
                    print(f"Error con producto: {prod_error}")
                    continue
            
            flash(f"✅ Entrada registrada exitosamente! ID: {id_movimiento}", 'success')
            return redirect(url_for('bodega.bodega_detalle_movimiento', id_movimiento=id_movimiento))
            
    except Exception as e:
        print(f"Error completo: {e}")
        flash(f"❌ Error al procesar entrada: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_nueva_entrada_form'))

def obtener_existencias_producto(id_producto):
    """Obtener existencias totales de un producto sumando todas las bodegas"""
    with get_db_cursor(True) as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(Existencias), 0) as Existencias_Totales
            FROM inventario_bodega
            WHERE ID_Producto = %s
        """, (id_producto,))
        
        result = cursor.fetchone()
        return result['Existencias_Totales'] if result else 0

# 4. NUEVA SALIDA (Venta/Consumo)
@bodega_bp.route('/bodega/movimientos/salida/nueva')
@bodega_required
def bodega_nueva_salida_form():
    """Mostrar formulario para nueva salida (venta/consumo)"""
    try:
        with get_db_cursor(True) as cursor:
            # Solo mostrar tipos de salida (Letra = 'S')
            cursor.execute("""
                SELECT * FROM catalogo_movimientos 
                WHERE Letra = 'S'
                ORDER BY Descripcion
            """)  # Ajuste también puede ser salida
            
            tipos_movimiento = cursor.fetchall()
            
            # Obtener bodegas
            cursor.execute("""
                SELECT * FROM bodegas 
                WHERE Estado = 1 
                ORDER BY Nombre
            """)
            bodegas = cursor.fetchall()
            
            # Obtener clientes (para ventas)
            cursor.execute("""
                SELECT * FROM clientes 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            clientes = cursor.fetchall()
            
            # Obtener facturas pendientes - CORREGIDO: formateo de fecha
            cursor.execute("""
                SELECT f.ID_Factura, f.Fecha, c.Nombre as Cliente,
                       (SELECT COUNT(*) FROM detalle_facturacion 
                        WHERE ID_Factura = f.ID_Factura) as Items
                FROM facturacion f
                JOIN clientes c ON f.IDCliente = c.ID_Cliente
                WHERE f.ID_Empresa = %s
                AND f.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                ORDER BY f.Fecha DESC
                LIMIT 50
            """, (session.get('id_empresa', 1),))
            
            facturas = cursor.fetchall()
            
            # Formatear fechas para el template
            for factura in facturas:
                if factura['Fecha']:
                    factura['Fecha_formatted'] = factura['Fecha'].strftime('%Y-%m-%d')
                else:
                    factura['Fecha_formatted'] = ''

            fecha_hoy = datetime.now().strftime('%Y-%m-%d')
            
            return render_template('bodega/movimientos/nueva_salida.html',
                                 tipos_movimiento=tipos_movimiento,
                                 bodegas=bodegas,
                                 clientes=clientes,
                                 facturas=facturas,
                                 fecha_hoy=fecha_hoy)
    except Exception as e:
        flash(f"Error al cargar formulario: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_historial_movimientos'))

# 5. PROCESAR SALIDA
@bodega_bp.route('/bodega/movimientos/salida/procesar', methods=['POST'])
@bodega_required
@bitacora_decorator("PROCESAR-SALIDA")
def bodega_procesar_salida():
    """Procesar nueva salida (venta/consumo/ajuste negativo)"""
    try:
        # Validar autenticación
        if not current_user.is_authenticated:
            flash("Debe iniciar sesión para realizar esta acción", 'error')
            return redirect(url_for('auth.login'))
        
        user_id = current_user.id
        
        # Validar datos básicos
        fecha = request.form.get('fecha')
        id_tipo_movimiento = request.form.get('id_tipo_movimiento')
        id_bodega = request.form.get('id_bodega')
        
        if not all([fecha, id_tipo_movimiento, id_bodega]):
            flash("Fecha, tipo de movimiento y bodega son requeridos", 'error')
            return redirect(url_for('bodega.bodega_nueva_salida_form'))
        
        try:
            id_tipo_movimiento = int(id_tipo_movimiento)
            id_bodega = int(id_bodega)
        except ValueError:
            flash("ID de tipo de movimiento o bodega no válido", 'error')
            return redirect(url_for('bodega.bodega_nueva_salida_form'))
        
        # Validar que sea tipo de salida
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT Letra FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = %s
            """, (id_tipo_movimiento,))
            
            tipo_mov = cursor.fetchone()
            if not tipo_mov or tipo_mov['Letra'] not in ['S', 'A']:
                flash("Tipo de movimiento no válido para salida", 'error')
                return redirect(url_for('bodega.bodega_nueva_salida_form'))
        
        # Obtener productos
        productos_json = request.form.get('productos')
        if not productos_json:
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('bodega.bodega_nueva_salida_form'))
        
        try:
            productos = json.loads(productos_json)
        except json.JSONDecodeError:
            flash("Formato de productos no válido", 'error')
            return redirect(url_for('bodega.bodega_nueva_salida_form'))
        
        with get_db_cursor() as cursor:
            # Obtener ID de empresa del usuario
            cursor.execute("""
                SELECT ID_Empresa FROM usuarios WHERE ID_Usuario = %s
            """, (user_id,))
            
            usuario_data = cursor.fetchone()
            id_empresa = usuario_data['ID_Empresa'] if usuario_data else 1
            
            # VERIFICAR STOCK antes de proceder
            productos_insuficientes = []
            
            for prod in productos:
                cursor.execute("""
                    SELECT Existencias 
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega, prod['id_producto']))
                
                stock = cursor.fetchone()
                cantidad_necesaria = Decimal(str(prod['cantidad']))
                
                stock_disponible = stock['Existencias'] if stock else Decimal('0')
                
                if stock_disponible < cantidad_necesaria:
                    # Obtener nombre del producto
                    cursor.execute("SELECT Descripcion FROM productos WHERE ID_Producto = %s", 
                                 (prod['id_producto'],))
                    producto_info = cursor.fetchone()
                    producto_nombre = producto_info['Descripcion'] if producto_info else 'Producto desconocido'
                    
                    productos_insuficientes.append({
                        'producto': producto_nombre,
                        'solicitado': float(cantidad_necesaria),
                        'disponible': float(stock_disponible)
                    })
            
            if productos_insuficientes:
                mensaje_error = "Stock insuficiente:<br>"
                for item in productos_insuficientes:
                    mensaje_error += f"- {item['producto']}: Solicitado {item['solicitado']}, Disponible {item['disponible']}<br>"
                flash(mensaje_error, 'error')
                return redirect(url_for('bodega.bodega_nueva_salida_form'))
            
            # VARIABLE PARA ID DE FACTURA
            id_factura_venta = None
            
            # SI ES VENTA, MANEJAR FACTURACIÓN Y CUENTAS POR COBRAR
            if id_tipo_movimiento == TIPO_VENTA:  # TIPO_VENTA = 2
                id_cliente = request.form.get('id_cliente')
                id_factura_existente = request.form.get('id_factura_venta')
                tipo_pago = request.form.get('tipo_pago')  # CONTADO o CREDITO
                
                if not id_cliente and not id_factura_existente:
                    flash("Para ventas debe seleccionar un cliente o una factura existente", 'error')
                    return redirect(url_for('bodega.bodega_nueva_salida_form'))
                
                if id_factura_existente:
                    # Usar factura existente
                    id_factura_venta = int(id_factura_existente)
                    
                    # Verificar que la factura pertenece a la empresa
                    cursor.execute("""
                        SELECT ID_Factura FROM facturacion 
                        WHERE ID_Factura = %s AND ID_Empresa = %s
                    """, (id_factura_venta, id_empresa))
                    
                    if not cursor.fetchone():
                        flash("Factura no encontrada o no pertenece a su empresa", 'error')
                        return redirect(url_for('bodega.bodega_nueva_salida_form'))
                        
                elif id_cliente:
                    # Crear nueva factura
                    cursor.execute("""
                        INSERT INTO facturacion 
                        (Fecha, IDCliente, Credito_Contado, Observacion, 
                         ID_Empresa, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        fecha,
                        id_cliente,
                        1 if tipo_pago == 'CREDITO' else 0,  # 1=Crédito, 0=Contado
                        request.form.get('observacion_factura') or None,
                        id_empresa,
                        user_id
                    ))
                    id_factura_venta = cursor.lastrowid
                    
                    # Calcular total de la venta - CORREGIDO: usar precio_unitario, NO costo_unitario
                    total_venta = Decimal('0')
                    for prod in productos:
                        cantidad = Decimal(str(prod['cantidad']))
                        # ✅ USAR PRECIO_UNITARIO para el total de venta
                        precio_unitario = Decimal(str(prod.get('precio_unitario', 0)))
                        total_item = cantidad * precio_unitario
                        total_venta += total_item
                        
                        # Insertar detalle de facturación - guardamos el precio de venta
                        cursor.execute("""
                            INSERT INTO detalle_facturacion 
                            (ID_Factura, ID_Producto, Cantidad, Costo, Total)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            id_factura_venta,
                            prod['id_producto'],
                            cantidad,
                            precio_unitario,  
                            total_item
                        ))

                    # Si es CRÉDITO, crear registro en cuentas por cobrar
                    if tipo_pago == 'CREDITO':
                        # Calcular fecha de vencimiento (30 días por defecto)
                        fecha_vencimiento = (datetime.strptime(fecha, '%Y-%m-%d') + 
                                           timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO cuentas_por_cobrar 
                            (Fecha, ID_Cliente, Num_Documento, Observacion,
                             Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                             ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            fecha,
                            id_cliente,
                            f"FACT-{id_factura_venta:06d}",  # Formato: FACT-000001
                            f"Venta a crédito - Factura #{id_factura_venta}",
                            fecha_vencimiento,
                            1,  # Tipo movimiento: 1 = Factura (debe)
                            total_venta,  # ✅ Usamos total_venta (basado en precio_unitario)
                            id_empresa,
                            total_venta,  # ✅ Saldo pendiente inicial = monto total (basado en precio)
                            id_factura_venta,
                            user_id
                        ))

                    if tipo_pago == 'CONTADO':
                        cursor.execute("SELECT Nombre FROM clientes WHERE ID_Cliente = %s", (id_cliente,))
                        cliente_data = cursor.fetchone()
                        nombre_cliente = cliente_data['Nombre'] if cliente_data else f'Cliente ID: {id_cliente}'
                        
                        cursor.execute("""
                            INSERT INTO caja_movimientos (
                                Fecha, Tipo_Movimiento, Descripcion, Monto, 
                                ID_Factura, ID_Usuario, Referencia_Documento
                            )
                            VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                        """, (
                            f'Venta al contado - Factura #{id_factura_venta} - Cliente: {nombre_cliente}',
                            total_venta,
                            id_factura_venta,
                            current_user.id,
                            f'FAC-{id_factura_venta:05d}'
                        ))
                    print(f"💰 Entrada en caja registrada: C${total_venta:,.2f}")
                    
                    flash(f"✅ Factura #{id_factura_venta} creada exitosamente", 'success')
                    
                    if tipo_pago == 'CREDITO':
                        flash(f"📝 Cuenta por cobrar registrada por C${total_venta:,.2f} - Vence: {fecha_vencimiento}", 'info')
            
            # Insertar movimiento de inventario (SALIDA)
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Factura_Venta,
                 Observacion, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                id_tipo_movimiento, 
                fecha, 
                id_bodega,
                id_factura_venta,
                request.form.get('observacion') or None,
                id_empresa,
                user_id
            ))
            
            id_movimiento = cursor.lastrowid
            
            # Procesar cada producto para el movimiento de inventario
            for prod in productos:
                try:
                    # Validar campos requeridos
                    if 'id_producto' not in prod or not prod['id_producto']:
                        continue
                    
                    if 'cantidad' not in prod or not prod['cantidad']:
                        continue
                    
                    # Convertir valores
                    id_producto = int(prod['id_producto'])
                    cantidad = Decimal(str(prod['cantidad']))
                    precio_unitario = Decimal(str(prod.get('precio_unitario', 0)))
                    
                    # Obtener costo promedio (último costo de entrada) - para el inventario
                    cursor.execute("""
                        SELECT Precio_Unitario 
                        FROM detalle_movimientos_inventario dmi
                        JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                        JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                        WHERE dmi.ID_Producto = %s 
                        AND cm.Letra = 'E'
                        ORDER BY mi.Fecha DESC, dmi.ID_Detalle_Movimiento DESC
                        LIMIT 1
                    """, (id_producto,))
                    
                    precio_result = cursor.fetchone()
                    
                    # Usar costo proporcionado o el último costo encontrado
                    if 'precio_unitario' in prod and prod['precio_unitario']:
                        precio = Decimal(str(prod['precio_unitario']))
                    elif precio_result:
                        precio = Decimal(str(precio_result['Precio_Unitario']))
                    else:
                        precio = Decimal('0')
                    
                    subtotal = cantidad * precio
                    
                    # Insertar detalle del movimiento de inventario
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario
                        (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                         Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        id_producto, 
                        cantidad,
                        precio, 
                        precio_unitario,  # Guardamos también el precio de venta aquí
                        subtotal,
                        user_id
                    ))
                    
                    # DESCONTAR de inventario_bodega
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                except Exception as prod_error:
                    print(f"Error con producto {prod.get('id_producto', 'desconocido')}: {prod_error}")
                    continue
            
            flash(f"✅ Salida registrada exitosamente! ID Movimiento: {id_movimiento}", 'success')
            
            # Redirigir según tipo
            if id_tipo_movimiento == TIPO_VENTA and id_factura_venta:
                return redirect(url_for('bodega.bodega_detalle_factura', id_factura=id_factura_venta))
            else:
                return redirect(url_for('bodega.bodega_detalle_movimiento', id_movimiento=id_movimiento))
            
    except Exception as e:
        flash(f"❌ Error al procesar salida: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_nueva_salida_form'))

# API para obtener productos con stock por bodega (para salidas)
@bodega_bp.route('/api/productos/stock-bodega')
@admin_or_bodega_required
def api_productos_stock_bodega():
    """API para obtener productos con stock disponible en una bodega específica"""
    try:
        bodega_id = request.args.get('bodega')
        
        if not bodega_id:
            return jsonify({'error': 'Se requiere ID de bodega'}), 400
        
        with get_db_cursor(True) as cursor:
            # Obtener productos activos con stock en la bodega específica
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    p.Unidad_Medida, 
                    um.Descripcion as Unidad_Descripcion,
                    p.Precio_Mercado as Precio_Venta, 
                    p.Stock_Minimo,
                    cp.Descripcion as Categoria_Descripcion,
                    COALESCE(ib.Existencias, 0) as Stock_Bodega,
                    COALESCE(SUM(ib_total.Existencias), 0) as Existencias_Totales
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                LEFT JOIN inventario_bodega ib_total ON p.ID_Producto = ib_total.ID_Producto
                WHERE p.Estado = 'activo'
                    AND COALESCE(ib.Existencias, 0) > 0
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, 
                         p.Unidad_Medida, Precio_Venta, p.Stock_Minimo,
                         um.Descripcion, cp.Descripcion, ib.Existencias
                ORDER BY p.Descripcion
                LIMIT 100
            """, (bodega_id,))
            
            productos = cursor.fetchall()
            
            # Convertir a lista de diccionarios y formatear números
            productos_list = []
            for producto in productos:
                producto_dict = dict(producto)
                producto_dict['Precio_Venta'] = float(producto_dict['Precio_Venta'] or 0)
                producto_dict['Stock_Bodega'] = float(producto_dict['Stock_Bodega'] or 0)
                producto_dict['Existencias_Totales'] = float(producto_dict['Existencias_Totales'] or 0)
                producto_dict['Stock_Minimo'] = float(producto_dict['Stock_Minimo'] or 0)
                productos_list.append(producto_dict)
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"Error en API productos stock bodega: {e}")
        return jsonify({'error': str(e)}), 500

# 6. FORMULARIO TRANSFERENCIA
@bodega_bp.route('/bodega/movimientos/transferencia/nueva')
@bodega_required
def bodega_nueva_transferencia_form():
    """Mostrar formulario para transferencia entre bodegas"""
    try:
        with get_db_cursor(True) as cursor:
            # Obtener bodegas de la empresa del usuario
            id_empresa = session.get('id_empresa', 1)
            cursor.execute("""
                SELECT ID_Bodega, Nombre, Ubicacion 
                FROM bodegas 
                WHERE Estado = 'activa' AND ID_Empresa = %s
                ORDER BY Nombre
            """, (id_empresa,))
            bodegas = cursor.fetchall()
            
            if not bodegas or len(bodegas) < 2:
                flash("Debe haber al menos 2 bodegas activas para hacer transferencias", 'error')
                return redirect(url_for('bodega.bodega_historial_movimientos'))
            
            # Obtener fecha actual
            from datetime import datetime
            fecha_actual = datetime.now().strftime('%Y-%m-%d')
            
            return render_template('bodega/movimientos/nueva_transferencia.html',
                                 bodegas=bodegas,
                                 fecha_actual=fecha_actual)
    except Exception as e:
        flash(f"Error al cargar formulario: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_historial_movimientos'))

# 2. PROCESAR TRANSFERENCIA (CON TS Y TE SEPARADOS)
@bodega_bp.route('/bodega/movimientos/transferencia/procesar', methods=['POST'])
@bodega_required
@bitacora_decorator("PROCESAR-TRANSFERENCIA")
def bodega_procesar_transferencia():
    """Procesar transferencia entre bodegas - Crea TS (salida) y TE (entrada) separados"""
    try:
        # Obtener datos del formulario
        fecha = request.form.get('fecha')
        id_bodega_origen = request.form.get('id_bodega_origen')
        id_bodega_destino = request.form.get('id_bodega_destino')
        ubicacion_entrega = request.form.get('ubicacion_entrega', '').strip()
        observacion = request.form.get('observacion', '').strip()
        
        # Validaciones básicas
        if not all([fecha, id_bodega_origen, id_bodega_destino]):
            flash("Fecha y bodegas son requeridas", 'error')
            return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
        
        try:
            id_bodega_origen = int(id_bodega_origen)
            id_bodega_destino = int(id_bodega_destino)
        except ValueError:
            flash("bodegas inválidas", 'error')
            return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
        
        if id_bodega_origen == id_bodega_destino:
            flash("La bodega de origen y destino no pueden ser la misma", 'error')
            return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
        
        # Validar productos
        productos_json = request.form.get('productos')
        if not productos_json or productos_json == '[]':
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
        
        productos = json.loads(productos_json)
        
        # Validar que haya productos
        if not productos:
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
        
        # Obtener usuario y empresa
        id_usuario = current_user.id
        id_empresa = session.get('id_empresa', 1)
        
        # IDs FIJOS para TS y TE (según tus datos: TS=12, TE=13)
        ID_TS = 12  # Traslado Salida
        ID_TE = 13  # Traslado Entrada
        
        with get_db_cursor(commit=True) as cursor:
            # Validar que ambas bodegas existan y pertenezcan a la empresa
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE ID_Bodega IN (%s, %s) 
                AND Estado = 'activa' 
                AND ID_Empresa = %s
            """, (id_bodega_origen, id_bodega_destino, id_empresa))
            
            bodegas_validas = cursor.fetchall()
            if len(bodegas_validas) != 2:
                flash("Una o ambas bodegas no son válidas", 'error')
                return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
            
            # Obtener nombres para mensajes
            bodega_origen_nombre = next((b['Nombre'] for b in bodegas_validas if b['ID_Bodega'] == id_bodega_origen), 'Origen')
            bodega_destino_nombre = next((b['Nombre'] for b in bodegas_validas if b['ID_Bodega'] == id_bodega_destino), 'Destino')
            
            # VERIFICAR STOCK en bodega origen
            productos_insuficientes = []
            productos_validos = []
            
            for prod in productos:
                producto_id = int(prod['id_producto'])
                cantidad = Decimal(str(prod['cantidad']))
                
                if cantidad <= 0:
                    flash(f"La cantidad para producto ID {producto_id} debe ser mayor a 0", 'error')
                    return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
                
                # Verificar si producto existe, está activo y pertenece a la empresa
                cursor.execute("""
                    SELECT ID_Producto, Descripcion, Precio_Mercado as Precio_Venta, COD_Producto
                    FROM productos 
                    WHERE ID_Producto = %s 
                    AND Estado = 'activo'
                    AND ID_Empresa = %s
                """, (producto_id, id_empresa))
                
                producto_existe = cursor.fetchone()
                if not producto_existe:
                    productos_insuficientes.append({
                        'producto': f'ID {producto_id}',
                        'error': 'Producto no existe, está inactivo o no pertenece a su empresa'
                    })
                    continue
                
                # Verificar stock disponible en bodega origen
                cursor.execute("""
                    SELECT COALESCE(Existencias, 0) as Existencias 
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega_origen, producto_id))
                
                stock = cursor.fetchone()
                stock_disponible = Decimal(str(stock['Existencias'])) if stock else Decimal('0')
                
                # Verificar si hay suficiente stock
                if stock_disponible < cantidad:
                    productos_insuficientes.append({
                        'producto': f"{producto_existe['COD_Producto'] or ''} {producto_existe['Descripcion']}",
                        'solicitado': float(cantidad),
                        'disponible': float(stock_disponible),
                        'faltante': float(cantidad - stock_disponible)
                    })
                else:
                    productos_validos.append({
                        'id_producto': producto_id,
                        'cantidad': cantidad,
                        'descripcion': producto_existe['Descripcion'],
                        'codigo': producto_existe['COD_Producto'],
                        'precio_venta': producto_existe['Precio_Venta'],
                        'stock_origen': stock_disponible
                    })
            
            if productos_insuficientes:
                mensaje_error = f"<strong>Stock insuficiente en bodega '{bodega_origen_nombre}':</strong><br><br>"
                for item in productos_insuficientes:
                    if 'error' in item:
                        mensaje_error += f"❌ <strong>{item['producto']}</strong>: {item['error']}<br>"
                    else:
                        mensaje_error += f"❌ <strong>{item['producto']}</strong>:<br>"
                        mensaje_error += f"&nbsp;&nbsp;Solicitado: {item['solicitado']:.2f}<br>"
                        mensaje_error += f"&nbsp;&nbsp;Disponible: {item['disponible']:.2f}<br>"
                        mensaje_error += f"&nbsp;&nbsp;<strong>Faltan: {item['faltante']:.2f}</strong><br>"
                flash(mensaje_error, 'error')
                return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
            
            if not productos_validos:
                flash("No hay productos válidos para transferir", 'error')
                return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
            
            # ============================================
            # 1. CREAR MOVIMIENTO DE SALIDA (TS - ID 12)
            # ============================================
            obs_salida = f"Salida por traslado a {bodega_destino_nombre}"
            if observacion:
                obs_salida += f" - {observacion}"
                
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino,
                 UbicacionEntrega, Observacion, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Activa')
            """, (
                ID_TS, fecha, id_bodega_origen, id_bodega_destino,
                ubicacion_entrega, obs_salida, id_empresa, id_usuario
            ))
            
            id_movimiento_salida = cursor.lastrowid
            
            # ============================================
            # 2. CREAR MOVIMIENTO DE ENTRADA (TE - ID 13)
            # ============================================
            obs_entrada = f"Entrada por traslado desde {bodega_origen_nombre}"
            if observacion:
                obs_entrada += f" - {observacion}"
                
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino,
                 UbicacionEntrega, Observacion, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Activa')
            """, (
                ID_TE, fecha, id_bodega_destino, id_bodega_origen,
                ubicacion_entrega, obs_entrada, id_empresa, id_usuario
            ))
            
            id_movimiento_entrada = cursor.lastrowid
            
            # ============================================
            # 3. PROCESAR CADA PRODUCTO (PARA AMBOS MOVIMIENTOS)
            # ============================================
            total_productos = 0
            total_unidades = Decimal('0')
            
            for prod in productos_validos:
                producto_id = prod['id_producto']
                cantidad = prod['cantidad']
                
                # Obtener el último costo de entrada del producto
                cursor.execute("""
                    SELECT dmi.Costo_Unitario 
                    FROM detalle_movimientos_inventario dmi
                    JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                    JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE dmi.ID_Producto = %s 
                    AND (cm.Letra = 'E' OR cm.Descripcion LIKE '%entrada%' OR cm.Descripcion LIKE '%compra%')
                    AND mi.Estado = 'Activa'
                    ORDER BY mi.Fecha DESC, dmi.ID_Detalle_Movimiento DESC
                    LIMIT 1
                """, (producto_id,))
                
                costo_result = cursor.fetchone()
                
                # Usar el costo si existe, si no usar 0
                costo_unitario = Decimal(str(costo_result['Costo_Unitario'])) if costo_result and costo_result['Costo_Unitario'] is not None else Decimal('0')
                subtotal = cantidad * costo_unitario
                
                # A. INSERTAR EN SALIDA (TS)
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario
                    (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                     Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_movimiento_salida, producto_id, cantidad,
                    costo_unitario, prod['precio_venta'], subtotal, id_usuario
                ))
                
                # B. INSERTAR EN ENTRADA (TE)
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario
                    (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                     Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_movimiento_entrada, producto_id, cantidad,
                    costo_unitario, prod['precio_venta'], subtotal, id_usuario
                ))
                
                # ============================================
                # 4. ACTUALIZAR INVENTARIOS
                # ============================================
                
                # A. DESCONTAR de bodega origen
                cursor.execute("""
                    UPDATE inventario_bodega 
                    SET Existencias = Existencias - %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (cantidad, id_bodega_origen, producto_id))
                
                if cursor.rowcount == 0:
                    flash(f"Error: Producto {prod['codigo']} no encontrado en inventario de bodega origen", 'error')
                    return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
                
                # B. AGREGAR a bodega destino - VERSIÓN CORREGIDA
                cursor.execute("""
                    INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    Existencias = Existencias + %s
                """, (id_bodega_destino, producto_id, cantidad, cantidad))
                
                total_productos += 1
                total_unidades += cantidad
            
            # ============================================
            # 5. MENSAJE DE CONFIRMACIÓN MEJORADO
            # ============================================
            flash(
                f"✅ <strong>Transferencia completada exitosamente!</strong><br><br>"
                f"📤 <strong>Salida #{id_movimiento_salida}</strong> (Traslado Salida)<br>"
                f"&nbsp;&nbsp;Desde: {bodega_origen_nombre}<br>"
                f"📥 <strong>Entrada #{id_movimiento_entrada}</strong> (Traslado Entrada)<br>"
                f"&nbsp;&nbsp;Hacia: {bodega_destino_nombre}<br>"
                f"📦 Productos transferidos: {total_productos}<br>"
                f"📊 Total unidades: {total_unidades:.2f}<br><br>"
                f"<small>Se registraron 2 movimientos separados para mejor trazabilidad</small>",
                'success'
            )
            
            # Redirigir al detalle de la SALIDA
            return redirect(url_for('bodega.bodega_detalle_movimiento', id_movimiento=id_movimiento_salida))
            
    except Exception as e:
        import traceback
        print(f"Error en procesar transferencia: {str(e)}")
        print(traceback.format_exc())
        flash(f"❌ Error al procesar transferencia: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_nueva_transferencia_form'))
    
# Función auxiliar para verificar transferencias (opcional)
@bodega_bp.route('/bodega/verificar-transferencia/<int:id_movimiento>')
@admin_or_bodega_required
def verificar_transferencia(id_movimiento):
    """Verificar consistencia de una transferencia"""
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.Fecha,
                    bo.ID_Bodega as Origen_ID,
                    bo.Nombre as Origen_Nombre,
                    bd.ID_Bodega as Destino_ID,
                    bd.Nombre as Destino_Nombre,
                    dmi.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    dmi.Cantidad,
                    (SELECT ib.Existencias FROM inventario_bodega ib 
                     WHERE ib.ID_Bodega = bo.ID_Bodega AND ib.ID_Producto = dmi.ID_Producto) as Existencia_Origen,
                    (SELECT ib.Existencias FROM inventario_bodega ib 
                     WHERE ib.ID_Bodega = bd.ID_Bodega AND ib.ID_Producto = dmi.ID_Producto) as Existencia_Destino
                FROM movimientos_inventario mi
                JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            
            if not detalles:
                return jsonify({'error': 'Transferencia no encontrada'}), 404
            
            # Verificar consistencia
            consistente = True
            mensajes = []
            
            for detalle in detalles:
                cantidad = Decimal(str(detalle['Cantidad']))
                origen_actual = Decimal(str(detalle['Existencia_Origen'] or 0))
                destino_actual = Decimal(str(detalle['Existencia_Destino'] or 0))
                
                # La lógica debería ser: destino_actual debería incluir la cantidad transferida
                if destino_actual < cantidad:
                    consistente = False
                    mensajes.append(f"❌ Producto {detalle['COD_Producto']}: "
                                  f"Destino tiene {destino_actual:.2f} pero debería tener al menos {cantidad:.2f}")
                else:
                    mensajes.append(f"✅ Producto {detalle['COD_Producto']}: "
                                  f"Correcto (Origen: {origen_actual:.2f}, Destino: {destino_actual:.2f})")
            
            return jsonify({
                'transferencia_id': id_movimiento,
                'consistente': consistente,
                'detalles': detalles,
                'mensajes': mensajes
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bodega_bp.route('/api/inventario/productos-bodega/<int:id_bodega>')
@admin_or_bodega_required
def api_productos_bodega_con_stock(id_bodega):
    """Obtener productos con stock en una bodega específica"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener productos activos
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.Descripcion, 
                    p.COD_Producto,
                    p.Precio_Mercado as Precio_Venta,
                    um.Descripcion as Unidad_Descripcion,
                    cp.Descripcion as Categoria_Descripcion
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                WHERE p.Estado = 'activo' AND p.ID_Empresa = %s
                ORDER BY p.Descripcion
            """, (id_empresa,))
            
            todos_productos = cursor.fetchall()
            productos_con_stock = []
            
            for producto in todos_productos:
                # Obtener stock en esta bodega específica
                cursor.execute("""
                    SELECT COALESCE(Existencias, 0) as Existencias
                    FROM inventario_bodega
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega, producto['ID_Producto']))
                
                stock_result = cursor.fetchone()
                stock = stock_result['Existencias'] if stock_result else 0
                
                if stock > 0:
                    # Obtener existencias totales usando TU función
                    existencias_totales = obtener_existencias_producto(producto['ID_Producto'])
                    
                    producto['Existencias'] = float(stock)
                    producto['Stock_Bodega'] = float(stock)
                    producto['Existencias_Totales'] = float(existencias_totales)
                    productos_con_stock.append(producto)
            
            return jsonify({
                'success': True,
                'productos': productos_con_stock,
                'total': len(productos_con_stock)
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 8. DETALLE DE MOVIMIENTO
@bodega_bp.route('/bodega/movimientos/detalle/<int:id_movimiento>')
@admin_or_bodega_required
def bodega_detalle_movimiento(id_movimiento):
    """Ver detalle completo de un movimiento"""
    try:
        with get_db_cursor(True) as cursor:
            # Movimiento principal
            cursor.execute("""
                SELECT mi.*, 
                       cm.Descripcion as Tipo_Movimiento_Descripcion,
                       cm.Letra,
                       bo.Nombre as Bodega_Origen_Nombre,
                       bd.Nombre as Bodega_Destino_Nombre,
                       p.Nombre as Proveedor_Nombre,
                       cl.Nombre as Cliente_Nombre,
                       f.Fecha as Factura_Fecha,
                       u.NombreUsuario as Usuario_Creacion_Nombre,
                       emp.Nombre_Empresa
                FROM movimientos_inventario mi
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN facturacion f ON mi.ID_Factura_Venta = f.ID_Factura
                LEFT JOIN clientes cl ON f.IDCliente = cl.ID_Cliente
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa emp ON mi.ID_Empresa = emp.ID_Empresa
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento no encontrado", 'error')
                return redirect(url_for('bodega.bodega_historial_movimientos'))
            
            # Detalle de productos
            cursor.execute("""
                SELECT dmi.*, 
                       p.COD_Producto, p.Descripcion as Producto_Descripcion,
                       um.Descripcion as Unidad_Medida_Descripcion,
                       um.Abreviatura as Unidad_Abreviatura,
                       cp.Descripcion as Categoria_Descripcion,
                       u.NombreUsuario as Usuario_Creacion_Nombre,
                       ib.Existencias as Stock_Actual
                FROM detalle_movimientos_inventario dmi
                JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN usuarios u ON dmi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (movimiento['ID_Bodega'], id_movimiento))
            
            detalle = cursor.fetchall()
            
            # Calcular totales
            total_cantidad = sum(Decimal(str(d['Cantidad'])) for d in detalle)
            total_costo = sum(Decimal(str(d['Subtotal'] or 0)) for d in detalle)
            
            # Para ventas, calcular total precio
            total_precio = 0
            if movimiento['Letra'] == 'S':
                total_precio = sum(Decimal(str(d['Precio_Unitario'] or 0)) * 
                                 Decimal(str(d['Cantidad'])) for d in detalle)
            
            return render_template('bodega/movimientos/detalle_movimiento.html',
                                 movimiento=movimiento,
                                 detalle=detalle,
                                 total_cantidad=total_cantidad,
                                 total_costo=total_costo,
                                 total_precio=total_precio)
            
    except Exception as e:
        flash(f"Error al cargar detalle: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_historial_movimientos'))

# 9. REPORTES PRINCIPAL
@bodega_bp.route('/bodega/movimientos/reportes')
@admin_or_bodega_required
def bodega_reportes_movimientos():
    """Página principal de reportes"""
    try:
        with get_db_cursor(True) as cursor:
            # Tipos de movimiento para filtro
            cursor.execute("SELECT * FROM catalogo_movimientos ORDER BY Descripcion")
            tipos_movimiento = cursor.fetchall()
            
            # bodegas para filtro
            cursor.execute("SELECT * FROM bodegas WHERE Estado = 1 ORDER BY Nombre")
            bodegas = cursor.fetchall()
            
            # Estadísticas del mes
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_movimientos,
                    SUM(CASE WHEN cm.Letra = 'E' THEN 1 ELSE 0 END) as entradas,
                    SUM(CASE WHEN cm.Letra = 'S' THEN 1 ELSE 0 END) as salidas,
                    SUM(CASE WHEN cm.ID_TipoMovimiento = 6 THEN 1 ELSE 0 END) as transferencias,
                    (SELECT SUM(dmi.Subtotal) 
                     FROM detalle_movimientos_inventario dmi
                     JOIN movimientos_inventario mi2 ON dmi.ID_Movimiento = mi2.ID_Movimiento
                     JOIN catalogo_movimientos cm2 ON mi2.ID_TipoMovimiento = cm2.ID_TipoMovimiento
                     WHERE mi2.Estado = 1 AND cm2.Letra = 'E'
                     AND MONTH(mi2.Fecha) = MONTH(CURRENT_DATE())
                     AND YEAR(mi2.Fecha) = YEAR(CURRENT_DATE())) as total_compras,
                    (SELECT SUM(dmi.Precio_Unitario * dmi.Cantidad) 
                     FROM detalle_movimientos_inventario dmi
                     JOIN movimientos_inventario mi2 ON dmi.ID_Movimiento = mi2.ID_Movimiento
                     JOIN catalogo_movimientos cm2 ON mi2.ID_TipoMovimiento = cm2.ID_TipoMovimiento
                     WHERE mi2.Estado = 1 AND cm2.Letra = 'S'
                     AND MONTH(mi2.Fecha) = MONTH(CURRENT_DATE())
                     AND YEAR(mi2.Fecha) = YEAR(CURRENT_DATE())) as total_ventas
                FROM movimientos_inventario mi
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.Estado = 1 
                AND MONTH(mi.Fecha) = MONTH(CURRENT_DATE())
                AND YEAR(mi.Fecha) = YEAR(CURRENT_DATE())
            """)
            estadisticas = cursor.fetchone()
            
            # Últimos movimientos
            cursor.execute("""
                SELECT mi.ID_Movimiento, mi.Fecha, cm.Descripcion as Tipo,
                       cm.Letra, bo.Nombre as Bodega_Origen, bd.Nombre as Bodega_Destino,
                       u.NombreUsuario as Usuario,
                       (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Productos,
                       (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Costo
                FROM movimientos_inventario mi
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE mi.Estado = 1
                ORDER BY mi.ID_Movimiento DESC
                LIMIT 10
            """)
            ultimos_movimientos = cursor.fetchall()
            
            # Productos con stock bajo - CORREGIDO
            cursor.execute("""
                SELECT p.Descripcion, p.COD_Producto, 
                       COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales,
                       p.Stock_Minimo,
                       um.Descripcion as Unidad_Medida,
                       (SELECT COUNT(*) FROM inventario_bodega 
                        WHERE ID_Producto = p.ID_Producto 
                        AND Existencias > 0) as bodegas_Con_Stock
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE p.Estado = 1
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto, 
                         p.Stock_Minimo, um.Descripcion
                HAVING COALESCE(SUM(ib.Existencias), 0) <= p.Stock_Minimo
                ORDER BY (COALESCE(SUM(ib.Existencias), 0) / NULLIF(p.Stock_Minimo, 0)) ASC
                LIMIT 10
            """)
            productos_stock_bajo = cursor.fetchall()
            
            return render_template('bodega/movimientos/reportes.html',
                                 tipos_movimiento=tipos_movimiento,
                                 bodegas=bodegas,
                                 estadisticas=estadisticas,
                                 ultimos_movimientos=ultimos_movimientos,
                                 productos_stock_bajo=productos_stock_bajo)
            
    except Exception as e:
        flash(f"Error al cargar reportes: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_dashboard'))

# 10. REPORTE FILTRADO
@bodega_bp.route('/bodega/movimientos/reporte/filtrar', methods=['POST'])
@admin_or_bodega_required
def bodega_reporte_filtrado():
    """Generar reporte con filtros"""
    try:
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        id_tipo_movimiento = request.form.get('id_tipo_movimiento')
        id_bodega = request.form.get('id_bodega')
        
        # Construir consulta
        query = """
            SELECT mi.ID_Movimiento, mi.Fecha, cm.Descripcion as Tipo_Movimiento,
                   cm.Letra, bo.Nombre as Bodega_Origen, bd.Nombre as Bodega_Destino,
                   p.Nombre as Proveedor, u.NombreUsuario as Usuario,
                   mi.Observacion, mi.Tipo_Compra, mi.N_Factura_Externa,
                   (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = mi.ID_Movimiento) as Cantidad_Productos,
                   (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Costo,
                   (SELECT SUM(Precio_Unitario * Cantidad) FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Precio
            FROM movimientos_inventario mi
            LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
            LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
            LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
            LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
            LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
            WHERE mi.Estado = 1
        """
        
        params = []
        
        if fecha_inicio:
            query += " AND mi.Fecha >= %s"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND mi.Fecha <= %s"
            params.append(fecha_fin)
        if id_tipo_movimiento and id_tipo_movimiento != 'todos':
            query += " AND mi.ID_TipoMovimiento = %s"
            params.append(id_tipo_movimiento)
        if id_bodega and id_bodega != 'todas':
            query += " AND (mi.ID_Bodega = %s OR mi.ID_Bodega_Destino = %s)"
            params.extend([id_bodega, id_bodega])
        
        query += " ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC"
        
        with get_db_cursor(True) as cursor:
            cursor.execute(query, tuple(params))
            movimientos = cursor.fetchall()
            
            # Calcular totales
            total_movimientos = len(movimientos)
            total_costo = sum(Decimal(str(m['Total_Costo'] or 0)) for m in movimientos)
            total_precio = sum(Decimal(str(m['Total_Precio'] or 0)) for m in movimientos)
            
            return render_template('bodega/movimientos/reporte_filtrado.html',
                                 movimientos=movimientos,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 total_movimientos=total_movimientos,
                                 total_costo=total_costo,
                                 total_precio=total_precio)
            
    except Exception as e:
        flash(f"Error al generar reporte: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_reportes_movimientos'))

# 11. ANULAR MOVIMIENTO
@bodega_bp.route('/bodega/movimientos/anular/<int:id_movimiento>', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("ANULAR-MOVIMIENTO")
def bodega_anular_movimiento(id_movimiento):
    """Anular un movimiento y revertir inventario"""
    try:
        motivo = request.form.get('motivo', 'Sin motivo especificado')
        
        with get_db_cursor() as cursor:
            # Obtener información del movimiento
            cursor.execute("""
                SELECT mi.*, cm.Descripcion, cm.Letra
                FROM movimientos_inventario mi
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.ID_Movimiento = %s AND mi.Estado = 1
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento no encontrado o ya anulado", 'warning')
                return redirect(url_for('bodega.bodega_historial_movimientos'))
            
            # Obtener detalle del movimiento
            cursor.execute("""
                SELECT * FROM detalle_movimientos_inventario
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            
            # Revertir inventario según tipo
            letra = movimiento['Letra']
            
            for detalle in detalles:
                cantidad = Decimal(str(detalle['Cantidad']))
                id_producto = detalle['ID_Producto']
                id_bodega = movimiento['ID_Bodega']
                
                if letra == 'E':  # Entrada → Descontar
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                    cursor.execute("""
                        UPDATE productos 
                        SET Existencias = Existencias - %s
                        WHERE ID_Producto = %s
                    """, (cantidad, id_producto))
                    
                elif letra == 'S':  # Salida → Agregar
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias + %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                    cursor.execute("""
                        UPDATE productos 
                        SET Existencias = Existencias + %s
                        WHERE ID_Producto = %s
                    """, (cantidad, id_producto))
                    
                elif movimiento['ID_TipoMovimiento'] == TIPO_TRASLADO:  # Transferencia
                    id_bodega_destino = movimiento['ID_Bodega_Destino']
                    
                    # Revertir origen (agregar)
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias + %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                    # Revertir destino (descontar)
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega_destino, id_producto))
            
            # Marcar movimiento como anulado
            cursor.execute("""
                UPDATE movimientos_inventario 
                SET Estado = 0, 
                    Fecha_Modificacion = NOW(),
                    ID_Usuario_Modificacion = %s,
                    Observacion = CONCAT(COALESCE(Observacion, ''), 
                    ' | ANULADO: ', %s)
                WHERE ID_Movimiento = %s
            """, (session.get('user_id'), motivo, id_movimiento))
            
            flash(f"✅ Movimiento #{id_movimiento} anulado exitosamente", 'success')
            
    except Exception as e:
        flash(f"❌ Error al anular movimiento: {str(e)}", 'error')
    
    return redirect(url_for('bodega.bodega_historial_movimientos'))

# 12. API PARA OBTENER STOCK
@bodega_bp.route('/api/inventario/stock/<int:id_producto>/<int:id_bodega>')
@admin_or_bodega_required
def api_obtener_stock(id_producto, id_bodega):
    """Obtener stock de un producto en una bodega específica"""
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT p.ID_Producto, p.Descripcion, p.COD_Producto,
                       ib.Existencias, p.Existencias as Total_General,
                       p.Precio_Mercado as Precio_Venta, p.Stock_Minimo,
                       um.Descripcion as Unidad_Medida
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE p.ID_Producto = %s AND p.Estado = 1
            """, (id_bodega, id_producto))
            
            producto = cursor.fetchone()
            
            if not producto:
                return jsonify({'error': 'Producto no encontrado'}), 404
            
            return jsonify({
                'success': True,
                'producto': producto
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# 13. API PARA BUSCAR PRODUCTOS
@bodega_bp.route('/api/productos/buscar')
@admin_or_bodega_required
def api_buscar_productos():
    """Buscar productos por código o descripción"""
    try:
        termino = request.args.get('q', '')
        id_bodega = request.args.get('bodega', '')
        
        if not termino:
            return jsonify([])
        
        with get_db_cursor(True) as cursor:
            query = """
                SELECT p.ID_Producto, p.COD_Producto, p.Descripcion, 
                       p.Unidad_Medida, um.Descripcion as Unidad_Descripcion,
                       p.Precio_Mercado as Precio_Venta, p.Existencias as Stock_General,
                       ib.Existencias as Stock_Bodega,
                       p.Stock_Minimo
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
            """
            
            params = []
            
            if id_bodega:
                query += " AND ib.ID_Bodega = %s"
                params.append(id_bodega)
            
            query += """
                WHERE (p.COD_Producto LIKE %s OR p.Descripcion LIKE %s) 
                AND p.Estado = 1
                ORDER BY p.Descripcion
                LIMIT 20
            """
            
            params.extend([f"%{termino}%", f"%{termino}%"])
            
            cursor.execute(query, tuple(params))
            productos = cursor.fetchall()
            
            return jsonify(productos)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# 14. IMPRIMIR MOVIMIENTO
@bodega_bp.route('/bodega/movimientos/imprimir/<int:id_movimiento>')
@admin_or_bodega_required
def bodega_imprimir_movimiento(id_movimiento):
    """Generar PDF para impresión del movimiento"""
    try:
        with get_db_cursor(True) as cursor:
            # Similar a detalle_movimiento pero optimizado para impresión
            cursor.execute("""
                SELECT mi.*, cm.Descripcion as Tipo_Movimiento,
                       bo.Nombre as Bodega_Origen, bd.Nombre as Bodega_Destino,
                       p.Nombre as Proveedor, u.NombreUsuario as Usuario,
                       emp.Nombre_Empresa, emp.RUC, emp.Direccion, emp.Telefono
                FROM movimientos_inventario mi
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa emp ON mi.ID_Empresa = emp.ID_Empresa
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento no encontrado", 'error')
                return redirect(url_for('bodega.bodega_historial_movimientos'))
            
            # Detalle
            cursor.execute("""
                SELECT dmi.*, p.Descripcion as Producto, p.COD_Producto,
                       um.Abreviatura as Unidad
                FROM detalle_movimientos_inventario dmi
                JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (id_movimiento,))
            
            detalle = cursor.fetchall()
            
            # Aquí normalmente generarías un PDF
            # Por ahora, redirigimos a una página de impresión
            return render_template('bodega/movimientos/imprimir_movimiento.html',
                                 movimiento=movimiento,
                                 detalle=detalle)
            
    except Exception as e:
        flash(f"Error al generar impresión: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_detalle_movimiento', id_movimiento=id_movimiento))

## MODULO BODEGA
# REPORTES AVANZADOS
@bodega_bp.route('/bodega/movimientos/reportes/avanzados', methods=['GET', 'POST'])
@admin_or_bodega_required
def bodega_reportes_avanzados():
    """Mostrar reportes avanzados de movimientos"""
    try:
        fecha_inicio = request.form.get('fecha_inicio') or datetime.now().strftime('%Y-%m-%d')
        fecha_fin = request.form.get('fecha_fin') or datetime.now().strftime('%Y-%m-%d')
        categoria_id = request.form.get('categoria_id')
        tipo_reporte = request.form.get('tipo_reporte', 'resumen_diario')
        
        with get_db_cursor(True) as cursor:
            # Consulta 1: Control de Productos (Existencia por Bodega)
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    um.Descripcion AS Unidad_Medida,
                    b.Nombre AS Bodega,
                    ib.Existencias AS Stock_Actual,
                    p.Stock_Minimo,
                    p.Precio_Mercado AS Precio_Venta,
                    CASE 
                        WHEN ib.Existencias <= p.Stock_Minimo THEN 'BAJO STOCK'
                        WHEN ib.Existencias = 0 THEN 'AGOTADO'
                        ELSE 'OK'
                    END AS Estado_Stock
                FROM inventario_bodega ib
                INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
                INNER JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE p.Estado = 'activo' AND b.Estado = 'activa'
                ORDER BY b.Nombre, p.Descripcion
            """)
            inventario = cursor.fetchall()
            
            # Consulta 2: Producto Más Vendido
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    SUM(dmi.Cantidad) AS Total_Vendido,
                    SUM(dmi.Subtotal) AS Total_Ingresos,
                    COUNT(DISTINCT mi.ID_Movimiento) AS Total_Ventas
                FROM detalle_movimientos_inventario dmi
                INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                WHERE cm.Letra = 'S'
                    AND mi.Estado = 'Activa'
                    AND mi.Fecha BETWEEN %s AND %s
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, cp.Descripcion
                ORDER BY Total_Vendido DESC
                LIMIT 10
            """, (fecha_inicio, fecha_fin))
            mas_vendidos = cursor.fetchall()
            
            # Consulta 3: Productos Vendidos por Categoría (con filtro)
            query_categorias = """
                SELECT 
                    cp.ID_Categoria,
                    cp.Descripcion AS Categoria,
                    mi.Fecha AS Fecha_Venta,
                    mi.Tipo_Compra,
                    COUNT(DISTINCT p.ID_Producto) AS Cantidad_Productos_Diferentes,
                    SUM(dmi.Cantidad) AS Total_Unidades_Vendidas,
                    SUM(dmi.Subtotal) AS Total_Ventas
                FROM detalle_movimientos_inventario dmi
                INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                INNER JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE cm.Letra = 'S'
                    AND mi.Estado = 'Activa'
                    AND mi.Fecha BETWEEN %s AND %s
            """
            params_categorias = [fecha_inicio, fecha_fin]
            
            if categoria_id and categoria_id != 'todas':
                query_categorias += " AND cp.ID_Categoria = %s"
                params_categorias.append(categoria_id)
            
            query_categorias += """
                GROUP BY cp.ID_Categoria, cp.Descripcion, mi.Fecha, mi.Tipo_Compra
                ORDER BY mi.Fecha DESC, Total_Ventas DESC
            """
            
            cursor.execute(query_categorias, tuple(params_categorias))
            ventas_categorias = cursor.fetchall()
            
            # Consulta 4: Productos con Bajo Stock
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    b.Nombre AS Bodega,
                    ib.Existencias AS Stock_Actual,
                    p.Stock_Minimo AS Stock_Minimo,
                    ROUND((ib.Existencias / p.Stock_Minimo) * 100, 2) AS Porcentaje_Stock,
                    CASE 
                        WHEN ib.Existencias = 0 THEN 'AGOTADO'
                        WHEN ib.Existencias < p.Stock_Minimo THEN 'BAJO STOCK'
                    END AS Alerta
                FROM inventario_bodega ib
                INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
                INNER JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                WHERE p.Estado = 'activo' 
                    AND b.Estado = 'activa'
                    AND ib.Existencias <= p.Stock_Minimo
                ORDER BY ib.Existencias ASC
            """)
            bajo_stock = cursor.fetchall()
            
            # Consulta 5: Productos No Vendidos en más de 4 Días - VERSIÓN CORREGIDA
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    MAX(mi.Fecha) AS Ultima_Venta,
                    DATEDIFF(CURDATE(), MAX(mi.Fecha)) AS Dias_Sin_Venta,
                    COALESCE(ib.Existencias, 0) AS Stock_Actual
                FROM productos p
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                LEFT JOIN (
                    SELECT dmi.ID_Producto, mi.Fecha
                    FROM detalle_movimientos_inventario dmi
                    INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                    INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE mi.Estado = 'Activa'
                        AND cm.Letra = 'S'
                ) mi ON p.ID_Producto = mi.ID_Producto
                WHERE p.Estado = 'activo'
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, cp.Descripcion, ib.Existencias
                HAVING Ultima_Venta IS NULL 
                    OR DATEDIFF(CURDATE(), Ultima_Venta) > 4
                ORDER BY Dias_Sin_Venta DESC
            """)
            sin_ventas = cursor.fetchall()
            
            # Consulta 6: Total Productos Vendidos a Contado y Crédito
            cursor.execute("""
                SELECT 
                    mi.Fecha,
                    p.COD_Producto,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    mi.Tipo_Compra,
                    SUM(dmi.Cantidad) AS Cantidad_Vendida,
                    SUM(dmi.Subtotal) AS Total_Venta,
                    GROUP_CONCAT(
                        CONCAT('Venta #', mi.ID_Movimiento, ': ', ROUND(dmi.Cantidad, 2), ' unidades')
                        SEPARATOR '; '
                    ) AS Detalle_Ventas
                FROM detalle_movimientos_inventario dmi
                INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                WHERE cm.Letra = 'S'
                    AND mi.Estado = 'Activa'
                    AND mi.Fecha BETWEEN %s AND %s
                GROUP BY mi.Fecha, p.ID_Producto, p.COD_Producto, p.Descripcion, cp.Descripcion, mi.Tipo_Compra
                ORDER BY mi.Fecha DESC, Producto, mi.Tipo_Compra
            """, (fecha_inicio, fecha_fin))
            ventas_contado_credito = cursor.fetchall()
            
            # Obtener categorías para el dropdown
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
            categorias = cursor.fetchall()
            
            # Resumen estadístico CORREGIDO (sin FILTER)
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT p.ID_Producto) as total_productos,
                    SUM(CASE WHEN ib.Existencias <= p.Stock_Minimo THEN 1 ELSE 0 END) as productos_bajo_stock,
                    SUM(CASE WHEN ib.Existencias = 0 THEN 1 ELSE 0 END) as productos_agotados
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE p.Estado = 'activo'
            """)
            resumen = cursor.fetchone()
            
        return render_template('bodega/reportes_avanzados.html',
                             inventario=inventario,
                             mas_vendidos=mas_vendidos,
                             ventas_categorias=ventas_categorias,
                             bajo_stock=bajo_stock,
                             sin_ventas=sin_ventas,
                             ventas_contado_credito=ventas_contado_credito,
                             categorias=categorias,
                             resumen=resumen,
                             fecha_inicio=fecha_inicio,
                             fecha_fin=fecha_fin,
                             categoria_seleccionada=categoria_id,
                             tipo_reporte=tipo_reporte)
            
    except Exception as e:
        flash(f"Error al cargar reportes: {str(e)}", 'error')
        return redirect(url_for('bodega.bodega_historial_movimientos'))


@bodega_bp.route('/movimientos')
@admin_or_bodega_required
def bodega_listar_movimientos():
    """Historial de movimientos de inventario"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    m.ID_Movimiento,
                    p.Descripcion AS Producto,
                    m.Tipo_Movimiento,
                    m.Cantidad,
                    m.Fecha,
                    u.NombreUsuario,
                    m.Referencia
                FROM movimientos_inventario m
                JOIN productos p ON m.ID_Producto = p.ID_Producto
                JOIN usuarios u ON m.ID_Usuario = u.ID_Usuario
                ORDER BY m.Fecha DESC
                LIMIT 100
            """)
            movimientos = cursor.fetchall()
        
        return render_template('bodega/movimientos.html', movimientos=movimientos)
    except Exception as e:
        flash(f"Error al cargar movimientos: {e}", "danger")
        return redirect(url_for('bodega.bodega_dashboard'))
