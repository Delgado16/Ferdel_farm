# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import convertir_hora_db, procesar_asignacion, procesar_lista_asignaciones

@vendedor_bp.route('/api/vendedor/procesar_abono', methods=['POST'])
@vendedor_required
def api_procesar_abono():
    """Procesa un abono con información completa de ruta, usuario y método de pago"""
    try:
        data = request.get_json()
        print(f"📥 Datos recibidos: {data}")
        
        if not data:
            return jsonify({'success': False, 'error': 'Datos no válidos'}), 400
            
        id_cliente = data.get('id_cliente')
        monto_abono = data.get('monto_abono')
        id_metodo_pago = data.get('id_metodo_pago')
        id_vendedor = int(current_user.id)
        
        print(f"🔍 Validando: id_cliente={id_cliente}, monto={monto_abono}, metodo={id_metodo_pago}")
        
        if not id_cliente:
            return jsonify({'success': False, 'error': 'ID de cliente no proporcionado'}), 400
            
        if not monto_abono or float(monto_abono) <= 0:
            return jsonify({'success': False, 'error': 'Monto inválido'}), 400
            
        if not id_metodo_pago:
            return jsonify({'success': False, 'error': 'Debe seleccionar un método de pago'}), 400
        
        monto_abono = float(monto_abono)
        id_metodo_pago = int(id_metodo_pago)
        
        with get_db_cursor(commit=True) as cursor:
            # 1. Obtener el nombre del método de pago
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM metodos_pago 
                WHERE ID_MetodoPago = %s
            """, (id_metodo_pago,))
            metodo = cursor.fetchone()
            
            print(f"💳 Método de pago encontrado: {metodo}")
            
            if not metodo:
                return jsonify({'success': False, 'error': 'Método de pago no válido'}), 400
            
            nombre_metodo_pago = metodo['Nombre']
            
            # 2. Obtener asignación activa del vendedor
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            """, (id_vendedor,))
            
            asignacion = cursor.fetchone()
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa asignada'}), 400
            
            print(f"📍 Asignación encontrada: {asignacion}")
            
            # 3. Obtener facturas pendientes del cliente
            cursor.execute("""
                SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente,
                       Fecha_Vencimiento,
                       CASE 
                           WHEN Fecha_Vencimiento < CURDATE() THEN 1 
                           ELSE 2 
                       END as Prioridad
                FROM cuentas_por_cobrar
                WHERE ID_Cliente = %s 
                  AND Estado IN ('Pendiente', 'Vencida')
                  AND Saldo_Pendiente > 0
                ORDER BY Prioridad ASC, Fecha_Vencimiento ASC
            """, (int(id_cliente),))
            
            facturas = cursor.fetchall()
            print(f"📄 Facturas encontradas: {len(facturas)}")
            
            if not facturas:
                return jsonify({'success': False, 'error': 'No hay facturas pendientes para este cliente'}), 400
            
            # ==============================================
            # REGISTRO EN CAJA - SOLO PARA EFECTIVO (ID=1)
            # ==============================================
            id_movimiento_caja = None
            nuevo_saldo = None
            
            if id_metodo_pago == 1:  # SOLO efectivo
                # Calcular saldo actual de caja
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        ELSE Monto 
                    END), 0) as Saldo_Actual
                    FROM movimientos_caja_ruta
                    WHERE ID_Asignacion = %s 
                      AND DATE(Fecha) = CURDATE() 
                      AND Tipo != 'CIERRE'
                      AND Estado = 'ACTIVO'
                """, (asignacion['ID_Asignacion'],))
                
                saldo_result = cursor.fetchone()
                saldo_actual = float(saldo_result['Saldo_Actual'] if saldo_result else 0)
                nuevo_saldo = saldo_actual + monto_abono
                
                # Registrar movimiento en caja
                concepto = f"Abono de cliente - Monto: C${monto_abono:,.2f} - Pago: {nombre_metodo_pago}"
                
                try:
                    cursor.execute("""
                        INSERT INTO movimientos_caja_ruta
                        (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                         Tipo_Pago, ID_Cliente, Saldo_Acumulado, Estado, ID_MetodoPago)
                        VALUES (%s, %s, 'ABONO', %s, %s, NULL, %s, %s, 'ACTIVO', %s)
                    """, (
                        asignacion['ID_Asignacion'],
                        id_vendedor,
                        concepto,
                        monto_abono,
                        int(id_cliente),
                        nuevo_saldo,
                        id_metodo_pago
                    ))
                    
                    id_movimiento_caja = cursor.lastrowid
                    print(f"✅ Movimiento de caja registrado (EFECTIVO): ID={id_movimiento_caja}")
                    
                except Exception as e:
                    print(f"❌ Error al insertar en movimientos_caja_ruta: {e}")
                    raise Exception(f"Error al registrar movimiento de caja: {str(e)}")
            else:
                # No es efectivo - NO se registra en caja
                print(f"⚠️ Método '{nombre_metodo_pago}' (ID={id_metodo_pago}) - NO se registra en caja")
            
            # 4. Distribuir el abono entre las facturas
            monto_restante = monto_abono
            detalle_abono = []
            monto_aplicado = 0
            ultimo_id_abono = None
            facturas_canceladas = []  # Lista para almacenar facturas que se cancelan completamente
            
            for factura in facturas:
                if monto_restante <= 0:
                    break
                    
                saldo_factura = float(factura['Saldo_Pendiente'])
                monto_aplicar = min(monto_restante, saldo_factura)
                nuevo_saldo_factura = saldo_factura - monto_aplicar
                nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0.01 else 'Pendiente'
                
                # Si la factura queda pagada completamente, agregar a la lista
                if nuevo_saldo_factura <= 0.01:
                    facturas_canceladas.append({
                        'id_movimiento': factura['ID_Movimiento'],
                        'num_documento': factura['Num_Documento'],
                        'monto_pagado': monto_aplicar
                    })
                
                # Actualizar factura
                cursor.execute("""
                    UPDATE cuentas_por_cobrar
                    SET Saldo_Pendiente = %s, 
                        Estado = %s
                    WHERE ID_Movimiento = %s
                """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                
                # Insertar en abonos_detalle (VERSIÓN CORREGIDA - sin Metodo_Pago_Nombre)
                try:
                    cursor.execute("""
                        INSERT INTO abonos_detalle
                        (ID_Movimiento_Caja, ID_Asignacion, ID_Usuario, ID_Cliente, 
                         ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo,
                         ID_MetodoPago)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_caja,      # Puede ser NULL para no-efectivo
                        asignacion['ID_Asignacion'],
                        id_vendedor,
                        int(id_cliente),
                        factura['ID_Movimiento'],
                        monto_aplicar,
                        saldo_factura,
                        nuevo_saldo_factura,
                        id_metodo_pago           # Solo el ID del método
                    ))
                    
                    ultimo_id_abono = cursor.lastrowid
                    print(f"✅ Detalle de abono insertado para factura {factura['Num_Documento']} (ID_MetodoPago={id_metodo_pago})")
                    
                except Exception as e:
                    print(f"❌ Error al insertar en abonos_detalle: {e}")
                    # Si falla, intentar al menos guardar el ID del movimiento de caja
                    ultimo_id_abono = id_movimiento_caja if id_movimiento_caja else 0
                
                detalle_abono.append({
                    'factura': factura['Num_Documento'],
                    'monto': monto_aplicar,
                    'saldo_anterior': saldo_factura,
                    'saldo_nuevo': nuevo_saldo_factura,
                    'estado': nuevo_estado,
                    'cancelada': nuevo_saldo_factura <= 0.01
                })
                
                monto_restante -= monto_aplicar
                monto_aplicado += monto_aplicar
            
            # 5. Actualizar saldo del cliente
            cursor.execute("""
                UPDATE clientes 
                SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total, 0) - %s),
                    Fecha_Ultimo_Pago = NOW()
                WHERE ID_Cliente = %s
            """, (monto_aplicado, int(id_cliente)))
            
            print(f"✅ Abono procesado: Monto={monto_aplicado}, Cliente={id_cliente}")
            
            # Si se cancelaron facturas, mostrar mensaje
            if facturas_canceladas:
                print(f"🎉 Facturas canceladas completamente: {len(facturas_canceladas)}")
                for factura_cancelada in facturas_canceladas:
                    print(f"   - Factura {factura_cancelada['num_documento']}: C${factura_cancelada['monto_pagado']:,.2f}")
            
            # ID para el recibo
            id_abono_para_recibo = ultimo_id_abono if ultimo_id_abono else (id_movimiento_caja if id_movimiento_caja else 0)
            
            # Preparar respuesta
            respuesta = {
                'success': True,
                'mensaje': 'Abono procesado correctamente',
                'id_movimiento': id_movimiento_caja if id_movimiento_caja else 0,
                'id_abono': id_abono_para_recibo,
                'id_metodo_pago': id_metodo_pago,
                'metodo_pago': nombre_metodo_pago,
                'ruta': asignacion['ID_Ruta'],
                'vendedor': current_user.username,
                'monto_abono': monto_abono,
                'monto_aplicado': monto_aplicado,
                'vuelto': monto_restante,
                'detalle': detalle_abono,
                'registro_caja': id_metodo_pago == 1,
                'facturas_canceladas': facturas_canceladas,  # Nuevo campo con las facturas canceladas
                'total_facturas_canceladas': len(facturas_canceladas)  # Contador de facturas canceladas
            }
            
            # Solo incluir nuevo_saldo_caja si fue efectivo
            if id_metodo_pago == 1:
                respuesta['nuevo_saldo_caja'] = nuevo_saldo
            
            return jsonify(respuesta)
            
    except Exception as e:
        print(f"❌ Error en api_procesar_abono: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@vendedor_bp.route('/api/vendedor/metodos_pago', methods=['GET'])
@vendedor_required
def api_metodos_pago():
    """Obtener lista de métodos de pago"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre
                FROM metodos_pago
                ORDER BY Nombre
            """)
            metodos = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'metodos_pago': metodos
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@vendedor_bp.route('/api/vendedor/verificar_saldo_cliente/<int:id_cliente>', methods=['GET'])
@vendedor_required
def api_verificar_saldo_cliente(id_cliente):
    """API para verificar el saldo pendiente de un cliente"""
    try:
        with get_db_cursor() as cursor:
            # Obtener la empresa del vendedor desde su asignación activa
            cursor.execute("""
                SELECT r.ID_Empresa
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            empresa = cursor.fetchone()
            
            if not empresa:
                return jsonify({
                    'success': False,
                    'error': 'No tienes una asignación activa hoy'
                }), 400
            
            # Obtener saldo pendiente del cliente
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA, Saldo_Pendiente_Total,
                       (SELECT COUNT(*) FROM cuentas_por_cobrar 
                        WHERE ID_Cliente = c.ID_Cliente 
                        AND Estado IN ('Pendiente', 'Vencida')) as Facturas_Pendientes
                FROM clientes c
                WHERE c.ID_Cliente = %s 
                AND c.ID_Empresa = %s
                AND c.Estado = 'ACTIVO'
            """, (id_cliente, empresa['ID_Empresa']))
            
            cliente = cursor.fetchone()
            
            if not cliente:
                return jsonify({
                    'success': False,
                    'error': 'Cliente no encontrado'
                }), 404
            
            # Si tiene saldo pendiente, obtener detalles de las facturas de ruta
            facturas_pendientes = []
            if cliente['Saldo_Pendiente_Total'] > 0:
                cursor.execute("""
                    SELECT c.ID_Movimiento, c.Fecha, c.Num_Documento, 
                           c.Monto_Movimiento, c.Saldo_Pendiente,
                           c.Fecha_Vencimiento,
                           DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as Dias_Vencido,
                           fr.ID_FacturaRuta,
                           fr.Fecha as FechaFactura
                    FROM cuentas_por_cobrar c
                    LEFT JOIN facturacion_ruta fr ON c.ID_FacturaRuta = fr.ID_FacturaRuta
                    WHERE c.ID_Cliente = %s 
                    AND c.Estado IN ('Pendiente', 'Vencida')
                    AND c.ID_FacturaRuta IS NOT NULL  -- Solo facturas de ruta
                    ORDER BY c.Fecha_Vencimiento ASC, c.Fecha ASC
                """, (id_cliente,))
                facturas_pendientes = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'cliente': {
                    'id': cliente['ID_Cliente'],
                    'nombre': cliente['Nombre'],
                    'ruc': cliente['RUC_CEDULA'],
                    'saldo_pendiente': float(cliente['Saldo_Pendiente_Total'] or 0),
                    'facturas_pendientes': cliente['Facturas_Pendientes']
                },
                'facturas_detalle': facturas_pendientes
            })
            
    except Exception as e:
        print(f"Error en verificar saldo: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vendedor_bp.route('/api/vendedor/verificar_saldo_cliente_offline/<int:id_cliente>', methods=['GET'])
@vendedor_required
def api_verificar_saldo_cliente_offline(id_cliente):
    """
    Versión simplificada para verificar un cliente específico offline.
    Esta función es llamada cuando hay conexión para obtener datos actualizados.
    """
    try:
        with get_db_cursor() as cursor:
            # Obtener la empresa del vendedor desde su asignación activa
            cursor.execute("""
                SELECT r.ID_Empresa
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            empresa = cursor.fetchone()
            
            if not empresa:
                return jsonify({
                    'success': False,
                    'error': 'No tienes una asignación activa hoy'
                }), 400
            
            # Obtener información completa del cliente
            cursor.execute("""
                SELECT 
                    c.ID_Cliente,
                    c.Nombre,
                    c.RUC_CEDULA,
                    c.Telefono,
                    c.Direccion,
                    c.perfil_cliente,
                    COALESCE((
                        SELECT SUM(Saldo_Pendiente) 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Cliente = c.ID_Cliente 
                        AND Estado IN ('Pendiente', 'Vencida')
                    ), 0) as Saldo_Pendiente_Total,
                    (
                        SELECT COUNT(*) 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Cliente = c.ID_Cliente 
                        AND Estado IN ('Pendiente', 'Vencida')
                    ) as Facturas_Pendientes
                FROM clientes c
                WHERE c.ID_Cliente = %s 
                AND c.ID_Empresa = %s
                AND c.Estado = 'ACTIVO'
            """, (id_cliente, empresa['ID_Empresa']))
            
            cliente = cursor.fetchone()
            
            if not cliente:
                return jsonify({
                    'success': False,
                    'error': 'Cliente no encontrado'
                }), 404
            
            # Obtener facturas pendientes si tiene saldo
            facturas_pendientes = []
            if cliente['Saldo_Pendiente_Total'] > 0:
                cursor.execute("""
                    SELECT 
                        c.ID_Movimiento,
                        c.Fecha,
                        c.Num_Documento,
                        c.Monto_Movimiento,
                        c.Saldo_Pendiente,
                        c.Fecha_Vencimiento,
                        DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as Dias_Vencido,
                        fr.ID_FacturaRuta,
                        fr.Fecha as FechaFactura
                    FROM cuentas_por_cobrar c
                    LEFT JOIN facturacion_ruta fr ON c.ID_FacturaRuta = fr.ID_FacturaRuta
                    WHERE c.ID_Cliente = %s 
                    AND c.Estado IN ('Pendiente', 'Vencida')
                    AND c.ID_FacturaRuta IS NOT NULL
                    ORDER BY c.Fecha_Vencimiento ASC, c.Fecha ASC
                    LIMIT 50
                """, (id_cliente,))
                facturas_pendientes = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'cliente': {
                    'id': cliente['ID_Cliente'],
                    'nombre': cliente['Nombre'],
                    'ruc': cliente['RUC_CEDULA'],
                    'telefono': cliente['Telefono'],
                    'direccion': cliente['Direccion'],
                    'perfil': cliente['perfil_cliente'],
                    'saldo_pendiente': float(cliente['Saldo_Pendiente_Total'] or 0),
                    'facturas_pendientes': cliente['Facturas_Pendientes']
                },
                'facturas_detalle': facturas_pendientes
            })
            
    except Exception as e:
        print(f"Error en verificar saldo: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vendedor_bp.route('/api/vendedor/sincronizar_clientes_saldos', methods=['GET'])
@vendedor_required
def api_sincronizar_clientes_saldos():
    """Sincronizar clientes y sus saldos pendientes"""
    try:
        id_vendedor = int(current_user.id)
        ultima_sincronizacion = request.args.get('ultima_sincronizacion')
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Empresa
                FROM asignacion_vendedores av
                WHERE av.ID_Usuario = %s AND av.Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
            
            # Obtener clientes de la ruta
            if ultima_sincronizacion:
                cursor.execute("""
                    SELECT c.ID_Cliente, c.Nombre, c.RUC_CEDULA, c.Telefono, 
                           c.Direccion, c.tipo_cliente, c.perfil_cliente,
                           COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Pendiente_Total,
                           c.Fecha_Ultimo_Movimiento, c.Fecha_Ultimo_Pago,
                           c.Estado as Cliente_Estado,
                           c.Fecha_Creacion
                    FROM clientes c
                    WHERE c.ID_Empresa = %s 
                      AND c.Estado = 'ACTIVO'
                      AND (c.ID_Ruta = %s OR c.ID_Ruta IS NULL)
                      AND (c.Fecha_Ultimo_Movimiento > %s OR c.Fecha_Creacion > %s)
                    ORDER BY c.Nombre
                """, (asignacion['ID_Empresa'], asignacion['ID_Ruta'], 
                      ultima_sincronizacion, ultima_sincronizacion))
            else:
                cursor.execute("""
                    SELECT c.ID_Cliente, c.Nombre, c.RUC_CEDULA, c.Telefono, 
                           c.Direccion, c.tipo_cliente, c.perfil_cliente,
                           COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Pendiente_Total,
                           c.Fecha_Ultimo_Movimiento, c.Fecha_Ultimo_Pago,
                           c.Estado as Cliente_Estado,
                           c.Fecha_Creacion
                    FROM clientes c
                    WHERE c.ID_Empresa = %s 
                      AND c.Estado = 'ACTIVO'
                      AND (c.ID_Ruta = %s OR c.ID_Ruta IS NULL)
                    ORDER BY c.Nombre
                """, (asignacion['ID_Empresa'], asignacion['ID_Ruta']))
            
            clientes = cursor.fetchall()
            
            # Para cada cliente con saldo, obtener facturas pendientes
            for cliente in clientes:
                if cliente['Saldo_Pendiente_Total'] > 0:
                    cursor.execute("""
                        SELECT cxc.ID_Movimiento, cxc.Num_Documento, 
                               cxc.Monto_Movimiento, cxc.Saldo_Pendiente,
                               cxc.Fecha_Vencimiento,
                               DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as Dias_Vencido,
                               DATE_FORMAT(cxc.Fecha_Vencimiento, '%%Y-%%m-%%d') as Fecha_Vencimiento_ISO
                        FROM cuentas_por_cobrar cxc
                        WHERE cxc.ID_Cliente = %s 
                          AND cxc.Estado IN ('Pendiente', 'Vencida')
                          AND cxc.Saldo_Pendiente > 0
                        ORDER BY 
                            CASE WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 0 ELSE 1 END,
                            cxc.Fecha_Vencimiento ASC
                    """, (cliente['ID_Cliente'],))
                    cliente['facturas_pendientes'] = cursor.fetchall()
                else:
                    cliente['facturas_pendientes'] = []
            
            # Obtener fecha de última modificación de clientes en la ruta
            cursor.execute("""
                SELECT MAX(GREATEST(
                    COALESCE(c.Fecha_Ultimo_Movimiento, '1900-01-01'),
                    COALESCE(c.Fecha_Creacion, '1900-01-01')
                )) as ultima_modificacion
                FROM clientes c
                WHERE c.ID_Empresa = %s 
                  AND (c.ID_Ruta = %s OR c.ID_Ruta IS NULL)
            """, (asignacion['ID_Empresa'], asignacion['ID_Ruta']))
            
            ultima_modificacion = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'clientes': clientes,
                'ultima_modificacion': ultima_modificacion['ultima_modificacion'] if ultima_modificacion else None,
                'asignacion_id': asignacion['ID_Asignacion']
            })
            
    except Exception as e:
        print(f"Error en api_sincronizar_clientes_saldos: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@vendedor_bp.route('/vendedor/abonos/mis_abonos', methods=['GET'])
@vendedor_required
def mis_abonos_detalle():
    """Muestra los abonos registrados por el vendedor con detalle de facturas"""
    try:
        id_vendedor = current_user.id
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    ad.Fecha,
                    ad.ID_Movimiento_Caja,
                    ad.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA,
                    ad.ID_CuentaCobrar,
                    cc.Num_Documento as Factura,
                    ad.Monto_Aplicado,
                    ad.Saldo_Anterior,
                    ad.Saldo_Nuevo,
                    CASE 
                        WHEN ad.Saldo_Nuevo = 0 THEN 'Pagada'
                        WHEN ad.Monto_Aplicado < ad.Saldo_Anterior THEN 'Pago Parcial'
                        ELSE 'Pendiente'
                    END as Estado_Factura,
                    r.Nombre_Ruta
                FROM abonos_detalle ad
                INNER JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                INNER JOIN cuentas_por_cobrar cc ON ad.ID_CuentaCobrar = cc.ID_Movimiento
                INNER JOIN asignacion_vendedores av ON ad.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE ad.ID_Usuario = %s
                ORDER BY ad.Fecha DESC
                LIMIT 50
            """, (id_vendedor,))
            
            abonos = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'vendedor': current_user.NombreUsuario,
                'total_abonos': len(abonos),
                'abonos': abonos
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@vendedor_bp.route('/vendedor/clientes')
@vendedor_required
def vendedor_clientes():
    """Lista de clientes del vendedor con su ruta asignada"""
    try:
        id_vendedor = int(current_user.id)
        
        # Obtener la ruta asignada al vendedor
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s AND av.Estado = 'Activa'
            """, (id_vendedor,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta activa asignada', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            # Parámetros de paginación y filtros
            page = request.args.get('page', 1, type=int)
            per_page = 10
            search = request.args.get('q', '')
            ruta_seleccionada = request.args.get('ruta', '')
            
            # Construir consulta base
            query_base = """
                FROM clientes c
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                WHERE c.Estado = 'ACTIVO'
                AND c.ID_Ruta = %s
            """
            params = [asignacion['ID_Ruta']]
            
            # Agregar filtro de búsqueda
            if search:
                query_base += """ AND (c.Nombre LIKE %s 
                                    OR c.Telefono LIKE %s 
                                    OR c.RUC_CEDULA LIKE %s)"""
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            # Agregar filtro de ruta específica (si se selecciona)
            if ruta_seleccionada and ruta_seleccionada != str(asignacion['ID_Ruta']):
                query_base += " AND c.ID_Ruta = %s"
                params.append(int(ruta_seleccionada))
            
            # Contar total
            cursor.execute(f"SELECT COUNT(*) as total {query_base}", params)
            total = cursor.fetchone()['total']
            
            # Obtener clientes paginados
            query_clientes = f"""
                SELECT 
                    c.ID_Cliente,
                    c.Nombre,
                    c.Telefono,
                    c.Direccion,
                    c.RUC_CEDULA,
                    c.Saldo_Pendiente_Total,
                    r.Nombre_Ruta
                {query_base}
                ORDER BY c.Nombre ASC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, (page - 1) * per_page])
            cursor.execute(query_clientes, params)
            clientes = cursor.fetchall()
            
            # Obtener todas las rutas disponibles para el filtro
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE ID_Empresa = (SELECT ID_Empresa FROM asignacion_vendedores WHERE ID_Usuario = %s LIMIT 1)
                AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (id_vendedor,))
            rutas = cursor.fetchall()
            
            # OBTENER MÉTODOS DE PAGO
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM metodos_pago 
                ORDER BY Nombre
            """)
            metodos_pago = cursor.fetchall()
            
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('vendedor/clientes/clientes.html',
                                 clientes=clientes,
                                 total=total,
                                 page=page,
                                 per_page=per_page,
                                 total_pages=total_pages,
                                 search=search,
                                 ruta_seleccionada=ruta_seleccionada,
                                 rutas=rutas,
                                 metodos_pago=metodos_pago,
                                 fecha_actual=datetime.now().strftime('%d/%m/%Y'))
                             
    except Exception as e:
        print(f"Error en vendedor_clientes: {str(e)}")
        traceback.print_exc()
        flash('Error al cargar clientes', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))


@vendedor_bp.route('/abono/<int:id_abono>/recibo')
@vendedor_required
def vendedor_recibo_abono(id_abono):
    """Generar recibo de abono con método de pago (para efectivo y no-efectivo)"""
    try:
        id_vendedor = int(current_user.id)
        auto_print = request.args.get('autoPrint', 0)
        
        print(f"🔍 Buscando abono ID: {id_abono} para vendedor ID: {id_vendedor}")
        
        with get_db_cursor() as cursor:
            # Buscar en abonos_detalle con JOIN a metodos_pago
            cursor.execute("""
                SELECT 
                    ad.ID_Detalle as id_abono,
                    ad.Monto_Aplicado,
                    ad.Fecha,
                    ad.ID_MetodoPago,
                    mp.Nombre as metodo_pago_nombre,
                    c.ID_Cliente,
                    c.Nombre as cliente_nombre,
                    c.RUC_CEDULA as cliente_ruc,
                    c.Saldo_Pendiente_Total as saldo_actual_cliente,
                    u.NombreUsuario as vendedor_nombre,
                    r.Nombre_Ruta as ruta_nombre,
                    e.Nombre_Empresa as empresa_nombre,
                    e.RUC as empresa_ruc,
                    e.Direccion as empresa_direccion,
                    e.Telefono as empresa_telefono
                FROM abonos_detalle ad
                INNER JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                INNER JOIN usuarios u ON ad.ID_Usuario = u.ID_Usuario
                INNER JOIN asignacion_vendedores av ON ad.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                INNER JOIN empresa e ON av.ID_Empresa = e.ID_Empresa
                LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                WHERE ad.ID_Detalle = %s
                AND ad.ID_Usuario = %s
            """, (id_abono, id_vendedor))
            
            abono = cursor.fetchone()
            print(f"📊 Resultado búsqueda en abonos_detalle: {abono is not None}")
            
            # Si no encuentra, buscar como backup en movimientos_caja_ruta (para abonos antiguos)
            if not abono:
                print(f"🔍 Buscando en movimientos_caja_ruta como backup...")
                cursor.execute("""
                    SELECT 
                        mc.ID_Movimiento as id_abono,
                        mc.Monto as Monto_Aplicado,
                        mc.Fecha,
                        mc.ID_MetodoPago,
                        mp.Nombre as metodo_pago_nombre,
                        c.ID_Cliente,
                        c.Nombre as cliente_nombre,
                        c.RUC_CEDULA as cliente_ruc,
                        c.Saldo_Pendiente_Total as saldo_actual_cliente,
                        u.NombreUsuario as vendedor_nombre,
                        r.Nombre_Ruta as ruta_nombre,
                        e.Nombre_Empresa as empresa_nombre,
                        e.RUC as empresa_ruc,
                        e.Direccion as empresa_direccion,
                        e.Telefono as empresa_telefono
                    FROM movimientos_caja_ruta mc
                    INNER JOIN clientes c ON mc.ID_Cliente = c.ID_Cliente
                    INNER JOIN usuarios u ON mc.ID_Usuario = u.ID_Usuario
                    INNER JOIN asignacion_vendedores av ON mc.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN metodos_pago mp ON mc.ID_MetodoPago = mp.ID_MetodoPago
                    INNER JOIN empresa e ON av.ID_Empresa = e.ID_Empresa
                    WHERE mc.ID_Movimiento = %s
                    AND mc.ID_Usuario = %s
                    AND mc.Tipo = 'ABONO'
                """, (id_abono, id_vendedor))
                
                abono = cursor.fetchone()
                print(f"📊 Resultado búsqueda backup: {abono is not None}")
            
            if not abono:
                print(f"❌ Abono {id_abono} no encontrado para vendedor {id_vendedor}")
                flash('Abono no encontrado', 'error')
                return redirect(url_for('vendedor.vendedor_clientes'))
            
            # Obtener TODOS los abonos del mismo movimiento para calcular el total
            # Primero, identificar el ID_Movimiento_Caja si existe
            cursor.execute("""
                SELECT ID_Movimiento_Caja 
                FROM abonos_detalle 
                WHERE ID_Detalle = %s
            """, (id_abono,))
            
            resultado_mov = cursor.fetchone()
            monto_total = float(abono['Monto_Aplicado'])  # Valor por defecto
            
            if resultado_mov and resultado_mov['ID_Movimiento_Caja']:
                # Si tiene movimiento de caja, sumar todos los detalles de ese movimiento
                id_mov_caja = resultado_mov['ID_Movimiento_Caja']
                cursor.execute("""
                    SELECT SUM(Monto_Aplicado) as total_abonado
                    FROM abonos_detalle
                    WHERE ID_Movimiento_Caja = %s
                """, (id_mov_caja,))
                
                total_result = cursor.fetchone()
                if total_result and total_result['total_abonado']:
                    monto_total = float(total_result['total_abonado'])
                    print(f"💰 Total abonado para movimiento {id_mov_caja}: {monto_total}")
            else:
                # Si no tiene movimiento de caja, buscar por fecha y cliente (mismo abono)
                cursor.execute("""
                    SELECT SUM(Monto_Aplicado) as total_abonado
                    FROM abonos_detalle
                    WHERE ID_Cliente = %s 
                      AND DATE(Fecha) = DATE(%s)
                      AND ID_Usuario = %s
                """, (abono['ID_Cliente'], abono['Fecha'], id_vendedor))
                
                total_result = cursor.fetchone()
                if total_result and total_result['total_abonado']:
                    monto_total = float(total_result['total_abonado'])
                    print(f"💰 Total abonado por fecha: {monto_total}")
            
            # Obtener método de pago
            metodo_pago = abono.get('metodo_pago_nombre')
            if not metodo_pago:
                # Si no tiene nombre, buscar por ID
                if abono.get('ID_MetodoPago'):
                    cursor.execute("SELECT Nombre FROM metodos_pago WHERE ID_MetodoPago = %s", (abono['ID_MetodoPago'],))
                    metodo_obj = cursor.fetchone()
                    if metodo_obj:
                        metodo_pago = metodo_obj['Nombre']
            
            if not metodo_pago:
                metodo_pago = 'NO ESPECIFICADO'
            
            print(f"✅ Método de pago: {metodo_pago}")
            print(f"💰 Monto individual del registro: {float(abono['Monto_Aplicado'])}")
            print(f"💰 Monto total abonado (suma): {monto_total}")
            
            # Calcular datos
            saldo_actual = float(abono['saldo_actual_cliente'])
            saldo_anterior = saldo_actual + monto_total  # Usar monto_total en lugar del individual
            
            # Formatear fecha
            fecha_abono = abono['Fecha']
            if isinstance(fecha_abono, str):
                from datetime import datetime
                try:
                    fecha_abono = datetime.strptime(fecha_abono, '%Y-%m-%d %H:%M:%S')
                except:
                    try:
                        fecha_abono = datetime.strptime(fecha_abono, '%Y-%m-%d')
                    except:
                        fecha_abono = datetime.now()
            
            # Generar número de recibo
            numero_recibo = f"REC-{fecha_abono.strftime('%Y%m%d')}-{abono['id_abono']:05d}"
            
            # Datos para el template
            ticket_data = {
                'numero_recibo': numero_recibo,
                'id_abono': abono['id_abono'],
                'fecha': fecha_abono.strftime('%d/%m/%Y %H:%M:%S'),
                'cliente': abono['cliente_nombre'],
                'cliente_ruc': abono['cliente_ruc'] or 'N/A',
                'vendedor': abono['vendedor_nombre'],
                'ruta': abono['ruta_nombre'],
                'metodo_pago': metodo_pago,
                'saldo_anterior_formateado': f"C${saldo_anterior:,.2f}",
                'monto_total_formateado': f"C${monto_total:,.2f}",  # ← NUEVO: total abonado
                'nuevo_saldo_formateado': f"C${saldo_actual:,.2f}",
                'empresa': {
                    'nombre': abono['empresa_nombre'],
                    'ruc': abono['empresa_ruc'],
                    'direccion': abono['empresa_direccion'] or '',
                    'telefono': abono['empresa_telefono'] or '',
                    'logo': '/static/ferdel.png'
                },
                'auto_print': auto_print
            }
            
            print(f"✅ Recibo generado exitosamente para abono {id_abono}")
            return render_template('vendedor/clientes/recibo_abono.html', ticket=ticket_data)
                             
    except Exception as e:
        print(f"❌ Error en recibo: {str(e)}")
        traceback.print_exc()
        flash('Error al generar recibo', 'error')
        return redirect(url_for('vendedor.vendedor_clientes'))


@vendedor_bp.route('/vendedor/abonos')
@vendedor_required
def vendedor_abonos():
    """Muestra los abonos realizados por el vendedor con opción a generar recibo y filtros"""
    try:
        id_vendedor = int(current_user.id)
        
        # Obtener parámetros de filtro desde la URL
        fecha_desde = request.args.get('fecha_desde', '')
        fecha_hasta = request.args.get('fecha_hasta', '')
        metodo_pago = request.args.get('metodo_pago', '')
        cliente = request.args.get('cliente', '')
        ver_todo = request.args.get('ver_todo', '')
        
        # Por defecto, si no se proporcionan filtros de fecha y no se solicita ver todo el historial, limitar a hoy
        if not fecha_desde and not fecha_hasta and not ver_todo:
            today_str = datetime.now().strftime('%Y-%m-%d')
            fecha_desde = today_str
            fecha_hasta = today_str
            
        print("=== DEBUG INFO ===")
        print(f"ID Vendedor: {id_vendedor}")
        print(f"Fecha Desde: {fecha_desde}")
        print(f"Fecha Hasta: {fecha_hasta}")
        print(f"Metodo Pago: {metodo_pago}")
        print(f"Cliente: {cliente}")
        print(f"Ver Todo: {ver_todo}")
        
        with get_db_cursor() as cursor:
            # PRIMERO: Verificar conexión y tabla
            cursor.execute("SELECT COUNT(*) as total FROM abonos_detalle WHERE ID_Usuario = %s", (id_vendedor,))
            count_result = cursor.fetchone()
            print(f"Total abonos en tabla: {count_result}")
            
            # Consulta MUY SIMPLE para probar
            query_simple = """
                SELECT * FROM abonos_detalle WHERE ID_Usuario = %s
            """
            print(f"Query simple: {query_simple}")
            print(f"Params simple: {(id_vendedor,)}")
            
            cursor.execute(query_simple, (id_vendedor,))
            resultados_simple = cursor.fetchall()
            print(f"Resultados consulta simple: {len(resultados_simple)}")
            
            # Consulta completa
            query = """
                SELECT 
                    ad.ID_Detalle,
                    ad.ID_Cliente,
                    c.Nombre AS Nombre_Cliente,
                    c.RUC_CEDULA,
                    c.Telefono,
                    ad.Monto_Aplicado,
                    ad.Fecha,
                    ad.Saldo_Anterior,
                    ad.Saldo_Nuevo,
                    COALESCE(mp.Nombre, 'Efectivo') AS Metodo_Pago,
                    COALESCE(r.Nombre_Ruta, 'Ruta Actual') AS Nombre_Ruta,
                    cc.Num_Documento AS Num_Documento
                FROM abonos_detalle ad
                INNER JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN asignacion_vendedores av ON ad.ID_Asignacion = av.ID_Asignacion
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN cuentas_por_cobrar cc ON ad.ID_CuentaCobrar = cc.ID_Movimiento
                WHERE ad.ID_Usuario = %s
            """
            
            params = [id_vendedor]
            print(f"\nParams iniciales: {params}")
            
            if fecha_desde and fecha_desde.strip():
                query += " AND DATE(ad.Fecha) >= %s"
                params.append(fecha_desde)
                print(f"Agregado filtro fecha_desde, params: {params}")
            
            if fecha_hasta and fecha_hasta.strip():
                query += " AND DATE(ad.Fecha) <= %s"
                params.append(fecha_hasta)
                print(f"Agregado filtro fecha_hasta, params: {params}")
            
            if metodo_pago and metodo_pago.strip():
                query += " AND ad.ID_MetodoPago = %s"
                params.append(int(metodo_pago))
                print(f"Agregado filtro metodo_pago, params: {params}")
            
            if cliente and cliente.strip():
                query += " AND c.Nombre LIKE %s"
                params.append(f'%{cliente}%')
                print(f"Agregado filtro cliente, params: {params}")
            
            query += " ORDER BY ad.Fecha DESC, ad.ID_Detalle DESC"
            
            print(f"\nQuery final: {query}")
            print(f"Params finales: {params}")
            print(f"Número de params: {len(params)}")
            
            # Ejecutar consulta
            cursor.execute(query, tuple(params))
            abonos_raw = cursor.fetchall()
            
            print(f"Registros de abono crudos encontrados: {len(abonos_raw)}")
            
            # Agrupar abonos en Python por cliente + fecha + metodo_pago
            from collections import OrderedDict
            grouped_dict = OrderedDict()
            
            for abono in abonos_raw:
                # La fecha en MySQL suele ser idéntica para inserciones en la misma transacción.
                # Formateamos la fecha a cadena para tener una clave consistente.
                fecha_str = abono['Fecha'].strftime('%Y-%m-%d %H:%M:%S') if abono['Fecha'] else 'N/A'
                key = (abono['ID_Cliente'], fecha_str, abono['Metodo_Pago'])
                
                if key not in grouped_dict:
                    grouped_dict[key] = {
                        'ID_Cliente': abono['ID_Cliente'],
                        'Nombre_Cliente': abono['Nombre_Cliente'],
                        'RUC_CEDULA': abono['RUC_CEDULA'],
                        'Telefono': abono['Telefono'],
                        'Fecha': abono['Fecha'],
                        'Metodo_Pago': abono['Metodo_Pago'],
                        'Nombre_Ruta': abono['Nombre_Ruta'],
                        'Monto_Total': 0.0,
                        'Detalles': []
                    }
                
                grouped_dict[key]['Monto_Total'] += float(abono['Monto_Aplicado'])
                grouped_dict[key]['Detalles'].append({
                    'ID_Detalle': abono['ID_Detalle'],
                    'Num_Documento': abono['Num_Documento'] or 'Venta / Factura General',
                    'Monto_Aplicado': abono['Monto_Aplicado'],
                    'Saldo_Anterior': abono['Saldo_Anterior'],
                    'Saldo_Nuevo': abono['Saldo_Nuevo']
                })
                
            abonos_agrupados = list(grouped_dict.values())
            print(f"Abonos agrupados: {len(abonos_agrupados)}")
            
            # Obtener métodos de pago
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
            metodos_pago = cursor.fetchall()
            
            # Resumen por método de pago
            resumen_pagos = []
            if abonos_raw:
                query_resumen = """
                    SELECT 
                        COALESCE(mp.Nombre, 'Efectivo') AS Metodo_Pago,
                        COUNT(*) AS Cantidad,
                        SUM(ad.Monto_Aplicado) AS Total
                    FROM abonos_detalle ad
                    LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE ad.ID_Usuario = %s
                    GROUP BY COALESCE(mp.Nombre, 'Efectivo')
                """
                cursor.execute(query_resumen, (id_vendedor,))
                resumen_pagos = cursor.fetchall()
            
            # Estadísticas basadas en abonos agrupados para que refleje transacciones reales de cobro
            total_monto = sum(abono['Monto_Total'] for abono in abonos_agrupados) if abonos_agrupados else 0
            cantidad_abonos = len(abonos_agrupados)
            
            estadisticas = {
                'Total_Abonos': cantidad_abonos,
                'Monto_Total': total_monto,
                'Promedio_Abono': (total_monto / cantidad_abonos) if cantidad_abonos > 0 else 0,
                'Primera_Fecha': abonos_agrupados[-1]['Fecha'] if abonos_agrupados else None,
                'Ultima_Fecha': abonos_agrupados[0]['Fecha'] if abonos_agrupados else None
            }
            
            today_str = datetime.now().strftime('%Y-%m-%d')
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            return render_template('vendedor/clientes/abonos.html', 
                                 abonos=abonos_agrupados,
                                 metodos_pago=metodos_pago,
                                 resumen_pagos=resumen_pagos,
                                 estadisticas=estadisticas,
                                 hoy=today_str,
                                 ayer=yesterday_str,
                                 filtros={
                                     'fecha_desde': fecha_desde,
                                     'fecha_hasta': fecha_hasta,
                                     'metodo_pago': metodo_pago,
                                     'cliente': cliente,
                                     'ver_todo': ver_todo
                                 })
            
    except Exception as e:
        print(f"Error en vendedor_abonos: {str(e)}")
        traceback.print_exc()
        flash('Error al cargar los abonos. Por favor, intente nuevamente.', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))


