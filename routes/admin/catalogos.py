from decimal import Decimal
import logging
import traceback
from venv import logger
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator, registrar_bitacora
from werkzeug.security import generate_password_hash, check_password_hash

# =======================================
# ===== MODULOS DEL ADMINISTRADOR ===== #
# =======================================
# CATALOGOS ROLES
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
    
# CATALOGOS USUARIOS
@admin_bp.route('/admin/usuarios')
@admin_required
@bitacora_decorator("USUARIOS")
def admin_usuarios():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa FROM usuarios u
                JOIN roles r ON u.ID_Rol = r.ID_Rol
                JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
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
                    JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
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

#CATALOGO EMPRESA
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

# CATALOGO CLIENTES
@admin_bp.route('/admin/catalog/client/clientes', methods=['GET'])
@admin_required
@bitacora_decorator("CLIENTES")
def admin_clientes():
    # Valores por defecto
    clientes = []
    rutas = []
    productos = []
    page = 1
    per_page = 20
    total = 0
    total_pages = 1
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Obtener rutas activas para el formulario
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (id_empresa,))
            rutas = cursor.fetchall()
            
            # Obtener productos activos para el selector de producto anticipado
            cursor.execute("""
                SELECT ID_Producto, Descripcion as Nombre
                FROM productos 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activo'
                ORDER BY Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            # Validar página
            if page < 1:
                page = 1
            
            offset = (page - 1) * per_page
            
            # Consulta base ACTUALIZADA con todas las nuevas columnas de anticipos
            base_query = """
                SELECT c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                       c.ID_Empresa, c.ID_Ruta, c.Saldo_Pendiente_Total,
                       c.Fecha_Ultimo_Movimiento, c.ID_Ultima_Factura, c.Fecha_Ultimo_Pago,
                       c.Estado, c.Fecha_Creacion, c.ID_Usuario_Creacion,
                       c.tipo_cliente, c.perfil_cliente,
                       c.Anticipo_Activo, c.Limite_Anticipo_Cajas, 
                       c.Cajas_Consumidas_Anticipo, c.Saldo_Anticipos, c.Producto_Anticipado,
                       e.Nombre_Empresa, r.Nombre_Ruta,
                       p.Descripcion as Nombre_Producto_Anticipado, p.COD_Producto as Codigo_Producto_Anticipado
                FROM clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                LEFT JOIN productos p ON c.Producto_Anticipado = p.ID_Producto
                WHERE c.Estado = 'ACTIVO' 
                AND c.ID_Empresa = %s
                AND e.Estado = 'Activo'
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total ACTUALIZADO
            count_query = """
                SELECT COUNT(*) as total 
                FROM clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado = 'ACTIVO' 
                AND c.ID_Empresa = %s
                AND e.Estado = 'Activo'
            """
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Calcular total de páginas
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            
            # Validar que la página no exceda el total
            if page > total_pages and total_pages > 0:
                page = total_pages
                offset = (page - 1) * per_page
            
            # Obtener datos con paginación
            if total > 0:
                data_query = base_query + " ORDER BY c.Nombre LIMIT %s OFFSET %s"
                params.extend([per_page, offset])
                
                cursor.execute(data_query, params)
                clientes = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/client/clientes: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los clientes. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/client/clientes.html", 
                        clientes=clientes, 
                        rutas=rutas,
                        productos=productos,
                        page=page,
                        per_page=per_page,
                        total=total,
                        total_pages=total_pages,
                        search=search_query)

