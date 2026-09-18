import re

with open(r'c:\Users\ferza\OneDrive\Documents\ferdel\routes\admin\productos.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_route = """
@admin_bp.route('/admin/bodega/productos/asignar_bodega/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("ASIGNAR_BODEGA_PRODUCTO")
def admin_asignar_bodega_producto(id_producto):
    try:
        id_bodega = request.form.get('id_bodega')
        cantidad = request.form.get('cantidad', 0)
        
        if not id_bodega:
            flash("Debe seleccionar una bodega", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        try:
            id_bodega = int(id_bodega)
            cantidad = float(cantidad)
        except ValueError:
            flash("Valores inválidos", "error")
            return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
            
        with get_db_cursor(commit=True) as cursor:
            # Check product
            cursor.execute("SELECT ID_Producto FROM productos WHERE ID_Producto = %s AND Estado = 'activo'", (id_producto,))
            if not cursor.fetchone():
                flash("Producto no encontrado o inactivo", "error")
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                
            cursor.execute(\"\"\"
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            \"\"\", (id_bodega, id_producto, cantidad))
            
        flash(f"Bodega asignada exitosamente", "success")
        
    except Exception as e:
        flash(f'Error al asignar bodega: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
        
    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
"""

if "admin_asignar_bodega_producto" not in content:
    content = content + "\n" + new_route
    with open(r'c:\Users\ferza\OneDrive\Documents\ferdel\routes\admin\productos.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Route added")
else:
    print("Route already exists")
