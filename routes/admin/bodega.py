from flask import render_template, redirect, url_for, request, flash, jsonify
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator

@admin_bp.route('/admin/bodega', methods=['GET'])
@admin_required
@bitacora_decorator("BODEGA")
def admin_bodega():
    try:
        with get_db_cursor() as cursor:
            # Obtener bodegas con información de empresa
            cursor.execute("""
                SELECT b.*, e.Nombre_Empresa 
                FROM bodegas b
                INNER JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                ORDER BY b.ID_Bodega DESC
            """)
            bodegas = cursor.fetchall()
            
            # Obtener lista de empresas para el modal de creación
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/bodega.html', 
                                 bodegas=bodegas,
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodegas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/bodega/detalle-inventario-bodega/<int:id_bodega>', methods=['GET'])
@admin_required
@bitacora_decorator("INVENTARIO-BODEGA")
def admin_detalle_inventario_bodega(id_bodega):
    try:
        with get_db_cursor() as cursor:
            # Obtener información de la bodega con el nombre de la empresa
            cursor.execute("""
                SELECT 
                    b.ID_Bodega,
                    b.Nombre,
                    b.Ubicacion,
                    b.Estado,
                    b.ID_Empresa,
                    b.Fecha_Creacion,
                    e.Nombre_Empresa 
                FROM bodegas b
                INNER JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                WHERE b.ID_Bodega = %s AND b.Estado = 'activa'
            """, (id_bodega,))
            bodega = cursor.fetchone()
            
            if not bodega:
                flash("Bodega no encontrada", "danger")
                return redirect(url_for('admin.admin_bodega'))
            
            # Obtener SOLO los productos que existen en esta bodega (Existencias > 0)
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    p.Stock_Minimo,
                    p.Precio_Mercado,
                    ib.Existencias
                FROM inventario_bodega ib
                INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
                WHERE ib.ID_Bodega = %s 
                AND ib.Existencias > 0 
                AND p.Estado = 'activo'
                ORDER BY p.COD_Producto ASC
            """, (id_bodega,))
            
            inventario = cursor.fetchall()
            
            # Calcular estadísticas
            total_productos = len(inventario)
            total_unidades = sum(item['Existencias'] for item in inventario) if inventario else 0
            valor_total = sum(item['Existencias'] * (item['Precio_Mercado'] or 0) for item in inventario) if inventario else 0
            
            return render_template('admin/bodega/detalle_inventario.html',
                                 bodega=bodega,
                                 inventario=inventario,
                                 total_productos=total_productos,
                                 total_unidades=total_unidades,
                                 valor_total=valor_total)
                                 
    except Exception as e:
        flash(f"Error al cargar inventario: {str(e)}", "danger")
        return redirect(url_for('admin.admin_bodega'))

@admin_bp.route('/admin/bodega/crear', methods=['POST'])
@admin_required
@bitacora_decorator("BODEGA-CREAR")
def admin_bodega_crear():
    try:
        nombre = request.form.get('nombre', '').strip()
        ubicacion = request.form.get('ubicacion', '').strip()
        id_empresa = request.form.get('id_empresa')

        if not nombre:
            flash("El nombre de la bodega es requerido", "danger")
            return redirect(url_for('admin.admin_bodega'))
        
        if not id_empresa:
            flash("La empresa es requerida", "danger")
            return redirect(url_for('admin.admin_bodega'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO bodegas (Nombre, Ubicacion, ID_Empresa) 
                VALUES (%s, %s, %s)
            """, (nombre, ubicacion, id_empresa))

        flash("Bodega creada exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear bodega: {str(e)}", "danger")
    return redirect(url_for('admin.admin_bodega'))

@admin_bp.route('/admin/bodega/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("BODEGA_EDITAR")
def admin_editar_bodega(id):
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        ubicacion = request.form.get('ubicacion')
        id_empresa = request.form.get('id_empresa')
        estado = request.form.get('estado', 'activa')
        
        if not nombre:
            flash("El nombre de la bodega es obligatorio", "danger")
            return redirect(url_for('admin.admin_editar_bodega', id=id))
        
        if not id_empresa:
            flash("La empresa es obligatoria", "danger")
            return redirect(url_for('admin.admin_editar_bodega', id=id))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE bodegas SET Nombre = %s, Ubicacion = %s, Estado = %s, ID_Empresa = %s WHERE ID_Bodega = %s",
                    (nombre, ubicacion, estado, id_empresa, id)
                )
                flash("Bodega actualizada exitosamente", "success")
                return redirect(url_for('admin.admin.admin_bodega'))
        except Exception as e:
            flash(f"Error al actualizar bodega: {str(e)}", "danger")
            return redirect(url_for('admin.admin_editar_bodega', id=id))
    
    # GET - Cargar datos de la bodega y empresas
    try:
        with get_db_cursor() as cursor:
            # Obtener datos de la bodega
            cursor.execute("SELECT * FROM bodegas WHERE ID_Bodega = %s", (id,))
            bodega = cursor.fetchone()
            
            if not bodega:
                flash("Bodega no encontrada", "danger")
                return redirect(url_for('admin.admin_bodega'))
            
            # Obtener lista de empresas para el dropdown
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/editar_bodega.html', 
                                 bodega=bodega, 
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodega: {str(e)}", "danger")
        return redirect(url_for('admin.admin_bodega'))
