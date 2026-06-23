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

@admin_bp.route('/admin/roles')
@admin_required
@bitacora_decorator("ROLES")
def admin_roles():
    """Listar todos los roles"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM roles ORDER BY Estado DESC, ID_Rol")
            roles = cursor.fetchall()
            return render_template('admin/catalog/rol/roles.html', roles=roles)
    except Exception as e:
        flash(f"Error al cargar roles: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/roles/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_ROL")
def crear_rol():
    """Crear un nuevo rol (formulario tradicional)"""
    try:
        nombre_rol = request.form.get('nombre_rol')
        
        if not nombre_rol or nombre_rol.strip() == '':
            flash("El nombre del rol es requerido", "danger")
            return redirect(url_for('admin.admin_roles'))
        
        # Validar si el rol ya existe
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ID_Rol FROM roles WHERE Nombre_Rol = %s", (nombre_rol.strip(),))
            if cursor.fetchone():
                flash("Ya existe un rol con ese nombre", "warning")
                return redirect(url_for('admin.admin_roles'))
        
        # Crear el nuevo rol
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO roles (Nombre_Rol, Estado) VALUES (%s, 'Activo')",
                (nombre_rol.strip(),)
            )
        
        flash("Rol creado exitosamente", "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al crear rol: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))


@admin_bp.route('/admin/roles/editar/<int:id_rol>', methods=['POST'])
@admin_required
@bitacora_decorator("EDITAR_ROL")
def editar_rol(id_rol):
    """Editar un rol existente (formulario tradicional)"""
    try:
        nombre_rol = request.form.get('nombre_rol')
        estado = request.form.get('estado')
        
        if not nombre_rol or nombre_rol.strip() == '':
            flash("El nombre del rol es requerido", "danger")
            return redirect(url_for('admin.admin_roles'))
        
        # Validar si el rol existe
        with get_db_cursor() as cursor:
            cursor.execute("SELECT Nombre_Rol FROM roles WHERE ID_Rol = %s", (id_rol,))
            rol_existente = cursor.fetchone()
            
            if not rol_existente:
                flash("Rol no encontrado", "danger")
                return redirect(url_for('admin.admin_roles'))
            
            # Validar si el nuevo nombre ya existe en otro rol
            cursor.execute(
                "SELECT ID_Rol FROM roles WHERE Nombre_Rol = %s AND ID_Rol != %s", 
                (nombre_rol.strip(), id_rol)
            )
            if cursor.fetchone():
                flash("Ya existe otro rol con ese nombre", "warning")
                return redirect(url_for('admin.admin_roles'))
        
        # Actualizar el rol
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE roles SET Nombre_Rol = %s, Estado = %s WHERE ID_Rol = %s",
                (nombre_rol.strip(), estado, id_rol)
            )
        
        flash("Rol actualizado exitosamente", "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al actualizar rol: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))


@admin_bp.route('/admin/roles/cambiar_estado/<int:id_rol>', methods=['POST'])
@admin_required
@bitacora_decorator("CAMBIAR_ESTADO_ROL")
def cambiar_estado_rol(id_rol):
    """Cambiar estado de Activo a Inactivo o viceversa (formulario tradicional)"""
    try:
        with get_db_cursor() as cursor:
            # Primero obtenemos el estado actual
            cursor.execute("SELECT Estado, Nombre_Rol FROM roles WHERE ID_Rol = %s", (id_rol,))
            rol = cursor.fetchone()
            
            if not rol:
                flash("Rol no encontrado", "danger")
                return redirect(url_for('admin.admin_roles'))
            
            # Cambiamos el estado
            nuevo_estado = 'Inactivo' if rol['Estado'] == 'Activo' else 'Activo'
            nombre_rol = rol['Nombre_Rol']
            
            cursor.execute(
                "UPDATE roles SET Estado = %s WHERE ID_Rol = %s",
                (nuevo_estado, id_rol)
            )
        
        mensaje = f"Rol '{nombre_rol}' {nuevo_estado.lower()} correctamente"
        flash(mensaje, "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al cambiar estado: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))


@admin_bp.route('/admin/roles/eliminar/<int:id_rol>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR_ROL")
def eliminar_rol(id_rol):
    """Eliminar un rol (formulario tradicional)"""
    try:
        with get_db_cursor() as cursor:
            # Verificar si el rol existe
            cursor.execute("SELECT Estado, Nombre_Rol FROM roles WHERE ID_Rol = %s", (id_rol,))
            rol = cursor.fetchone()
            
            if not rol:
                flash("Rol no encontrado", "danger")
                return redirect(url_for('admin.admin_roles'))
            
            # Verificar si el rol está activo
            if rol['Estado'] == 'Activo':
                flash("No se puede eliminar un rol activo. Primero debe inactivarlo.", "warning")
                return redirect(url_for('admin.admin_roles'))
            
            # Verificar si hay usuarios asociados al rol
            cursor.execute("SELECT COUNT(*) as count FROM usuarios WHERE ID_Rol = %s", (id_rol,))
            usuarios_asociados = cursor.fetchone()['count']
            
            if usuarios_asociados > 0:
                flash(f"No se puede eliminar el rol porque tiene {usuarios_asociados} usuario(s) asociado(s).", "warning")
                return redirect(url_for('admin.admin_roles'))
        
        # Si pasa las validaciones, eliminar
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM roles WHERE ID_Rol = %s", (id_rol,))
        
        flash(f"Rol '{rol['Nombre_Rol']}' eliminado exitosamente", "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al eliminar rol: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))


@admin_bp.route('/admin/usuarios')
@admin_required
@bitacora_decorator("USUARIOS")
def admin_usuarios():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa FROM usuarios u
                JOIN roles r ON u.ID_Rol = r.ID_Rol
                JOIN empresa e ON u.ID_Empresa = e.ID_Empresa
            """)
            usuarios = cursor.fetchall()
            
            cursor.execute("SELECT * FROM roles")
            roles = cursor.fetchall()
            
            cursor.execute("SELECT * FROM empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/usuarios.html', usuarios=usuarios, roles=roles, empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar usuarios: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/catalog/crear-usuario', methods=['POST'])
@admin_required
@bitacora_decorator("USUARIOS")
def crear_usuario():
    username = request.form.get('username')
    password = request.form.get('password')
    rol_id = request.form.get('rol_id')
    empresa_id = request.form.get('empresa_id')

    if not all([username, password, rol_id, empresa_id]):
        flash("Todos los campos son requeridos", "danger")
        return redirect(url_for('admin.admin_usuarios'))

    hashed_password = generate_password_hash(password)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuarios (NombreUsuario, Contraseña, ID_Rol, ID_Empresa, Estado)
                VALUES (%s, %s, %s, %s, 'Activo')
            """, (username, hashed_password, rol_id, empresa_id))
            registrar_bitacora(modulo="USUARIOS", accion=f"CREAR_USUARUI: {username}")
            flash("Usuario creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear usuario: {e}", "danger")
    
    return redirect(url_for('admin.admin_usuarios'))


@admin_bp.route('/admin/catalog/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(user_id):
    try:
        with get_db_cursor() as cursor:
            if request.method == 'GET':
                # Obtener datos del usuario a editar
                cursor.execute("""
                    SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa 
                    FROM usuarios u
                    JOIN roles r ON u.ID_Rol = r.ID_Rol
                    JOIN empresa e ON u.ID_Empresa = e.ID_Empresa
                    WHERE u.ID_Usuario = %s
                """, (user_id,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    flash("Usuario no encontrado", "danger")
                    return redirect(url_for('admin.admin_usuarios'))
                
                # Obtener roles y empresas para el formulario
                cursor.execute("SELECT * FROM roles")
                roles = cursor.fetchall()
                
                cursor.execute("SELECT * FROM empresa")
                empresas = cursor.fetchall()
                
                return render_template('admin/catalog/editar_usuario.html', 
                                     usuario=usuario, 
                                     roles=roles, 
                                     empresas=empresas)
            
            elif request.method == 'POST':
                # Procesar el formulario de edición
                username = request.form.get('username')
                rol_id = request.form.get('rol_id')
                empresa_id = request.form.get('empresa_id')
                estado = request.form.get('estado')
                password = request.form.get('password')
                
                if not all([username, rol_id, empresa_id, estado]):
                    flash("Todos los campos son requeridos", "danger")
                    return redirect(url_for('admin.editar_usuario', user_id=user_id))
                
                # Construir la consulta dinámicamente
                update_fields = []
                update_values = []
                
                update_fields.append("NombreUsuario = %s")
                update_values.append(username)
                
                update_fields.append("ID_Rol = %s")
                update_values.append(rol_id)
                
                update_fields.append("ID_Empresa = %s")
                update_values.append(empresa_id)
                
                update_fields.append("Estado = %s")
                update_values.append(estado)
                
                # Si se proporcionó una nueva contraseña, actualizarla
                if password:
                    hashed_password = generate_password_hash(password)
                    update_fields.append("Contraseña = %s")
                    update_values.append(hashed_password)
                
                # Agregar el ID al final de los valores
                update_values.append(user_id)
                
                # Ejecutar la actualización
                query = f"UPDATE usuarios SET {', '.join(update_fields)} WHERE ID_Usuario = %s"
                cursor.execute(query, update_values)
                
                flash("Usuario actualizado exitosamente", "success")
                return redirect(url_for('admin.admin_usuarios'))
                
    except Exception as e:
        flash(f"Error al editar usuario: {e}", "danger")
        return redirect(url_for('admin.admin_usuarios'))


@admin_bp.route('/admin/catalog/empresa/empresas', methods=['GET'])
@admin_required
@bitacora_decorator("EMPRESA")
def admin_empresas():
    """Listar todas las empresas"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, Direccion, Telefono, Estado, RUC 
                FROM empresa 
                ORDER BY Nombre_Empresa
            """)
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/empresa/empresas.html', empresas=empresas)
    except Exception as e:
        flash(f'Error al cargar empresas: {str(e)}', 'error')
        return render_template('admin/catalog/empresa/empresas.html', empresas=[])


@admin_bp.route('/admin/catalog/empresa/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EMPRESA_CREAR")
def crear_empresa():
    """Crear nueva empresa (GET: mostrar modal, POST: procesar formulario)"""
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre_empresa')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ruc = request.form.get('ruc')
            estado = request.form.get('estado', 'Activo')
            
            # Validaciones básicas
            if not nombre:
                flash('El nombre de la empresa es obligatorio', 'error')
                return redirect(url_for('admin.admin_empresas'))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO empresa (Nombre_Empresa, Direccion, Telefono, RUC, Estado)
                    VALUES (%s, %s, %s, %s, %s)
                """, (nombre, direccion, telefono, ruc, estado))
                
            flash('Empresa creada exitosamente', 'success')
            return redirect(url_for('admin.admin_empresas'))
            
        except Exception as e:
            flash(f'Error al crear empresa: {str(e)}', 'error')
            return redirect(url_for('admin.admin_empresas'))
    
    # GET: Redirigir a la página principal (el modal está en empresas.html)
    return redirect(url_for('admin.admin_empresas'))


