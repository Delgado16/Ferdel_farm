# -*- coding: utf-8 -*-
from collections import defaultdict
from decimal import Decimal
import logging
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import date, datetime, time, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required
from helpers.bitacora import bitacora_decorator, registrar_bitacora
from werkzeug.security import generate_password_hash, check_password_hash
from .. import admin_bp

@admin_bp.route('/admin/catalog/medidas/unidades-medidas', methods=['GET'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS")
def admin_unidades_medidas():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_Unidad, Descripcion, Abreviatura 
                FROM unidades_medida 
                ORDER BY Descripcion DESC
            """)
            unidades = cursor.fetchall()
            return render_template('admin/catalog/medidas/unidades_medidas.html', 
                                 unidades=unidades)
    except Exception as e:
        flash(f"Error al cargar unidades de medida: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/catalog/medidas/crear-unidad', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-CREAR")
def admin_crear_unidad_medida():

    if request.method == 'POST':
        descripcion = request.form.get('descripcion','').strip()
        abreviatura = request.form.get('abreviatura','').strip()

        if not descripcion or not abreviatura:
            flash("Descripción y abreviatura son obligatorias.", "danger")
            return redirect(url_for('admin.admin_unidades_medidas'))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO unidades_medida (Descripcion, Abreviatura)
                    VALUES (%s, %s)
                """, (descripcion, abreviatura))
                
                flash("Unidad de medida creada exitosamente.", "success")
                return redirect(url_for('admin.admin_unidades_medidas'))
            
        except Exception as e:
            flash(f"Error al crear unidad de medida: {e}", "danger")
            return redirect(url_for('admin.admin_unidades_medidas'))
    
    return render_template('admin/catalog/medidas/crear_unidad.html')


@admin_bp.route('/admin/catalog/medidas/editar-unidad/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-EDITAR")
def admin_editar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            
            if request.method == 'POST':

                descripcion = request.form.get('descripcion','').strip()
                abreviatura = request.form.get('abreviatura','').strip()

                if not descripcion or not abreviatura:
                    flash("Descripción y abreviatura son obligatorias.", "danger")
                    return redirect(url_for('admin.admin_unidades_medidas'))
                
                cursor.execute("""
                    UPDATE unidades_medida
                    SET Descripcion = %s, Abreviatura = %s
                    WHERE ID_Unidad = %s
                    """, (descripcion, abreviatura, id))
                
                flash("Unidad de medida actualizada exitosamente.", "success")
                return redirect(url_for('admin.admin_unidades_medidas'))
            
            else:

                #obtener datos actuales
                cursor.execute("""
                    SELECT ID_Unidad, Descripcion, Abreviatura
                    FROM unidades_medida
                    WHERE ID_Unidad = %s
                    """, (id,))
                
                unidad = cursor.fetchone()

                if not unidad:
                    flash("Unidad de medida no encontrada.", "danger")
                    return redirect(url_for('admin.admin_unidades_medidas'))
                
                return render_template('admin/catalog/medidas/editar_unidad_medida.html',
                                        unidad=unidad)
        
    except Exception as e:
        flash(f"Error al editar unidad de medida: {e}", "danger")
        return redirect(url_for('admin.admin_unidades_medidas'))


@admin_bp.route('/admin/catalog/medidas/unidades-medidas/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS-ELIMINAR")
def eliminar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la unidad existe
            cursor.execute("SELECT Descripcion FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            unidad = cursor.fetchone()
            
            if not unidad:
                flash("Unidad de medida no encontrada", "danger")
                return redirect(url_for('admin.admin_unidades_medidas'))
            
            cursor.execute("DELETE FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            
            flash(f"Unidad de medida '{unidad['Descripcion']}' eliminada exitosamente", "success")
            
    except Exception as e:
        flash(f"Error al eliminar unidad de medida: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_unidades_medidas'))


@admin_bp.route('/admin/catalog/categorias', methods=['GET'])
@admin_required
@bitacora_decorator("CATEGORIAS")
def admin_categorias():
    try:
        with get_db_cursor() as cursor: 
            cursor.execute("""
                SELECT ID_Categoria, Descripcion, Estado 
                FROM categorias_producto 
                ORDER BY ID_Categoria DESC
            """)
            categorias = cursor.fetchall()
            return render_template('admin/catalog/categorias/categorias.html', 
                                 categorias=categorias)
    except Exception as e:
        logger.error(f"Error al cargar categorías: {str(e)}", exc_info=True)
        flash("Error al cargar las categorías", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/catalog/categorias/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_CREAR")
def admin_categorias_crear():
    try:
        descripcion = request.form.get('descripcion', '').strip()
        estado = request.form.get('estado', 'Activo')  # Obtener estado del formulario
        
        if not descripcion:
            flash("La descripción es requerida", "danger")
            return redirect(url_for('admin.admin_categorias'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO categorias_producto (Descripcion, Estado) 
                VALUES (%s, %s)
            """, (descripcion, estado))
            
        flash("Categoría creada exitosamente", "success")
    except Exception as e:
        logger.error(f"Error al crear categoría: {str(e)}", exc_info=True)
        flash(f"Error al crear categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_categorias'))


@admin_bp.route('/admin/catalog/categorias/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_EDITAR")
def admin_categorias_editar(id):
    try:
        if request.method == 'GET':
            # Mostrar formulario con datos actuales
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT ID_Categoria, Descripcion, Estado 
                    FROM categorias_producto 
                    WHERE ID_Categoria = %s
                """, (id,))
                categoria = cursor.fetchone()
                
                if not categoria:
                    flash("Categoría no encontrada", "danger")
                    return redirect(url_for('admin.admin_categorias'))
                
                return render_template('admin/catalog/categorias/editar_categoria.html', 
                                     categoria=categoria)
        
        else:  # POST - procesar edición
            descripcion = request.form.get('descripcion', '').strip()
            estado = request.form.get('estado', 'Activo')  # Obtener estado del formulario
            
            if not descripcion:
                flash("La descripción es requerida", "danger")
                return redirect(url_for('admin.admin_categorias_editar', id=id))
            
            # Verificar que la categoría existe
            with get_db_cursor(commit=True) as cursor:
                # Primero verificar existencia
                cursor.execute("""
                    SELECT ID_Categoria 
                    FROM categorias_producto 
                    WHERE ID_Categoria = %s
                """, (id,))
                
                if not cursor.fetchone():
                    flash("Categoría no encontrada", "danger")
                    return redirect(url_for('admin.admin_categorias'))
                
                # Actualizar categoría incluyendo el estado
                cursor.execute("""
                    UPDATE categorias_producto 
                    SET Descripcion = %s, Estado = %s 
                    WHERE ID_Categoria = %s
                """, (descripcion, estado, id))
            
            flash("Categoría actualizada exitosamente", "success")
            return redirect(url_for('admin.admin_categorias'))
            
    except Exception as e:
        logger.error(f"Error al editar categoría {id}: {str(e)}", exc_info=True)
        flash(f"Error al editar categoría: {str(e)}", "danger")
        return redirect(url_for('admin.admin_categorias'))


@admin_bp.route('/admin/catalog/categorias/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_ELIMINAR")
def admin_categorias_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la categoría existe
            cursor.execute("""
                SELECT ID_Categoria, Estado FROM categorias_producto 
                WHERE ID_Categoria = %s
            """, (id,))
            
            categoria = cursor.fetchone()
            if not categoria:
                flash("Categoría no encontrada", "warning")
                return redirect(url_for('admin.admin_categorias'))
            
            cursor.execute("""
                UPDATE categorias_producto 
                SET Estado = 'Inactivo' 
                WHERE ID_Categoria = %s
            """, (id,))
            
            affected_rows = cursor.rowcount
            
        if affected_rows > 0:
            flash("Categoría desactivada exitosamente", "success")
        else:
            flash("No se pudo desactivar la categoría", "warning")
            
    except Exception as e:
        logger.error(f"Error al eliminar categoría ID {id}: {str(e)}", exc_info=True)
        
        # Verificar si es error de integridad referencial
        if "foreign key constraint" in str(e).lower() or "1451" in str(e):
            flash("No se puede eliminar la categoría porque tiene productos asociados", "danger")
        else:
            flash(f"Error al eliminar categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_categorias'))


@admin_bp.route('/admin/catalog/categorias/toggle-estado/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_TOGGLE_ESTADO")
def admin_categorias_toggle_estado(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Obtener estado actual
            cursor.execute("""
                SELECT Estado FROM categorias_producto 
                WHERE ID_Categoria = %s
            """, (id,))
            
            categoria = cursor.fetchone()
            if not categoria:
                flash("Categoría no encontrada", "warning")
                return redirect(url_for('admin.admin_categorias'))
            
            # Cambiar estado
            nuevo_estado = 'Inactivo' if categoria['Estado'] == 'Activo' else 'Activo'
            cursor.execute("""
                UPDATE categorias_producto 
                SET Estado = %s 
                WHERE ID_Categoria = %s
            """, (nuevo_estado, id))
            
        flash(f"Categoría {nuevo_estado.lower()} exitosamente", "success")
        
    except Exception as e:
        logger.error(f"Error al cambiar estado de categoría {id}: {str(e)}", exc_info=True)
        flash(f"Error al cambiar estado: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_categorias'))


@admin_bp.route('/admin/catalog/movimientos/movimientos-inventario', methods=['GET'])
@admin_required
@bitacora_decorator("MOVIMIENTOS-INVENTARIO")
def admin_movimientos_inventario():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT * FROM catalogo_movimientos ORDER BY ID_TipoMovimiento""")
            movimientos = cursor.fetchall()
            return render_template('admin/catalog/movimientos/movimientos_inventario.html', 
                                 movimientos=movimientos)
    except Exception as e:
        flash(f"Error al cargar movimientos de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))


@admin_bp.route('/admin/catalog/movimientos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR-MOVIMIENTO-INVENTARIO")
def admin_crear_movimiento():
    try:
        descripcion = request.form.get('descripcion')
        adicion = request.form.get('adicion')
        letra = request.form.get('letra')
        
        if not descripcion or not letra:
            flash("Descripción y Letra son campos obligatorios", "warning")
            return redirect(url_for('admin.admin_movimientos_inventario'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO catalogo_movimientos (Descripcion, Adicion, Letra) VALUES (%s, %s, %s)",
                (descripcion, adicion, letra)
            )
            
        flash("Movimiento de inventario creado exitosamente", "success")
        return redirect(url_for('admin.admin_movimientos_inventario'))
        
    except Exception as e:
        flash(f"Error al crear movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin.admin_movimientos_inventario'))


@admin_bp.route('/admin/catalog/movimientos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR-MOVIMIENTO-INVENTARIO")
def admin_editar_movimiento(id):
    try:
        if request.method == 'POST':
            descripcion = request.form.get('descripcion')
            adicion = request.form.get('adicion')
            letra = request.form.get('letra')
            
            if not descripcion or not letra:
                flash("Descripción y Letra son campos obligatorios", "warning")
                return redirect(url_for('admin.admin_editar_movimiento', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE catalogo_movimientos SET Descripcion = %s, Adicion = %s, Letra = %s WHERE ID_TipoMovimiento = %s",
                    (descripcion, adicion, letra, id)
                )
                
            flash("Movimiento de inventario actualizado exitosamente", "success")
            return redirect(url_for('admin.admin_movimientos_inventario'))
        
        # GET - Cargar datos del movimiento
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM catalogo_movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin.admin_movimientos_inventario'))
                
        return render_template('admin/catalog/movimientos/editar_movimiento.html', movimiento=movimiento)
        
    except Exception as e:
        flash(f"Error al editar movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin.admin_movimientos_inventario'))


@admin_bp.route('/admin/catalog/movimientos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR-MOVIMIENTO-INVENTARIO")
def admin_eliminar_movimiento(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si el movimiento existe
            cursor.execute("SELECT * FROM catalogo_movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin.admin_movimientos_inventario'))
            
            # Eliminar el movimiento
            cursor.execute("DELETE FROM catalogo_movimientos WHERE ID_TipoMovimiento = %s", (id,))
            
        flash("Movimiento de inventario eliminado exitosamente", "success")
        
    except Exception as e:
        flash(f"Error al eliminar movimiento de inventario: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_movimientos_inventario'))


