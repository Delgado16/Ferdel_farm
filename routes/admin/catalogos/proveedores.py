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


