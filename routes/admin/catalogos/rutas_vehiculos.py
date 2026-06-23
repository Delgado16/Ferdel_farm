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

@admin_bp.route('/admin/rutas', methods=['GET'])
@admin_required
@bitacora_decorator("RUTAS")
def admin_rutas():
    try:
        with get_db_cursor() as cursor:
            # Obtener rutas - ACTUALIZADO para nueva estructura
            cursor.execute("""
                SELECT 
                    r.ID_Ruta,
                    r.Nombre_Ruta,
                    r.Descripcion,
                    r.ID_Empresa,
                    r.Estado,
                    DATE_FORMAT(r.Fecha_Creacion, '%d/%m/%Y %H:%i:%s') as Fecha_Creacion,
                    e.Nombre_Empresa as Nombre_Empresa 
                FROM rutas r 
                LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                ORDER BY r.ID_Ruta DESC
            """)
            
            rutas = cursor.fetchall()
            
            # Obtener empresas activas para los select
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
        return render_template('admin/catalog/rutas/rutas.html', rutas=rutas, empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar rutas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/rutas/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR-RUTA")
def crear_ruta():
    try:
        # Obtener datos del formulario - ACTUALIZADO (sin hora_inicio y hora_fin)
        nombre_ruta = request.form.get('nombre_ruta', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        id_empresa = request.form.get('id_empresa')
        
        print(f"DEBUG: Creando ruta - Nombre: '{nombre_ruta}', Empresa: '{id_empresa}'")
        
        # Validaciones básicas
        if not nombre_ruta:
            flash("El nombre de la ruta es obligatorio", "danger")
            return redirect(url_for('admin.admin_rutas'))
        
        if not id_empresa:
            flash("Debe seleccionar una empresa", "danger")
            return redirect(url_for('admin.admin_rutas'))
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar si ya existe una ruta con el mismo nombre
            cursor.execute("SELECT ID_Ruta FROM rutas WHERE Nombre_Ruta = %s", (nombre_ruta,))
            if cursor.fetchone():
                flash("Ya existe una ruta con ese nombre. Por favor, use un nombre diferente.", "warning")
                return redirect(url_for('admin.admin_rutas'))
            
            # Verificar que la empresa existe
            cursor.execute("SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", (id_empresa,))
            if not cursor.fetchone():
                flash("La empresa seleccionada no existe o no está activa", "danger")
                return redirect(url_for('admin.admin_rutas'))
            
            # Insertar nueva ruta - ACTUALIZADO: Solo Nombre_Ruta, Descripcion, ID_Empresa, Estado
            cursor.execute("""
                INSERT INTO rutas (Nombre_Ruta, Descripcion, ID_Empresa, Estado)
                VALUES (%s, %s, %s, 'Activa')
            """, (nombre_ruta, descripcion or None, id_empresa))
            
            nuevo_id = cursor.lastrowid
            print(f"DEBUG: Ruta creada con ID: {nuevo_id}")
        
        flash("✅ Ruta creada exitosamente", "success")
        return redirect(url_for('admin.admin_rutas'))
        
    except Exception as e:
        print(f"ERROR en crear_ruta: {str(e)}")
        flash(f"Error al crear ruta: {str(e)}", "danger")
        return redirect(url_for('admin.admin_rutas'))


@admin_bp.route('/admin/rutas/editar/<int:id_ruta>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR-RUTA")
def admin_editar_ruta(id_ruta):
    """Maneja tanto la visualización como el procesamiento del formulario de edición"""
    
    try:
        with get_db_cursor() as cursor:
            # Obtener empresas activas (se usa en ambos métodos)
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            # ========== MÉTODO GET: Mostrar formulario ==========
            if request.method == 'GET':
                # Obtener los datos de la ruta específica - ACTUALIZADO para nueva estructura
                cursor.execute("""
                    SELECT 
                        r.ID_Ruta,
                        r.Nombre_Ruta,
                        r.Descripcion,
                        r.Estado,
                        r.ID_Empresa,
                        r.Fecha_Creacion,
                        e.Nombre_Empresa
                    FROM rutas r 
                    LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                    WHERE r.ID_Ruta = %s
                """, (id_ruta,))
                ruta = cursor.fetchone()
                
                if not ruta:
                    flash("❌ La ruta no existe", "danger")
                    return redirect(url_for('admin.admin_rutas'))
                
                print(f"DEBUG: Mostrando formulario para editar ruta ID: {id_ruta}")
                print(f"DEBUG: Datos de la ruta: {dict(ruta)}")
                
                return render_template('admin/catalog/rutas/editar_ruta.html', 
                                     ruta=ruta, 
                                     empresas=empresas)
            
            # ========== MÉTODO POST: Procesar formulario ==========
            elif request.method == 'POST':
                # Obtener datos del formulario - ACTUALIZADO (sin hora_inicio y hora_fin)
                nombre_ruta = request.form.get('nombre_ruta', '').strip()
                descripcion = request.form.get('descripcion', '').strip()
                id_empresa = request.form.get('id_empresa')
                
                print(f"DEBUG: Procesando edición de ruta {id_ruta}")
                print(f"DEBUG: Datos recibidos - Nombre: '{nombre_ruta}', Empresa: '{id_empresa}'")
                
                # Validaciones
                errores = []
                
                if not nombre_ruta:
                    errores.append("El nombre de la ruta es obligatorio")
                
                if not id_empresa:
                    errores.append("Debe seleccionar una empresa")
                else:
                    # Validar que el ID de empresa es numérico
                    try:
                        id_empresa = int(id_empresa)
                    except ValueError:
                        errores.append("El ID de empresa no es válido")
                
                if errores:
                    for error in errores:
                        flash(f"❌ {error}", "danger")
                    
                    # Obtener datos actuales para mostrar el formulario con errores
                    cursor.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor.fetchone()
                    
                    return render_template('admin/catalog/rutas/editar_ruta.html', 
                                         ruta=ruta, 
                                         empresas=empresas)
                
                # Verificar si la ruta existe - ACTUALIZADO (sin hora_inicio y hora_fin)
                cursor.execute("""
                    SELECT ID_Ruta, Nombre_Ruta, Descripcion, ID_Empresa 
                    FROM rutas 
                    WHERE ID_Ruta = %s
                """, (id_ruta,))
                ruta_existente = cursor.fetchone()
                
                if not ruta_existente:
                    flash("❌ La ruta no existe", "danger")
                    return redirect(url_for('admin.admin_rutas'))
                
                # Verificar si ya existe otra ruta con el mismo nombre
                cursor.execute("""
                    SELECT ID_Ruta 
                    FROM rutas 
                    WHERE Nombre_Ruta = %s AND ID_Ruta != %s
                """, (nombre_ruta, id_ruta))
                
                if cursor.fetchone():
                    flash("⚠️ Ya existe otra ruta con ese nombre. Por favor, use un nombre diferente.", "warning")
                    
                    # Recargar datos para mostrar el formulario con el error
                    cursor.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor.fetchone()
                    
                    return render_template('admin/catalog/rutas/editar_ruta.html', 
                                         ruta=ruta, 
                                         empresas=empresas)
                
                # Verificar que la empresa existe y está activa
                cursor.execute("""
                    SELECT ID_Empresa, Nombre_Empresa 
                    FROM empresa 
                    WHERE ID_Empresa = %s AND Estado = 'Activo'
                """, (id_empresa,))
                
                empresa_valida = cursor.fetchone()
                if not empresa_valida:
                    flash("❌ La empresa seleccionada no existe o no está activa", "danger")
                    
                    # Recargar datos para mostrar el formulario con el error
                    cursor.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor.fetchone()
                    
                    return render_template('admin/catalog/rutas/editar_ruta.html', 
                                         ruta=ruta, 
                                         empresas=empresas)
                
                # Comparar datos actuales con nuevos para ver si hubo cambios
                hubo_cambios = False
                cambios_detalle = []
                
                # Comparar nombre
                if ruta_existente['Nombre_Ruta'] != nombre_ruta:
                    hubo_cambios = True
                    cambios_detalle.append(f"Nombre: '{ruta_existente['Nombre_Ruta']}' → '{nombre_ruta}'")
                
                # Comparar descripción (manejar valores None)
                desc_actual = ruta_existente['Descripcion'] or ''
                desc_nueva = descripcion or ''
                if desc_actual != desc_nueva:
                    hubo_cambios = True
                    cambios_detalle.append(f"Descripción actualizada")
                
                # Comparar empresa
                if ruta_existente['ID_Empresa'] != id_empresa:
                    hubo_cambios = True
                    cambios_detalle.append(f"Empresa: ID {ruta_existente['ID_Empresa']} → ID {id_empresa}")
                
                if not hubo_cambios:
                    flash("ℹ No se realizaron cambios en la ruta", "info")
                    return redirect(url_for('admin.admin_rutas'))
                
                # Actualizar ruta en la base de datos - ACTUALIZADO (sin hora_inicio y hora_fin)
                cursor.execute("""
                    UPDATE rutas 
                    SET 
                        Nombre_Ruta = %s,
                        Descripcion = %s,
                        ID_Empresa = %s
                    WHERE ID_Ruta = %s
                """, (nombre_ruta, descripcion or None, id_empresa, id_ruta))
                
                print(f"DEBUG: Ruta {id_ruta} actualizada exitosamente")
                print(f"DEBUG: Cambios realizados: {cambios_detalle}")
                
                # Registrar en bitácora
                if cambios_detalle:
                    cambios_texto = " | ".join(cambios_detalle)
                    print(f"BITACORA: Ruta {id_ruta} modificada - {cambios_texto}")
                
                flash("✅ Ruta actualizada exitosamente", "success")
                return redirect(url_for('admin.admin_rutas'))
    
    except Exception as e:
        print(f"ERROR en editar_ruta (ID: {id_ruta}): {str(e)}")
        
        flash(f"❌ Error al procesar la ruta: {str(e)}", "danger")
        
        # Si es POST, intentar redirigir de nuevo al formulario con datos básicos
        if request.method == 'POST':
            try:
                # Intentar obtener datos básicos para mostrar el formulario
                with get_db_cursor() as cursor2:
                    cursor2.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
                    empresas = cursor2.fetchall()
                    
                    cursor2.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor2.fetchone()
                    
                    if ruta:
                        return render_template('admin/catalog/rutas/editar_ruta.html', 
                                             ruta=ruta, 
                                             empresas=empresas)
            except Exception as e2:
                print(f"ERROR secundario al recuperar datos: {str(e2)}")
        
        return redirect(url_for('admin.admin_rutas'))


@admin_bp.route('/admin/rutas/cambiar-estado/<int:id_ruta>', methods=['POST'])
@admin_required
@bitacora_decorator("CAMBIAR-ESTADO-RUTA")
def cambiar_estado_ruta(id_ruta):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Obtener estado actual
            cursor.execute("SELECT Estado, Nombre_Ruta FROM rutas WHERE ID_Ruta = %s", (id_ruta,))
            resultado = cursor.fetchone()
            
            if not resultado:
                flash("La ruta no existe", "danger")
                return redirect(url_for('admin.admin_rutas'))
            
            estado_actual = resultado['Estado']
            nombre_ruta = resultado['Nombre_Ruta']
            nuevo_estado = 'Inactiva' if estado_actual == 'Activa' else 'Activa'
            
            # Actualizar estado
            cursor.execute("""
                UPDATE rutas 
                SET Estado = %s
                WHERE ID_Ruta = %s
            """, (nuevo_estado, id_ruta))
            
            print(f"DEBUG: Ruta {id_ruta} '{nombre_ruta}' cambiada de '{estado_actual}' a '{nuevo_estado}'")
        
        estado_texto = "desactivada" if nuevo_estado == 'Inactiva' else "activada"
        flash(f"✅ Ruta '{nombre_ruta}' {estado_texto} exitosamente", "success")
        return redirect(url_for('admin.admin_rutas'))
        
    except Exception as e:
        print(f"ERROR en cambiar_estado_ruta: {str(e)}")
        flash(f"Error al cambiar estado de ruta: {str(e)}", "danger")
        return redirect(url_for('admin.admin_rutas'))


@admin_bp.route('/admin/rutas/eliminar', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR-RUTA")
def eliminar_ruta(): 
    try:
        # Obtener ID del formulario
        id_ruta = request.form.get('id_ruta')
        
        # Validar que se recibió el ID
        if not id_ruta:
            flash("ID de ruta no especificado", "danger")
            return redirect(url_for('admin.admin_rutas'))
        
        # Convertir a entero
        id_ruta = int(id_ruta)
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la ruta existe
            cursor.execute("SELECT Nombre_Ruta FROM rutas WHERE ID_Ruta = %s", (id_ruta,))
            ruta = cursor.fetchone()
            
            if not ruta:
                flash("La ruta no existe", "danger")
                return redirect(url_for('admin.admin_rutas'))
            
            nombre_ruta = ruta['Nombre_Ruta']
            
            # Eliminar ruta
            cursor.execute("DELETE FROM rutas WHERE ID_Ruta = %s", (id_ruta,))
            
            print(f"DEBUG: Ruta {id_ruta} '{nombre_ruta}' eliminada")
        
        flash(f"✅ Ruta '{nombre_ruta}' eliminada exitosamente", "success")
        return redirect(url_for('admin.admin_rutas'))
        
    except Exception as e:
        print(f"ERROR en eliminar_ruta: {str(e)}")
        flash(f"Error al eliminar ruta: {str(e)}", "danger")
        return redirect(url_for('admin.admin_rutas')) 


@admin_bp.route('/admin/vehiculos/vehiculos')
@admin_required
def admin_vehiculos():
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT v.*, e.Nombre_Empresa as Nombre_Empresa 
                FROM vehiculos v
                LEFT JOIN empresa e ON v.ID_Empresa = e.ID_Empresa
                ORDER BY v.Fecha_Creacion DESC
            """)
            vehiculos = cursor.fetchall()
            
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
        # Inyectar current_year directamente
        from datetime import datetime
        current_year = datetime.now().year
        
        return render_template('admin/catalog/vehiculo/vehiculo.html', 
                             vehiculos=vehiculos, 
                             empresas=empresas,
                             current_year=current_year) 
        
    except Exception as e:
        flash(f'Error al cargar vehículos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/vehiculos/crear', methods=['POST'])
@admin_required
def crear_vehiculo():
    try:
        # Obtener datos del formulario
        placa = request.form.get('placa')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        anio = request.form.get('anio')
        id_empresa = request.form.get('id_empresa')
        tipo_combustible = request.form.get('tipo_combustible')
        fecha_vencimiento_seguro = request.form.get('fecha_vencimiento_seguro')
        
        # Validar datos requeridos
        if not all([placa, id_empresa]):
            flash('Placa y Empresa son campos requeridos', 'error')
            return redirect(url_for('admin.admin_vehiculos'))
        
        with get_db_cursor() as cursor:
            # Verificar si la placa ya existe para esta empresa
            cursor.execute("""
                SELECT ID_Vehiculo FROM vehiculos 
                WHERE Placa = %s AND ID_Empresa = %s
            """, (placa, id_empresa))
            
            if cursor.fetchone():
                flash('La placa ya existe para esta empresa', 'error')
                return redirect(url_for('admin.admin_vehiculos'))
            
            # Insertar nuevo vehículo
            cursor.execute("""
                INSERT INTO vehiculos 
                (Placa, Marca, Modelo, Anio, ID_Empresa, Tipo_Combustible, Fecha_Vencimiento_Seguro)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (placa, marca, modelo, anio, id_empresa, tipo_combustible, fecha_vencimiento_seguro))
            
            flash('Vehículo creado exitosamente', 'success')
            return redirect(url_for('admin.admin_vehiculos'))
            
    except Exception as e:
        flash(f'Error al crear vehículo: {str(e)}', 'error')
        return redirect(url_for('admin.admin_vehiculos'))


@admin_bp.route('/admin/vehiculos/<int:id>')
@admin_required
def obtener_vehiculo(id):
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT v.*, e.Nombre_Empresa as Nombre_Empresa 
                FROM vehiculos v
                LEFT JOIN empresa e ON v.ID_Empresa = e.ID_Empresa
                WHERE v.ID_Vehiculo = %s
            """, (id,))
            
            vehiculo = cursor.fetchone()
            
            if not vehiculo:
                return jsonify({'error': 'Vehículo no encontrado'}), 404
            
            # Convertir a diccionario y manejar fechas
            vehiculo_dict = dict(vehiculo)
            vehiculo_dict['Fecha_Vencimiento_Seguro'] = vehiculo['Fecha_Vencimiento_Seguro'].isoformat() if vehiculo['Fecha_Vencimiento_Seguro'] else None
            
            return jsonify(vehiculo_dict)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/vehiculos/editar/<int:id>')
@admin_required
def mostrar_editar_vehiculo(id):
    """Muestra el formulario de edición de vehículo (GET)"""
    try:
        with get_db_cursor(True) as cursor:
            # Obtener datos del vehículo
            cursor.execute("""
                SELECT v.*, e.Nombre_Empresa as Nombre_Empresa 
                FROM vehiculos v
                LEFT JOIN empresa e ON v.ID_Empresa = e.ID_Empresa
                WHERE v.ID_Vehiculo = %s
            """, (id,))
            
            vehiculo = cursor.fetchone()
            
            if not vehiculo:
                flash('Vehículo no encontrado', 'error')
                return redirect(url_for('admin.admin_vehiculos'))
            
            # Obtener lista de empresas activas
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
        # Inyectar current_year
        from datetime import datetime
        current_year = datetime.now().year
        
        # Asegurar que el año sea un entero (year en MySQL puede devolver como decimal)
        if vehiculo['Anio']:
            vehiculo['Anio'] = int(vehiculo['Anio'])
        
        return render_template('admin/catalog/vehiculo/vehiculo_editar.html', 
                             vehiculo=vehiculo, 
                             empresas=empresas,
                             current_year=current_year)
            
    except Exception as e:
        flash(f'Error al cargar formulario de edición: {str(e)}', 'error')
        return redirect(url_for('admin_vehiculos'))


@admin_bp.route('/admin/vehiculos/editar/<int:id>', methods=['POST'])
@admin_required
def procesar_editar_vehiculo(id):
    """Procesa el formulario de edición de vehículo (POST)"""
    try:
        # Obtener datos del formulario
        placa = request.form.get('placa')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        anio = request.form.get('anio')
        id_empresa = request.form.get('id_empresa')
        tipo_combustible = request.form.get('tipo_combustible')
        fecha_vencimiento_seguro = request.form.get('fecha_vencimiento_seguro')
        estado = request.form.get('estado')  # Nuevo campo para estado
        
        # Validar datos requeridos
        if not all([placa, id_empresa, estado]):
            flash('Placa, Empresa y Estado son campos requeridos', 'error')
            return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))
        
        # Validar que el estado sea válido
        estados_validos = ['Disponible', 'En Ruta', 'Mantenimiento', 'Inactivo']
        if estado not in estados_validos:
            flash('Estado inválido', 'error')
            return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))
        
        with get_db_cursor() as cursor:
            # Verificar si la placa ya existe para otra empresa u otro vehículo
            cursor.execute("""
                SELECT ID_Vehiculo FROM vehiculos 
                WHERE Placa = %s AND ID_Empresa = %s AND ID_Vehiculo != %s
            """, (placa, id_empresa, id))
            
            if cursor.fetchone():
                flash('La placa ya existe para esta empresa en otro vehículo', 'error')
                return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))
            
            # Actualizar vehículo con todos los campos incluyendo estado
            cursor.execute("""
                UPDATE vehiculos 
                SET Placa = %s,
                    Marca = %s,
                    Modelo = %s,
                    Anio = %s,
                    ID_Empresa = %s,
                    Tipo_Combustible = %s,
                    Fecha_Vencimiento_Seguro = %s,
                    Estado = %s
                WHERE ID_Vehiculo = %s
            """, (placa, marca, modelo, anio, id_empresa, tipo_combustible, 
                  fecha_vencimiento_seguro, estado, id))
            
            flash('Vehículo actualizado exitosamente', 'success')
            return redirect(url_for('admin.admin_vehiculos'))
            
    except Exception as e:
        flash(f'Error al actualizar vehículo: {str(e)}', 'error')
        return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))


@admin_bp.route('/admin/vehiculos/cambiar-estado/<int:id>', methods=['POST'])
@admin_required
def cambiar_estado_vehiculo(id):
    """Cambia el estado del vehículo entre Activo/Inactivo (POST)"""
    try:
        # Obtener el nuevo estado del formulario
        nuevo_estado = request.form.get('nuevo_estado')
        
        if not nuevo_estado:
            flash('Estado no especificado', 'error')
            return redirect(url_for('admin.admin_vehiculos'))
        
        with get_db_cursor() as cursor:
            # Verificar que el vehículo existe
            cursor.execute("""
                SELECT Estado FROM vehiculos WHERE ID_Vehiculo = %s
            """, (id,))
            
            resultado = cursor.fetchone()
            if not resultado:
                flash('Vehículo no encontrado', 'error')
                return redirect(url_for('admin.admin_vehiculos'))
            
            # Actualizar solo el estado
            cursor.execute("""
                UPDATE vehiculos 
                SET Estado = %s
                WHERE ID_Vehiculo = %s
            """, (nuevo_estado, id))
            
            flash(f'Estado del vehículo actualizado a {nuevo_estado}', 'success')
            return redirect(url_for('admin.admin_vehiculos'))
            
    except Exception as e:
        flash(f'Error al cambiar estado del vehículo: {str(e)}', 'error')
        return redirect(url_for('admin.admin_vehiculos'))

