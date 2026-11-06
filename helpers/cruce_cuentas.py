import logging

logger = logging.getLogger(__name__)

def obtener_o_crear_metodo_pago_cruce(cursor):
    """
    Obtiene el ID_MetodoPago válido para 'Cruce de Cuentas'.
    Si no existe, intenta crearlo en la tabla metodos_pago.
    Si no se puede crear, busca cualquier método existente para nunca violar Foreign Key.
    """
    try:
        cursor.execute("SELECT ID_MetodoPago FROM metodos_pago WHERE Nombre = 'Cruce de Cuentas' LIMIT 1")
        mp = cursor.fetchone()
        if mp and mp.get('ID_MetodoPago'):
            return mp['ID_MetodoPago']

        # Buscar si existe con un nombre parecido
        cursor.execute("SELECT ID_MetodoPago FROM metodos_pago WHERE Nombre LIKE '%Cruce%' OR Nombre LIKE '%Compensaci%' LIMIT 1")
        mp = cursor.fetchone()
        if mp and mp.get('ID_MetodoPago'):
            return mp['ID_MetodoPago']

        # Si no existe, crearlo
        cursor.execute("INSERT INTO metodos_pago (Nombre) VALUES ('Cruce de Cuentas')")
        return cursor.lastrowid
    except Exception as e:
        logger.warning(f"Aviso al obtener/crear 'Cruce de Cuentas': {e}")
        try:
            # Tomar el primer ID de método de pago que exista en la tabla para respetar FK
            cursor.execute("SELECT ID_MetodoPago FROM metodos_pago ORDER BY ID_MetodoPago ASC LIMIT 1")
            first_mp = cursor.fetchone()
            if first_mp and first_mp.get('ID_MetodoPago'):
                return first_mp['ID_MetodoPago']
        except Exception:
            pass
        return 1

