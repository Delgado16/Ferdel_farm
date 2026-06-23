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
                    f.Fecha_Creacion as Fecha,
                    f.Credito_Contado,
                    f.Observacion,
                    f.Estado,
                    'NORMAL' as Tipo_Factura,
                    COALESCE(SUM(df.Total), 0) as Total_Factura,
                    COUNT(df.ID_Detalle) as Cantidad_Productos,
                    CASE 
                        WHEN f.Credito_Contado = 0 THEN 'CONTADO'
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        ELSE 'DESCONOCIDO'
                    END as Tipo_Pago
                FROM facturacion f
                LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.IDCliente = %s 
                    AND f.Estado = 'Activa'
                GROUP BY f.ID_Factura, f.Fecha_Creacion, f.Credito_Contado, f.Observacion, f.Estado
                ORDER BY f.Fecha_Creacion DESC
                LIMIT 10
            """, (id,))
            
            facturas_normales = cursor.fetchall()
            
            # 4. Últimas facturas (facturacion ruta)
            cursor.execute("""
                SELECT 
                    fr.ID_FacturaRuta as ID_Factura,
                    fr.Fecha_Creacion as Fecha,
                    fr.Credito_Contado,
                    fr.Observacion,
                    fr.Estado,
                    'RUTA' as Tipo_Factura,
                    COALESCE(SUM(dfr.Total), 0) as Total_Factura,
                    COUNT(dfr.ID_DetalleRuta) as Cantidad_Productos,
                    CASE 
                        WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                        WHEN fr.Credito_Contado = 2 THEN 'CRÉDITO'
                        ELSE 'DESCONOCIDO'
                    END as Tipo_Pago
                FROM facturacion_ruta fr
                LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                GROUP BY fr.ID_FacturaRuta, fr.Fecha_Creacion, fr.Credito_Contado, fr.Observacion, fr.Estado
                ORDER BY fr.Fecha_Creacion DESC
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
            
            # 6. Ventas por mes - CONSULTA CORREGIDA (facturacion normal)
            cursor.execute("""
                SELECT 
                    YEAR(f.Fecha_Creacion) as Anio,
                    MONTH(f.Fecha_Creacion) as Numero_Mes,
                    MONTHNAME(f.Fecha_Creacion) as Nombre_Mes,
                    COUNT(DISTINCT f.ID_Factura) as Cantidad_Facturas,
                    COUNT(DISTINCT CASE WHEN f.Credito_Contado = 0 THEN f.ID_Factura END) as Cantidad_Contado,
                    COUNT(DISTINCT CASE WHEN f.Credito_Contado = 1 THEN f.ID_Factura END) as Cantidad_Credito,
                    COALESCE(SUM(df.Total), 0) as Total_Ventas,
                    COALESCE(SUM(CASE WHEN f.Credito_Contado = 0 THEN df.Total ELSE 0 END), 0) as Total_Contado,
                    COALESCE(SUM(CASE WHEN f.Credito_Contado = 1 THEN df.Total ELSE 0 END), 0) as Total_Credito,
                    MIN(f.Fecha_Creacion) as Primera_Factura_Mes,
                    MAX(f.Fecha_Creacion) as Ultima_Factura_Mes
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.IDCliente = %s 
                    AND f.Estado = 'Activa'
                GROUP BY YEAR(f.Fecha_Creacion), MONTH(f.Fecha_Creacion), MONTHNAME(f.Fecha_Creacion)
                ORDER BY YEAR(f.Fecha_Creacion) DESC, MONTH(f.Fecha_Creacion) DESC
            """, (id,))
            
            ventas_normales = cursor.fetchall()
            
            # 7. Ventas por mes - CONSULTA CORREGIDA (facturacion ruta)
            cursor.execute("""
                SELECT 
                    YEAR(fr.Fecha_Creacion) as Anio,
                    MONTH(fr.Fecha_Creacion) as Numero_Mes,
                    MONTHNAME(fr.Fecha_Creacion) as Nombre_Mes,
                    COUNT(DISTINCT fr.ID_FacturaRuta) as Cantidad_Facturas,
                    COUNT(DISTINCT CASE WHEN fr.Credito_Contado = 1 THEN fr.ID_FacturaRuta END) as Cantidad_Contado,
                    COUNT(DISTINCT CASE WHEN fr.Credito_Contado = 2 THEN fr.ID_FacturaRuta END) as Cantidad_Credito,
                    COALESCE(SUM(dfr.Total), 0) as Total_Ventas,
                    COALESCE(SUM(CASE WHEN fr.Credito_Contado = 1 THEN dfr.Total ELSE 0 END), 0) as Total_Contado,
                    COALESCE(SUM(CASE WHEN fr.Credito_Contado = 2 THEN dfr.Total ELSE 0 END), 0) as Total_Credito,
                    MIN(fr.Fecha_Creacion) as Primera_Factura_Mes,
                    MAX(fr.Fecha_Creacion) as Ultima_Factura_Mes
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                GROUP BY YEAR(fr.Fecha_Creacion), MONTH(fr.Fecha_Creacion), MONTHNAME(fr.Fecha_Creacion)
                ORDER BY YEAR(fr.Fecha_Creacion) DESC, MONTH(fr.Fecha_Creacion) DESC
            """, (id,))
            
            ventas_ruta = cursor.fetchall()
            
            # Combinar ventas por mes
            from collections import defaultdict
            ventas_dict = defaultdict(lambda: {
                'Cantidad_Facturas': 0,
                'Cantidad_Contado': 0,
                'Cantidad_Credito': 0,
                'Total_Ventas': 0,
                'Total_Contado': 0,
                'Total_Credito': 0,
                'Primera_Factura_Mes': None,
                'Ultima_Factura_Mes': None,
                'Nombre_Mes': ''
            })
            
            # Procesar ventas normales
            for venta in ventas_normales:
                key = f"{venta['Anio']}-{venta['Numero_Mes']}"
                ventas_dict[key]['Anio'] = venta['Anio']
                ventas_dict[key]['Numero_Mes'] = venta['Numero_Mes']
                ventas_dict[key]['Nombre_Mes'] = venta['Nombre_Mes']
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
            
            # Procesar ventas de ruta
            for venta in ventas_ruta:
                key = f"{venta['Anio']}-{venta['Numero_Mes']}"
                if key not in ventas_dict:
                    ventas_dict[key]['Anio'] = venta['Anio']
                    ventas_dict[key]['Numero_Mes'] = venta['Numero_Mes']
                    ventas_dict[key]['Nombre_Mes'] = venta['Nombre_Mes']
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
            from collections import defaultdict
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
                    AND f.Fecha_Creacion >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """, (id,))
            anio_normal = cursor.fetchone()['total'] or 0
            
            cursor.execute("""
                SELECT COALESCE(SUM(dfr.Total), 0) as total
                FROM facturacion_ruta fr
                INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Cliente = %s 
                    AND fr.Estado = 'Activa'
                    AND fr.Fecha_Creacion >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
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


