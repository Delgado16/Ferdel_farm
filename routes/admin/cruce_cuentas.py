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
    vinculación bilateral (Cruce de Cuentas / Contraparte).
    
    OPTIMIZADO PARA RENDIMIENTO:
    - Ejecuta únicamente consultas agrupadas por lote (Batch) en vez de N+1 queries.
    - Carga perezosa (Lazy load) de movimientos vía AJAX al abrir el modal.
    - No ejecuta escrituras pesadas de compensación en la petición GET inicial.
    """
    try:
        id_empresa = session.get('id_empresa', 1)

        with get_db_cursor(commit=False) as cursor:
            # 1. Obtener todas las parejas de clientes y proveedores vinculados
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
            parejas_raw = cursor.fetchall() or []

            if not parejas_raw:
                resumen_vacio = {
                    'total_contrapartes': 0,
                    'total_saldo_cxc': 0.0,
                    'total_saldo_cxp': 0.0,
                    'total_compensable': 0.0,
                    'saldo_neto_global': 0.0,
                    'diferencia_global': 0.0
                }
                return render_template(
                    'admin/finanzas/cruce_cuentas.html',
                    contrapartes=[],
                    resumen=resumen_vacio
                )

            # Recolectar listas de IDs únicos
            client_ids = list({par['ID_Cliente'] for par in parejas_raw if par.get('ID_Cliente')})
            prov_ids = list({par['ID_Proveedor'] for par in parejas_raw if par.get('ID_Proveedor')})

            ventas_map = {}
            abonos_map = {}
            compras_map = {}
            pagos_map = {}

            # 2. Métricas de Ventas en BATCH (1 sola query agrupada para todos los clientes)
            if client_ids:
                fmt_c = ','.join(['%s'] * len(client_ids))
                cursor.execute(f"""
                    SELECT 
                        f.IDCliente,
                        COUNT(DISTINCT f.ID_Factura) as total_ventas,
                        COALESCE(SUM(df.Total), 0) as monto_ventas
                    FROM facturacion f
                    INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    WHERE f.IDCliente IN ({fmt_c}) AND f.Estado = 'Activa'
                    GROUP BY f.IDCliente
                """, tuple(client_ids))
                for row in cursor.fetchall():
                    ventas_map[row['IDCliente']] = row

            # 3. Métricas de Compras en BATCH (1 sola query agrupada para todos los proveedores)
            if prov_ids:
                fmt_p = ','.join(['%s'] * len(prov_ids))
                cursor.execute(f"""
                    SELECT 
                        mi.ID_Proveedor,
                        COUNT(DISTINCT mi.ID_Movimiento) as total_compras,
                        COALESCE(SUM(dmi.Subtotal), 0) as monto_compras
                    FROM movimientos_inventario mi
                    INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                    WHERE mi.ID_Proveedor IN ({fmt_p}) AND mi.ID_TipoMovimiento = 1 AND mi.Estado = 'Activa'
                    GROUP BY mi.ID_Proveedor
                """, tuple(prov_ids))
                for row in cursor.fetchall():
                    compras_map[row['ID_Proveedor']] = row

            # 4. Abonos y Cruces de CxC en BATCH (1 sola query unificada)
            if client_ids:
                fmt_c = ','.join(['%s'] * len(client_ids))
                cursor.execute(f"""
                    SELECT 
                        ag.ID_Cliente,
                        COUNT(*) as total_abonos,
                        COALESCE(SUM(ag.Monto_Aplicado), 0) as monto_abonos,
                        COUNT(CASE WHEN (ag.caja_movimientos = 'Cruce de Cuentas' OR ag.caja_movimientos LIKE '%%Cruce%%') THEN 1 END) as total_cruces,
                        COALESCE(SUM(CASE WHEN (ag.caja_movimientos = 'Cruce de Cuentas' OR ag.caja_movimientos LIKE '%%Cruce%%') THEN ag.Monto_Aplicado ELSE 0 END), 0) as monto_cruzado
                    FROM abonos_general ag
                    WHERE ag.ID_Cliente IN ({fmt_c})
                    GROUP BY ag.ID_Cliente
                """, tuple(client_ids))
                for row in cursor.fetchall():
                    abonos_map[row['ID_Cliente']] = row

            # 5. Pagos a Proveedores CxP en BATCH (1 sola query)
            if prov_ids:
                fmt_p = ','.join(['%s'] * len(prov_ids))
                cursor.execute(f"""
                    SELECT 
                        apd.ID_Proveedor,
                        COUNT(*) as total_pagos,
                        COALESCE(SUM(apd.Monto_Aplicado), 0) as monto_pagos
                    FROM abonos_proveedores_detalle apd
                    WHERE apd.ID_Proveedor IN ({fmt_p})
                    GROUP BY apd.ID_Proveedor
                """, tuple(prov_ids))
                for row in cursor.fetchall():
                    pagos_map[row['ID_Proveedor']] = row

            # 6. Consolidación de datos en memoria (instantáneo, O(N))
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

                v_info = ventas_map.get(id_cli, {})
                c_info = compras_map.get(id_prov, {})
                a_info = abonos_map.get(id_cli, {})
                p_info = pagos_map.get(id_prov, {})

                contrapartes.append({
                    'cliente': {
                        'id': id_cli,
                        'nombre': par['Cliente_Nombre'],
                        'ruc': par['Cliente_RUC'],
                        'telefono': par['Cliente_Telefono'],
                        'estado': par['Cliente_Estado'],
                        'saldo_cxc': saldo_cxc,
                        'total_ventas_count': v_info.get('total_ventas', 0),
                        'total_ventas_monto': float(v_info.get('monto_ventas') or 0.0),
                        'total_abonos_monto': float(a_info.get('monto_abonos') or 0.0)
                    },
                    'proveedor': {
                        'id': id_prov,
                        'nombre': par['Proveedor_Nombre'],
                        'ruc': par['Proveedor_RUC'],
                        'telefono': par['Proveedor_Telefono'],
                        'estado': par['Proveedor_Estado'],
                        'saldo_cxp': saldo_cxp,
                        'total_compras_count': c_info.get('total_compras', 0),
                        'total_compras_monto': float(c_info.get('monto_compras') or 0.0),
                        'total_pagos_monto': float(p_info.get('monto_pagos') or 0.0)
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
                        'total_cruzado_historico': float(a_info.get('monto_cruzado') or 0.0),
                        'total_cruces_count': a_info.get('total_cruces', 0)
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


@admin_bp.route('/admin/cruce-cuentas/movimientos/<int:id_cliente>/<int:id_proveedor>', methods=['GET'])
@admin_required
def admin_cruce_cuentas_movimientos(id_cliente, id_proveedor):
    """
    Retorna en JSON los últimos movimientos (ventas, compras, abonos, pagos)
    para una contraparte específica de forma asíncrona (Lazy load para el modal).
    """
    try:
        with get_db_cursor(commit=False) as cursor:
            # 1. Últimas 5 Ventas
            cursor.execute("""
                SELECT f.ID_Factura, f.Fecha, 
                       COALESCE((SELECT SUM(Total) FROM detalle_facturacion df WHERE df.ID_Factura = f.ID_Factura), 0) as Total,
                       f.Credito_Contado, f.Estado
                FROM facturacion f
                WHERE f.IDCliente = %s
                ORDER BY f.Fecha DESC, f.ID_Factura DESC
                LIMIT 5
            """, (id_cliente,))
            raw_ventas = cursor.fetchall() or []
            ultimas_ventas = []
            for v in raw_ventas:
                ultimas_ventas.append({
                    'id': v['ID_Factura'],
                    'fecha': v['Fecha'].strftime('%d/%m/%Y') if v.get('Fecha') else 'N/A',
                    'tipo': 'Contado' if v.get('Credito_Contado') == 0 else 'Crédito',
                    'total': float(v.get('Total') or 0.0),
                    'estado': v.get('Estado') or 'Activa'
                })

            # 2. Últimas 5 Compras
            cursor.execute("""
                SELECT mi.ID_Movimiento, mi.Fecha, 
                       COALESCE((SELECT SUM(Subtotal) FROM detalle_movimientos_inventario dmi WHERE dmi.ID_Movimiento = mi.ID_Movimiento), 0) as Total,
                       mi.Tipo_Compra, mi.Estado
                FROM movimientos_inventario mi
                WHERE mi.ID_Proveedor = %s AND mi.ID_TipoMovimiento = 1
                ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
                LIMIT 5
            """, (id_proveedor,))
            raw_compras = cursor.fetchall() or []
            ultimas_compras = []
            for c in raw_compras:
                ultimas_compras.append({
                    'id': c['ID_Movimiento'],
                    'fecha': c['Fecha'].strftime('%d/%m/%Y') if c.get('Fecha') else 'N/A',
                    'tipo': c.get('Tipo_Compra') or 'Compra',
                    'total': float(c.get('Total') or 0.0),
                    'estado': c.get('Estado') or 'Activa'
                })

            # 3. Últimos 5 Abonos y Cobros de CxC
            cursor.execute("""
                SELECT ag.ID_Detalle, ag.Fecha, ag.Monto_Aplicado, ag.caja_movimientos, mp.Nombre as Metodo
                FROM abonos_general ag
                LEFT JOIN metodos_pago mp ON ag.ID_MetodoPago = mp.ID_MetodoPago
                WHERE ag.ID_Cliente = %s
                ORDER BY ag.Fecha DESC, ag.ID_Detalle DESC
                LIMIT 5
            """, (id_cliente,))
            raw_abonos = cursor.fetchall() or []
            ultimos_abonos = []
            for a in raw_abonos:
                caja_mov = a.get('caja_movimientos') or ''
                ultimos_abonos.append({
                    'id': a['ID_Detalle'],
                    'fecha': a['Fecha'].strftime('%d/%m/%Y') if a.get('Fecha') else 'N/A',
                    'metodo': a.get('Metodo') or caja_mov or 'Abono',
                    'es_cruce': caja_mov == 'Cruce de Cuentas' or 'cruce' in caja_mov.lower(),
                    'monto': float(a.get('Monto_Aplicado') or 0.0)
                })

            # 4. Últimos 5 Pagos al Proveedor (CxP)
            cursor.execute("""
                SELECT apd.ID_Detalle, apd.Fecha, apd.Monto_Aplicado, apd.Detalles_Metodo, apd.Comentarios, mp.Nombre as Metodo
                FROM abonos_proveedores_detalle apd
                LEFT JOIN metodos_pago mp ON apd.ID_MetodoPago = mp.ID_MetodoPago
                WHERE apd.ID_Proveedor = %s
                ORDER BY apd.Fecha DESC, apd.ID_Detalle DESC
                LIMIT 5
            """, (id_proveedor,))
            raw_pagos = cursor.fetchall() or []
            ultimos_pagos = []
            for p in raw_pagos:
                det = (p.get('Detalles_Metodo') or '') + ' ' + (p.get('Comentarios') or '')
                ultimos_pagos.append({
                    'id': p['ID_Detalle'],
                    'fecha': p['Fecha'].strftime('%d/%m/%Y') if p.get('Fecha') else 'N/A',
                    'metodo': p.get('Metodo') or p.get('Detalles_Metodo') or 'Pago',
                    'es_cruce': 'cruce' in det.lower(),
                    'monto': float(p.get('Monto_Aplicado') or 0.0)
                })

            return jsonify({
                'success': True,
                'ventas': ultimas_ventas,
                'compras': ultimas_compras,
                'abonos': ultimos_abonos,
                'pagos': ultimos_pagos
            })

    except Exception as e:
        logger.error(f"Error al obtener movimientos de contraparte: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


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
