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
        ruc_cedula = request.form.get('ruc_cedula','').strip().upper()
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
                import re
                if not re.search(r'[A-Za-z]', ruc_cedula):
                    flash("El RUC/Cédula debe contener al menos una letra", "danger")
                    return redirect(url_for('admin.admin_proveedores'))
                
                clean_ruc = ruc_cedula.replace("-", "").replace(" ", "")
                cursor.execute(
                    """SELECT 1 FROM proveedores 
                    WHERE REPLACE(REPLACE(RUC_CEDULA, '-', ''), ' ', '') = %s 
                    AND ID_Empresa = %s 
                    AND Estado = 'ACTIVO'""", 
                    (clean_ruc, id_empresa)
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
                ruc_cedula = request.form.get('ruc_cedula','').strip().upper()
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
                    import re
                    if not re.search(r'[A-Za-z]', ruc_cedula):
                        flash("El RUC/Cédula debe contener al menos una letra", "danger")
                        return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                               proveedor=proveedor)
                    
                    clean_ruc = ruc_cedula.replace("-", "").replace(" ", "")
                    cursor.execute(
                        """SELECT 1 FROM proveedores 
                        WHERE REPLACE(REPLACE(RUC_CEDULA, '-', ''), ' ', '') = %s 
                        AND ID_Proveedor != %s 
                        AND ID_Empresa = %s 
                        AND Estado = 'ACTIVO'""",
                        (clean_ruc, id, id_empresa)
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


import json

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
                       (SELECT COUNT(*) FROM cuentas_por_pagar cp 
                        WHERE cp.ID_Proveedor = p.ID_Proveedor 
                          AND cp.ID_Empresa = %s 
                          AND cp.Estado IN ('Pendiente', 'Vencida', 'Parcial')) as total_facturas_pendientes
                FROM proveedores p
                WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s
            """, (id_empresa, id, id_empresa))
            
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
                WHERE cp.ID_Proveedor = %s AND cp.ID_Empresa = %s
                    AND cp.Estado IN ('Pendiente', 'Vencida', 'Parcial')
                ORDER BY cp.Fecha_Vencimiento ASC
            """, (id, id_empresa))
            
            facturas_pendientes = cursor.fetchall()
            
            for factura in facturas_pendientes:
                if factura.get('Dias_Vencido') is None:
                    factura['Dias_Vencido'] = 0

            # 3. Facturas/Cuentas ya saldadas históricas
            cursor.execute("""
                SELECT 
                    cp.ID_Cuenta,
                    cp.Num_Documento,
                    cp.Fecha,
                    cp.Fecha_Vencimiento,
                    cp.Monto_Movimiento,
                    cp.Saldo_Pendiente,
                    cp.Estado,
                    cp.Observacion
                FROM cuentas_por_pagar cp
                WHERE cp.ID_Proveedor = %s AND cp.ID_Empresa = %s
                    AND cp.Estado IN ('Pagada', 'Cancelada', 'Saldada')
                ORDER BY cp.Fecha DESC
                LIMIT 50
            """, (id, id_empresa))
            cuentas_saldadas = cursor.fetchall()
            
            # 4. Historial de Pagos y Abonos realizados
            cursor.execute("""
                SELECT 
                    'Pago Directo' as Origen,
                    pcp.ID_Pago as ID_Registro,
                    pcp.Fecha,
                    pcp.Monto as Monto_Aplicado,
                    pcp.Comentarios as Observacion,
                    COALESCE(mp.Nombre, 'Efectivo') as Metodo_Pago,
                    u.NombreUsuario as Usuario,
                    cpp.Num_Documento as Documento
                FROM pagos_cuentaspagar pcp
                INNER JOIN cuentas_por_pagar cpp ON pcp.ID_Cuenta = cpp.ID_Cuenta
                INNER JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                WHERE cpp.ID_Proveedor = %s AND cpp.ID_Empresa = %s
                
                UNION ALL
                
                SELECT 
                    'Abono CXP' as Origen,
                    apd.ID_Detalle as ID_Registro,
                    apd.Fecha,
                    apd.Monto_Aplicado,
                    CASE 
                        WHEN cpp2.Num_Documento = 'ABONO-GLOBAL' THEN 'Abono directo / Excedente a cuenta'
                        ELSE CONCAT('Abono a Doc: ', cpp2.Num_Documento)
                    END as Observacion,
                    COALESCE(mp2.Nombre, 'Efectivo') as Metodo_Pago,
                    u2.NombreUsuario as Usuario,
                    COALESCE(cpp2.Num_Documento, 'ABONO-GLOBAL') as Documento
                FROM abonos_proveedores_detalle apd
                INNER JOIN proveedores prov2 ON apd.ID_Proveedor = prov2.ID_Proveedor
                INNER JOIN usuarios u2 ON apd.ID_Usuario = u2.ID_Usuario
                LEFT JOIN metodos_pago mp2 ON apd.ID_MetodoPago = mp2.ID_MetodoPago
                LEFT JOIN cuentas_por_pagar cpp2 ON apd.ID_CuentaPagar = cpp2.ID_Cuenta
                WHERE apd.ID_Proveedor = %s AND prov2.ID_Empresa = %s
                
                ORDER BY Fecha DESC
            """, (id, id_empresa, id, id_empresa))
            historial_abonos = cursor.fetchall()
            
            ultimo_abono = historial_abonos[0] if historial_abonos else None
            
            # 5. Últimas compras (solo Activas, excluyendo Anuladas y Canceladas)
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.Fecha,
                    mi.N_Factura_Externa,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    u.NombreUsuario as Usuario_Registro
                FROM movimientos_inventario mi
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE mi.ID_Proveedor = %s AND mi.ID_Empresa = %s
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                ORDER BY mi.Fecha DESC
                LIMIT 50
            """, (id, id_empresa))
            
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
                compra['total_compra'] = float(resultado['total_compra']) if resultado and resultado['total_compra'] else 0.0
                compra['cantidad_productos'] = resultado['cantidad_productos'] if resultado and resultado['cantidad_productos'] else 0
            
            # 6. Antigüedad de saldos (Aging)
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
                WHERE cp.ID_Proveedor = %s AND cp.ID_Empresa = %s
                    AND cp.Estado IN ('Pendiente', 'Vencida', 'Parcial')
            """, (id, id_empresa))
            
            aging = cursor.fetchone()
            if not aging:
                aging = {'Rango_0_30': 0, 'Rango_31_60': 0, 'Rango_61_90': 0, 'Vencido': 0, 'Mas_90': 0}
            
            # 7. RESUMEN DE COMPRAS POR MES - EXCLUYENDO ANULADAS (Últimos 12 meses)
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
                WHERE mi.ID_Proveedor = %s AND mi.ID_Empresa = %s
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                GROUP BY YEAR(mi.Fecha), MONTH(mi.Fecha)
                ORDER BY YEAR(mi.Fecha) DESC, MONTH(mi.Fecha) DESC
                LIMIT 12
            """, (id, id_empresa))
            
            compras_por_mes = cursor.fetchall()
            
            nombres_meses = {
                1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
                7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
            }
            for mes in compras_por_mes:
                mes['Nombre_Mes'] = nombres_meses.get(mes['Numero_Mes'], f"Mes {mes['Numero_Mes']}")
            
            # 8. Top productos comprados - EXCLUYENDO ANULADAS
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
                WHERE mi.ID_Proveedor = %s AND mi.ID_Empresa = %s
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto
                ORDER BY Total_Invertido DESC
                LIMIT 10
            """, (id, id_empresa))
            
            top_productos = cursor.fetchall()
            
            # 9. Estadísticas completas y semáforo
            monto_vencido = float(aging.get('Vencido', 0) or 0)
            saldo_total = float(proveedor.get('Saldo_Pendiente') or 0)
            
            if monto_vencido > 0:
                estado_crediticio = "Con Deuda Vencida"
                color_crediticio = "danger"
            elif saldo_total > 0:
                estado_crediticio = "Con Saldo al Día"
                color_crediticio = "warning"
            else:
                estado_crediticio = "Al Día / Solvente"
                color_crediticio = "success"
                
            total_abonos_monto = sum(float(a['Monto_Aplicado'] or 0) for a in historial_abonos)
            
            stats = {
                'total_facturas': len(facturas_pendientes),
                'facturas_vencidas': sum(1 for f in facturas_pendientes if f['Estado'] == 'Vencida'),
                'saldo_total': saldo_total,
                'monto_vencido': monto_vencido,
                'estado_crediticio': estado_crediticio,
                'color_crediticio': color_crediticio,
                'total_abonos_count': len(historial_abonos),
                'total_abonos_monto': total_abonos_monto,
                'total_saldadas_count': len(cuentas_saldadas)
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
                WHERE mi.ID_Proveedor = %s AND mi.ID_Empresa = %s
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
            """, (id, id_empresa))
            totales = cursor.fetchone()
            stats.update(totales)
            
            total_inv = float(stats.get('total_invertido') or 0)
            total_comp = int(stats.get('total_compras') or 0)
            stats['ticket_promedio'] = (total_inv / total_comp) if total_comp > 0 else 0.0
            
            # Compras último año (solo Activas)
            cursor.execute("""
                SELECT COALESCE(SUM(dmi.Subtotal), 0) as total
                FROM movimientos_inventario mi
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.ID_Proveedor = %s AND mi.ID_Empresa = %s
                    AND mi.Estado = 'Activa'
                    AND mi.Estado NOT IN ('Anulada', 'Cancelada')
                    AND mi.Fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """, (id, id_empresa))
            stats['total_ultimo_anio'] = float(cursor.fetchone()['total'] or 0)
            
            # 10. Datos JSON para gráficos en frontend
            meses_ordenados = list(reversed(compras_por_mes))
            chart_labels = [f"{m['Nombre_Mes'][:3]} {m['Anio']}" for m in meses_ordenados]
            chart_contado = [float(m['Total_Contado'] or 0) for m in meses_ordenados]
            chart_credito = [float(m['Total_Credito'] or 0) for m in meses_ordenados]
            
            top_prod_labels = [p['Producto'][:20] + ('...' if len(p['Producto']) > 20 else '') for p in top_productos[:5]]
            top_prod_values = [float(p['Total_Invertido'] or 0) for p in top_productos[:5]]
            
            chart_data = {
                'labels': chart_labels,
                'contado': chart_contado,
                'credito': chart_credito,
                'top_prod_labels': top_prod_labels,
                'top_prod_values': top_prod_values
            }
            
            return render_template('admin/catalog/proveedor/detalle_proveedor.html', 
                                 proveedor=proveedor,
                                 facturas_pendientes=facturas_pendientes,
                                 cuentas_saldadas=cuentas_saldadas,
                                 historial_abonos=historial_abonos,
                                 ultimo_abono=ultimo_abono,
                                 ultimas_compras=ultimas_compras,
                                 aging=aging,
                                 compras_por_mes=compras_por_mes,
                                 top_productos=top_productos,
                                 stats=stats,
                                 chart_json=json.dumps(chart_data),
                                 today=datetime.now().date())
    
    except Exception as e:
        logging.error(f"Error al cargar detalle del proveedor: {str(e)}")
        logging.error(traceback.format_exc())
        flash(f"Error al cargar el detalle del proveedor: {str(e)}", "danger")
        return redirect(url_for("admin.admin_proveedores"))


@admin_bp.route('/catalog/proveedor/compra-detalle/<int:id_movimiento>', methods=['GET'])
@admin_bp.route('/admin/catalog/proveedor/compra-detalle/<int:id_movimiento>', methods=['GET'])
@admin_required
def admin_proveedor_compra_detalle(id_movimiento):
    """Endpoint AJAX para consultar el desglose de productos de una factura de compra"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # 1. Cabecera del movimiento de inventario / compra
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.Fecha,
                    mi.N_Factura_Externa,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    mi.Estado,
                    p.Nombre as Proveedor,
                    p.RUC_CEDULA,
                    u.NombreUsuario as Usuario_Registro
                FROM movimientos_inventario mi
                INNER JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE mi.ID_Movimiento = %s AND mi.ID_Empresa = %s
            """, (id_movimiento, id_empresa))
            
            compra = cursor.fetchone()
            if not compra:
                return jsonify({'success': False, 'error': 'Compra o factura no encontrada'}), 404
            
            # Formatear fecha de forma segura
            if compra.get('Fecha'):
                try:
                    compra['Fecha_Str'] = compra['Fecha'].strftime('%d/%m/%Y')
                except Exception:
                    compra['Fecha_Str'] = str(compra['Fecha'])
            else:
                compra['Fecha_Str'] = 'N/A'
                
            # 2. Detalle de productos comprados
            cursor.execute("""
                SELECT 
                    dmi.ID_Detalle_Movimiento,
                    p.ID_Producto,
                    p.Descripcion as Producto,
                    p.COD_Producto,
                    dmi.Cantidad,
                    dmi.Costo_Unitario,
                    dmi.Subtotal
                FROM detalle_movimientos_inventario dmi
                INNER JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento ASC
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            
            total_calculado = sum(float(item['Subtotal'] or 0) for item in detalles)
            for item in detalles:
                item['Cantidad'] = float(item['Cantidad'] or 0)
                item['Costo_Unitario'] = float(item['Costo_Unitario'] or 0)
                item['Subtotal'] = float(item['Subtotal'] or 0)
                
            return jsonify({
                'success': True,
                'compra': compra,
                'detalles': detalles,
                'total_calculado': total_calculado
            })
            
    except Exception as e:
        logging.error(f"Error al obtener detalle de compra {id_movimiento}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500