def procesar_compensacion_vinculada(cursor, id_cliente=None, id_proveedor=None, id_empresa=1, id_usuario=1, monto_especifico=None, observacion="Cruce automático de cuentas"):
    """
    Compensa automáticamente o por monto específico los saldos pendientes
    entre un cliente y un proveedor vinculados.
    
    Actualiza:
    - cuentas_por_cobrar (FIFO)
    - clientes.Saldo_Pendiente_Total
    - pagos_cuentascobrar y abonos_general
    - cuentas_por_pagar (FIFO)
    - proveedores.Saldo_Pendiente
    - pagos_cuentaspagar y abonos_proveedores_detalle
    
    Retorna dict con resultado:
    {
        'success': bool,
        'monto_compensado': float,
        'saldo_cxc_anterior': float,
        'saldo_cxc_nuevo': float,
        'saldo_cxp_anterior': float,
        'saldo_cxp_nuevo': float,
        'mensaje': str
    }
    """
    try:
        # 1. Identificar cliente y proveedor vinculados (búsqueda bidireccional tolerante)
        if id_cliente and not id_proveedor:
            cursor.execute("""
                SELECT c.ID_Cliente, c.Nombre as Nombre_Cliente, c.Saldo_Pendiente_Total, c.ID_Proveedor_Vinculado,
                       p.ID_Proveedor, p.Nombre as Nombre_Proveedor, p.Saldo_Pendiente as Saldo_PXP
                FROM clientes c
                INNER JOIN proveedores p ON (c.ID_Proveedor_Vinculado = p.ID_Proveedor OR p.ID_Cliente_Vinculado = c.ID_Cliente)
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                LIMIT 1
            """, (id_cliente, id_empresa, id_empresa))
            datos = cursor.fetchone()
        elif id_proveedor and not id_cliente:
            cursor.execute("""
                SELECT p.ID_Proveedor, p.Nombre as Nombre_Proveedor, p.Saldo_Pendiente as Saldo_PXP, p.ID_Cliente_Vinculado,
                       c.ID_Cliente, c.Nombre as Nombre_Cliente, c.Saldo_Pendiente_Total
                FROM proveedores p
                INNER JOIN clientes c ON (p.ID_Cliente_Vinculado = c.ID_Cliente OR c.ID_Proveedor_Vinculado = p.ID_Proveedor)
                WHERE p.ID_Proveedor = %s AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL) AND c.ID_Empresa = %s
                LIMIT 1
            """, (id_proveedor, id_empresa, id_empresa))
            datos = cursor.fetchone()
        elif id_cliente and id_proveedor:
            cursor.execute("""
                SELECT c.ID_Cliente, c.Nombre as Nombre_Cliente, c.Saldo_Pendiente_Total, c.ID_Proveedor_Vinculado,
                       p.ID_Proveedor, p.Nombre as Nombre_Proveedor, p.Saldo_Pendiente as Saldo_PXP
                FROM clientes c
                INNER JOIN proveedores p ON (c.ID_Proveedor_Vinculado = p.ID_Proveedor OR p.ID_Cliente_Vinculado = c.ID_Cliente)
                WHERE c.ID_Cliente = %s AND p.ID_Proveedor = %s AND c.ID_Empresa = %s AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                LIMIT 1
            """, (id_cliente, id_proveedor, id_empresa, id_empresa))
            datos = cursor.fetchone()
        else:
            return {'success': False, 'monto_compensado': 0.0, 'mensaje': 'No se especificó cliente ni proveedor.'}

        if not datos:
            return {'success': False, 'monto_compensado': 0.0, 'mensaje': 'No existe contraparte vinculada.'}

        id_cli = datos['ID_Cliente']
        id_prov = datos['ID_Proveedor']
        
        # Asegurar vinculación bidireccional en base de datos si faltaba en alguno
        cursor.execute("UPDATE clientes SET ID_Proveedor_Vinculado = %s WHERE ID_Cliente = %s AND (ID_Proveedor_Vinculado IS NULL OR ID_Proveedor_Vinculado != %s)", (id_prov, id_cli, id_prov))
        cursor.execute("UPDATE proveedores SET ID_Cliente_Vinculado = %s WHERE ID_Proveedor = %s AND (ID_Cliente_Vinculado IS NULL OR ID_Cliente_Vinculado != %s)", (id_cli, id_prov, id_cli))
        nombre_cli = datos['Nombre_Cliente']
        nombre_prov = datos['Nombre_Proveedor']
        saldo_cxc = float(datos.get('Saldo_Pendiente_Total') or 0)
        saldo_cxp = float(datos.get('Saldo_PXP') or 0)

        # Si alguna de las dos cuentas está en 0 o negativa, no hay nada compensable
        if saldo_cxc <= 0.001 or saldo_cxp <= 0.001:
            return {
                'success': True,
                'monto_compensado': 0.0,
                'saldo_cxc_anterior': saldo_cxc,
                'saldo_cxc_nuevo': saldo_cxc,
                'saldo_cxp_anterior': saldo_cxp,
                'saldo_cxp_nuevo': saldo_cxp,
                'mensaje': 'No hay saldos mutuos pendientes que compensar.'
            }

        max_compensable = min(saldo_cxc, saldo_cxp)
        if monto_especifico is not None:
            monto_cruce = min(float(monto_especifico), max_compensable)
        else:
            monto_cruce = max_compensable

        if monto_cruce <= 0.001:
            return {
                'success': True,
                'monto_compensado': 0.0,
                'saldo_cxc_anterior': saldo_cxc,
                'saldo_cxc_nuevo': saldo_cxc,
                'saldo_cxp_anterior': saldo_cxp,
                'saldo_cxp_nuevo': saldo_cxp,
                'mensaje': 'Monto de compensación calculado es cero.'
            }

        # Obtener o asegurar ID del método de pago 'Cruce de Cuentas'
        id_metodo_pago = obtener_o_crear_metodo_pago_cruce(cursor)

        nota_cxc = f"Cruce de Cuentas con Proveedor: {nombre_prov} (ID #{id_prov}). {observacion}".strip()
        nota_cxp = f"Cruce de Cuentas con Cliente: {nombre_cli} (ID #{id_cli}). {observacion}".strip()

        # -------------------------------------------------------------
        # 1. APLICAR FIFO EN CUENTAS POR COBRAR (CxC) DEL CLIENTE
        # -------------------------------------------------------------
        cursor.execute("""
            SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente, Fecha_Vencimiento
            FROM cuentas_por_cobrar
            WHERE ID_Cliente = %s AND Estado IN ('Pendiente', 'Vencida') AND Saldo_Pendiente > 0
            ORDER BY Fecha_Vencimiento ASC, ID_Movimiento ASC
        """, (id_cli,))
        cuentas_cxc = cursor.fetchall()

        remanente_cxc = monto_cruce
        for cxc in cuentas_cxc:
            if remanente_cxc <= 0.0001:
                break
            saldo_inv = float(cxc['Saldo_Pendiente'] or 0)
            abono_aplicar = min(remanente_cxc, saldo_inv)
            nuevo_saldo_inv = saldo_inv - abono_aplicar
            nuevo_estado_inv = 'Pagada' if nuevo_saldo_inv <= 0.0001 else 'Pendiente'

            # Registrar en pagos_cuentascobrar
            cursor.execute("""
                INSERT INTO pagos_cuentascobrar 
                (ID_Movimiento, Monto, ID_MetodoPago, Comentarios, Detalles_Metodo, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (cxc['ID_Movimiento'], abono_aplicar, id_metodo_pago, nota_cxc, 'Cruce de Cuentas Contable', id_usuario))

            # Registrar en abonos_general
            cursor.execute("""
                INSERT INTO abonos_general 
                (ID_Usuario, ID_Cliente, ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo, ID_MetodoPago, caja_movimientos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_usuario, id_cli, cxc['ID_Movimiento'], abono_aplicar, saldo_inv, nuevo_saldo_inv, id_metodo_pago, 'Cruce de Cuentas'))

            # Actualizar cuenta por cobrar
            cursor.execute("""
                UPDATE cuentas_por_cobrar
                SET Saldo_Pendiente = %s, Estado = %s
                WHERE ID_Movimiento = %s
            """, (nuevo_saldo_inv, nuevo_estado_inv, cxc['ID_Movimiento']))

            remanente_cxc -= abono_aplicar

        # Actualizar saldo total del cliente
        nuevo_saldo_cxc = max(0.0, saldo_cxc - monto_cruce)
        cursor.execute("""
            UPDATE clientes
            SET Saldo_Pendiente_Total = %s, Fecha_Ultimo_Pago = NOW(), Fecha_Ultimo_Movimiento = NOW()
            WHERE ID_Cliente = %s AND ID_Empresa = %s
        """, (nuevo_saldo_cxc, id_cli, id_empresa))

        # -------------------------------------------------------------
        # 2. APLICAR FIFO EN CUENTAS POR PAGAR (CxP) DEL PROVEEDOR
        # -------------------------------------------------------------
        cursor.execute("""
            SELECT ID_Cuenta, Num_Documento, Saldo_Pendiente, Fecha_Vencimiento
            FROM cuentas_por_pagar
            WHERE ID_Proveedor = %s AND ID_Empresa = %s AND Estado IN ('Pendiente', 'Vencida', 'Parcial') AND Saldo_Pendiente > 0
            ORDER BY Fecha_Vencimiento ASC, ID_Cuenta ASC
        """, (id_prov, id_empresa))
        cuentas_cxp = cursor.fetchall()

        # Si el proveedor tenía saldo pendiente registrado pero sin renglón en cuentas_por_pagar
        if not cuentas_cxp and saldo_cxp > 0:
            cursor.execute("""
                INSERT INTO cuentas_por_pagar 
                (Fecha, ID_Proveedor, Num_Documento, Observacion, Tipo_Movimiento, Monto_Movimiento, ID_Empresa, Saldo_Pendiente, ID_Usuario_Creacion, Estado)
                VALUES (NOW(), %s, 'SALDO-INICIAL', 'Saldo inicial adeudado a proveedor', 1, %s, %s, %s, %s, 'Pendiente')
            """, (id_prov, saldo_cxp, id_empresa, saldo_cxp, id_usuario))
            id_cxp_creada = cursor.lastrowid
            cuentas_cxp = [{
                'ID_Cuenta': id_cxp_creada,
                'Num_Documento': 'SALDO-INICIAL',
                'Saldo_Pendiente': saldo_cxp,
                'Fecha_Vencimiento': None
            }]

        remanente_cxp = monto_cruce
        for cxp in cuentas_cxp:
            if remanente_cxp <= 0.0001:
                break
            saldo_inv_cxp = float(cxp['Saldo_Pendiente'] or 0)
            abono_aplicar_cxp = min(remanente_cxp, saldo_inv_cxp)
            nuevo_saldo_cxp = saldo_inv_cxp - abono_aplicar_cxp
            nuevo_estado_cxp = 'Pagada' if nuevo_saldo_cxp <= 0.0001 else 'Parcial'

            # Registrar en pagos_cuentaspagar
            cursor.execute("""
                INSERT INTO pagos_cuentaspagar 
                (ID_Cuenta, Fecha, Monto, ID_MetodoPago, Detalles_Metodo, Comentarios, ID_Usuario_Creacion)
                VALUES (%s, NOW(), %s, %s, %s, %s, %s)
            """, (cxp['ID_Cuenta'], abono_aplicar_cxp, id_metodo_pago, 'Cruce de Cuentas Contable', nota_cxp, id_usuario))

            # Registrar en abonos_proveedores_detalle
            cursor.execute("""
                INSERT INTO abonos_proveedores_detalle 
                (ID_Usuario, ID_Proveedor, ID_CuentaPagar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo, ID_MetodoPago, Detalles_Metodo, Comentarios)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_usuario, id_prov, cxp['ID_Cuenta'], abono_aplicar_cxp, saldo_inv_cxp, nuevo_saldo_cxp, id_metodo_pago, 'Cruce de Cuentas Contable', nota_cxp))

            # Actualizar cuenta por pagar
            cursor.execute("""
                UPDATE cuentas_por_pagar
                SET Saldo_Pendiente = %s, Estado = %s
                WHERE ID_Cuenta = %s
            """, (nuevo_saldo_cxp, nuevo_estado_cxp, cxp['ID_Cuenta']))

            remanente_cxp -= abono_aplicar_cxp

        # Actualizar saldo total del proveedor
        nuevo_saldo_cxp = max(0.0, saldo_cxp - monto_cruce)
        cursor.execute("""
            UPDATE proveedores
            SET Saldo_Pendiente = %s
            WHERE ID_Proveedor = %s AND (ID_Empresa = %s OR ID_Empresa IS NULL)
        """, (nuevo_saldo_cxp, id_prov, id_empresa))

        logger.info(f"Cruce de cuentas aplicado: Cliente #{id_cli} y Proveedor #{id_prov} por monto C$ {monto_cruce:,.2f}")

        return {
            'success': True,
            'monto_compensado': monto_cruce,
            'saldo_cxc_anterior': saldo_cxc,
            'saldo_cxc_nuevo': nuevo_saldo_cxc,
            'saldo_cxp_anterior': saldo_cxp,
            'saldo_cxp_nuevo': nuevo_saldo_cxp,
            'mensaje': f'Se compensaron exitosamente C$ {monto_cruce:,.2f} entre {nombre_cli} y {nombre_prov}.'
        }

    except Exception as e:
        logger.error(f"Error procesando compensación vinculada: {e}", exc_info=True)
        raise e


def auto_compensar_saldos_mutuos(cursor, id_empresa=1, id_usuario=1):
    """
    Busca automáticamente todas las parejas de clientes y proveedores vinculados
    que tengan saldos mutuos pendientes (ambos > 0) y ejecuta el cruce
    de cuentas inmediato sin intervención del usuario.
    """
    try:
        cursor.execute("""
            SELECT c.ID_Cliente, p.ID_Proveedor
            FROM clientes c
            INNER JOIN proveedores p ON (c.ID_Proveedor_Vinculado = p.ID_Proveedor OR p.ID_Cliente_Vinculado = c.ID_Cliente)
            WHERE c.Saldo_Pendiente_Total > 0.001 
              AND p.Saldo_Pendiente > 0.001
              AND c.Estado = 'ACTIVO'
              AND p.Estado = 'ACTIVO'
        """)
        parejas = cursor.fetchall()
        total_compensados = 0
        for par in parejas:
            res = procesar_compensacion_vinculada(
                cursor,
                id_cliente=par['ID_Cliente'],
                id_proveedor=par['ID_Proveedor'],
                id_empresa=id_empresa,
                id_usuario=id_usuario,
                observacion="Auto-compensación automática del sistema"
            )
            if res.get('success') and res.get('monto_compensado', 0) > 0:
                total_compensados += 1
        return total_compensados
    except Exception as e:
        logger.error(f"Error en auto_compensar_saldos_mutuos: {e}", exc_info=True)
        return 0