@admin_bp.route('/admin/catalog/empresa/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EMPRESA_EDITAR")
def editar_empresa(id):
    """Editar empresa (GET: mostrar formulario, POST: procesar edición)"""
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre_empresa')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ruc = request.form.get('ruc')
            estado = request.form.get('estado')
            
            if not nombre:
                flash('El nombre de la empresa es obligatorio', 'error')
                return redirect(url_for('admin.editar_empresa', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE empresa 
                    SET Nombre_Empresa = %s, Direccion = %s, Telefono = %s, 
                        RUC = %s, Estado = %s
                    WHERE ID_Empresa = %s
                """, (nombre, direccion, telefono, ruc, estado, id))
                
            flash('Empresa actualizada exitosamente', 'success')
            return redirect(url_for('admin.admin_empresas'))
            
        except Exception as e:
            flash(f'Error al actualizar empresa: {str(e)}', 'error')
            return redirect(url_for('admin.editar_empresa', id=id))
    
    # GET: Mostrar formulario de edición
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, Direccion, Telefono, Estado, RUC 
                FROM empresa 
                WHERE ID_Empresa = %s
            """, (id,))
            empresa = cursor.fetchone()
            
            if not empresa:
                flash('Empresa no encontrada', 'error')
                return redirect(url_for('admin.admin_empresas'))
                
            return render_template('admin/catalog/empresa/editar_empresa.html', empresa=empresa)
            
    except Exception as e:
        flash(f'Error al cargar empresa: {str(e)}', 'error')
        return redirect(url_for('admin.admin_empresas'))


