import logging
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user
from config.database import get_db_cursor
from auth.decorators import admin_required
from helpers.bitacora import bitacora_decorator
from helpers.cruce_cuentas import procesar_compensacion_vinculada, auto_compensar_saldos_mutuos
from . import admin_bp

logger = logging.getLogger(__name__)

@admin_bp.route('/admin/cruce-cuentas', methods=['GET'])
@admin_required
@bitacora_decorator("ADMIN-CRUCE-CUENTAS-LISTADO")
def admin_cruce_cuentas():
    """
    Vista principal de Cruce de Cuentas / Contrapartes vinculadas.
    Muestra únicamente los Clientes y Proveedores que tienen la opción activa de
    vinculación bilateral (Cruce de Cuentas / Contraparte), consolidando sus
    ventas, compras, abonos y saldos compensables.
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id if current_user.is_authenticated else 1

        with get_db_cursor(commit=True) as cursor:
            # 1. Ejecutar auto-compensación en segundo plano si hay saldos mutuos pendientes
            try:
                auto_compensar_saldos_mutuos(cursor, id_empresa=id_empresa, id_usuario=id_usuario)
            except Exception as e_auto:
                logger.warning(f"Aviso en auto_compensar_saldos_mutuos: {e_auto}")

            # 2. Obtener todas las parejas de clientes y proveedores vinculados
            cursor.execute("""
                SELECT DISTINCT
                    c.ID_Cliente,
                    c.Nombre as Cliente_Nombre,
                    c.RUC_CEDULA as Cliente_RUC,
                    c.Telefono as Cliente_Telefono,
                    c.Direccion as Cliente_Direccion,
                    c.Saldo_Pendiente_Total as Saldo_Cliente,
                    c.Estado as Cliente_Estado,
                    c.ID_Proveedor_Vinculado,
                    p.ID_Proveedor,
                    p.Nombre as Proveedor_Nombre,
                    p.RUC_CEDULA as Proveedor_RUC,
                    p.Telefono as Proveedor_Telefono,
                    p.Direccion as Proveedor_Direccion,
                    p.Saldo_Pendiente as Saldo_Proveedor,
                    p.Estado as Proveedor_Estado,
                    p.ID_Cliente_Vinculado
                FROM clientes c
                INNER JOIN proveedores p ON (c.ID_Proveedor_Vinculado = p.ID_Proveedor OR p.ID_Cliente_Vinculado = c.ID_Cliente)
                WHERE (c.ID_Proveedor_Vinculado IS NOT NULL OR p.ID_Cliente_Vinculado IS NOT NULL)
                  AND c.ID_Empresa = %s
                  AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                ORDER BY c.Nombre ASC
            """, (id_empresa, id_empresa))
            parejas_raw = cursor.fetchall()

            contrapartes = []
            total_saldo_cxc_global = 0.0
            total_saldo_cxp_global = 0.0
            total_compensable_global = 0.0

            for par in parejas_raw:
                id_cli = par['ID_Cliente']
                id_prov = par['ID_Proveedor']

                saldo_cxc = float(par.get('Saldo_Cliente') or 0.0)
                saldo_cxp = float(par.get('Saldo_Proveedor') or 0.0)
                diferencia = saldo_cxc - saldo_cxp
                saldo_neto = abs(diferencia)
                monto_compensable = min(saldo_cxc, saldo_cxp) if saldo_cxc > 0.001 and saldo_cxp > 0.001 else 0.0

                total_saldo_cxc_global += saldo_cxc
                total_saldo_cxp_global += saldo_cxp
                total_compensable_global += monto_compensable

                if monto_compensable > 0.001:
                    estado_balance = 'COMPENSABLE'
                    estado_label = 'Compensable Inmediato'
                    color_balance = 'warning'
                elif saldo_cxc > 0.001 and saldo_cxp <= 0.001:
                    estado_balance = 'FAVOR_EMPRESA'
                    estado_label = 'Saldo a Favor de FerDel'
                    color_balance = 'primary'
                elif saldo_cxp > 0.001 and saldo_cxc <= 0.001:
                    estado_balance = 'FAVOR_CONTRAPARTE'
                    estado_label = 'Saldo a Favor de Contraparte'
                    color_balance = 'danger'
                else:
                    estado_balance = 'SALDADO'
                    estado_label = 'Al Día / Compensado'
                    color_balance = 'success'

                # --- 3. Métricas de Ventas al Cliente ---
                cursor.execute("""
                    SELECT 
                        COUNT(f.ID_Factura) as total_ventas,
                        COALESCE(SUM(df.Total), 0) as monto_ventas,
                        MAX(f.Fecha) as ultima_fecha_venta
                    FROM facturacion f
                    LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    WHERE f.IDCliente = %s AND f.Estado = 'Activa'
                """, (id_cli,))
                res_ventas = cursor.fetchone() or {}

                # --- 4. Métricas de Compras al Proveedor ---
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT mi.ID_Movimiento) as total_compras,
                        COALESCE(SUM(dmi.Subtotal), 0) as monto_compras,
                        MAX(mi.Fecha) as ultima_fecha_compra
                    FROM movimientos_inventario mi
                    LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                    WHERE mi.ID_Proveedor = %s AND mi.ID_TipoMovimiento = 1 AND mi.Estado = 'Activa'
                """, (id_prov,))
                res_compras = cursor.fetchone() or {}

                # --- 5. Abonos y Cobros de CxC ---
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_abonos,
                        COALESCE(SUM(Monto_Aplicado), 0) as monto_abonos
                    FROM abonos_general
                    WHERE ID_Cliente = %s
                """, (id_cli,))
                res_abonos_cli = cursor.fetchone() or {}

                # --- 6. Abonos y Pagos a Proveedor (CxP) ---
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_pagos,
                        COALESCE(SUM(Monto_Aplicado), 0) as monto_pagos
                    FROM abonos_proveedores_detalle
                    WHERE ID_Proveedor = %s
                """, (id_prov,))
                res_pagos_prov = cursor.fetchone() or {}

                # --- 7. Total Cruces / Compensaciones mutuas registradas ---
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_cruces,
                        COALESCE(SUM(Monto_Aplicado), 0) as monto_cruzado
                    FROM abonos_general
                    WHERE ID_Cliente = %s AND (caja_movimientos = 'Cruce de Cuentas' OR caja_movimientos LIKE '%Cruce%')
                """, (id_cli,))
                res_cruces = cursor.fetchone() or {}

                # --- 8. Facturas y Movimientos Recientes para Desglose Rápido ---
                cursor.execute("""
                    SELECT f.ID_Factura, f.Fecha, 
                           COALESCE((SELECT SUM(Total) FROM detalle_facturacion df WHERE df.ID_Factura = f.ID_Factura), 0) as Total,
                           f.Credito_Contado, f.Estado
                    FROM facturacion f
                    WHERE f.IDCliente = %s
                    ORDER BY f.Fecha DESC, f.ID_Factura DESC
                    LIMIT 5
                """, (id_cli,))
                ultimas_ventas = cursor.fetchall() or []

                cursor.execute("""
                    SELECT mi.ID_Movimiento, mi.Fecha, 
                           COALESCE((SELECT SUM(Subtotal) FROM detalle_movimientos_inventario dmi WHERE dmi.ID_Movimiento = mi.ID_Movimiento), 0) as Total,
                           mi.Tipo_Compra, mi.Estado
                    FROM movimientos_inventario mi
                    WHERE mi.ID_Proveedor = %s AND mi.ID_TipoMovimiento = 1
                    ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
                    LIMIT 5
                """, (id_prov,))
                ultimas_compras = cursor.fetchall() or []

                cursor.execute("""
                    SELECT ag.ID_Detalle, ag.Fecha, ag.Monto_Aplicado, ag.caja_movimientos, mp.Nombre as Metodo
                    FROM abonos_general ag
                    LEFT JOIN metodos_pago mp ON ag.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE ag.ID_Cliente = %s
                    ORDER BY ag.Fecha DESC, ag.ID_Detalle DESC
                    LIMIT 5
                """, (id_cli,))
                ultimos_abonos_cli = cursor.fetchall() or []

                cursor.execute("""
                    SELECT apd.ID_Detalle, apd.Fecha, apd.Monto_Aplicado, apd.Detalles_Metodo, apd.Comentarios, mp.Nombre as Metodo
                    FROM abonos_proveedores_detalle apd
                    LEFT JOIN metodos_pago mp ON apd.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE apd.ID_Proveedor = %s
                    ORDER BY apd.Fecha DESC, apd.ID_Detalle DESC
                    LIMIT 5
                """, (id_prov,))
                ultimos_pagos_prov = cursor.fetchall() or []

                contrapartes.append({
                    'cliente': {
                        'id': id_cli,
                        'nombre': par['Cliente_Nombre'],
                        'ruc': par['Cliente_RUC'],
                        'telefono': par['Cliente_Telefono'],
                        'estado': par['Cliente_Estado'],
                        'saldo_cxc': saldo_cxc,
                        'total_ventas_count': res_ventas.get('total_ventas', 0),
                        'total_ventas_monto': float(res_ventas.get('monto_ventas') or 0.0),
                        'ultima_fecha_venta': res_ventas.get('ultima_fecha_venta'),
                        'total_abonos_monto': float(res_abonos_cli.get('monto_abonos') or 0.0),
                        'ultimas_ventas': ultimas_ventas,
                        'ultimos_abonos': ultimos_abonos_cli
                    },
                    'proveedor': {
                        'id': id_prov,
                        'nombre': par['Proveedor_Nombre'],
                        'ruc': par['Proveedor_RUC'],
                        'telefono': par['Proveedor_Telefono'],
                        'estado': par['Proveedor_Estado'],
                        'saldo_cxp': saldo_cxp,
                        'total_compras_count': res_compras.get('total_compras', 0),
                        'total_compras_monto': float(res_compras.get('monto_compras') or 0.0),
                        'ultima_fecha_compra': res_compras.get('ultima_fecha_compra'),
                        'total_pagos_monto': float(res_pagos_prov.get('monto_pagos') or 0.0),
                        'ultimas_compras': ultimas_compras,
                        'ultimos_pagos': ultimos_pagos_prov
                    },
                    'balance': {
                        'saldo_cxc': saldo_cxc,
                        'saldo_cxp': saldo_cxp,
                        'saldo_neto': saldo_neto,
                        'diferencia': diferencia,
                        'monto_compensable': monto_compensable,
                        'estado': estado_balance,
                        'label': estado_label,
                        'color': color_balance,
                        'total_cruzado_historico': float(res_cruces.get('monto_cruzado') or 0.0),
                        'total_cruces_count': res_cruces.get('total_cruces', 0)
                    }
                })

            resumen_global = {
                'total_contrapartes': len(contrapartes),
                'total_saldo_cxc': total_saldo_cxc_global,
                'total_saldo_cxp': total_saldo_cxp_global,
                'total_compensable': total_compensable_global,
                'saldo_neto_global': abs(total_saldo_cxc_global - total_saldo_cxp_global),
                'diferencia_global': total_saldo_cxc_global - total_saldo_cxp_global
            }

            return render_template(
                'admin/finanzas/cruce_cuentas.html',
                contrapartes=contrapartes,
                resumen=resumen_global
            )

    except Exception as e:
        logger.error(f"Error en admin_cruce_cuentas: {e}", exc_info=True)
        flash(f"Error al cargar el panel de Cruce de Cuentas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/cruce-cuentas/aplicar', methods=['POST'])
@admin_required
@bitacora_decorator("ADMIN-CRUCE-CUENTAS-APLICAR")
def admin_cruce_cuentas_aplicar():
    """
    Ejecuta una compensación / cruce de cuentas directo entre un cliente y un proveedor vinculados.
    Permite cruzar todo el monto compensable o un monto específico ingresado por el usuario.
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id if current_user.is_authenticated else 1

        id_cliente = request.form.get('id_cliente', type=int)
        id_proveedor = request.form.get('id_proveedor', type=int)
        monto_str = request.form.get('monto_cruce', '').strip()
        observacion = request.form.get('observacion', 'Cruce manual desde panel de Cruce de Cuentas').strip()

        if not id_cliente or not id_proveedor:
            flash("Debe especificar cliente y proveedor vinculados para aplicar el cruce.", "warning")
            return redirect(url_for('admin.admin_cruce_cuentas'))

        monto_especifico = None
        if monto_str:
            try:
                monto_val = float(monto_str)
                if monto_val > 0:
                    monto_especifico = monto_val
            except ValueError:
                pass

        with get_db_cursor(commit=True) as cursor:
            res = procesar_compensacion_vinculada(
                cursor,
                id_cliente=id_cliente,
                id_proveedor=id_proveedor,
                id_empresa=id_empresa,
                id_usuario=id_usuario,
                monto_especifico=monto_especifico,
                observacion=observacion
            )

            if res.get('success') and res.get('monto_compensado', 0) > 0:
                flash(f"✅ ¡Cruce aplicado exitosamente! {res.get('mensaje')}", "success")
            else:
                flash(res.get('mensaje', 'No se pudo realizar la compensación. Verifique los saldos pendientes.'), "info")

    except Exception as e:
        logger.error(f"Error al procesar cruce de cuentas directo: {e}", exc_info=True)
        flash(f"Error al aplicar cruce de cuentas: {str(e)}", "danger")

    return redirect(url_for('admin.admin_cruce_cuentas'))


@admin_bp.route('/admin/cruce-cuentas/compensar-todos', methods=['POST'])
@admin_required
@bitacora_decorator("ADMIN-CRUCE-CUENTAS-COMPENSAR-TODOS")
def admin_cruce_cuentas_compensar_todos():
    """
    Aplica auto-compensación a todas las contrapartes con saldos mutuos compensables.
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id if current_user.is_authenticated else 1

        with get_db_cursor(commit=True) as cursor:
            total_compensados = auto_compensar_saldos_mutuos(cursor, id_empresa=id_empresa, id_usuario=id_usuario)

            if total_compensados > 0:
                flash(f"✅ ¡Se compensaron automáticamente {total_compensados} cuenta(s) vinculada(s) con saldos mutuos!", "success")
            else:
                flash("Todos los balances entre contrapartes vinculadas ya se encuentran al día o no presentan saldos mutuos compensables.", "info")

    except Exception as e:
        logger.error(f"Error al auto-compensar todos: {e}", exc_info=True)
        flash(f"Error al procesar compensaciones automáticas: {str(e)}", "danger")

    return redirect(url_for('admin.admin_cruce_cuentas'))