@admin_bp.route('/admin/catalog/client/crear-cliente', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-CREAR")
def admin_crear_cliente():
    try:
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        direccion = request.form.get("direccion", "").strip()
        ruc_cedula = request.form.get("ruc_cedula", "").strip()
        tipo_cliente = request.form.get("tipo_cliente", "Comun").strip()
        perfil_cliente = request.form.get("perfil_cliente", "Mercado").strip()
        id_ruta = request.form.get("id_ruta", "").strip()
        
        # NUEVOS CAMPOS DE ANTICIPO
        anticipo_activo = request.form.get("anticipo_activo", "0").strip()
        limite_anticipo_cajas = request.form.get("limite_anticipo_cajas", "0").strip()
        saldo_anticipos = request.form.get("saldo_anticipos", "0").strip()
        producto_anticipado = request.form.get("producto_anticipado", "").strip()
        
        id_usuario = current_user.id
        id_empresa = session.get('id_empresa', 1)

        # Validaciones básicas
        if not nombre:
            flash("El nombre del cliente es obligatorio.", "danger")
            return redirect(url_for("admin.admin_clientes"))
        
        if not telefono:
            flash("El teléfono del cliente es obligatorio.", "danger")
            return redirect(url_for("admin.admin_clientes"))
        
        if not id_usuario:
            flash("Error de autenticación. Por favor, inicie sesión nuevamente.", "danger")
            return redirect(url_for("admin.admin_clientes"))
        
        # NUEVAS VALIDACIONES DE ANTICIPO
        anticipo_activo = 1 if anticipo_activo == "1" else 0
        
        try:
            limite_anticipo_cajas = int(limite_anticipo_cajas) if limite_anticipo_cajas else 0
            if limite_anticipo_cajas < 0:
                limite_anticipo_cajas = 0
        except ValueError:
            limite_anticipo_cajas = 0
        
        try:
            saldo_anticipos = float(saldo_anticipos) if saldo_anticipos else 0
            if saldo_anticipos < 0:
                saldo_anticipos = 0
        except ValueError:
            saldo_anticipos = 0
        
        if producto_anticipado:
            try:
                producto_anticipado = int(producto_anticipado)
                if producto_anticipado <= 0:
                    producto_anticipado = None
            except (ValueError, TypeError):
                producto_anticipado = None
        else:
            producto_anticipado = None
        
        # Validar tipo de cliente
        if tipo_cliente not in ['Comun', 'Especial']:
            tipo_cliente = 'Comun'
        
        # Validar perfil de cliente
        if perfil_cliente not in ['Ruta', 'Mayorista', 'Mercado', 'Especial']:
            perfil_cliente = 'Mercado'
        
        # Validar ID_Ruta (puede ser opcional)
        if id_ruta:
            try:
                id_ruta = int(id_ruta)
                if id_ruta <= 0:
                    id_ruta = None
            except (ValueError, TypeError):
                id_ruta = None
        else:
            id_ruta = None
        
        with get_db_cursor() as cursor:
            # Verificar que la empresa existe y está activa
            cursor.execute(
                "SELECT 1 FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", 
                (id_empresa,)
            )
            empresa_activa = cursor.fetchone()
            
            if not empresa_activa:
                flash("Empresa no válida o inactiva.", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # Si se proporcionó una ruta, verificar que existe y pertenece a la empresa
            if id_ruta:
                cursor.execute(
                    """SELECT 1 FROM rutas 
                    WHERE ID_Ruta = %s 
                    AND ID_Empresa = %s 
                    AND Estado = 'Activa'""",
                    (id_ruta, id_empresa)
                )
                ruta_valida = cursor.fetchone()
                if not ruta_valida:
                    flash("La ruta seleccionada no es válida o está inactiva.", "danger")
                    return redirect(url_for("admin.admin_clientes"))
            
            # Si se proporcionó un producto anticipado, verificar que existe
            if producto_anticipado:
                cursor.execute(
                    """SELECT 1 FROM productos 
                    WHERE ID_Producto = %s AND ID_Empresa = %s AND Estado = 'Activo'""",
                    (producto_anticipado, id_empresa)
                )
                producto_valido = cursor.fetchone()
                if not producto_valido:
                    flash("El producto anticipado seleccionado no es válido.", "danger")
                    return redirect(url_for("admin.admin_clientes"))
            
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    """SELECT 1 FROM clientes 
                    WHERE RUC_CEDULA = %s 
                    AND ID_Empresa = %s 
                    AND Estado = 'ACTIVO'""", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un cliente con este RUC/Cédula", "danger")
                    return redirect(url_for("admin.admin_clientes"))

            # Validación adicional para anticipos activos
            if anticipo_activo == 1:
                if limite_anticipo_cajas == 0 and saldo_anticipos == 0 and not producto_anticipado:
                    flash("Si activa anticipos, debe configurar al menos: límite de cajas, saldo o producto anticipado.", "danger")
                    return redirect(url_for("admin.admin_clientes"))

            # Insertar nuevo cliente con todos los campos incluyendo anticipos
            cursor.execute("""
                INSERT INTO clientes 
                (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, 
                 ID_Usuario_Creacion, tipo_cliente, perfil_cliente, ID_Ruta,
                 Saldo_Pendiente_Total, Estado,
                 Anticipo_Activo, Limite_Anticipo_Cajas, Saldo_Anticipos, 
                 Producto_Anticipado, Cajas_Consumidas_Anticipo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, 
                  id_usuario, tipo_cliente, perfil_cliente, id_ruta,
                  0.00, 'ACTIVO',
                  anticipo_activo, limite_anticipo_cajas, saldo_anticipos,
                  producto_anticipado, 0))
            
            flash("Cliente agregado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al crear cliente: {str(e)}", exc_info=True)
        flash("Error al guardar el cliente", "danger")
    
    return redirect(url_for("admin.admin_clientes"))

@admin_bp.route('/admin/catalog/client/editar-cliente/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-EDITAR")
def admin_editar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Obtener rutas activas para el formulario
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (id_empresa,))
            rutas = cursor.fetchall()
            
            # Obtener productos activos para el selector de producto anticipado
            cursor.execute("""
                SELECT ID_Producto, Descripcion, COD_Producto
                FROM productos 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activo'
                ORDER BY Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            # Verificar que el cliente existe y obtener todos sus datos incluyendo anticipos
            cursor.execute(
                """SELECT c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                          c.ID_Empresa, c.ID_Ruta, c.Saldo_Pendiente_Total,
                          c.Fecha_Ultimo_Movimiento, c.ID_Ultima_Factura, c.Fecha_Ultimo_Pago,
                          c.Estado, c.Fecha_Creacion, c.ID_Usuario_Creacion,
                          c.tipo_cliente, c.perfil_cliente,
                          c.Anticipo_Activo, c.Limite_Anticipo_Cajas, 
                          c.Cajas_Consumidas_Anticipo, c.Saldo_Anticipos, c.Producto_Anticipado,
                          r.Nombre_Ruta
                   FROM clientes c
                   INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                   LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                   WHERE c.ID_Cliente = %s 
                   AND c.ID_Empresa = %s 
                   AND e.Estado = 'Activo'
                """,
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # MÉTODO GET - Mostrar formulario
            if request.method == 'GET':
                return render_template("admin/catalog/client/editar_clientes.html", 
                                     cliente=cliente, 
                                     rutas=rutas,
                                     productos=productos)
            
            # MÉTODO POST - Procesar formulario
            elif request.method == 'POST':
                nombre = request.form.get("nombre", "").strip()
                telefono = request.form.get("telefono", "").strip()
                direccion = request.form.get("direccion", "").strip()
                ruc_cedula = request.form.get("ruc_cedula", "").strip()
                estado = request.form.get("estado", "ACTIVO").strip()
                tipo_cliente = request.form.get("tipo_cliente", "Comun").strip()
                perfil_cliente = request.form.get("perfil_cliente", "Mercado").strip()
                id_ruta = request.form.get("id_ruta", "").strip()
                
                # NUEVOS CAMPOS DE ANTICIPO
                anticipo_activo = request.form.get("anticipo_activo", "0").strip()
                limite_anticipo_cajas = request.form.get("limite_anticipo_cajas", "0").strip()
                saldo_anticipos = request.form.get("saldo_anticipos", "0").strip()
                producto_anticipado = request.form.get("producto_anticipado", "").strip()
                cajas_consumidas = request.form.get("cajas_consumidas_anticipo", "0").strip()

                # Validaciones básicas
                if not nombre:
                    flash("El nombre del cliente es obligatorio.", "danger")
                    return render_template("admin/catalog/client/editar_clientes.html", 
                                         cliente=cliente, rutas=rutas, productos=productos)
                
                if not telefono:
                    flash("El teléfono del cliente es obligatorio.", "danger")
                    return render_template("admin/catalog/client/editar_clientes.html", 
                                         cliente=cliente, rutas=rutas, productos=productos)
                
                # Validar estado
                if estado not in ['ACTIVO', 'INACTIVO']:
                    estado = 'ACTIVO'
                
                # Validar tipo de cliente
                if tipo_cliente not in ['Comun', 'Especial']:
                    tipo_cliente = 'Comun'
                
                # Validar perfil de cliente
                if perfil_cliente not in ['Ruta', 'Mayorista', 'Mercado', 'Especial']:
                    perfil_cliente = 'Mercado'
                
                # NUEVAS VALIDACIONES DE ANTICIPO
                anticipo_activo = 1 if anticipo_activo == "1" else 0
                
                try:
                    limite_anticipo_cajas = int(limite_anticipo_cajas) if limite_anticipo_cajas else 0
                    if limite_anticipo_cajas < 0:
                        limite_anticipo_cajas = 0
                except ValueError:
                    limite_anticipo_cajas = 0
                
                try:
                    saldo_anticipos = float(saldo_anticipos) if saldo_anticipos else 0
                    if saldo_anticipos < 0:
                        saldo_anticipos = 0
                except ValueError:
                    saldo_anticipos = 0
                
                try:
                    cajas_consumidas = int(cajas_consumidas) if cajas_consumidas else 0
                    if cajas_consumidas < 0:
                        cajas_consumidas = 0
                    # Validar que no exceda el límite
                    if cajas_consumidas > limite_anticipo_cajas and limite_anticipo_cajas > 0:
                        cajas_consumidas = limite_anticipo_cajas
                except ValueError:
                    cajas_consumidas = 0
                
                if producto_anticipado:
                    try:
                        producto_anticipado = int(producto_anticipado)
                        if producto_anticipado <= 0:
                            producto_anticipado = None
                    except (ValueError, TypeError):
                        producto_anticipado = None
                else:
                    producto_anticipado = None
                
                # Validar ID_Ruta
                if id_ruta:
                    try:
                        id_ruta = int(id_ruta)
                        if id_ruta <= 0:
                            id_ruta = None
                    except (ValueError, TypeError):
                        id_ruta = None
                        
                    if id_ruta:
                        cursor.execute(
                            """SELECT 1 FROM rutas 
                            WHERE ID_Ruta = %s 
                            AND ID_Empresa = %s 
                            AND Estado = 'Activa'""",
                            (id_ruta, id_empresa)
                        )
                        ruta_valida = cursor.fetchone()
                        if not ruta_valida:
                            flash("La ruta seleccionada no es válida o está inactiva.", "danger")
                            return render_template("admin/catalog/client/editar_clientes.html", 
                                                 cliente=cliente, rutas=rutas, productos=productos)
                else:
                    id_ruta = None
                
                # Validar producto anticipado
                if producto_anticipado:
                    cursor.execute(
                        """SELECT 1 FROM productos 
                        WHERE ID_Producto = %s AND ID_Empresa = %s AND Estado = 'Activo'""",
                        (producto_anticipado, id_empresa)
                    )
                    producto_valido = cursor.fetchone()
                    if not producto_valido:
                        flash("El producto anticipado seleccionado no es válido.", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", 
                                             cliente=cliente, rutas=rutas, productos=productos)
                
                # Validación adicional para anticipos activos
                if anticipo_activo == 1:
                    if limite_anticipo_cajas == 0 and saldo_anticipos == 0 and not producto_anticipado:
                        flash("Si activa anticipos, debe configurar al menos: límite de cajas, saldo o producto anticipado.", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", 
                                             cliente=cliente, rutas=rutas, productos=productos)

                # Verificar si el RUC/Cédula ya existe en otro cliente activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        """SELECT 1 FROM clientes 
                        WHERE RUC_CEDULA = %s 
                        AND ID_Cliente != %s 
                        AND ID_Empresa = %s 
                        AND Estado = 'ACTIVO'""",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro cliente activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", 
                                             cliente=cliente, rutas=rutas, productos=productos)

                # UPDATE ACTUALIZADO con campos de anticipo
                cursor.execute("""
                    UPDATE clientes 
                    SET Nombre = %s, 
                        Telefono = %s, 
                        Direccion = %s, 
                        RUC_CEDULA = %s, 
                        Estado = %s,
                        tipo_cliente = %s,
                        perfil_cliente = %s,
                        ID_Ruta = %s,
                        Anticipo_Activo = %s,
                        Limite_Anticipo_Cajas = %s,
                        Saldo_Anticipos = %s,
                        Producto_Anticipado = %s,
                        Cajas_Consumidas_Anticipo = %s
                    WHERE ID_Cliente = %s 
                    AND ID_Empresa = %s
                """, (nombre, telefono, direccion, ruc_cedula, estado, 
                      tipo_cliente, perfil_cliente, id_ruta,
                      anticipo_activo, limite_anticipo_cajas, saldo_anticipos,
                      producto_anticipado, cajas_consumidas, id, id_empresa))
                
                # Registrar en bitácora
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Cliente {accion} correctamente.", "success")
                
                return redirect(url_for("admin.admin_clientes"))
                
    except Exception as e:
        logging.error(f"Error en edición de cliente: {str(e)}", exc_info=True)
        flash("Error al procesar la solicitud", "danger")
        return redirect(url_for("admin.admin_clientes"))
    
    return redirect(url_for("admin.admin_clientes"))

@admin_bp.route('/admin/catalog/client/eliminar-cliente/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-ELIMINAR")
def admin_eliminar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente pertenece a la empresa actual y está activo
            cursor.execute(
                """SELECT c.* 
                FROM clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s 
                AND c.Estado = 'ACTIVO' AND e.Estado = 'Activo'""",
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # Eliminar (cambiar estado a INACTIVO)
            cursor.execute(
                "UPDATE clientes SET Estado = 'INACTIVO' WHERE ID_Cliente = %s AND ID_Empresa = %s",
                (id, id_empresa)
            )
            
            flash("Cliente eliminado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al eliminar cliente: {str(e)}")
        flash("Error al eliminar el cliente", "danger")
    
    return redirect(url_for("admin.admin_clientes"))

@admin_bp.route('/admin/catalog/detalle-cliente/<int:id>', methods=['GET'])
@admin_required
@bitacora_decorator("DETALLE_CLIENTE")
def admin_detalle_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # 1. Datos básicos del cliente
            cursor.execute("""
                SELECT c.*, 
                       r.Nombre_Ruta,
                       COUNT(DISTINCT cxc.ID_Movimiento) as total_facturas_pendientes
                FROM clientes c
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                LEFT JOIN cuentas_por_cobrar cxc ON c.ID_Cliente = cxc.ID_Cliente 
                    AND cxc.Estado IN ('Pendiente', 'Vencida')
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s
                GROUP BY c.ID_Cliente
            """, (id, id_empresa))
            
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # 2. Cuentas por cobrar pendientes
            cursor.execute("""
                SELECT 
                    cxc.ID_Movimiento,
                    cxc.Num_Documento,
                    cxc.Fecha,
                    cxc.Fecha_Vencimiento,
                    cxc.Monto_Movimiento,
                    cxc.Saldo_Pendiente,
                    cxc.Estado,
                    cxc.Observacion,
                    DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) AS Dias_Vencido,
                    CASE 
                        WHEN cxc.Estado = 'Vencida' THEN 'danger'
                        WHEN cxc.Estado = 'Pendiente' AND cxc.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'warning'
                        WHEN cxc.Estado = 'Pendiente' THEN 'success'
                        ELSE 'secondary'
                    END as Color_Estado
                FROM cuentas_por_cobrar cxc
                WHERE cxc.ID_Cliente = %s 
                    AND cxc.Estado IN ('Pendiente', 'Vencida')
                ORDER BY cxc.Fecha_Vencimiento ASC
            """, (id,))
            
            cuentas_pendientes = cursor.fetchall()
            
            for cuenta in cuentas_pendientes:
                if cuenta.get('Dias_Vencido') is None:
                    cuenta['Dias_Vencido'] = 0
            
            # 3. Últimas facturas (facturacion normal)
            cursor.execute("""
                SELECT 
                    f.ID_Factura as ID_Factura,
                    f.Fecha,
                    f.Credito_Contado,
                    f.Observacion,
                    f.Estado,
                    'NORMAL' as Tipo_Factura,
                    COALESCE(SUM(df.Total), 0) as Total_Factura,
                    COUNT(df.ID_Detalle) as Cantidad_Productos
                FROM facturacion f
                LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.IDCliente = %s 
                    AND f.Estado = 'Activa'
                GROUP BY f.ID_Factura
                ORDER BY f.Fecha DESC
                LIMIT 10
            """, (id,))
            
            facturas_normales = cursor.fetchall()
            
            # 4. Últimas facturas (facturacion ruta)
            cursor.execute("""
                SELECT 
                    fr.ID_FacturaRuta as ID_Factura,
                    fr.Fecha,
                    fr.Credito_Contado,
                    fr.Observacion,
                    fr.Estado,
                    'RUTA' as Tipo_Factura,
                    COALESCE(SUM(dfr.Total), 0) as Total_Factura,
                    COUNT(dfr.ID_DetalleRuta) as Cantidad_Productos
                FROM facturacion_ruta fr
                LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                GROUP BY fr.ID_FacturaRuta
                ORDER BY fr.Fecha DESC
                LIMIT 10
            """, (id,))
            
            facturas_ruta = cursor.fetchall()
            
            # Combinar y ordenar las facturas
            ultimas_facturas = list(facturas_normales) + list(facturas_ruta)
            ultimas_facturas.sort(key=lambda x: x['Fecha'] if x['Fecha'] else datetime.min.date(), reverse=True)
            ultimas_facturas = ultimas_facturas[:10]
            
            # 5. Antigüedad de saldos (Aging)
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE 
                        WHEN cxc.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) 
                        THEN cxc.Saldo_Pendiente ELSE 0 END), 0) as Rango_0_30,
                    COALESCE(SUM(CASE 
                        WHEN cxc.Fecha_Vencimiento BETWEEN DATE_ADD(CURDATE(), INTERVAL 31 DAY) AND DATE_ADD(CURDATE(), INTERVAL 60 DAY) 
                        THEN cxc.Saldo_Pendiente ELSE 0 END), 0) as Rango_31_60,
                    COALESCE(SUM(CASE 
                        WHEN cxc.Fecha_Vencimiento BETWEEN DATE_ADD(CURDATE(), INTERVAL 61 DAY) AND DATE_ADD(CURDATE(), INTERVAL 90 DAY) 
                        THEN cxc.Saldo_Pendiente ELSE 0 END), 0) as Rango_61_90,
                    COALESCE(SUM(CASE 
                        WHEN cxc.Fecha_Vencimiento < CURDATE() 
                        THEN cxc.Saldo_Pendiente ELSE 0 END), 0) as Vencido,
                    COALESCE(SUM(CASE 
                        WHEN cxc.Fecha_Vencimiento > DATE_ADD(CURDATE(), INTERVAL 90 DAY) 
                        THEN cxc.Saldo_Pendiente ELSE 0 END), 0) as Mas_90
                FROM cuentas_por_cobrar cxc
                WHERE cxc.ID_Cliente = %s 
                    AND cxc.Estado IN ('Pendiente', 'Vencida')
            """, (id,))
            
            aging = cursor.fetchone()
            if not aging:
                aging = {'Rango_0_30': 0, 'Rango_31_60': 0, 'Rango_61_90': 0, 'Vencido': 0, 'Mas_90': 0}
            
            # 6. Ventas por mes (facturacion normal)
            cursor.execute("""
                SELECT 
                    YEAR(f.Fecha) as Anio,
                    MONTH(f.Fecha) as Numero_Mes,
                    COUNT(DISTINCT f.ID_Factura) as Cantidad_Facturas,
                    COUNT(DISTINCT CASE WHEN f.Credito_Contado = 1 THEN f.ID_Factura END) as Cantidad_Contado,
                    COUNT(DISTINCT CASE WHEN f.Credito_Contado = 2 THEN f.ID_Factura END) as Cantidad_Credito,
                    COALESCE(SUM(df.Total), 0) as Total_Ventas,
                    COALESCE(SUM(CASE WHEN f.Credito_Contado = 1 THEN df.Total ELSE 0 END), 0) as Total_Contado,
                    COALESCE(SUM(CASE WHEN f.Credito_Contado = 2 THEN df.Total ELSE 0 END), 0) as Total_Credito,
                    MIN(f.Fecha) as Primera_Factura_Mes,
                    MAX(f.Fecha) as Ultima_Factura_Mes
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.IDCliente = %s 
                    AND f.Estado = 'Activa'
                GROUP BY YEAR(f.Fecha), MONTH(f.Fecha)
            """, (id,))
            
            ventas_normales = cursor.fetchall()
            
            # 7. Ventas por mes (facturacion ruta)
            cursor.execute("""
                SELECT 
                    YEAR(fr.Fecha) as Anio,
                    MONTH(fr.Fecha) as Numero_Mes,
                    COUNT(DISTINCT fr.ID_FacturaRuta) as Cantidad_Facturas,
                    COUNT(DISTINCT CASE WHEN fr.Credito_Contado = 1 THEN fr.ID_FacturaRuta END) as Cantidad_Contado,
                    COUNT(DISTINCT CASE WHEN fr.Credito_Contado = 2 THEN fr.ID_FacturaRuta END) as Cantidad_Credito,
                    COALESCE(SUM(dfr.Total), 0) as Total_Ventas,
                    COALESCE(SUM(CASE WHEN fr.Credito_Contado = 1 THEN dfr.Total ELSE 0 END), 0) as Total_Contado,
                    COALESCE(SUM(CASE WHEN fr.Credito_Contado = 2 THEN dfr.Total ELSE 0 END), 0) as Total_Credito,
                    MIN(fr.Fecha) as Primera_Factura_Mes,
                    MAX(fr.Fecha) as Ultima_Factura_Mes
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                GROUP BY YEAR(fr.Fecha), MONTH(fr.Fecha)
            """, (id,))
            
            ventas_ruta = cursor.fetchall()
            
            # Combinar ventas por mes
            ventas_dict = defaultdict(lambda: {
                'Cantidad_Facturas': 0,
                'Cantidad_Contado': 0,
                'Cantidad_Credito': 0,
                'Total_Ventas': 0,
                'Total_Contado': 0,
                'Total_Credito': 0,
                'Primera_Factura_Mes': None,
                'Ultima_Factura_Mes': None
            })
            
            for venta in ventas_normales:
                key = f"{venta['Anio']}-{venta['Numero_Mes']}"
                ventas_dict[key]['Anio'] = venta['Anio']
                ventas_dict[key]['Numero_Mes'] = venta['Numero_Mes']
                ventas_dict[key]['Cantidad_Facturas'] += venta['Cantidad_Facturas']
                ventas_dict[key]['Cantidad_Contado'] += venta['Cantidad_Contado']
                ventas_dict[key]['Cantidad_Credito'] += venta['Cantidad_Credito']
                ventas_dict[key]['Total_Ventas'] += float(venta['Total_Ventas'] or 0)
                ventas_dict[key]['Total_Contado'] += float(venta['Total_Contado'] or 0)
                ventas_dict[key]['Total_Credito'] += float(venta['Total_Credito'] or 0)
                if venta['Primera_Factura_Mes'] and (not ventas_dict[key]['Primera_Factura_Mes'] or venta['Primera_Factura_Mes'] < ventas_dict[key]['Primera_Factura_Mes']):
                    ventas_dict[key]['Primera_Factura_Mes'] = venta['Primera_Factura_Mes']
                if venta['Ultima_Factura_Mes'] and (not ventas_dict[key]['Ultima_Factura_Mes'] or venta['Ultima_Factura_Mes'] > ventas_dict[key]['Ultima_Factura_Mes']):
                    ventas_dict[key]['Ultima_Factura_Mes'] = venta['Ultima_Factura_Mes']
            
            for venta in ventas_ruta:
                key = f"{venta['Anio']}-{venta['Numero_Mes']}"
                if key not in ventas_dict:
                    ventas_dict[key]['Anio'] = venta['Anio']
                    ventas_dict[key]['Numero_Mes'] = venta['Numero_Mes']
                ventas_dict[key]['Cantidad_Facturas'] += venta['Cantidad_Facturas']
                ventas_dict[key]['Cantidad_Contado'] += venta['Cantidad_Contado']
                ventas_dict[key]['Cantidad_Credito'] += venta['Cantidad_Credito']
                ventas_dict[key]['Total_Ventas'] += float(venta['Total_Ventas'] or 0)
                ventas_dict[key]['Total_Contado'] += float(venta['Total_Contado'] or 0)
                ventas_dict[key]['Total_Credito'] += float(venta['Total_Credito'] or 0)
                if venta['Primera_Factura_Mes'] and (not ventas_dict[key]['Primera_Factura_Mes'] or venta['Primera_Factura_Mes'] < ventas_dict[key]['Primera_Factura_Mes']):
                    ventas_dict[key]['Primera_Factura_Mes'] = venta['Primera_Factura_Mes']
                if venta['Ultima_Factura_Mes'] and (not ventas_dict[key]['Ultima_Factura_Mes'] or venta['Ultima_Factura_Mes'] > ventas_dict[key]['Ultima_Factura_Mes']):
                    ventas_dict[key]['Ultima_Factura_Mes'] = venta['Ultima_Factura_Mes']
            
            ventas_por_mes = sorted(ventas_dict.values(), key=lambda x: (x['Anio'], x['Numero_Mes']), reverse=True)
            
            # 8. Top productos comprados (facturacion normal)
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion as Producto,
                    p.COD_Producto,
                    COALESCE(SUM(df.Cantidad), 0) as Cantidad_Total,
                    COALESCE(SUM(df.Total), 0) as Total_Vendido
                FROM detalle_facturacion df
                INNER JOIN facturacion f ON df.ID_Factura = f.ID_Factura
                INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                WHERE f.IDCliente = %s 
                    AND f.Estado = 'Activa'
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto
            """, (id,))
            
            top_productos_normal = cursor.fetchall()
            
            # 9. Top productos comprados (facturacion ruta)
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion as Producto,
                    p.COD_Producto,
                    COALESCE(SUM(dfr.Cantidad), 0) as Cantidad_Total,
                    COALESCE(SUM(dfr.Total), 0) as Total_Vendido
                FROM detalle_facturacion_ruta dfr
                INNER JOIN facturacion_ruta fr ON dfr.ID_FacturaRuta = fr.ID_FacturaRuta
                INNER JOIN productos p ON dfr.ID_Producto = p.ID_Producto
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto
            """, (id,))
            
            top_productos_ruta = cursor.fetchall()
            
            # Combinar top productos
            productos_dict = defaultdict(lambda: {'Cantidad_Total': 0, 'Total_Vendido': 0})
            for prod in top_productos_normal:
                key = prod['ID_Producto']
                productos_dict[key]['ID_Producto'] = prod['ID_Producto']
                productos_dict[key]['Producto'] = prod['Producto']
                productos_dict[key]['COD_Producto'] = prod['COD_Producto']
                productos_dict[key]['Cantidad_Total'] += float(prod['Cantidad_Total'] or 0)
                productos_dict[key]['Total_Vendido'] += float(prod['Total_Vendido'] or 0)
            
            for prod in top_productos_ruta:
                key = prod['ID_Producto']
                if key not in productos_dict:
                    productos_dict[key]['ID_Producto'] = prod['ID_Producto']
                    productos_dict[key]['Producto'] = prod['Producto']
                    productos_dict[key]['COD_Producto'] = prod['COD_Producto']
                productos_dict[key]['Cantidad_Total'] += float(prod['Cantidad_Total'] or 0)
                productos_dict[key]['Total_Vendido'] += float(prod['Total_Vendido'] or 0)
            
            top_productos = sorted(productos_dict.values(), key=lambda x: x['Total_Vendido'], reverse=True)[:10]
            
            # 10. Anticipos activos del cliente (con barra de progreso)
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    p.Descripcion as Producto,
                    p.COD_Producto,
                    a.Cantidad_Cajas,
                    a.Cajas_Consumidas,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Restantes,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    a.Fecha_Anticipo,
                    a.Fecha_Vencimiento,
                    a.Estado,
                    ROUND((a.Cajas_Consumidas / a.Cantidad_Cajas) * 100, 1) as Porcentaje_Consumido,
                    ROUND(((a.Cantidad_Cajas - a.Cajas_Consumidas) / a.Cantidad_Cajas) * 100, 1) as Porcentaje_Restante
                FROM anticipos_clientes a
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Cliente = %s AND a.Estado = 'ACTIVO'
                ORDER BY a.Fecha_Vencimiento ASC
            """, (id,))
            
            anticipos = cursor.fetchall()
            
            # 11. Últimas entregas del cliente (consumos de anticipos)
            cursor.execute("""
                SELECT 
                    e.ID_Entrega,
                    e.Fecha_Entrega,
                    e.Cantidad_Cajas,
                    e.Precio_Unitario,
                    e.Total,
                    e.Notas,
                    p.Descripcion as Producto,
                    p.COD_Producto,
                    e.Usa_Anticipo
                FROM entregas e
                INNER JOIN productos p ON e.ID_Producto = p.ID_Producto
                WHERE e.ID_Cliente = %s 
                    AND e.Usa_Anticipo = 1
                ORDER BY e.Fecha_Entrega DESC
                LIMIT 10
            """, (id,))
            
            ultimas_entregas = cursor.fetchall()
            
            # 12. Último abono del cliente
            cursor.execute("""
                SELECT 
                    ad.ID_Detalle,
                    ad.Monto_Aplicado,
                    ad.Fecha,
                    ad.Saldo_Anterior,
                    ad.Saldo_Nuevo,
                    mp.Nombre as Metodo_Pago,
                    u.NombreUsuario as Vendedor,
                    a.Nombre_Ruta as Ruta,
                    cxc.Num_Documento as Documento
                FROM abonos_detalle ad
                LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON ad.ID_Usuario = u.ID_Usuario
                LEFT JOIN asignacion_vendedores av ON ad.ID_Asignacion = av.ID_Asignacion
                LEFT JOIN rutas a ON av.ID_Ruta = a.ID_Ruta
                LEFT JOIN cuentas_por_cobrar cxc ON ad.ID_CuentaCobrar = cxc.ID_Movimiento
                WHERE ad.ID_Cliente = %s
                ORDER BY ad.Fecha DESC
                LIMIT 1
            """, (id,))
            
            ultimo_abono = cursor.fetchone()
            
            # 13. Estadísticas rápidas
            stats = {
                'total_facturas_pendientes': len(cuentas_pendientes),
                'facturas_vencidas': sum(1 for f in cuentas_pendientes if f['Estado'] == 'Vencida'),
                'saldo_total': float(cliente.get('Saldo_Pendiente_Total') or 0),
                'monto_vencido': float(aging.get('Vencido', 0) or 0),
                'anticipos_activos': len(anticipos),
                'total_anticipado': sum(float(a.get('Saldo_Restante') or 0) for a in anticipos)
            }
            
            # Calcular total de ventas
            cursor.execute("""
                SELECT COALESCE(SUM(df.Total), 0) as total_ventas
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.IDCliente = %s AND f.Estado = 'Activa'
            """, (id,))
            total_normal = cursor.fetchone()['total_ventas'] or 0
            
            cursor.execute("""
                SELECT COALESCE(SUM(dfr.Total), 0) as total_ventas
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s AND fr.Estado = 'Activa'
            """, (id,))
            total_ruta = cursor.fetchone()['total_ventas'] or 0
            
            stats['total_ventas'] = float(total_normal) + float(total_ruta)
            
            # Ventas último año
            cursor.execute("""
                SELECT COALESCE(SUM(df.Total), 0) as total
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.IDCliente = %s 
                    AND f.Estado = 'Activa'
                    AND f.Fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """, (id,))
            anio_normal = cursor.fetchone()['total'] or 0
            
            cursor.execute("""
                SELECT COALESCE(SUM(dfr.Total), 0) as total
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                    AND fr.Fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """, (id,))
            anio_ruta = cursor.fetchone()['total'] or 0
            
            stats['total_ultimo_anio'] = float(anio_normal) + float(anio_ruta)
            
            return render_template('admin/catalog/client/detalle_clientes.html', 
                                 cliente=cliente,
                                 cuentas_pendientes=cuentas_pendientes,
                                 ultimas_facturas=ultimas_facturas,
                                 aging=aging,
                                 ventas_por_mes=ventas_por_mes,
                                 top_productos=top_productos,
                                 anticipos=anticipos,
                                 ultimas_entregas=ultimas_entregas,
                                 ultimo_abono=ultimo_abono,
                                 stats=stats,
                                 today=datetime.now().date())
    
    except Exception as e:
        logging.error(f"Error al cargar detalle del cliente: {str(e)}")
        logging.error(traceback.format_exc())
        flash(f"Error al cargar el detalle del cliente: {str(e)}", "danger")
        return redirect(url_for("admin.admin_clientes"))

# SUCURSALES DE CLIENTES
@admin_bp.route('/admin/catalog/client/sucursales')
@admin_required
@bitacora_decorator("SUCURSALES_CLIENTES")
def admin_sucursales_clientes():
    try:
        with get_db_cursor() as cursor:
            # Obtener todas las sucursales activas con información de clientes
            cursor.execute("""
                SELECT s.ID_Sucursal, s.Nombre_Sucursal, s.Direccion, s.Telefono, 
                       s.Encargado, s.Estado, s.Fecha_Creacion,
                       s.ID_Cliente, c.Nombre as Nombre_Cliente
                FROM sucursales s
                INNER JOIN clientes c ON s.ID_Cliente = c.ID_Cliente
                WHERE s.Estado = 'ACTIVO'
                ORDER BY c.Nombre, s.Nombre_Sucursal
            """)
            sucursales = cursor.fetchall()
            
            # Obtener lista de clientes activos para el formulario
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA, Direccion 
                FROM clientes 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            clientes = cursor.fetchall()
            
            return render_template("admin/catalog/client/sucursales_clientes.html", 
                                 sucursales=sucursales, 
                                 clientes=clientes)
    except Exception as e:
        logging.error(f"Error al cargar sucursales de clientes: {str(e)}")
        flash("Error al cargar las sucursales de clientes", "danger")
        return render_template("admin/catalog/client/sucursales_clientes.html", 
                             sucursales=[], clientes=[])

@admin_bp.route('/admin/catalog/client/sucursales/create', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_SUCURSAL")
def admin_sucursales_create():
    try:
        # Obtener datos del formulario
        id_cliente = request.form.get('id_cliente')
        nombre_sucursal = request.form.get('nombre_sucursal', '').strip().upper()
        direccion = request.form.get('direccion', '').strip()
        telefono = request.form.get('telefono', '').strip()
        encargado = request.form.get('encargado', '').strip().upper()
        
        # Validaciones
        if not id_cliente:
            flash("Debe seleccionar un cliente", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        if not nombre_sucursal:
            flash("El nombre de la sucursal es obligatorio", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        if len(nombre_sucursal) < 3:
            flash("El nombre de la sucursal debe tener al menos 3 caracteres", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente existe y está activo
            cursor.execute("""
                SELECT ID_Cliente, Nombre FROM clientes 
                WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
            """, (id_cliente,))
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("El cliente seleccionado no existe o está inactivo", "danger")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Verificar si ya existe una sucursal con el mismo nombre para ese cliente
            cursor.execute("""
                SELECT ID_Sucursal FROM sucursales 
                WHERE ID_Cliente = %s AND Nombre_Sucursal = %s AND Estado = 'ACTIVO'
            """, (id_cliente, nombre_sucursal))
            
            if cursor.fetchone():
                flash(f"Ya existe una sucursal activa con el nombre '{nombre_sucursal}' para el cliente {cliente['Nombre']}", "warning")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Insertar nueva sucursal
            cursor.execute("""
                INSERT INTO sucursales (ID_Cliente, Nombre_Sucursal, Direccion, Telefono, Encargado, Estado, Fecha_Creacion)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVO', %s)
            """, (id_cliente, nombre_sucursal, direccion, telefono, encargado, datetime.now()))
            
            flash(f"Sucursal '{nombre_sucursal}' creada exitosamente para el cliente {cliente['Nombre']}", "success")
            
    except Exception as e:
        logging.error(f"Error al crear sucursal: {str(e)}")
        flash("Error al crear la sucursal. Por favor, intente nuevamente", "danger")
    
    return redirect(url_for('admin.admin_sucursales_clientes'))

@admin_bp.route('/admin/catalog/client/sucursales/edit/<int:id_sucursal>', methods=['POST'])
@admin_required
@bitacora_decorator("EDITAR_SUCURSAL")
def admin_sucursales_edit(id_sucursal):
    try:
        # Obtener datos del formulario
        nombre_sucursal = request.form.get('nombre_sucursal', '').strip().upper()
        direccion = request.form.get('direccion', '').strip()
        telefono = request.form.get('telefono', '').strip()
        encargado = request.form.get('encargado', '').strip().upper()
        
        if not nombre_sucursal:
            flash("El nombre de la sucursal es obligatorio", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        with get_db_cursor() as cursor:
            # Verificar que la sucursal existe
            cursor.execute("SELECT ID_Sucursal, ID_Cliente, Nombre_Sucursal FROM sucursales WHERE ID_Sucursal = %s", (id_sucursal,))
            sucursal = cursor.fetchone()
            
            if not sucursal:
                flash("La sucursal no existe", "danger")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Verificar si el nuevo nombre ya existe para el mismo cliente (excluyendo la sucursal actual)
            cursor.execute("""
                SELECT ID_Sucursal FROM sucursales 
                WHERE ID_Cliente = %s AND Nombre_Sucursal = %s AND ID_Sucursal != %s AND Estado = 'ACTIVO'
            """, (sucursal['ID_Cliente'], nombre_sucursal, id_sucursal))
            
            if cursor.fetchone():
                flash(f"Ya existe otra sucursal con el nombre '{nombre_sucursal}' para este cliente", "warning")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Actualizar sucursal
            cursor.execute("""
                UPDATE sucursales 
                SET Nombre_Sucursal = %s, Direccion = %s, Telefono = %s, Encargado = %s
                WHERE ID_Sucursal = %s
            """, (nombre_sucursal, direccion, telefono, encargado, id_sucursal))
            
            flash("Sucursal actualizada exitosamente", "success")
            
    except Exception as e:
        logging.error(f"Error al editar sucursal {id_sucursal}: {str(e)}")
        flash("Error al actualizar la sucursal", "danger")
    
    return redirect(url_for('admin.admin_sucursales_clientes'))

@admin_bp.route('/admin/catalog/client/sucursales/delete/<int:id_sucursal>')
@admin_required
@bitacora_decorator("ELIMINAR_SUCURSAL")
def admin_sucursales_delete(id_sucursal):
    try:
        with get_db_cursor() as cursor:
            # Obtener nombre de la sucursal antes de desactivar
            cursor.execute("SELECT Nombre_Sucursal FROM sucursales WHERE ID_Sucursal = %s", (id_sucursal,))
            sucursal = cursor.fetchone()
            
            if not sucursal:
                flash("La sucursal no existe", "danger")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Desactivar la sucursal
            cursor.execute("""
                UPDATE sucursales 
                SET Estado = 'INACTIVO' 
                WHERE ID_Sucursal = %s
            """, (id_sucursal,))
            
            flash(f"Sucursal '{sucursal['Nombre_Sucursal']}' desactivada exitosamente", "success")
            
    except Exception as e:
        logging.error(f"Error al eliminar sucursal {id_sucursal}: {str(e)}")
        flash("Error al eliminar la sucursal", "danger")
    
    return redirect(url_for('admin.admin_sucursales_clientes'))

@admin_bp.route('/admin/catalog/client/sucursales/get/<int:id_sucursal>')
@admin_required
def admin_sucursales_get(id_sucursal):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Sucursal, ID_Cliente, Nombre_Sucursal, Direccion, 
                       Telefono, Encargado, Estado
                FROM sucursales 
                WHERE ID_Sucursal = %s
            """, (id_sucursal,))
            
            sucursal = cursor.fetchone()
            if sucursal:
                return jsonify({'success': True, 'data': sucursal})
            else:
                return jsonify({'success': False, 'error': 'Sucursal no encontrada'})
                
    except Exception as e:
        logging.error(f"Error al obtener sucursal {id_sucursal}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# CATALOGO PROVEEDORES
@admin_bp.route('/admin/catalog/proveedor/proveedores', methods=['GET'])
@admin_required
@bitacora_decorator("PROVEEDORES")
def admin_proveedores():
    # Valores por defecto
    proveedores = []
    page = 1
    per_page = 20
    total = 0
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            offset = (page - 1) * per_page
            
            # Consulta base (incluyendo Saldo_Pendiente)
            base_query = """
                SELECT p.*, e.Nombre_Empresa
                FROM proveedores p
                INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total
            count_query = "SELECT COUNT(*) as total FROM proveedores p WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s"
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Obtener datos con paginación
            data_query = base_query + " ORDER BY p.Nombre LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(data_query, params)
            proveedores = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/proveedor/proveedores: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los proveedores. Por favor intenta nuevamente.", "danger")
    
    return render_template("admin/catalog/proveedor/proveedores.html", 
                        proveedores=proveedores, 
                        page=page,
                        per_page=per_page,
                        total=total,
                        search=search_query)
    
@admin_bp.route('/admin/catalog/proveedor/crear-proveedor', methods=['POST'])  
@admin_required
@bitacora_decorator("PROVEEDORES-CREAR")
def admin_crear_proveedor():
    try:
        nombre = request.form.get('nombre','').strip()
        telefono = request.form.get('telefono','').strip()
        direccion = request.form.get('direccion','').strip()
        ruc_cedula = request.form.get('ruc_cedula','').strip()
        saldo_pendiente = request.form.get('saldo_pendiente', '0.00').strip()
        id_usuario = session.get('id_usuario',1)
        id_empresa = session.get('id_empresa',1)
        
        if not nombre:
            flash("El nombre del proveedor es obligatorio","danger")
            return redirect(url_for('admin.admin_proveedores'))
        
        # Convertir saldo pendiente a decimal
        try:
            saldo_pendiente = float(saldo_pendiente) if saldo_pendiente else 0.00
        except ValueError:
            saldo_pendiente = 0.00
        
        with get_db_cursor() as cursor:
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    "SELECT 1 FROM proveedores WHERE RUC_CEDULA = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un proveedor con este RUC/Cédula", "danger")
                    return redirect(url_for("admin.admin_proveedores"))

            # Insertar nuevo proveedor (incluyendo Saldo_Pendiente)
            cursor.execute("""
                INSERT INTO proveedores (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, ID_Usuario_Creacion, Saldo_Pendiente)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, id_usuario, saldo_pendiente))
            
            flash("Proveedor agregado correctamente.", "success")
    except Exception as e:
        logging.error(f"Error al crear proveedor: {str(e)}")
        flash("Error al guardar el proveedor", "danger")
    return redirect(url_for('admin.admin_proveedores'))

