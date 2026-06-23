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

@admin_bp.route('/admin/gastos/tipos', methods=['GET'])
@admin_required
@bitacora_decorator("VER_TIPOS_GASTO")
def admin_tipos_gasto():
    """Listar todos los tipos de gasto"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre, Descripcion, Origen, 
                       ID_Categoria_Inventario, Estado
                FROM tipos_gasto 
                WHERE ID_Empresa = %s
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
        return render_template(
            'admin/catalog/gastos/tipos_gasto.html',
            tipos_gasto=tipos_gasto,
            titulo="Tipos de Gastos"
        )
        
    except Exception as e:
        logger.error(f"Error al listar tipos de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))


@admin_bp.route('/admin/gastos/tipos/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CREAR_TIPO_GASTO")
def crear_tipo_gasto():
    """Crear nuevo tipo de gasto"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener categorías de inventario para el select
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                WHERE Estado = 'Activo'
                ORDER BY Descripcion
            """)
            categorias_inventario = cursor.fetchall()
            
            if request.method == 'POST':
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                origen = request.form.get('origen')
                id_categoria_inventario = request.form.get('id_categoria_inventario') or None
                estado = request.form.get('estado', 'Activo')
                
                if not nombre:
                    flash('El nombre del tipo de gasto es requerido', 'error')
                    return redirect(url_for('admin.crear_tipo_gasto'))
                
                if origen == 'INVENTARIO' and not id_categoria_inventario:
                    flash('Debe seleccionar una categoría de inventario', 'error')
                    return redirect(url_for('admin.crear_tipo_gasto'))
                
                # Verificar si ya existe
                cursor.execute("""
                    SELECT ID_Tipo_Gasto FROM tipos_gasto 
                    WHERE Nombre = %s AND ID_Empresa = %s
                """, [nombre, id_empresa])
                existe = cursor.fetchone()
                
                if existe:
                    flash('Ya existe un tipo de gasto con ese nombre', 'error')
                    return redirect(url_for('admin.crear_tipo_gasto'))
                
                cursor.execute("""
                    INSERT INTO tipos_gasto (Nombre, Descripcion, Origen, ID_Categoria_Inventario, Estado, ID_Empresa)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, [nombre, descripcion, origen, id_categoria_inventario, estado, id_empresa])
                
                flash(f'Tipo de gasto "{nombre}" creado exitosamente', 'success')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            return render_template(
                'admin/catalog/gastos/tipo_gasto_form.html',
                tipo=None,
                categorias_inventario=categorias_inventario,
                titulo="Crear Tipo de Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al crear tipo de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_tipos_gasto'))


@admin_bp.route('/admin/gastos/tipos/editar/<int:id_tipo>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_TIPO_GASTO")
def editar_tipo_gasto(id_tipo):
    """Editar tipo de gasto existente"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre, Descripcion, Origen, 
                       ID_Categoria_Inventario, Estado
                FROM tipos_gasto 
                WHERE ID_Tipo_Gasto = %s AND ID_Empresa = %s
            """, [id_tipo, id_empresa])
            tipo = cursor.fetchone()
            
            if not tipo:
                flash('Tipo de gasto no encontrado', 'error')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            # Obtener categorías de inventario
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                WHERE Estado = 'Activo'
                ORDER BY Descripcion
            """)
            categorias_inventario = cursor.fetchall()
            
            if request.method == 'POST':
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                origen = request.form.get('origen')
                id_categoria_inventario = request.form.get('id_categoria_inventario') or None
                estado = request.form.get('estado')
                
                if not nombre:
                    flash('El nombre del tipo de gasto es requerido', 'error')
                    return redirect(url_for('admin.editar_tipo_gasto', id_tipo=id_tipo))
                
                if origen == 'INVENTARIO' and not id_categoria_inventario:
                    flash('Debe seleccionar una categoría de inventario', 'error')
                    return redirect(url_for('admin.editar_tipo_gasto', id_tipo=id_tipo))
                
                cursor.execute("""
                    UPDATE tipos_gasto 
                    SET Nombre = %s, Descripcion = %s, Origen = %s, 
                        ID_Categoria_Inventario = %s, Estado = %s
                    WHERE ID_Tipo_Gasto = %s AND ID_Empresa = %s
                """, [nombre, descripcion, origen, id_categoria_inventario, estado, id_tipo, id_empresa])
                
                flash(f'Tipo de gasto "{nombre}" actualizado exitosamente', 'success')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            return render_template(
                'admin/catalog/gastos/tipo_gasto_form.html',
                tipo=tipo,
                categorias_inventario=categorias_inventario,
                titulo="Editar Tipo de Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al editar tipo de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_tipos_gasto'))


@admin_bp.route('/admin/gastos/tipos/eliminar/<int:id_tipo>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR_TIPO_GASTO")
def eliminar_tipo_gasto(id_tipo):
    """Eliminar (desactivar) tipo de gasto"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Verificar si tiene subcategorías asociadas
            cursor.execute("""
                SELECT COUNT(*) as total FROM subcategorias_gasto 
                WHERE ID_Tipo_Gasto = %s
            """, [id_tipo])
            subcategorias = cursor.fetchone()
            
            if subcategorias['total'] > 0:
                flash(f'No se puede eliminar: tiene {subcategorias["total"]} subcategorías asociadas', 'error')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            # Desactivar en lugar de eliminar
            cursor.execute("""
                UPDATE tipos_gasto 
                SET Estado = 'Inactivo'
                WHERE ID_Tipo_Gasto = %s AND ID_Empresa = %s
            """, [id_tipo, id_empresa])
            
            flash('Tipo de gasto desactivado exitosamente', 'success')
            
    except Exception as e:
        logger.error(f"Error al eliminar tipo de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_tipos_gasto'))


@admin_bp.route('/admin/gastos/subcategorias', methods=['GET'])
@admin_required
@bitacora_decorator("VER_SUBCATEGORIAS")
def admin_subcategorias():
    """Listar todas las subcategorías"""
    try:
        id_empresa = session.get('id_empresa', 1)
        tipo_filtro = request.args.get('tipo', '')
        
        with get_db_cursor(True) as cursor:
            query = """
                SELECT sg.ID_Subcategoria, sg.Nombre, sg.Descripcion, sg.Estado,
                       tg.Nombre as tipo_gasto_nombre, tg.ID_Tipo_Gasto
                FROM subcategorias_gasto sg
                INNER JOIN tipos_gasto tg ON sg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE tg.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if tipo_filtro:
                query += " AND tg.ID_Tipo_Gasto = %s"
                params.append(tipo_filtro)
            
            query += " ORDER BY tg.Nombre, sg.Nombre"
            
            cursor.execute(query, params)
            subcategorias = cursor.fetchall()
            
            # Obtener tipos de gasto para el filtro
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE ID_Empresa = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
        return render_template(
            'admin/catalog/gastos/subcategorias.html',
            subcategorias=subcategorias,
            tipos_gasto=tipos_gasto,
            tipo_filtro=tipo_filtro,
            titulo="Subcategorías de Gastos"
        )
        
    except Exception as e:
        logger.error(f"Error al listar subcategorías: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))


@admin_bp.route('/admin/gastos/subcategorias/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CREAR_SUBCATEGORIA")
def crear_subcategoria():
    """Crear nueva subcategoría"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE ID_Empresa = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                estado = request.form.get('estado', 'Activo')
                
                if not id_tipo_gasto:
                    flash('Debe seleccionar un tipo de gasto', 'error')
                    return redirect(url_for('admin.crear_subcategoria'))
                
                if not nombre:
                    flash('El nombre de la subcategoría es requerido', 'error')
                    return redirect(url_for('admin.crear_subcategoria'))
                
                # Verificar si ya existe
                cursor.execute("""
                    SELECT ID_Subcategoria FROM subcategorias_gasto 
                    WHERE ID_Tipo_Gasto = %s AND Nombre = %s
                """, [id_tipo_gasto, nombre])
                existe = cursor.fetchone()
                
                if existe:
                    flash('Ya existe una subcategoría con ese nombre para este tipo de gasto', 'error')
                    return redirect(url_for('admin.crear_subcategoria'))
                
                cursor.execute("""
                    INSERT INTO subcategorias_gasto (ID_Tipo_Gasto, Nombre, Descripcion, Estado)
                    VALUES (%s, %s, %s, %s)
                """, [id_tipo_gasto, nombre, descripcion, estado])
                
                flash(f'Subcategoría "{nombre}" creada exitosamente', 'success')
                return redirect(url_for('admin.admin_subcategorias'))
            
            return render_template(
                'admin/catalog/gastos/subcategoria_form.html',
                subcategoria=None,
                tipos_gasto=tipos_gasto,
                titulo="Crear Subcategoría"
            )
            
    except Exception as e:
        logger.error(f"Error al crear subcategoría: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_subcategorias'))


@admin_bp.route('/admin/gastos/subcategorias/editar/<int:id_sub>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_SUBCATEGORIA")
def editar_subcategoria(id_sub):
    """Editar subcategoría existente"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT sg.*, tg.ID_Tipo_Gasto, tg.Nombre as tipo_nombre
                FROM subcategorias_gasto sg
                INNER JOIN tipos_gasto tg ON sg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE sg.ID_Subcategoria = %s AND tg.ID_Empresa = %s
            """, [id_sub, id_empresa])
            subcategoria = cursor.fetchone()
            
            if not subcategoria:
                flash('Subcategoría no encontrada', 'error')
                return redirect(url_for('admin.admin_subcategorias'))
            
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE ID_Empresa = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                estado = request.form.get('estado')
                
                if not nombre:
                    flash('El nombre de la subcategoría es requerido', 'error')
                    return redirect(url_for('admin.editar_subcategoria', id_sub=id_sub))
                
                cursor.execute("""
                    UPDATE subcategorias_gasto 
                    SET ID_Tipo_Gasto = %s, Nombre = %s, Descripcion = %s, Estado = %s
                    WHERE ID_Subcategoria = %s
                """, [id_tipo_gasto, nombre, descripcion, estado, id_sub])
                
                flash(f'Subcategoría "{nombre}" actualizada exitosamente', 'success')
                return redirect(url_for('admin.admin_subcategorias'))
            
            return render_template(
                'admin/catalog/gastos/subcategoria_form.html',
                subcategoria=subcategoria,
                tipos_gasto=tipos_gasto,
                titulo="Editar Subcategoría"
            )
            
    except Exception as e:
        logger.error(f"Error al editar subcategoría: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_subcategorias'))


@admin_bp.route('/admin/gastos/subcategorias/eliminar/<int:id_sub>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR_SUBCATEGORIA")
def eliminar_subcategoria(id_sub):
    """Eliminar (desactivar) subcategoría"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Verificar si tiene gastos asociados
            cursor.execute("""
                SELECT COUNT(*) as total FROM gastos_generales 
                WHERE ID_Subcategoria = %s AND ID_Empresa = %s
            """, [id_sub, id_empresa])
            gastos = cursor.fetchone()
            
            if gastos['total'] > 0:
                flash(f'No se puede eliminar: tiene {gastos["total"]} gastos asociados', 'error')
                return redirect(url_for('admin.admin_subcategorias'))
            
            # Desactivar en lugar de eliminar
            cursor.execute("""
                UPDATE subcategorias_gasto 
                SET Estado = 'Inactivo'
                WHERE ID_Subcategoria = %s
            """, [id_sub])
            
            flash('Subcategoría desactivada exitosamente', 'success')
            
    except Exception as e:
        logger.error(f"Error al eliminar subcategoría: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_subcategorias'))


