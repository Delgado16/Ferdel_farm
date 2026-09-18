import re

with open(r'c:\Users\ferza\OneDrive\Documents\ferdel\routes\admin\productos.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_route = """
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
            cursor.execute("SELECT Descripcion, Precio_Mercado FROM productos WHERE ID_Producto = %s AND Estado = 'activo'", (id_producto,))
            prod_info = cursor.fetchone()
            if not prod_info:
                flash("Producto no encontrado o inactivo", "error")
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                
            cursor.execute("SELECT COALESCE(Existencias, 0) as Existencias FROM inventario_bodega WHERE ID_Bodega = %s AND ID_Producto = %s", (id_bodega_origen, id_producto))
            stock_info = cursor.fetchone()
            if isinstance(stock_info, dict):
                stock_disponible = Decimal(str(stock_info['Existencias'])) if stock_info else Decimal('0')
            else:
                stock_disponible = Decimal(str(stock_info[0])) if stock_info else Decimal('0')
            
            if stock_disponible < cantidad:
                flash(f"Stock insuficiente en la bodega de origen. Disponible: {stock_disponible}", "error")
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                
            cursor.execute("SELECT Nombre FROM bodegas WHERE ID_Bodega = %s", (id_bodega_origen,))
            origen_res = cursor.fetchone()
            bodega_origen_nombre = origen_res['Nombre'] if isinstance(origen_res, dict) else origen_res[0]

            cursor.execute("SELECT Nombre FROM bodegas WHERE ID_Bodega = %s", (id_bodega_destino,))
            destino_res = cursor.fetchone()
            bodega_destino_nombre = destino_res['Nombre'] if isinstance(destino_res, dict) else destino_res[0]
            
            cursor.execute(\"\"\"
                SELECT dmi.Costo_Unitario 
                FROM detalle_movimientos_inventario dmi
                JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE dmi.ID_Producto = %s 
                AND (cm.Letra = 'E' OR cm.Descripcion LIKE '%%entrada%%' OR cm.Descripcion LIKE '%%compra%%')
                AND mi.Estado = 'Activa'
                ORDER BY mi.Fecha DESC, dmi.ID_Detalle_Movimiento DESC
                LIMIT 1
            \"\"\", (id_producto,))
            costo_result = cursor.fetchone()
            if isinstance(costo_result, dict):
                costo_unitario = Decimal(str(costo_result['Costo_Unitario'])) if costo_result and costo_result['Costo_Unitario'] is not None else Decimal('0')
            elif costo_result:
                costo_unitario = Decimal(str(costo_result[0])) if costo_result[0] is not None else Decimal('0')
            else:
                costo_unitario = Decimal('0')
            
            if isinstance(prod_info, dict):
                precio_venta = Decimal(str(prod_info['Precio_Mercado'])) if prod_info['Precio_Mercado'] else Decimal('0')
            else:
                precio_venta = Decimal(str(prod_info[1])) if prod_info[1] else Decimal('0')

            subtotal = cantidad * costo_unitario
            
            obs_salida = f"Salida por traslado a {bodega_destino_nombre}"
            if observacion: obs_salida += f" - {observacion}"
            obs_entrada = f"Entrada por traslado desde {bodega_origen_nombre}"
            if observacion: obs_entrada += f" - {observacion}"
            
            cursor.execute(\"\"\"
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino, Observacion, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Activa')
            \"\"\", (ID_TS, fecha_actual, id_bodega_origen, id_bodega_destino, obs_salida, id_empresa, id_usuario))
            id_mov_salida = cursor.lastrowid
            
            cursor.execute(\"\"\"
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino, Observacion, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Activa')
            \"\"\", (ID_TE, fecha_actual, id_bodega_destino, id_bodega_origen, obs_entrada, id_empresa, id_usuario))
            id_mov_entrada = cursor.lastrowid
            
            cursor.execute(\"\"\"
                INSERT INTO detalle_movimientos_inventario
                (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            \"\"\", (id_mov_salida, id_producto, cantidad, costo_unitario, precio_venta, subtotal, id_usuario))
            
            cursor.execute(\"\"\"
                INSERT INTO detalle_movimientos_inventario
                (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            \"\"\", (id_mov_entrada, id_producto, cantidad, costo_unitario, precio_venta, subtotal, id_usuario))
            
            cursor.execute(\"\"\"
                UPDATE inventario_bodega 
                SET Existencias = Existencias - %s
                WHERE ID_Bodega = %s AND ID_Producto = %s
            \"\"\", (cantidad, id_bodega_origen, id_producto))
            
            cursor.execute(\"\"\"
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            \"\"\", (id_bodega_destino, id_producto, cantidad))
            
        flash(f"Se transfirieron {cantidad} unidades exitosamente", "success")
        
    except Exception as e:
        flash(f'Error al transferir producto: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
        
    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
"""

if "admin_transferir_producto_bodega" not in content:
    content = content + "\n" + new_route
    with open(r'c:\Users\ferza\OneDrive\Documents\ferdel\routes\admin\productos.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Route added")
else:
    print("Route already exists")