@admin_bp.route('/admin/catalog/proveedor/editar-proveedor/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-EDITAR")
def admin_editar_proveedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                           SELECT p.* 
                           FROM proveedores p
                           INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND e.Estado = 'Activo'
                           """, (id, id_empresa))
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado.", "danger")
                return redirect(url_for("admin.admin_proveedores"))
            
            if request.method == 'GET':
                return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                       proveedor=proveedor)
                
            elif request.method == 'POST':
                nombre = request.form.get('nombre','').strip()
                telefono = request.form.get('telefono','').strip()
                direccion = request.form.get('direccion','').strip()
                ruc_cedula = request.form.get('ruc_cedula','').strip()
                estado = request.form.get('estado','ACTIVO').strip()
                saldo_pendiente = request.form.get('saldo_pendiente', '0.00').strip()
                
                if not nombre:
                    flash("El nombre del proveedor es obligatorio","danger")
                    return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                           proveedor=proveedor)
                
                # Convertir saldo pendiente a decimal
                try:
                    saldo_pendiente = float(saldo_pendiente) if saldo_pendiente else 0.00
                except ValueError:
                    saldo_pendiente = 0.00
                
                # Verificar si el RUC/Cédula ya existe en otro proveedor activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        "SELECT 1 FROM proveedores WHERE RUC_CEDULA = %s AND ID_Proveedor != %s AND ID_Empresa = %s AND Estado = 'ACTIVO'",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro proveedor activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                               proveedor=proveedor)
                
                # Actualizar proveedor (incluyendo Saldo_Pendiente)
                cursor.execute("""
                               UPDATE proveedores 
                               SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s, Estado = %s, Saldo_Pendiente = %s
                               WHERE ID_Proveedor = %s AND ID_Empresa = %s
                               """, (nombre, telefono, direccion, ruc_cedula, estado, saldo_pendiente, id, id_empresa))
                
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Proveedor {accion} correctamente.","success")
                
                return redirect(url_for("admin.admin_proveedores"))
            
    except Exception as e:
        logging.error(f"Error en edición de proveedor: {str(e)}")
        flash("Error al procesar la solicitud","danger")
        return redirect(url_for("admin.admin_proveedores"))

    return redirect(url_for("admin.admin_proveedores"))

@admin_bp.route('/admin/catalog/proveedor/eliminar-proveedor/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-ELIMINAR")
def admin_eliminar_proveedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            #verificar que el proveedor pertenece a la empresa
            cursor.execute("""
                           SELECT p.*
                           FROM proveedores p
                           INNER JOIN empresa e On p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND p.Estado = 'ACTIVO' AND e.Estado = 'Activo'
                           """, (id, id_empresa)
                        )
            
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado","danger")
                return redirect(url_for("admin.admin_proveedores"))

            #Eliminar (cambiar estado a INACTIVO)
            cursor.execute("""
                           UPDATE proveedores SET Estado = 'INACTIVO' 
                           WHERE ID_Proveedor = %s AND ID_Empresa = %s
                           """, (id, id_empresa)
                           )
            
            flash("Proveedor eliminado correctamente.","success")
    
    except Exception as e:
        logging.error(f"Error al eliminar proveedor: {str(e)}")
        flash("Error al eliminar el proveedor","danger")
    
    return redirect(url_for("admin.admin_proveedores"))

@admin_bp.route('/admin/catalog/detalle-proveedor/<int:id>', methods=['GET'])
@admin_required
@bitacora_decorator("DETALLE_PROVEEDOR")
def admin_detalle_proveedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # 1. Datos básicos del proveedor
            cursor.execute("""
                SELECT p.*, 
                       COUNT(DISTINCT cp.ID_Cuenta) as total_facturas_pendientes
                FROM proveedores p
                LEFT JOIN cuentas_por_pagar cp ON p.ID_Proveedor = cp.ID_Proveedor 
                    AND cp.Estado IN ('Pendiente', 'Vencida', 'Parcial')
                WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s
                GROUP BY p.ID_Proveedor
            """, (id, id_empresa))
            
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado", "danger")
                return redirect(url_for("admin.admin_proveedores"))
            
            # 2. Facturas pendientes del proveedor
            cursor.execute("""
                SELECT 
                    cp.ID_Cuenta,
                    cp.Num_Documento,
                    cp.Fecha,
                    cp.Fecha_Vencimiento,
                    cp.Monto_Movimiento,
                    cp.Saldo_Pendiente,
                    cp.Estado,
                    cp.Observacion,
                    DATEDIFF(CURDATE(), cp.Fecha_Vencimiento) AS Dias_Vencido,
                    CASE 
                        WHEN cp.Estado = 'Vencida' THEN 'danger'
                        WHEN cp.Estado = 'Pendiente' AND cp.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'warning'
                        WHEN cp.Estado = 'Pendiente' THEN 'success'
                        WHEN cp.Estado = 'Parcial' THEN 'info'
                        ELSE 'secondary'
                    END as Color_Estado
                FROM cuentas_por_pagar cp
                WHERE cp.ID_Proveedor = %s 
                    AND cp.Estado IN ('Pendiente', 'Vencida', 'Parcial')
                ORDER BY cp.Fecha_Vencimiento ASC
            """, (id,))
            
            facturas_pendientes = cursor.fetchall()
            
            for factura in facturas_pendientes:
                if factura.get('Dias_Vencido') is None:
                    factura['Dias_Vencido'] = 0
            
            # 3. Últimas compras (solo Activas, excluyendo Anuladas y Canceladas)
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.Fecha,
                    mi.N_Factura_Externa,
                    mi.Tipo_Compra,
                    mi.Observacion
                FROM movimientos_inventario mi
                WHERE mi.ID_Proveedor = %s 
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                ORDER BY mi.Fecha DESC
                LIMIT 10
            """, (id,))
            
            ultimas_compras = cursor.fetchall()
            
            # Calcular totales por compra
            for compra in ultimas_compras:
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(Subtotal), 0) as total_compra,
                        COUNT(*) as cantidad_productos
                    FROM detalle_movimientos_inventario
                    WHERE ID_Movimiento = %s
                """, (compra['ID_Movimiento'],))
                resultado = cursor.fetchone()
                compra['total_compra'] = resultado['total_compra'] if resultado['total_compra'] else 0
                compra['cantidad_productos'] = resultado['cantidad_productos'] if resultado['cantidad_productos'] else 0
            
            # 4. Detalle de productos comprados
            if ultimas_compras:
                ids_movimientos = [compra['ID_Movimiento'] for compra in ultimas_compras]
                placeholders = ','.join(['%s'] * len(ids_movimientos))
                
                cursor.execute(f"""
                    SELECT 
                        dmi.ID_Movimiento,
                        p.ID_Producto,
                        p.Descripcion as Producto,
                        p.COD_Producto,
                        dmi.Cantidad,
                        dmi.Costo_Unitario,
                        dmi.Subtotal
                    FROM detalle_movimientos_inventario dmi
                    JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE dmi.ID_Movimiento IN ({placeholders})
                    ORDER BY dmi.ID_Movimiento DESC, dmi.ID_Detalle_Movimiento ASC
                """, tuple(ids_movimientos))
                
                detalle_compras = cursor.fetchall()
            else:
                detalle_compras = []
            
            # 5. Antigüedad de saldos (Aging)
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE 
                        WHEN cp.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY) 
                        THEN cp.Saldo_Pendiente ELSE 0 END), 0) as Rango_0_30,
                    COALESCE(SUM(CASE 
                        WHEN cp.Fecha_Vencimiento BETWEEN DATE_ADD(CURDATE(), INTERVAL 31 DAY) AND DATE_ADD(CURDATE(), INTERVAL 60 DAY) 
                        THEN cp.Saldo_Pendiente ELSE 0 END), 0) as Rango_31_60,
                    COALESCE(SUM(CASE 
                        WHEN cp.Fecha_Vencimiento BETWEEN DATE_ADD(CURDATE(), INTERVAL 61 DAY) AND DATE_ADD(CURDATE(), INTERVAL 90 DAY) 
                        THEN cp.Saldo_Pendiente ELSE 0 END), 0) as Rango_61_90,
                    COALESCE(SUM(CASE 
                        WHEN cp.Fecha_Vencimiento < CURDATE() 
                        THEN cp.Saldo_Pendiente ELSE 0 END), 0) as Vencido,
                    COALESCE(SUM(CASE 
                        WHEN cp.Fecha_Vencimiento > DATE_ADD(CURDATE(), INTERVAL 90 DAY) 
                        THEN cp.Saldo_Pendiente ELSE 0 END), 0) as Mas_90
                FROM cuentas_por_pagar cp
                WHERE cp.ID_Proveedor = %s 
                    AND cp.Estado IN ('Pendiente', 'Vencida', 'Parcial')
            """, (id,))
            
            aging = cursor.fetchone()
            if not aging:
                aging = {'Rango_0_30': 0, 'Rango_31_60': 0, 'Rango_61_90': 0, 'Vencido': 0, 'Mas_90': 0}
            
            # 6. RESUMEN DE COMPRAS POR MES - EXCLUYENDO ANULADAS
            cursor.execute("""
                SELECT 
                    YEAR(mi.Fecha) as Anio,
                    MONTH(mi.Fecha) as Numero_Mes,
                    COUNT(DISTINCT mi.ID_Movimiento) as Cantidad_Compras,
                    COUNT(DISTINCT CASE WHEN mi.Tipo_Compra = 'CONTADO' THEN mi.ID_Movimiento END) as Cantidad_Contado,
                    COUNT(DISTINCT CASE WHEN mi.Tipo_Compra = 'CREDITO' THEN mi.ID_Movimiento END) as Cantidad_Credito,
                    COALESCE(SUM(dmi.Subtotal), 0) as Total_Compras,
                    COALESCE(SUM(CASE WHEN mi.Tipo_Compra = 'CONTADO' THEN dmi.Subtotal ELSE 0 END), 0) as Total_Contado,
                    COALESCE(SUM(CASE WHEN mi.Tipo_Compra = 'CREDITO' THEN dmi.Subtotal ELSE 0 END), 0) as Total_Credito,
                    COALESCE(AVG(dmi.Subtotal), 0) as Promedio_Compra,
                    MIN(mi.Fecha) as Primera_Compra_Mes,
                    MAX(mi.Fecha) as Ultima_Compra_Mes
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.ID_Proveedor = %s 
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                GROUP BY YEAR(mi.Fecha), MONTH(mi.Fecha)
                ORDER BY Anio DESC, Numero_Mes DESC
            """, (id,))
            
            compras_por_mes = cursor.fetchall()
            
            # 7. Top productos comprados - EXCLUYENDO ANULADAS
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion as Producto,
                    p.COD_Producto,
                    COALESCE(SUM(dmi.Cantidad), 0) as Cantidad_Total,
                    COALESCE(SUM(dmi.Subtotal), 0) as Total_Invertido,
                    COUNT(DISTINCT mi.ID_Movimiento) as Veces_Comprado
                FROM detalle_movimientos_inventario dmi
                INNER JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                WHERE mi.ID_Proveedor = %s 
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto
                ORDER BY Total_Invertido DESC
                LIMIT 10
            """, (id,))
            
            top_productos = cursor.fetchall()
            
            # 8. Estadísticas completas - EXCLUYENDO ANULADAS
            stats = {
                'total_facturas': len(facturas_pendientes),
                'facturas_vencidas': sum(1 for f in facturas_pendientes if f['Estado'] == 'Vencida'),
                'saldo_total': float(proveedor.get('Saldo_Pendiente') or 0),
                'monto_vencido': float(aging.get('Vencido', 0) or 0),
            }
            
            # Totales generales de compras (solo Activas)
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT mi.ID_Movimiento) as total_compras,
                    COALESCE(SUM(dmi.Subtotal), 0) as total_invertido,
                    COALESCE(SUM(CASE WHEN mi.Tipo_Compra = 'CONTADO' THEN dmi.Subtotal ELSE 0 END), 0) as total_contado,
                    COALESCE(SUM(CASE WHEN mi.Tipo_Compra = 'CREDITO' THEN dmi.Subtotal ELSE 0 END), 0) as total_credito
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.ID_Proveedor = %s 
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
            """, (id,))
            totales = cursor.fetchone()
            stats.update(totales)
            
            # Compras último año (solo Activas)
            cursor.execute("""
                SELECT COALESCE(SUM(dmi.Subtotal), 0) as total
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.ID_Proveedor = %s 
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                    AND mi.Fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """, (id,))
            stats['total_ultimo_anio'] = float(cursor.fetchone()['total'] or 0)
            
            return render_template('admin/catalog/proveedor/detalle_proveedor.html', 
                                 proveedor=proveedor,
                                 facturas_pendientes=facturas_pendientes,
                                 ultimas_compras=ultimas_compras,
                                 detalle_compras=detalle_compras,
                                 aging=aging,
                                 compras_por_mes=compras_por_mes,
                                 top_productos=top_productos,
                                 stats=stats,
                                 today=datetime.now().date())
    
    except Exception as e:
        logging.error(f"Error al cargar detalle del proveedor: {str(e)}")
        logging.error(traceback.format_exc())
        flash(f"Error al cargar el detalle del proveedor: {str(e)}", "danger")
        return redirect(url_for("admin.admin_proveedores"))

# CATALOGO MEDIDAS
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

# CATALOGO CATEGORIAS
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

# CATALOGO METODOS DE PAGO
@admin_bp.route('/admin/catalog/metodospagos/metodo-pagos', methods=['GET'])
@admin_required
@bitacora_decorator("METODOS-PAGO")
def admin_metodos_pago():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM Metodos_Pago 
                ORDER BY ID_MetodoPago DESC
            """)
            metodos = cursor.fetchall()
            return render_template('admin/catalog/metodospagos/metodo_pagos.html', 
                                 metodos=metodos)
    except Exception as e:
        flash(f"Error al cargar métodos de pago: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/catalog/metodospagos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-CREAR")
def admin_metodos_pago_crear():
    try:
        nombre = request.form.get('nombre', '').strip()

        if not nombre:
            flash("El nombre del método de pago es requerido", "danger")
            return redirect(url_for('admin.admin_metodos_pago'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Metodos_Pago (Nombre) 
                VALUES (%s)
            """, (nombre,))

        flash("Método de pago creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear método de pago: {str(e)}", "danger")
    return redirect(url_for('admin.admin_metodos_pago'))

@admin_bp.route('/admin/catalog/metodospagos/editar/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-EDITAR")
def admin_metodos_pago_editar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # GET
            if request.method == 'GET':
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM Metodos_Pago
                    WHERE ID_MetodoPago = %s 
                               """,(id,))
                
                metodo = cursor.fetchone()

                if not metodo:
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                return render_template('admin/catalog/metodospagos/editar_metodo_pago.html',
                                       metodo=metodo)
            
            #POST
            elif request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()

                if not nombre:
                    flash("El nombre del método de pago es requerido", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                cursor.execute("""
                        SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s   
                        """, (id,))
                
                if not cursor.fetchone():
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                cursor.execute("""
                    UPDATE Metodos_Pago
                    SET Nombre = %s
                    WHERE ID_MetodoPago = %s
                    """, (nombre, id))
                
                flash("Metodo d epago actualizado exitosamente", "success")
                return redirect(url_for('admin.admin_metodos_pago'))

    except Exception as e:
        flash(f"Error al editar método de pago: {str(e)}", "danger")
        return redirect(url_for('admin.admin_metodos_pago'))

@admin_bp.route('/admin/catalog/metodospagos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-ELIMINAR")
def admin_metodos_pago_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s
            """, (id,))

            if not cursor.fetchone():
                flash("Método de pago no encontrado.", "danger")
                return redirect(url_for('admin.admin_metodos_pago'))
            
            cursor.execute("""
                DELETE FROM Metodos_Pago
                WHERE ID_MetodoPago = %s
            """, (id,))

        flash("Metodos de pago eliminado exitosamente", "success")
            
    except Exception as e:
        #Manejar error de integridad referencial
        if "foreing key constraint" in str(e).lower():
            flash("No se puede eliminar el método de pago porque está asociado a otros registros.", "danger")
        else:
            flash(f"Error al eliminar método de pago: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_metodos_pago'))

#CATALOGO MOVIMINETOS DE INVENTARIO
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

# CATALOGO TIPOS DE GASTOS
# ========== GESTIÓN DE TIPOS DE GASTO ==========
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

# ========== GESTIÓN DE SUBCATEGORÍAS ==========
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

#### RUTAS #####
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

## VEHICULOS
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
 