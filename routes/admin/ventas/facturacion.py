# -*- coding: utf-8 -*-
from decimal import Decimal
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import date, datetime, time, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator
from .. import admin_bp

@admin_bp.route('/ventas/ventas-salidas', methods=['GET'])
@admin_or_bodega_required
@bitacora_decorator("VENTAS-SALIDAS")
def admin_ventas_salidas():
    fecha_str = request.args.get('fecha')
    estado_filtro = request.args.get('estado', 'todas').upper()
    tipo_filtro = request.args.get('tipo', '').upper()
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.now().date()

        with get_db_cursor(True) as cursor:
            # Construir condiciones WHERE dinámicamente
            where_conditions = []
            params = []
            
            if estado_filtro == 'ACTIVAS':
                where_conditions.append("f.Estado = 'Activa'")
            elif estado_filtro == 'ANULADAS':
                where_conditions.append("f.Estado = 'Anulada'")
            
            # Agregar filtro por tipo de venta (Contado/Crédito)
            if tipo_filtro == 'CONTADO':
                where_conditions.append("f.Credito_Contado = 0")
            elif tipo_filtro == 'CREDITO':
                where_conditions.append("f.Credito_Contado = 1")
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Usar subconsulta para obtener solo el movimiento más reciente de cada venta
            cursor.execute(f"""
                SELECT 
                    f.ID_Factura,
                    f.Fecha,
                    f.Observacion,
                    f.ID_Usuario_Creacion,
                    f.Credito_Contado,
                    f.Estado as Estado_Factura, 
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.ID_Movimiento,
                    mi.Tipo_Compra,
                    mi.Estado as Estado_Movimiento,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    (SELECT COUNT(*) FROM detalle_facturacion df 
                     WHERE df.ID_Factura = f.ID_Factura) as Total_Productos,
                    COALESCE((SELECT SUM(Total) FROM detalle_facturacion df 
                     WHERE df.ID_Factura = f.ID_Factura), 0) as Total_Venta,
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        WHEN f.Credito_Contado = 0 THEN 'CONTADO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado,
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 'ACTIVA'
                        WHEN f.Estado = 'Anulada' THEN 'ANULADA'
                        ELSE UPPER(f.Estado)
                    END as Estado_Formateado,
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 'badge-success'
                        WHEN f.Estado = 'Anulada' THEN 'badge-danger'
                        ELSE 'badge-secondary'
                    END as Estado_Clase,
                    -- Usar la estructura correcta de cuentas_por_cobrar
                    (SELECT COUNT(*) FROM cuentas_por_cobrar cpc 
                     WHERE cpc.ID_Factura = f.ID_Factura 
                     AND cpc.Estado IN ('Pendiente', 'Vencida')) as Tiene_Credito_Pendiente
                FROM facturacion f
                LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN (
                    SELECT mi1.*
                    FROM movimientos_inventario mi1
                    INNER JOIN (
                        SELECT ID_Factura_Venta, MAX(Fecha_Creacion) as Ultima_Fecha
                        FROM movimientos_inventario 
                        WHERE ID_Factura_Venta IS NOT NULL
                        GROUP BY ID_Factura_Venta
                    ) mi2 ON mi1.ID_Factura_Venta = mi2.ID_Factura_Venta 
                          AND mi1.Fecha_Creacion = mi2.Ultima_Fecha
                ) mi ON f.ID_Factura = mi.ID_Factura_Venta
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                {where_clause}
                ORDER BY f.Fecha DESC, f.ID_Factura DESC
                LIMIT 10 
            """, tuple(params))
            ventas = cursor.fetchall()
            
            # ========== CONSULTAS DE RESUMEN FINANCIERO ==========
            
            # **CONSULTA 1: Ventas TOTALES (Contado + Crédito) de TODAS las ventas ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(df.Total), 0) as Ventas_Totales
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.Estado = 'Activa'
            """)
            resultado_ventas_total = cursor.fetchone()
            ventas_totales = resultado_ventas_total['Ventas_Totales'] if resultado_ventas_total else 0.0
            
            # **CONSULTA 2: Ventas SOLO AL CONTADO**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(df.Total), 0) as Ventas_Contado
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.Estado = 'Activa'
                    AND f.Credito_Contado = 0
            """)
            resultado_ventas_contado = cursor.fetchone()
            ventas_contado_total = resultado_ventas_contado['Ventas_Contado'] if resultado_ventas_contado else 0.0
            
            # **CONSULTA 3: Ventas en CRÉDITO (total facturado a crédito)**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(df.Total), 0) as Ventas_Credito
                FROM facturacion f
                INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                WHERE f.Estado = 'Activa'
                    AND f.Credito_Contado = 1
            """)
            resultado_ventas_credito = cursor.fetchone()
            ventas_credito_total = resultado_ventas_credito['Ventas_Credito'] if resultado_ventas_credito else 0.0
            
            # **CONSULTA 4: Créditos pendientes de cobrar (usando Saldo_Pendiente)**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(cpc.Saldo_Pendiente), 0) as Creditos_Pendientes
                FROM cuentas_por_cobrar cpc
                INNER JOIN facturacion f ON cpc.ID_Factura = f.ID_Factura
                WHERE cpc.Estado IN ('Pendiente', 'Vencida')
                    AND f.Estado = 'Activa'
            """)
            resultado_creditos_pendientes = cursor.fetchone()
            creditos_pendientes = resultado_creditos_pendientes['Creditos_Pendientes'] if resultado_creditos_pendientes else 0.0
            
            # **CONSULTA 5: Créditos ya cobrados (Pagadas)**
            # Nota: Para saber cuánto se ha cobrado, calculamos Monto_Movimiento - Saldo_Pendiente
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(cpc.Monto_Movimiento - cpc.Saldo_Pendiente), 0) as Creditos_Cobrados
                FROM cuentas_por_cobrar cpc
                INNER JOIN facturacion f ON cpc.ID_Factura = f.ID_Factura
                WHERE cpc.Estado = 'Pagada'
                    AND f.Estado = 'Activa'
            """)
            resultado_creditos_cobrados = cursor.fetchone()
            creditos_cobrados = resultado_creditos_cobrados['Creditos_Cobrados'] if resultado_creditos_cobrados else 0.0
            
            # Alternativa: Si quieres calcular todos los cobrados (incluyendo pagos parciales)
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(cpc.Monto_Movimiento - cpc.Saldo_Pendiente), 0) as Total_Cobrado
                FROM cuentas_por_cobrar cpc
                INNER JOIN facturacion f ON cpc.ID_Factura = f.ID_Factura
                WHERE f.Estado = 'Activa'
                    AND cpc.Saldo_Pendiente = 0
            """)
            resultado_total_cobrado = cursor.fetchone()
            total_cobrado = resultado_total_cobrado['Total_Cobrado'] if resultado_total_cobrado else 0.0
            
            # **VALIDACIÓN: Verificar que contado + crédito = total**
            suma_contado_credito = ventas_contado_total + ventas_credito_total
            diferencia = abs(ventas_totales - suma_contado_credito)
            if diferencia > 0.01:
                print(f"⚠️ ADVERTENCIA: Discrepancia en ventas detectada")
                print(f"   Total BD: {ventas_totales}, Contado: {ventas_contado_total}, Crédito: {ventas_credito_total}")
                print(f"   Suma manual: {suma_contado_credito}, Diferencia: {diferencia}")
                ventas_totales = suma_contado_credito
            
            # ========== ESTADÍSTICAS PARA LAS VENTAS MOSTRADAS (LIMIT 100) ==========
            
            # Obtener estadísticas por estado para mostrar en los filtros
            cursor.execute("""
                SELECT 
                    f.Estado,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(df.Total), 0) as total_monto
                FROM facturacion f
                LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                GROUP BY f.Estado
            """)
            estadisticas_estado = cursor.fetchall()
            
            # Calcular estadísticas SOLO para las ventas mostradas en la tabla
            total_ventas_mostradas = len(ventas)
            monto_total_mostradas = 0.0
            ventas_contado_mostradas = 0
            ventas_credito_mostradas = 0
            ventas_activas_mostradas = 0
            ventas_anuladas_mostradas = 0
            
            for venta in ventas:
                total_venta = venta.get('Total_Venta')
                if total_venta is not None:
                    try:
                        monto_total_mostradas += float(total_venta)
                    except (TypeError, ValueError):
                        pass
                
                if venta.get('Credito_Contado') == 0:
                    ventas_contado_mostradas += 1
                elif venta.get('Credito_Contado') == 1:
                    ventas_credito_mostradas += 1
                
                if venta.get('Estado_Factura') == 'Activa':
                    ventas_activas_mostradas += 1
                elif venta.get('Estado_Factura') == 'Anulada':
                    ventas_anuladas_mostradas += 1
            
            return render_template('admin/ventas/ventas_salidas.html', 
                                 # Datos de la tabla
                                 ventas=ventas,
                                 
                                 # Estadísticas de las ventas MOSTRADAS
                                 total_ventas=total_ventas_mostradas,
                                 ventas_contado=ventas_contado_mostradas,
                                 ventas_credito=ventas_credito_mostradas,
                                 ventas_activas=ventas_activas_mostradas,
                                 ventas_anuladas=ventas_anuladas_mostradas,
                                 monto_total=monto_total_mostradas,
                                 
                                 # Resumen financiero TOTAL
                                 ventas_totales=ventas_totales,
                                 ventas_contado_total=ventas_contado_total,
                                 ventas_credito_total=ventas_credito_total,
                                 creditos_pendientes=creditos_pendientes,
                                 creditos_cobrados=creditos_cobrados,
                                 total_cobrado=total_cobrado,
                                 
                                 # Filtros
                                 estado_filtro=estado_filtro,
                                 tipo_filtro=tipo_filtro, 
                                 estadisticas_estado=estadisticas_estado)
    except Exception as e:
        flash(f'Error al cargar ventas: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/ventas/crear', methods=['GET', 'POST'])
@admin_or_bodega_required
@bitacora_decorator("CREAR_VENTA")
def admin_crear_venta():
    """
    Crear nueva venta con precios según perfil del cliente (Ruta, Mayorista, Mercado)
    
    LÓGICA:
    - Si el cliente paga el 100% (contado): Solo caja, NO cuenta por cobrar
    - Si el cliente paga solo una parte (contado parcial): 
        * Lo pagado va a caja
        * El saldo pendiente se registra automáticamente como CUENTA POR COBRAR
        * Se ACTUALIZA el Saldo_Pendiente_Total del cliente
    """
    try:
        # Obtener ID de empresa y usuario desde la sesión
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        if not id_empresa:
            flash('No se pudo determinar la empresa', 'error')
            return redirect(url_for('admin.admin_ventas_salidas'))
        
        if not id_usuario:
            flash('Usuario no autenticado', 'error')
            return redirect(url_for('admin.admin_ventas_salidas'))

        with get_db_cursor(True) as cursor:
            # Obtener el ID_TipoMovimiento para VENTAS
            cursor.execute("""
                SELECT ID_TipoMovimiento, Descripcion, Letra 
                FROM catalogo_movimientos 
                WHERE Descripcion LIKE '%Venta%' OR Letra = 'S' 
                LIMIT 1
            """)
            tipo_movimiento = cursor.fetchone()
            
            if not tipo_movimiento:
                flash('Error: No se encontró el tipo de movimiento para ventas en el catálogo', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))
            
            id_tipo_movimiento = tipo_movimiento['ID_TipoMovimiento']
            
            # Obtener clientes con su perfil y saldo pendiente
            cursor.execute("""
                SELECT 
                    c.ID_Cliente, 
                    c.Nombre, 
                    c.RUC_CEDULA, 
                    c.tipo_cliente,
                    c.perfil_cliente,
                    c.Saldo_Pendiente_Total,
                    r.Nombre_Ruta
                FROM clientes c
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                WHERE c.Estado = 'ACTIVO' AND (c.ID_Empresa = %s OR c.ID_Empresa IS NULL)
                ORDER BY c.perfil_cliente, c.Nombre
            """, (id_empresa,))
            clientes = cursor.fetchall()
            
            # Obtener bodega principal
            cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_principal = cursor.fetchone()
            if not bodega_principal:
                flash('Error: No hay bodegas activas en el sistema', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))
            
            id_bodega_principal = bodega_principal['ID_Bodega']
            
            # Obtener categorías de productos
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            # Obtener productos con los 3 tipos de precio
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    COALESCE(ib.Existencias, 0) as Existencias,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    p.ID_Categoria,
                    c.Descripcion as Categoria
                FROM productos p
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                WHERE p.Estado = 'activo' 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND COALESCE(ib.Existencias, 0) > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_bodega_principal, id_empresa))
            productos = cursor.fetchall()
            
            # Obtener datos de la empresa
            cursor.execute("SELECT Nombre_Empresa, RUC, Direccion, Telefono FROM empresa WHERE ID_Empresa = %s", (id_empresa,))
            empresa_data = cursor.fetchone()
            
            # Obtener métodos de pago disponibles
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM metodos_pago 
                ORDER BY ID_MetodoPago
            """)
            metodos_pago = cursor.fetchall()

        # Si es POST, procesar el formulario
        if request.method == 'POST':
            print("📨 Iniciando procesamiento de venta...")
            
            # Obtener datos del formulario
            id_cliente = request.form.get('id_cliente','').strip()
            tipo_venta = request.form.get('tipo_venta')
            observacion = request.form.get('observacion', '')
            fecha_vencimiento = request.form.get('fecha_vencimiento', '')
            
            # Obtener métodos de pago del formulario
            metodos_pago_ids = request.form.getlist('metodo_pago_id[]')
            metodos_pago_nombres = request.form.getlist('metodo_pago_nombre[]')
            montos_pago = request.form.getlist('monto_pago[]')
            referencias_pago = request.form.getlist('referencia_pago[]')
            
            # Obtener productos del formulario
            productos_ids = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            precios = request.form.getlist('precio[]')
            
            print(f"Datos recibidos - Cliente: {id_cliente}, Tipo: {tipo_venta}")
            print(f"Productos recibidos: {len(productos_ids)}")
            print(f"Métodos de pago: {len(metodos_pago_ids)}")
            
            # Validaciones básicas
            if not id_cliente or not tipo_venta:
                error_msg = 'Cliente y tipo de venta son obligatorios'
                print(f"❌ {error_msg}")
                flash(error_msg, 'error')
                return render_template('admin/ventas/crear_venta.html',
                                    clientes=clientes,
                                    bodega_principal=bodega_principal,
                                    productos=productos,
                                    categorias=categorias,
                                    empresa=empresa_data,
                                    metodos_pago=metodos_pago,
                                    id_tipo_movimiento=id_tipo_movimiento)
            
            if not productos_ids or len(productos_ids) == 0:
                error_msg = 'Debe agregar al menos un producto a la venta'
                print(f"❌ {error_msg}")
                flash(error_msg, 'error')
                return render_template('admin/ventas/crear_venta.html',
                                    clientes=clientes,
                                    bodega_principal=bodega_principal,
                                    productos=productos,
                                    categorias=categorias,
                                    empresa=empresa_data,
                                    metodos_pago=metodos_pago,
                                    id_tipo_movimiento=id_tipo_movimiento)
            
            # Usar otro contexto para la transacción de la venta
            with get_db_cursor(True) as cursor:
                # Obtener perfil del cliente y saldo actual
                cursor.execute("""
                    SELECT tipo_cliente, perfil_cliente, Nombre, Saldo_Pendiente_Total
                    FROM clientes 
                    WHERE ID_Cliente = %s
                """, (id_cliente,))
                
                cliente_data = cursor.fetchone()
                if not cliente_data:
                    raise Exception("Cliente no encontrado")
                
                tipo_cliente = cliente_data['tipo_cliente']
                perfil_cliente = cliente_data['perfil_cliente']
                nombre_cliente = cliente_data['Nombre']
                saldo_actual_cliente = float(cliente_data['Saldo_Pendiente_Total'] or 0)
                
                print(f"👤 Cliente: {nombre_cliente}")
                print(f"📊 Perfil: {perfil_cliente} | Tipo: {tipo_cliente}")
                print(f"💰 Saldo actual del cliente (antes de esta venta): C${saldo_actual_cliente:,.2f}")
                
                # Verificar facturas pendientes (solo para información)
                cursor.execute("""
                    SELECT 
                        COUNT(*) as facturas_pendientes,
                        COALESCE(SUM(Saldo_Pendiente), 0) as total_pendiente
                    FROM cuentas_por_cobrar 
                    WHERE ID_Cliente = %s 
                    AND Estado IN ('Pendiente', 'Vencida')
                    AND Saldo_Pendiente > 0
                    AND ID_Factura IS NOT NULL
                """, (id_cliente,))
                
                estado_cuenta = cursor.fetchone()
                facturas_pendientes = estado_cuenta['facturas_pendientes'] or 0
                total_pendiente = float(estado_cuenta['total_pendiente'] or 0)
                
                if facturas_pendientes > 0:
                    print(f"📋 Cliente tiene {facturas_pendientes} factura(s) pendiente(s) por C${total_pendiente:,.2f}")
                    observacion = f"{observacion} | Cliente tiene {facturas_pendientes} factura(s) pendiente(s) por C${total_pendiente:,.2f}"
                
                # Validar visibilidad de productos
                productos_invalidos = []
                for i, producto_id in enumerate(productos_ids):
                    cantidad = float(cantidades[i]) if cantidades[i] else 0
                    if cantidad <= 0:
                        continue
                    
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as valido,
                            p.Descripcion,
                            c.Descripcion as categoria_nombre
                        FROM productos p
                        INNER JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                        INNER JOIN config_visibilidad_categorias cfg ON c.ID_Categoria = cfg.ID_Categoria
                        WHERE p.ID_Producto = %s
                          AND cfg.tipo_cliente = %s
                          AND cfg.visible = 1
                          AND p.Estado = 'activo'
                    """, (producto_id, tipo_cliente))
                    
                    resultado = cursor.fetchone()
                    if not resultado or resultado['valido'] == 0:
                        productos_invalidos.append({
                            'id': producto_id,
                            'nombre': resultado['Descripcion'] if resultado else f"ID:{producto_id}",
                            'categoria': resultado['categoria_nombre'] if resultado else 'Desconocida'
                        })
                
                if productos_invalidos:
                    productos_error = ", ".join([f"{p['nombre']} ({p['categoria']})" for p in productos_invalidos])
                    error_msg = f"Los siguientes productos no están disponibles para este cliente ({tipo_cliente}): {productos_error}"
                    print(f"❌ {error_msg}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'success': False, 'error': error_msg}), 400
                    else:
                        flash(error_msg, 'error')
                        return render_template('admin/ventas/crear_venta.html',
                                            clientes=clientes,
                                            bodega_principal=bodega_principal,
                                            productos=productos,
                                            categorias=categorias,
                                            empresa=empresa_data,
                                            metodos_pago=metodos_pago,
                                            id_tipo_movimiento=id_tipo_movimiento)
                
                print("✅ Validación de visibilidad completada")
                
                # Calcular total de la venta
                total_venta = 0
                items_venta = []
                
                for i in range(len(productos_ids)):
                    id_producto = int(productos_ids[i])
                    cantidad = float(cantidades[i]) if cantidades[i] else 0
                    precio = float(precios[i]) if precios[i] else 0
                    
                    if cantidad <= 0 or precio <= 0:
                        continue
                    
                    total_linea = cantidad * precio
                    total_venta += total_linea
                    
                    items_venta.append({
                        'id_producto': id_producto,
                        'cantidad': cantidad,
                        'precio': precio,
                        'total_linea': total_linea
                    })
                
                # 🔥 PROCESAR PAGOS - Calcular cuánto pagó el cliente
                metodos_pago_list = []
                total_pagado = 0
                monto_efectivo = 0
                
                for i in range(len(metodos_pago_ids)):
                    if i < len(montos_pago) and montos_pago[i]:
                        monto = float(montos_pago[i])
                        if monto > 0:
                            nombre_metodo = metodos_pago_nombres[i] if i < len(metodos_pago_nombres) else ''
                            
                            metodo_pago = {
                                'id_metodo': int(metodos_pago_ids[i]),
                                'nombre': nombre_metodo,
                                'monto': monto,
                                'referencia': referencias_pago[i] if i < len(referencias_pago) else ''
                            }
                            metodos_pago_list.append(metodo_pago)
                            total_pagado += monto
                            
                            if nombre_metodo.upper() in ['EFECTIVO', 'EFECTIVO CORDODAS', 'EFECTIVO DOLARES', 'CASH']:
                                monto_efectivo += monto
                
                print(f"📊 Total venta: C${total_venta:,.2f}")
                print(f"💵 Total pagado: C${total_pagado:,.2f}")
                print(f"💰 Monto en EFECTIVO: C${monto_efectivo:,.2f}")
                
                # 🔥 VALIDACIÓN: El pago no puede exceder el total
                if total_pagado > total_venta:
                    raise Exception(f'El monto total pagado (C${total_pagado:,.2f}) no puede exceder el total de la venta (C${total_venta:,.2f})')
                
                # 🔥 LÓGICA PRINCIPAL: Determinar el saldo a crédito
                saldo_pendiente = total_venta - total_pagado
                
                # Si hay saldo pendiente, necesitamos una fecha de vencimiento
                if saldo_pendiente > 0:
                    if not fecha_vencimiento:
                        from datetime import date, timedelta
                        fecha_vencimiento = (date.today() + timedelta(days=30)).isoformat()
                        print(f"📅 Fecha de vencimiento asignada: {fecha_vencimiento}")
                    
                    # Agregar a la observación
                    observacion = f"{observacion} | PAGO PARCIAL: Pagó C${total_pagado:,.2f}, Saldo pendiente C${saldo_pendiente:,.2f} (Vence: {fecha_vencimiento})"
                else:
                    observacion = f"{observacion} | PAGO COMPLETO: Canceló el 100% de la factura"
                
                print(f"💰 Saldo pendiente a crédito: C${saldo_pendiente:,.2f}")
                
                # 1. Crear factura
                import json
                
                # Guardar métodos de pago en JSON
                metodos_pago_json = json.dumps(metodos_pago_list, ensure_ascii=False) if metodos_pago_list else None
                
                # Credito_Contado: 1 si hay saldo pendiente, 0 si pagó todo
                es_credito = 1 if saldo_pendiente > 0 else 0
                
                cursor.execute("""
                    INSERT INTO facturacion (
                        Fecha, IDCliente, Credito_Contado, Observacion, 
                        metodos_pago, ID_Empresa, ID_Usuario_Creacion
                    )
                    VALUES (CURDATE(), %s, %s, %s, %s, %s, %s)
                """, (
                    id_cliente,
                    es_credito,
                    observacion,
                    metodos_pago_json,
                    id_empresa,
                    id_usuario
                ))
                
                # Obtener el ID de la factura
                cursor.execute("SELECT LAST_INSERT_ID() as id_factura")
                id_factura = cursor.fetchone()['id_factura']
                print(f"🧾 Factura #{id_factura} creada (Credito_Contado={es_credito})")
                
                total_cajillas_huevos = 0
                
                # CONSTANTES
                ID_SEPARADOR = 11
                ID_CATEGORIA_HUEVOS = 1
                ID_BODEGA_EMPAQUE = 1
                
                # 2. Procesar productos
                for item in items_venta:
                    # Verificar stock
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega_principal, item['id_producto']))
                    
                    stock = cursor.fetchone()
                    stock_actual = stock['Stock'] if stock else 0
                    
                    if stock_actual < item['cantidad']:
                        cursor.execute("SELECT Descripcion FROM productos WHERE ID_Producto = %s", (item['id_producto'],))
                        producto_nombre = cursor.fetchone()['Descripcion']
                        raise Exception(f'Stock insuficiente para: {producto_nombre}. Stock actual: {stock_actual}')
                    
                    # Insertar detalle de facturación
                    cursor.execute("""
                        INSERT INTO detalle_facturacion (
                            ID_Factura, ID_Producto, Cantidad, Costo, Total
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, item['id_producto'], item['cantidad'], item['precio'], item['total_linea']))
                    
                    # Actualizar inventario
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (item['cantidad'], id_bodega_principal, item['id_producto']))
                    
                    print(f"  {item['cantidad']} x C${item['precio']} = C${item['total_linea']}")
                    
                    # Detectar productos de huevos
                    cursor.execute("SELECT ID_Categoria FROM productos WHERE ID_Producto = %s", (item['id_producto'],))
                    producto_cat = cursor.fetchone()
                    if producto_cat and producto_cat['ID_Categoria'] == ID_CATEGORIA_HUEVOS:
                        total_cajillas_huevos += item['cantidad']
                
                print(f"🥚 Total cajillas de huevos: {total_cajillas_huevos}")
                
                # 3. Procesar separadores
                separadores_totales = 0
                if total_cajillas_huevos > 0:
                    separadores_entre_cajillas = total_cajillas_huevos
                    separadores_base_extra = total_cajillas_huevos // 10
                    separadores_totales = separadores_entre_cajillas + separadores_base_extra
                    
                    print(f"📦 Separadores necesarios: {separadores_totales}")
                    
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                    
                    stock_separadores = cursor.fetchone()
                    stock_actual_separadores = stock_separadores['Stock'] if stock_separadores else 0
                    
                    if stock_actual_separadores >= separadores_totales:
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = Existencias - %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (separadores_totales, ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                        
                        cursor.execute("""
                            INSERT INTO detalle_facturacion (
                                ID_Factura, ID_Producto, Cantidad, Costo, Total
                            )
                            VALUES (%s, %s, %s, 0, 0)
                        """, (id_factura, ID_SEPARADOR, separadores_totales))
                        
                        print(f"  ✅ {separadores_totales} separadores descontados")
                    else:
                        warning_msg = f'Stock insuficiente de separadores. Necesarios: {separadores_totales}, Disponibles: {stock_actual_separadores}'
                        print(f"  ⚠️ {warning_msg}")
                        cursor.execute("""
                            UPDATE facturacion 
                            SET Observacion = CONCAT(COALESCE(Observacion, ''), ' | [ADVERTENCIA: ', %s, ']')
                            WHERE ID_Factura = %s
                        """, (warning_msg, id_factura))
                
                # 4. Registrar movimiento de inventario
                tipo_movimiento_str = 'CREDITO' if saldo_pendiente > 0 else 'CONTADO'
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        ID_TipoMovimiento, ID_Bodega, Fecha, Tipo_Compra,
                        Observacion, ID_Empresa, ID_Usuario_Creacion, Estado,
                        ID_Factura_Venta
                    )
                    VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, 1, %s)
                """, (
                    id_tipo_movimiento,
                    id_bodega_principal,
                    tipo_movimiento_str,
                    f"{observacion} | Perfil cliente: {perfil_cliente}",
                    id_empresa,
                    id_usuario,
                    id_factura
                ))
                
                cursor.execute("SELECT LAST_INSERT_ID() as id_movimiento")
                id_movimiento = cursor.fetchone()['id_movimiento']
                
                # 5. Insertar detalles del movimiento
                for item in items_venta:
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        item['id_producto'],
                        item['cantidad'],
                        item['precio'],
                        item['precio'],
                        item['total_linea'],
                        id_usuario
                    ))
                
                if separadores_totales > 0:
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, 0, 0, 0, %s)
                    """, (id_movimiento, ID_SEPARADOR, separadores_totales, id_usuario))
                
                # 6. Registrar pago en caja (si hay efectivo)
                if monto_efectivo > 0:
                    descripcion_pago = f"Venta {perfil_cliente} - Factura #{id_factura} - Cliente: {nombre_cliente}"
                    if saldo_pendiente > 0:
                        descripcion_pago = f"Abono inicial - {descripcion_pago}"
                    
                    if len(metodos_pago_list) > 1:
                        otros_metodos = [f'{p["nombre"]}: C${p["monto"]:,.2f}' 
                                        for p in metodos_pago_list 
                                        if p['nombre'].upper() not in ['EFECTIVO', 'EFECTIVO CORDODAS', 'EFECTIVO DOLARES', 'CASH']]
                        if otros_metodos:
                            descripcion_pago += f" (Efectivo únicamente - Otros métodos: {', '.join(otros_metodos)})"
                    
                    cursor.execute("""
                        INSERT INTO caja_movimientos (
                            Fecha, Tipo_Movimiento, Descripcion, Monto, 
                            ID_Factura, ID_Usuario, Referencia_Documento
                        )
                        VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                    """, (
                        descripcion_pago,
                        monto_efectivo,
                        id_factura,
                        id_usuario,
                        f'FAC-{id_factura:05d}'
                    ))
                    print(f"💰 Pago en EFECTIVO registrado en caja: C${monto_efectivo:,.2f}")
                else:
                    print(f"ℹ️ No hay pago en efectivo - No se registra movimiento en caja")
                
                # 7. Crear cuenta por cobrar si hay saldo pendiente
                if saldo_pendiente > 0:
                    print(f"🔴 Creando cuenta por cobrar por saldo pendiente: C${saldo_pendiente:,.2f}")
                    
                    # 🔥 ACTUALIZAR SALDO PENDIENTE CONSOLIDADO DEL CLIENTE
                    nuevo_saldo = saldo_actual_cliente + saldo_pendiente
                    
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = %s,
                            Fecha_Ultimo_Movimiento = NOW(),
                            ID_Ultima_Factura = %s
                        WHERE ID_Cliente = %s
                    """, (nuevo_saldo, id_factura, id_cliente))
                    
                    print(f"💰 Saldo cliente actualizado:")
                    print(f"   Saldo anterior: C${saldo_actual_cliente:,.2f}")
                    print(f"   + Nuevo crédito: C${saldo_pendiente:,.2f}")
                    print(f"   = Nuevo saldo total: C${nuevo_saldo:,.2f}")
                    
                    # Insertar registro en cuentas por cobrar
                    cursor.execute("""
                        INSERT INTO cuentas_por_cobrar (
                            Fecha, ID_Cliente, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                            ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion
                        )
                        VALUES (CURDATE(), %s, %s, %s, %s, 
                                1, %s, %s, %s, %s, %s)
                    """, (
                        id_cliente,
                        f'FAC-{id_factura:05d}',
                        f"Saldo pendiente de venta {perfil_cliente} - {observacion}",
                        fecha_vencimiento,
                        saldo_pendiente,
                        id_empresa,
                        saldo_pendiente,
                        id_factura,
                        id_usuario
                    ))
                    print(f"💳 Cuenta por cobrar creada por C${saldo_pendiente:,.2f} con vencimiento {fecha_vencimiento}")
                else:
                    # No hay crédito, solo actualizar última factura
                    cursor.execute("""
                        UPDATE clientes 
                        SET Fecha_Ultimo_Movimiento = NOW(),
                            ID_Ultima_Factura = %s
                        WHERE ID_Cliente = %s
                    """, (id_factura, id_cliente))
                    print(f"ℹ️ No hay saldo pendiente - No se crea cuenta por cobrar")
                
                # Construir mensaje de éxito
                if saldo_pendiente > 0:
                    success_msg = f'✅ Venta {perfil_cliente} creada! Factura #{id_factura} - Total: C${total_venta:,.2f} - Pagado: C${total_pagado:,.2f} - Saldo pendiente (crédito): C${saldo_pendiente:,.2f} - Vence: {fecha_vencimiento}'
                else:
                    success_msg = f'✅ Venta {perfil_cliente} completada! Factura #{id_factura} - Total: C${total_venta:,.2f} - Pagado: C${total_pagado:,.2f}'
                
                print(f"🎯 {success_msg}")
                flash(success_msg, 'success')
                
                return jsonify({
                    'success': True,
                    'message': success_msg,
                    'id_factura': id_factura,
                    'total_venta': total_venta,
                    'total_pagado': total_pagado,
                    'monto_efectivo': monto_efectivo,
                    'saldo_pendiente': saldo_pendiente,
                    'nuevo_saldo_cliente': nuevo_saldo if saldo_pendiente > 0 else saldo_actual_cliente,
                    'metodos_pago': metodos_pago_list,
                    'perfil_cliente': perfil_cliente,
                    'cajillas_huevos': total_cajillas_huevos,
                    'separadores': separadores_totales,
                    'facturas_pendientes': facturas_pendientes,
                    'total_pendiente': total_pendiente,
                    'fecha_vencimiento': fecha_vencimiento if saldo_pendiente > 0 else None,
                    'redirect_url': url_for('admin.admin_generar_ticket', id_factura=id_factura)
                })
        
        # Si es GET, mostrar el formulario
        return render_template('admin/ventas/crear_venta.html',
                            clientes=clientes,
                            bodega_principal=bodega_principal,
                            productos=productos,
                            categorias=categorias,
                            empresa=empresa_data,
                            metodos_pago=metodos_pago,
                            id_tipo_movimiento=id_tipo_movimiento)
            
    except Exception as e:
        error_msg = f' Error al procesar venta: {str(e)}'
        print(f"{error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        
        if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
        
        flash(error_msg, 'error')
        return render_template('admin/ventas/crear_venta.html',
                            clientes=clientes if 'clientes' in locals() else [],
                            bodega_principal=bodega_principal if 'bodega_principal' in locals() else None,
                            productos=productos if 'productos' in locals() else [],
                            categorias=categorias if 'categorias' in locals() else [],
                            empresa=empresa_data if 'empresa_data' in locals() else None,
                            metodos_pago=metodos_pago if 'metodos_pago' in locals() else [],
                            id_tipo_movimiento=id_tipo_movimiento if 'id_tipo_movimiento' in locals() else None)


@admin_bp.route('/admin/ventas/ticket/<int:id_factura>')
@admin_or_bodega_required
def admin_generar_ticket(id_factura):
    try:
        from datetime import datetime
        
        with get_db_cursor(True) as cursor:
            # Obtener datos de la factura (usando SOLO facturacion)
            cursor.execute("""
                SELECT 
                    f.ID_Factura,
                    f.Fecha,
                    f.Observacion,
                    f.Credito_Contado,
                    f.ID_Usuario_Creacion,
                    f.metodos_pago,
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    c.Telefono as Telefono_Cliente,
                    c.Direccion as Direccion_Cliente,
                    c.perfil_cliente,
                    c.Saldo_Pendiente_Total,
                    r.Nombre_Ruta,
                    u.NombreUsuario as Usuario,
                    e.ID_Empresa,
                    COALESCE(e.Nombre_Empresa, 'MI EMPRESA') as Nombre_Empresa,
                    COALESCE(e.RUC, 'RUC NO CONFIGURADO') as RUC_Empresa,
                    COALESCE(e.Direccion, '') as Direccion_Empresa,
                    COALESCE(e.Telefono, '') as Telefono_Empresa,
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado
                FROM facturacion f
                LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa e ON f.ID_Empresa = e.ID_Empresa
                WHERE f.ID_Factura = %s
            """, (id_factura,))
            factura = cursor.fetchone()
            
            if not factura:
                flash('Factura no encontrada', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))
            
            # Obtener detalles de la factura
            cursor.execute("""
                SELECT 
                    df.ID_Detalle,
                    df.Cantidad,
                    df.Costo as Precio,
                    df.Total as Subtotal,
                    p.ID_Producto,
                    COALESCE(p.COD_Producto, 'N/A') as COD_Producto,
                    COALESCE(p.Descripcion, 'PRODUCTO ELIMINADO') as Producto,
                    cat.Descripcion as Categoria
                FROM detalle_facturacion df
                LEFT JOIN productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
                WHERE df.ID_Factura = %s
                ORDER BY df.ID_Detalle
            """, (id_factura,))
            detalles = cursor.fetchall()
            
            if not detalles:
                flash('La factura no tiene detalles de productos', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))
            
            # Calcular total de la venta actual
            total_venta_actual = sum(float(detalle['Subtotal'] or 0) for detalle in detalles)
            
            # Obtener saldo anterior del cliente (suma de cuentas por cobrar pendientes ANTES de esta venta)
            cursor.execute("""
                SELECT COALESCE(SUM(Saldo_Pendiente), 0) as Saldo_Anterior
                FROM cuentas_por_cobrar 
                WHERE ID_Cliente = %s 
                AND Estado IN ('Pendiente', 'Vencida')
                AND Saldo_Pendiente > 0
                AND ID_Factura != %s
            """, (factura['ID_Cliente'], id_factura))
            saldo_anterior_result = cursor.fetchone()
            saldo_anterior = float(saldo_anterior_result['Saldo_Anterior'] or 0)
            
            # Calcular saldo total (saldo anterior + venta actual)
            saldo_total = saldo_anterior + total_venta_actual
            
            # Obtener abono/cliente (si es crédito, el abono es 0; si es contado, es el total pagado)
            abono_cliente = 0
            concepto_abono = ''
            fecha_abono = ''
            
            if factura['Credito_Contado'] == 0:  # CONTADO
                import json
                if factura['metodos_pago']:
                    try:
                        metodos_pago = json.loads(factura['metodos_pago'])
                        abono_cliente = sum(float(p.get('monto', 0)) for p in metodos_pago)
                        concepto_abono = "Pago realizado en efectivo/transferencia"
                        fecha_abono = datetime.now().strftime('%d/%m/%Y %H:%M')
                    except:
                        abono_cliente = total_venta_actual
                        concepto_abono = "Pago en efectivo"
                        fecha_abono = datetime.now().strftime('%d/%m/%Y %H:%M')
                else:
                    abono_cliente = total_venta_actual
                    concepto_abono = "Pago en efectivo"
                    fecha_abono = datetime.now().strftime('%d/%m/%Y %H:%M')
            else:  # CRÉDITO
                # Buscar si hubo algún abono registrado para esta factura en caja_movimientos
                cursor.execute("""
                    SELECT COALESCE(SUM(Monto), 0) as Total_Abonado
                    FROM caja_movimientos
                    WHERE ID_Factura = %s 
                    AND Tipo_Movimiento = 'ENTRADA'
                    AND Estado = 'ACTIVO'
                """, (id_factura,))
                abono_result = cursor.fetchone()
                abono_cliente = float(abono_result['Total_Abonado'] if abono_result else 0)
                
                if abono_cliente > 0:
                    concepto_abono = "Abono registrado en caja"
                    fecha_abono = datetime.now().strftime('%d/%m/%Y %H:%M')
                else:
                    concepto_abono = "Venta a crédito - pendiente de pago"
                    fecha_abono = ''
            
            # Obtener el nuevo saldo pendiente del cliente (de la tabla clientes)
            nuevo_saldo_cliente = float(factura['Saldo_Pendiente_Total'] or 0)
            
            # Obtener facturas pendientes del cliente (para mostrar en el ticket)
            cursor.execute("""
                SELECT 
                    cxc.Num_Documento,
                    cxc.Saldo_Pendiente,
                    cxc.Monto_Movimiento as Monto_Original,
                    cxc.Fecha_Vencimiento,
                    cxc.Estado,
                    DATE_FORMAT(cxc.Fecha_Vencimiento, '%%d/%%m/%%Y') as Fecha_Vencimiento_Formateada
                FROM cuentas_por_cobrar cxc
                WHERE cxc.ID_Cliente = %s 
                AND cxc.Estado IN ('Pendiente', 'Vencida')
                AND cxc.Saldo_Pendiente > 0
                ORDER BY 
                    CASE WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 0 ELSE 1 END,
                    cxc.Fecha_Vencimiento ASC
            """, (factura['ID_Cliente'],))
            facturas_pendientes = cursor.fetchall()
            
            # Formatear valores para mostrar
            venta_realizada_formateada = f"C$ {total_venta_actual:,.2f}"
            saldo_anterior_formateado = f"C$ {saldo_anterior:,.2f}"
            abono_cliente_formateado = f"C$ {abono_cliente:,.2f}" if abono_cliente > 0 else ""
            nuevo_saldo_pendiente_formateado = f"C$ {nuevo_saldo_cliente:,.2f}"
            
            # Procesar métodos de pago para el ticket
            metodos_pago = []
            total_pagado = 0
            
            if factura['Credito_Contado'] == 0 and factura['metodos_pago']:
                import json
                try:
                    metodos_pago = json.loads(factura['metodos_pago'])
                    total_pagado = sum(float(p.get('monto', 0)) for p in metodos_pago)
                except:
                    pass
            
            # Formatear detalles
            for detalle in detalles:
                cantidad = float(detalle['Cantidad'])
                if cantidad.is_integer():
                    detalle['Cantidad_Formateada'] = f"{int(cantidad)}"
                else:
                    detalle['Cantidad_Formateada'] = f"{cantidad:,.2f}"
                detalle['Precio_Formateado'] = f"C$ {float(detalle['Precio']):,.2f}"
                detalle['Subtotal_Formateado'] = f"C$ {float(detalle['Subtotal']):,.2f}"
            
            hora_emision = datetime.now()
            
            # Obtener información de cuenta por cobrar para crédito
            cuenta_cobrar = None
            if factura['Credito_Contado'] == 1:
                cursor.execute("""
                    SELECT 
                        Saldo_Pendiente,
                        Fecha_Vencimiento,
                        Num_Documento
                    FROM cuentas_por_cobrar
                    WHERE ID_Factura = %s
                    AND Estado IN ('Pendiente', 'Vencida')
                    LIMIT 1
                """, (id_factura,))
                cuenta_cobrar = cursor.fetchone()
            
            # Preparar datos para el template
            ticket_data = {
                'id_factura': factura['ID_Factura'],
                'fecha': factura['Fecha'],
                'hora_emision': hora_emision,
                'cliente': factura['Cliente'] or 'Consumidor Final',
                'ruc_cliente': factura['RUC_Cliente'] or 'Consumidor Final',
                'ruta': factura['Nombre_Ruta'] or 'N/A',
                'cliente_detalles': {
                    'telefono': factura['Telefono_Cliente'],
                    'direccion': factura['Direccion_Cliente']
                },
                'perfil_cliente': factura.get('perfil_cliente', 'No definido'),
                'tipo_venta': factura['Tipo_Venta_Formateado'],
                'observacion': factura['Observacion'],
                'usuario': factura['Usuario'] or 'Usuario No Especificado',
                'detalles': detalles,
                'total': total_venta_actual,
                'total_formateado': f"C$ {total_venta_actual:,.2f}",
                'total_pagado': total_pagado,
                'saldo_pendiente': nuevo_saldo_cliente if factura['Credito_Contado'] == 1 else max(0, total_venta_actual - total_pagado),
                'metodos_pago': metodos_pago,
                'empresa': {
                    'nombre': factura['Nombre_Empresa'],
                    'ruc': factura['RUC_Empresa'],
                    'direccion': factura['Direccion_Empresa'],
                    'telefono': factura['Telefono_Empresa']
                },
                'es_credito': factura['Credito_Contado'] == 1,
                'cuenta_cobrar': cuenta_cobrar,
                'facturas_pendientes': facturas_pendientes
            }
            
            return render_template('admin/ventas/ticket_venta.html', 
                                 ticket=ticket_data,
                                 venta_realizada_formateada=venta_realizada_formateada,
                                 saldo_anterior_formateado=saldo_anterior_formateado,
                                 saldo_total=saldo_total,
                                 abono_cliente=abono_cliente,
                                 abono_cliente_formateado=abono_cliente_formateado,
                                 nuevo_saldo_pendiente=nuevo_saldo_cliente,
                                 nuevo_saldo_pendiente_formateado=nuevo_saldo_pendiente_formateado,
                                 concepto_abono=concepto_abono,
                                 fecha_abono=fecha_abono,
                                 facturas_pendientes=facturas_pendientes)
                             
    except Exception as e:
        flash(f'Error al generar ticket: {str(e)}', 'error')
        print(f"Error detallado: {traceback.format_exc()}")
        return redirect(url_for('admin.admin_ventas_salidas'))


@admin_bp.route('/admin/ventas/detalles/<int:id_factura>', methods=['GET'])
@bitacora_decorator("DETALLES_VENTA")
def admin_detalles_venta(id_factura):
    try:
        # Obtener ID de empresa desde la sesión
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # 1. Obtener información general de la factura - INCLUYENDO MÉTODOS DE PAGO
            cursor.execute("""
                SELECT 
                    f.ID_Factura,
                    DATE_FORMAT(f.Fecha, '%d/%m/%Y') as Fecha_Formateada, 
                    f.Fecha as Fecha_Original,
                    f.Observacion,
                    f.ID_Usuario_Creacion,
                    f.Credito_Contado,
                    f.Estado as Estado_Factura,
                    f.ID_Empresa,
                    f.metodos_pago,
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    c.Direccion as Direccion_Cliente,
                    c.Telefono as Telefono_Cliente,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.ID_Movimiento,
                    mi.Estado as Estado_Movimiento,
                    mi.ID_Bodega,
                    COALESCE(b.Nombre, 'BODEGA PRINCIPAL') as Bodega,
                    e.Nombre_Empresa,
                    e.RUC as RUC_Empresa,
                    e.Direccion as Direccion_Empresa,
                    e.Telefono as Telefono_Empresa,
                    -- Formatear tipo de venta
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado,
                    f.Credito_Contado as Tipo_Venta_Numerico,
                    f.Estado as Estado_Factura,
                    UPPER(f.Estado) as Estado_Factura_Formateado,
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 1
                        ELSE 0
                    END as Estado_Factura_Numerico,
                    COALESCE(mi.Estado, 'NO APLICA') as Estado_Movimiento_Formateado,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'ACTIVO'
                        WHEN mi.Estado = 'Anulada' THEN 'ANULADO'
                        ELSE 'NO APLICA'
                    END as Estado_Movimiento_Mayusculas,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 1
                        WHEN mi.Estado = 'Anulada' THEN 0
                        ELSE -1
                    END as Estado_Movimiento_Numerico,
                    -- Calcular total de la factura
                    COALESCE((SELECT SUM(Total) FROM detalle_facturacion WHERE ID_Factura = f.ID_Factura), 0) as Total_Factura,
                    -- Obtener tipo de movimiento si existe
                    cm.Descripcion as Tipo_Movimiento
                FROM facturacion f
                LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa e ON f.ID_Empresa = e.ID_Empresa
                LEFT JOIN movimientos_inventario mi ON mi.ID_Factura_Venta = f.ID_Factura
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE f.ID_Factura = %s 
                  AND f.ID_Empresa = %s
                LIMIT 1
            """, (id_factura, id_empresa))
            
            factura = cursor.fetchone()
            
            if not factura:
                flash('Factura no encontrada o no pertenece a su empresa', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))
            
            # 2. PROCESAR MÉTODOS DE PAGO
            import json
            metodos_pago = []
            total_pagado = 0
            
            if factura['metodos_pago']:
                try:
                    metodos_pago = json.loads(factura['metodos_pago'])
                    total_pagado = sum(float(p['monto']) for p in metodos_pago)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"Error al decodificar métodos de pago: {e}")
                    metodos_pago = []
                    total_pagado = 0
            
            # Si es contado pero no hay métodos registrados, mostrar como efectivo completo
            if factura['Credito_Contado'] == 0 and not metodos_pago:
                total_venta = float(factura['Total_Factura'] or 0)
                metodos_pago = [{
                    'nombre': 'Efectivo',
                    'monto': total_venta,
                    'referencia': ''
                }]
                total_pagado = total_venta
            
            # Calcular saldo pendiente
            total_venta = float(factura['Total_Factura'] or 0)
            saldo_pendiente = total_venta - total_pagado if factura['Credito_Contado'] == 1 else 0
            
            # 3. Obtener detalles de los productos vendidos
            cursor.execute("""
            SELECT 
                df.ID_Detalle,
                df.ID_Producto,
                p.COD_Producto,
                p.Descripcion as Producto,
                df.Cantidad,
                df.Costo as Precio_Unitario,
                df.Total as Subtotal,
                cat.Descripcion as Categoria,
                COALESCE(
                    (SELECT Descripcion 
                     FROM unidades_medida um 
                     WHERE um.ID_Unidad = p.Unidad_Medida
                     LIMIT 1),
                    'UNIDAD'
                ) as Unidad_Medida,
                COALESCE(
                    (SELECT Existencias 
                     FROM inventario_bodega ib
                     WHERE ib.ID_Producto = p.ID_Producto 
                       AND ib.ID_Bodega = COALESCE(%s, 1)
                     LIMIT 1),
                    0
                ) as Existencia_Actual,
                COALESCE(
                    (SELECT dmi.Cantidad 
                     FROM detalle_movimientos_inventario dmi
                     WHERE dmi.ID_Producto = p.ID_Producto
                       AND dmi.ID_Movimiento = %s
                     LIMIT 1),
                    df.Cantidad
                ) as Cantidad_Movimiento
            FROM detalle_facturacion df
            INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
            LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
            WHERE df.ID_Factura = %s
            ORDER BY df.ID_Detalle
            """, (factura.get('ID_Bodega', 1), factura.get('ID_Movimiento', 0), id_factura))
            
            detalles = cursor.fetchall()
            
            # 4. Calcular totales
            total_productos = len(detalles)
            
            # 5. Verificar si tiene crédito pendiente
            cursor.execute("""
                SELECT 
                    COUNT(*) as Tiene_Credito_Pendiente,
                    COALESCE(SUM(Saldo_Pendiente), 0) as Saldo_Pendiente_Total,
                    GROUP_CONCAT(Num_Documento SEPARATOR ', ') as Documentos_Credito,
                    MAX(Fecha_Vencimiento) as Fecha_Vencimiento_Max
                FROM cuentas_por_cobrar 
                WHERE ID_Factura = %s 
                  AND Saldo_Pendiente > 0
                  AND Estado = 1
            """, (id_factura,))
            
            credito_info = cursor.fetchone()
            tiene_credito_pendiente = credito_info['Tiene_Credito_Pendiente'] > 0
            
            # 6. Obtener historial de pagos si es crédito (CORREGIDO)
            pagos = []
            if tiene_credito_pendiente:
                try:
                    cursor.execute("""
                        SELECT 
                            DATE_FORMAT(pc.Fecha, '%%d/%%m/%%Y %%H:%%i') as Fecha_Pago_Formateada,
                            pc.Fecha as Fecha_Original,
                            pc.Monto as Monto_Pago,
                            pc.Comentarios as Observacion,
                            COALESCE(mp.Nombre_Metodo, 
                                CASE 
                                    WHEN pc.ID_MetodoPago = 1 THEN 'Efectivo'
                                    WHEN pc.ID_MetodoPago = 2 THEN 'Transferencia'
                                    WHEN pc.ID_MetodoPago = 3 THEN 'Depósito Bancario'
                                    WHEN pc.ID_MetodoPago = 4 THEN 'Tarjeta Débito'
                                    WHEN pc.ID_MetodoPago = 5 THEN 'Tarjeta Crédito'
                                    WHEN pc.ID_MetodoPago = 6 THEN 'Cheque'
                                    ELSE CONCAT('Método ', pc.ID_MetodoPago)
                                END
                            ) as Forma_Pago,
                            pc.Detalles_Metodo as Numero_Comprobante,
                            pc.ID_MetodoPago
                        FROM pagos_cuentascobrar pc
                        LEFT JOIN metodos_pago mp ON pc.ID_MetodoPago = mp.ID_MetodoPago
                        WHERE pc.ID_Movimiento IN (
                            SELECT ID_Movimiento 
                            FROM cuentas_por_cobrar 
                            WHERE ID_Factura = %s 
                              AND Estado = 1
                        )
                        ORDER BY pc.Fecha DESC
                    """, (id_factura,))
                    pagos = cursor.fetchall()
                    print(f"DEBUG - Pagos encontrados para factura {id_factura}: {len(pagos)}")
                except Exception as e:
                    print(f"Error al obtener pagos: {e}")
                    pagos = []
            
            # 7. Obtener datos del movimiento de inventario (si existe)
            movimiento_info = None
            if factura.get('ID_Movimiento'):
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        DATE_FORMAT(mi.Fecha, '%%d/%%m/%%Y') as Fecha_Formateada,
                        mi.Fecha,
                        mi.Observacion,
                        mi.ID_Usuario_Creacion,
                        mi.Estado,
                        mi.ID_Bodega,
                        DATE_FORMAT(mi.Fecha, '%%d/%%m/%%Y %%H:%%i') as Fecha_Completa,
                        cm.Descripcion as Tipo_Movimiento,
                        b.Nombre as Nombre_Bodega,
                        u.NombreUsuario as Usuario_Creacion
                    FROM movimientos_inventario mi
                    LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                    WHERE mi.ID_Movimiento = %s
                """, (factura['ID_Movimiento'],))
                movimiento_info = cursor.fetchone()
            
            # DEBUG: Imprimir información para verificar
            print(f"DEBUG - Factura ID: {factura['ID_Factura']}")
            print(f"DEBUG - Fecha Formateada: {factura['Fecha_Formateada']}")
            print(f"DEBUG - Tipo Venta Formateado: {factura['Tipo_Venta_Formateado']}")
            print(f"DEBUG - Estado Factura: {factura['Estado_Factura']}")
            print(f"DEBUG - Total Pagado: {total_pagado}")
            print(f"DEBUG - Saldo Pendiente: {saldo_pendiente}")
            print(f"DEBUG - Métodos de Pago: {len(metodos_pago)}")
            print(f"DEBUG - Pagos históricos: {len(pagos)}")
            
            return render_template('admin/ventas/detalle_venta.html',
                                 factura=factura,
                                 detalles=detalles,
                                 movimiento_info=movimiento_info,
                                 total_productos=total_productos,
                                 total_venta=total_venta,
                                 total_pagado=total_pagado,
                                 saldo_pendiente=saldo_pendiente,
                                 metodos_pago=metodos_pago,
                                 tiene_credito_pendiente=tiene_credito_pendiente,
                                 credito_info=credito_info,
                                 pagos=pagos,
                                 hoy=datetime.now())
                                 
    except Exception as e:
        flash(f'Error al cargar detalles de la venta: {str(e)}', 'error')
        print(f"Error detallado: {traceback.format_exc()}")
        return redirect(url_for('admin.admin_ventas_salidas'))


@admin_bp.route('/ventas/anular/<int:id_factura>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("ANULAR_VENTA")
def admin_anular_venta(id_factura):
    """Anular una venta/factura existente - GET para mostrar datos, POST para procesar"""
    
    # Obtener datos de sesión
    id_empresa = session.get('id_empresa', 1)
    id_usuario = current_user.id
    
    if not id_empresa:
        return jsonify({'success': False, 'error': 'No se pudo determinar la empresa'}), 400
    
    if request.method == 'GET':
        # ============ OBTENER DATOS PARA MOSTRAR EN MODAL ============
        try:
            with get_db_cursor(True) as cursor:
                # 1. OBTENER DATOS PRINCIPALES DE LA FACTURA
                cursor.execute("""
                    SELECT 
                        f.ID_Factura,
                        f.Fecha,
                        f.Fecha_Creacion,
                        f.Estado,
                        f.Credito_Contado,
                        f.Observacion,
                        f.IDCliente,
                        c.Nombre as cliente_nombre,
                        c.RUC_CEDULA as cliente_ruc,
                        b.Nombre as bodega_nombre,
                        u.NombreUsuario as vendedor,
                        cpc.ID_Movimiento as id_cuenta_cobrar,
                        cpc.Estado as estado_cuenta,
                        cpc.Saldo_Pendiente,
                        DATE_FORMAT(f.Fecha_Creacion, '%d/%m/%Y') as fecha_corta,
                        DATE_FORMAT(f.Fecha_Creacion, '%d/%m/%Y') as fecha_creacion_corta,
                        DATE_FORMAT(f.Fecha_Creacion, '%d/%m/%Y %H:%i') as fecha_completa,
                        DATE_FORMAT(f.Fecha_Creacion, '%H:%i') as hora,
                        (SELECT SUM(Total) FROM detalle_facturacion WHERE ID_Factura = f.ID_Factura) as total_factura,
                        DATEDIFF(CURDATE(), DATE(f.Fecha_Creacion)) as dias_pasados
                    FROM facturacion f
                    LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                    LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                    LEFT JOIN cuentas_por_cobrar cpc ON f.ID_Factura = cpc.ID_Factura
                    LEFT JOIN movimientos_inventario mi ON f.ID_Factura = mi.ID_Factura_Venta AND mi.Estado = 'Activa'
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    WHERE f.ID_Factura = %s 
                    AND f.ID_Empresa = %s
                """, (id_factura, id_empresa))
                
                venta = cursor.fetchone()
                
                if not venta:
                    return jsonify({'success': False, 'error': 'Venta/Factura no encontrada'}), 404
                
                if venta['Estado'] != 'Activa':
                    return jsonify({
                        'success': False, 
                        'error': f'Esta venta ya está {venta["Estado"].lower()}'
                    }), 400
                
                # 2. OBTENER PRODUCTOS DE LA VENTA
                cursor.execute("""
                    SELECT 
                        df.ID_Producto,
                        df.Cantidad,
                        df.Costo as precio_unitario,
                        df.Total as subtotal,
                        p.COD_Producto as codigo,
                        p.Descripcion,
                        p.Unidad_Medida
                    FROM detalle_facturacion df
                    INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                    WHERE df.ID_Factura = %s
                    ORDER BY df.ID_Detalle
                """, (id_factura,))
                
                productos = cursor.fetchall()
                
                # 3. OBTENER MOVIMIENTOS DE CAJA RELACIONADOS
                cursor.execute("""
                    SELECT 
                        cm.ID_Movimiento,
                        cm.Tipo_Movimiento,
                        cm.Descripcion,
                        cm.Monto,
                        DATE_FORMAT(cm.Fecha, '%d/%m/%Y %H:%i') as fecha_movimiento,
                        cm.Referencia_Documento,
                        cm.Estado as estado_caja,
                        cm.Es_Ajuste,
                        cm.Movimiento_Origen,
                        cm.Comentario_Ajuste,
                        DATE_FORMAT(cm.Fecha_Anulacion, '%d/%m/%Y %H:%i') as fecha_anulacion_caja,
                        ua.NombreUsuario as usuario_anula
                    FROM caja_movimientos cm
                    LEFT JOIN usuarios ua ON cm.ID_Usuario_Anula = ua.ID_Usuario
                    WHERE cm.ID_Factura = %s
                    ORDER BY 
                        CASE WHEN cm.Estado = 'ACTIVO' THEN 0 ELSE 1 END,
                        cm.Fecha DESC
                    LIMIT 10
                """, (id_factura,))
                
                movimientos_caja = cursor.fetchall()
                
                # 4. OBTENER PAGOS DE CUENTAS POR COBRAR (si es crédito)
                pagos_cxc = []
                if venta['Credito_Contado'] == 1:
                    cursor.execute("""
                        SELECT 
                            pxc.ID_Pago,
                            pxc.Monto,
                            pxc.Fecha_Pago,
                            pxc.Metodo_Pago,
                            DATE_FORMAT(pxc.Fecha_Pago, '%d/%m/%Y') as fecha_pago_formateada
                        FROM pagos_cxc pxc
                        WHERE pxc.ID_Factura = %s
                        ORDER BY pxc.Fecha_Pago DESC
                    """, (id_factura,))
                    pagos_cxc = cursor.fetchall()
                
                # 5. CALCULAR TOTALES
                total_productos = len(productos)
                total_cantidad = sum(float(p['Cantidad']) for p in productos)
                total_venta = sum(float(p['subtotal']) for p in productos) if productos else 0
                
                # 6. FORMATEAR DATOS PARA EL FRONTEND
                datos_venta = {
                    'id_factura': venta['ID_Factura'],
                    'fecha': venta['fecha_completa'],
                    'fecha_corta': venta['fecha_corta'],
                    'hora': venta['hora'],
                    'fecha_raw': venta['Fecha'].isoformat() if venta['Fecha'] else None,
                    'fecha_creacion_raw': venta['Fecha_Creacion'].isoformat() if venta['Fecha_Creacion'] else None,
                    'estado': venta['Estado'],
                    'tipo_venta': 'CONTADO' if venta['Credito_Contado'] == 0 else 'CRÉDITO',
                    'tipo_venta_raw': venta['Credito_Contado'],
                    'cliente': venta['cliente_nombre'] or 'Consumidor Final',
                    'cliente_ruc': venta['cliente_ruc'] or 'N/A',
                    'bodega': venta['bodega_nombre'] or 'No especificada',
                    'vendedor': venta['vendedor'] or 'Sistema',
                    'observacion': venta['Observacion'] or '',
                    'total_venta': total_venta,
                    'total_venta_formateado': f"C${total_venta:,.2f}",
                    'total_productos': total_productos,
                    'total_cantidad': total_cantidad,
                    'es_factura_pasada': venta['dias_pasados'] > 0,
                    'dias_pasados': venta['dias_pasados'],
                    'tiene_cuenta_cobrar': venta['id_cuenta_cobrar'] is not None,
                    'estado_cuenta': venta['estado_cuenta'],
                    'saldo_pendiente': float(venta['Saldo_Pendiente']) if venta['Saldo_Pendiente'] else 0,
                    'movimientos_caja': [
                        {
                            'id': m['ID_Movimiento'],
                            'tipo': m['Tipo_Movimiento'],
                            'descripcion': m['Descripcion'],
                            'monto': float(m['Monto']),
                            'fecha': m['fecha_movimiento'],
                            'referencia': m['Referencia_Documento'],
                            'estado': m['estado_caja'],
                            'es_ajuste': bool(m['Es_Ajuste']),
                            'movimiento_origen': m['Movimiento_Origen'],
                            'fecha_anulacion': m['fecha_anulacion_caja'],
                            'usuario_anula': m['usuario_anula']
                        }
                        for m in movimientos_caja
                    ],
                    'tiene_movimientos_caja': len(movimientos_caja) > 0,
                    'pagos_cxc': [
                        {
                            'id': p['ID_Pago'],
                            'monto': float(p['Monto']),
                            'fecha_pago': p['fecha_pago_formateada'],
                            'metodo_pago': p['Metodo_Pago']
                        }
                        for p in pagos_cxc
                    ],
                    'tiene_pagos_cxc': len(pagos_cxc) > 0,
                    'productos': [
                        {
                            'id': p['ID_Producto'],
                            'codigo': p['codigo'],
                            'descripcion': p['Descripcion'],
                            'cantidad': float(p['Cantidad']),
                            'precio_unitario': float(p['precio_unitario']),
                            'subtotal': float(p['subtotal']),
                            'unidad_medida': p['Unidad_Medida']
                        }
                        for p in productos
                    ]
                }
                
                return jsonify({
                    'success': True,
                    'venta': datos_venta,
                    'usuario_actual': {
                        'id': id_usuario,
                        'nombre': current_user.NombreUsuario if hasattr(current_user, 'NombreUsuario') else 'Usuario'
                    }
                })
                
        except Exception as e:
            print(f" Error obteniendo datos de venta #{id_factura}: {str(e)}")
            traceback.print_exc()
            
            return jsonify({
                'success': False,
                'error': f'Error interno al obtener datos: {str(e)}'
            }), 500
    
    elif request.method == 'POST':
        # ============ PROCESAR ANULACIÓN ============
        try:
            print(f"🔄 Iniciando anulación de venta #{id_factura}...")
            print(f"⚠️  VERIFICACIÓN: No se debe crear ningún INSERT en movimientos_inventario")
            
            # Verificar usuario
            if not id_usuario:
                flash('Usuario no autenticado', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))

            # Obtener datos del formulario
            motivo_anulacion = request.form.get('motivo_anulacion', 'Anulación por usuario').strip()
            metodo_pago_original = request.form.get('metodo_pago_original', 'efectivo')
            hay_que_revertir_efectivo = request.form.get('revertir_efectivo', '0') == '1'
            comentario_reversion = request.form.get('comentario_reversion', '').strip()
            
            if not motivo_anulacion:
                motivo_anulacion = 'Anulación sin especificar motivo'
            
            with get_db_cursor(True) as cursor:
                # 1. VERIFICAR LA FACTURA/VENTA Y OBTENER DATOS COMPLETOS
                # IMPORTANTE: Buscar el movimiento con Estado = 'Activa' (con tilde)
                cursor.execute("""
                    SELECT 
                        f.ID_Factura,
                        f.Fecha,
                        f.Fecha_Creacion,
                        f.Estado,
                        f.Credito_Contado,
                        f.Observacion,
                        f.IDCliente,
                        c.Nombre as cliente_nombre,
                        c.RUC_CEDULA as cliente_ruc,
                        cpc.ID_Movimiento as id_cuenta_cobrar,
                        cpc.Estado as estado_cuenta,
                        cpc.Saldo_Pendiente,
                        mi.ID_Movimiento as id_movimiento_original,
                        mi.ID_Bodega as id_bodega_original,
                        (SELECT SUM(Total) FROM detalle_facturacion WHERE ID_Factura = f.ID_Factura) as total_factura,
                        (SELECT COUNT(*) FROM caja_movimientos WHERE ID_Factura = f.ID_Factura AND Estado = 'ACTIVO') as movimientos_caja_activos,
                        DATEDIFF(CURDATE(), DATE(f.Fecha_Creacion)) as dias_pasados
                    FROM facturacion f
                    LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                    LEFT JOIN cuentas_por_cobrar cpc ON f.ID_Factura = cpc.ID_Factura
                    LEFT JOIN movimientos_inventario mi ON f.ID_Factura = mi.ID_Factura_Venta 
                        AND (mi.Estado = 'Activa' OR mi.Estado = 'ACTIVA')
                    WHERE f.ID_Factura = %s 
                    AND f.ID_Empresa = %s
                    ORDER BY mi.ID_Movimiento DESC
                    LIMIT 1
                """, (id_factura, id_empresa))
                
                venta = cursor.fetchone()
                
                if not venta:
                    flash('Venta/Factura no encontrada', 'error')
                    return redirect(url_for('admin.admin_ventas_salidas'))
                
                if venta['Estado'] != 'Activa':
                    flash(f'Esta venta ya está {venta["Estado"].lower()}', 'warning')
                    return redirect(url_for('admin.admin_ventas_salidas'))
                
                print(f"📋 Venta #{id_factura} encontrada - Cliente: {venta['cliente_nombre']}")
                print(f"📦 Movimiento original: #{venta['id_movimiento_original']}")
                print(f"💰 Total factura: C${float(venta['total_factura'] or 0):,.2f}")
                
                # Forzar reversión de efectivo si hay movimientos de caja activos
                if venta['movimientos_caja_activos'] > 0:
                    print(f"💰 Esta factura tiene {venta['movimientos_caja_activos']} movimiento(s) de caja ACTIVO(s)")
                    hay_que_revertir_efectivo = True
                
                # Validar cuenta por cobrar si es crédito
                if venta['Credito_Contado'] == 1 and venta['id_cuenta_cobrar']:
                    if venta['estado_cuenta'] == 'Pagada':
                        hay_que_revertir_efectivo = True
                        print("⚠️  Cuenta por cobrar pagada - se requiere reversión de efectivo")
                    elif venta['estado_cuenta'] == 'Anulada':
                        flash('La cuenta por cobrar ya está anulada', 'warning')
                        return redirect(url_for('admin.admin_ventas_salidas'))
                
                # 2. OBTENER LOS PRODUCTOS VENDIDOS
                cursor.execute("""
                    SELECT 
                        df.ID_Producto,
                        df.Cantidad,
                        df.Costo,
                        df.Total as subtotal,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida
                    FROM detalle_facturacion df
                    INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                    WHERE df.ID_Factura = %s
                """, (id_factura,))
                
                productos_vendidos = cursor.fetchall()
                
                if not productos_vendidos:
                    flash('No hay productos en esta venta', 'error')
                    return redirect(url_for('admin.admin_ventas_salidas'))
                
                # Calcular total de la venta
                total_venta = sum(float(p['subtotal']) for p in productos_vendidos)
                print(f"📦 Productos a revertir: {len(productos_vendidos)}")
                
                # 3. DETERMINAR BODEGA
                id_bodega = None
                
                if venta['id_bodega_original']:
                    id_bodega = venta['id_bodega_original']
                    cursor.execute("SELECT Nombre FROM bodegas WHERE ID_Bodega = %s", (id_bodega,))
                    bodega = cursor.fetchone()
                    nombre_bodega = bodega['Nombre'] if bodega else "Desconocida"
                    print(f"🏪 Bodega original: {nombre_bodega} (#{id_bodega})")
                else:
                    cursor.execute("""
                        SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 1 LIMIT 1
                    """)
                    bodega = cursor.fetchone()
                    if bodega:
                        id_bodega = bodega['ID_Bodega']
                        nombre_bodega = bodega['Nombre']
                    else:
                        flash('Error: No hay bodegas activas', 'error')
                        return redirect(url_for('admin.admin_ventas_salidas'))
                
                # ============ CAMBIAR ESTADO DE MOVIMIENTOS DE CAJA ============
                movimientos_caja_anulados = 0
                monto_total_revertido = 0
                
                if hay_que_revertir_efectivo and total_venta > 0:
                    print(f"💰 Cambiando estado de movimientos de caja...")
                    
                    cursor.execute("""
                        SELECT ID_Movimiento, Monto, Tipo_Movimiento, Estado, Descripcion, Es_Ajuste
                        FROM caja_movimientos 
                        WHERE ID_Factura = %s AND Estado = 'ACTIVO'
                        ORDER BY Fecha DESC
                    """, (id_factura,))
                    
                    movimientos_existentes = cursor.fetchall()
                    
                    if movimientos_existentes:
                        for movimiento in movimientos_existentes:
                            cursor.execute("""
                                UPDATE caja_movimientos 
                                SET Estado = 'ANULADO',
                                    Fecha_Anulacion = NOW(),
                                    ID_Usuario_Anula = %s,
                                    Comentario_Ajuste = CONCAT(
                                        COALESCE(Comentario_Ajuste, ''), 
                                        ' | ANULADO POR ANULACIÓN DE VENTA #', %s, ': ', %s
                                    )
                                WHERE ID_Movimiento = %s AND Estado = 'ACTIVO'
                            """, (id_usuario, id_factura, motivo_anulacion, movimiento['ID_Movimiento']))
                            
                            if cursor.rowcount > 0:
                                movimientos_caja_anulados += 1
                                monto_total_revertido += float(movimiento['Monto'])
                    
                    print(f"✅ Movimientos de caja anulados: {movimientos_caja_anulados}")
                
                # 4. MODIFICAR EL MOVIMIENTO DE INVENTARIO ORIGINAL (NO CREAR NUEVO)
                if not venta['id_movimiento_original']:
                    flash('Error: No se encontró el movimiento de inventario original', 'error')
                    return redirect(url_for('admin.admin_ventas_salidas'))
                
                id_movimiento_original = venta['id_movimiento_original']
                print(f"🔄 Modificando movimiento original #{id_movimiento_original} en lugar de crear uno nuevo")
                
                # Preparar observación
                observacion_anulacion = f'ANULADA - Venta #{id_factura} - Cliente: {venta["cliente_nombre"]} - Motivo: {motivo_anulacion}'
                if comentario_reversion:
                    observacion_anulacion += f" - {comentario_reversion}"
                
                # CAMBIAR el tipo de movimiento a ANULACIÓN (ID 10) y estado a 'Anulada'
                cursor.execute("""
                    UPDATE movimientos_inventario 
                    SET ID_TipoMovimiento = 10,  -- Tipo ANULACIÓN
                        Estado = 'Anulada',
                        Observacion = %s,
                        Fecha_Modificacion = NOW(),
                        ID_Usuario_Modificacion = %s
                    WHERE ID_Movimiento = %s
                """, (observacion_anulacion, id_usuario, id_movimiento_original))
                
                print(f"✅ Movimiento #{id_movimiento_original} actualizado a tipo ANULACIÓN")
                
                # ELIMINAR detalles anteriores
                cursor.execute("""
                    DELETE FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento_original,))
                
                print(f"🗑️  Detalles anteriores eliminados")
                
                # INSERTAR nuevos detalles en el MISMO movimiento
                total_devolucion = 0
                productos_devueltos = []
                
                for producto in productos_vendidos:
                    cantidad = float(producto['Cantidad'])
                    costo = float(producto['Costo'])
                    subtotal = float(producto['subtotal'])
                    total_devolucion += subtotal
                    
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion, Fecha_Creacion
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (id_movimiento_original, producto['ID_Producto'], cantidad, 
                          costo, costo, subtotal, id_usuario))
                    
                    # Devolver productos al inventario
                    cursor.execute("""
                        SELECT Existencias 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega, producto['ID_Producto']))
                    
                    inventario = cursor.fetchone()
                    
                    if inventario:
                        nuevas_existencias = float(inventario['Existencias']) + cantidad
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (nuevas_existencias, id_bodega, producto['ID_Producto']))
                    else:
                        cursor.execute("""
                            INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                        """, (id_bodega, producto['ID_Producto'], cantidad))
                    
                    productos_devueltos.append({
                        'codigo': producto['COD_Producto'],
                        'descripcion': producto['Descripcion'],
                        'cantidad': cantidad,
                        'precio': costo,
                        'total': subtotal
                    })
                
                print(f"✅ {len(productos_devueltos)} productos devueltos al inventario")
                print(f"💰 Total devolución: C${total_devolucion:,.2f}")
                
                # 5. ANULAR LA FACTURA
                nueva_observacion = f"{venta['Observacion'] or ''} | ANULADA: {motivo_anulacion}"
                if comentario_reversion:
                    nueva_observacion += f" | {comentario_reversion}"
                
                cursor.execute("""
                    UPDATE facturacion 
                    SET Estado = 'Anulada', Observacion = %s
                    WHERE ID_Factura = %s
                """, (nueva_observacion, id_factura))
                
                print(f"📝 Factura #{id_factura} ANULADA")
                
                # 6. ANULAR CUENTA POR COBRAR SI ES CRÉDITO
                if venta['Credito_Contado'] == 1 and venta['id_cuenta_cobrar']:
                    cursor.execute("""
                        UPDATE cuentas_por_cobrar 
                        SET Estado = 'Anulada',
                            Saldo_Pendiente = 0,
                            Observacion = CONCAT(
                                COALESCE(Observacion, ''), 
                                ' | ANULADA: ', %s, ' | Fecha: ', CURDATE()
                            )
                        WHERE ID_Movimiento = %s AND Estado != 'Anulada'
                    """, (motivo_anulacion, venta['id_cuenta_cobrar']))
                    
                    if cursor.rowcount > 0:
                        print(f"✅ Cuenta por cobrar #{venta['id_cuenta_cobrar']} anulada")
                
                # 7. VERIFICACIÓN FINAL - CONFIRMAR QUE NO HAY REGISTROS DUPLICADOS
                cursor.execute("""
                    SELECT COUNT(*) as total, 
                           GROUP_CONCAT(ID_Movimiento) as ids,
                           GROUP_CONCAT(Estado) as estados,
                           GROUP_CONCAT(ID_TipoMovimiento) as tipos
                    FROM movimientos_inventario 
                    WHERE ID_Factura_Venta = %s
                """, (id_factura,))
                
                verificacion = cursor.fetchone()
                print(f"🔍 Verificación final - Movimientos para factura #{id_factura}:")
                print(f"   Total registros: {verificacion['total']} (debe ser 1)")
                print(f"   IDs: {verificacion['ids']}")
                print(f"   Estados: {verificacion['estados']}")
                print(f"   Tipos: {verificacion['tipos']}")
                
                if verificacion['total'] > 1:
                    print(f"⚠️  ALERTA: Hay {verificacion['total']} registros, debería haber solo 1")
                
                # Mensaje de éxito
                mensaje = f'✅ VENTA #{id_factura} ANULADA EXITOSAMENTE\n'
                mensaje += f'📋 Movimiento: #{id_movimiento_original} (modificado, no duplicado)\n'
                mensaje += f'👤 Cliente: {venta["cliente_nombre"]}\n'
                mensaje += f'💰 Total anulado: C${total_devolucion:,.2f}\n'
                mensaje += f'📦 Productos devueltos: {len(productos_devueltos)}\n'
                if movimientos_caja_anulados > 0:
                    mensaje += f'🏧 Movimientos de caja anulados: {movimientos_caja_anulados}\n'
                
                flash(mensaje, 'success')
                
                return redirect(url_for('admin.admin_ventas_salidas'))
                
        except Exception as e:
            error_msg = f' Error al anular venta #{id_factura}: {str(e)}'
            print(error_msg)
            traceback.print_exc()
            flash(error_msg, 'error')
            return redirect(url_for('admin.admin_ventas_salidas'))


@admin_bp.route('/admin/facturas/ventas', methods=['GET'])
@admin_required
@bitacora_decorator("FACTURAS_VENTAS")
def admin_facturas_ventas():
    try:
        # Obtener parámetros de filtro
        filtro = request.args.get('filtro', 'mes')
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        vista = request.args.get('vista', 'general')  # general, vendedores, detalle_vendedor, detalle_factura
        id_vendedor = request.args.get('id_vendedor', '')
        estado_factura = request.args.get('estado', 'todas')  # todas, activas, anuladas
        
        with get_db_cursor() as cursor:
            # Construir condición WHERE según el filtro
            where_condition_ruta = ""
            where_condition_local = ""
            params = []
            
            if filtro == 'hoy':
                where_condition_ruta = "AND fr.Fecha = CURDATE()"
                where_condition_local = "AND f.Fecha = CURDATE()"
            elif filtro == 'ayer':
                where_condition_ruta = "AND fr.Fecha = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
                where_condition_local = "AND f.Fecha = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            elif filtro == 'semana':
                where_condition_ruta = "AND fr.Fecha >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
                where_condition_local = "AND f.Fecha >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
            elif filtro == 'mes':
                where_condition_ruta = "AND fr.Fecha BETWEEN DATE_FORMAT(CURDATE(), '%Y-%m-01') AND LAST_DAY(CURDATE())"
                where_condition_local = "AND f.Fecha BETWEEN DATE_FORMAT(CURDATE(), '%Y-%m-01') AND LAST_DAY(CURDATE())"
            elif filtro == 'rango' and fecha_inicio and fecha_fin:
                where_condition_ruta = "AND fr.Fecha BETWEEN %s AND %s"
                where_condition_local = "AND f.Fecha BETWEEN %s AND %s"
                params = [fecha_inicio, fecha_fin]
            
            # ============ VISTA GENERAL ============
            if vista == 'general':
                # 1. Consulta para ventas de RUTA (todas las rutas)
                query_rutas = f"""
                    SELECT 
                        'RUTA' AS tipo,
                        r.Nombre_Ruta AS entidad,
                        r.ID_Ruta,
                        COALESCE(
                            (SELECT u.NombreUsuario 
                             FROM asignacion_vendedores av2 
                             INNER JOIN usuarios u ON av2.ID_Usuario = u.ID_Usuario
                             WHERE av2.ID_Ruta = r.ID_Ruta 
                             ORDER BY av2.Fecha_Asignacion DESC 
                             LIMIT 1),
                            'Sin asignar'
                        ) AS vendedor,
                        COALESCE(
                            (SELECT u.ID_Usuario 
                             FROM asignacion_vendedores av2 
                             INNER JOIN usuarios u ON av2.ID_Usuario = u.ID_Usuario
                             WHERE av2.ID_Ruta = r.ID_Ruta 
                             ORDER BY av2.Fecha_Asignacion DESC 
                             LIMIT 1),
                            NULL
                        ) AS id_vendedor,
                        r.Estado AS estado_ruta,
                        COUNT(DISTINCT fr.ID_FacturaRuta) AS total_facturas,
                        COALESCE(SUM(dfr.Total), 0) AS total_vendido,
                        SUM(CASE WHEN fr.Estado = 'Anulada' THEN 1 ELSE 0 END) AS facturas_anuladas,
                        MAX(fr.Fecha) AS ultima_fecha
                    FROM rutas r
                    LEFT JOIN asignacion_vendedores av ON r.ID_Ruta = av.ID_Ruta
                    LEFT JOIN facturacion_ruta fr ON av.ID_Asignacion = fr.ID_Asignacion 
                        {where_condition_ruta}
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    GROUP BY r.ID_Ruta, r.Nombre_Ruta, r.Estado
                    ORDER BY total_vendido DESC
                """
                
                # 2. Consulta para ventas de LOCAL
                query_local = f"""
                    SELECT 
                        'LOCAL' AS tipo,
                        'Local General' AS entidad,
                        NULL AS ID_Ruta,
                        u.NombreUsuario AS vendedor,
                        u.ID_Usuario AS id_vendedor,
                        'Activo' AS estado_ruta,
                        COUNT(DISTINCT f.ID_Factura) AS total_facturas,
                        COALESCE(SUM(df.Total), 0) AS total_vendido,
                        SUM(CASE WHEN f.Estado = 'Anulada' THEN 1 ELSE 0 END) AS facturas_anuladas,
                        MAX(f.Fecha) AS ultima_fecha
                    FROM facturacion f
                    INNER JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                    LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    WHERE f.Estado = 'Activa'
                        {where_condition_local}
                    GROUP BY u.ID_Usuario
                    ORDER BY total_vendido DESC
                """
                
                # 3. Consulta para evolución de ventas (por día)
                query_evolucion_ruta = f"""
                    SELECT 
                        fr.Fecha,
                        SUM(dfr.Total) AS total_dia
                    FROM facturacion_ruta fr
                    INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE fr.Estado = 'Activa'
                        {where_condition_ruta}
                    GROUP BY fr.Fecha
                    ORDER BY fr.Fecha
                """
                
                query_evolucion_local = f"""
                    SELECT 
                        f.Fecha,
                        SUM(df.Total) AS total_dia
                    FROM facturacion f
                    INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    WHERE f.Estado = 'Activa'
                        {where_condition_local}
                    GROUP BY f.Fecha
                    ORDER BY f.Fecha
                """
                
                # 4. Top 5 vendedores
                query_top_vendedores = f"""
                    (SELECT 
                        u.NombreUsuario AS vendedor,
                        u.ID_Usuario AS id_vendedor,
                        SUM(dfr.Total) AS total_vendido,
                        'RUTA' AS origen
                    FROM facturacion_ruta fr
                    INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE fr.Estado = 'Activa'
                        {where_condition_ruta}
                    GROUP BY u.ID_Usuario)
                    
                    UNION ALL
                    
                    (SELECT 
                        u.NombreUsuario AS vendedor,
                        u.ID_Usuario AS id_vendedor,
                        SUM(df.Total) AS total_vendido,
                        'LOCAL' AS origen
                    FROM facturacion f
                    INNER JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    INNER JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                    WHERE f.Estado = 'Activa'
                        {where_condition_local}
                    GROUP BY u.ID_Usuario)
                    
                    ORDER BY total_vendido DESC
                    LIMIT 5
                """
                
                # Ejecutar consultas
                cursor.execute(query_rutas, params)
                ventas_rutas = cursor.fetchall()
                
                cursor.execute(query_local, params)
                ventas_local = cursor.fetchall()
                
                cursor.execute(query_evolucion_ruta, params if 'BETWEEN' in where_condition_ruta else [])
                evolucion_ruta = cursor.fetchall()
                
                cursor.execute(query_evolucion_local, params if 'BETWEEN' in where_condition_local else [])
                evolucion_local = cursor.fetchall()
                
                cursor.execute(query_top_vendedores, params + params if 'BETWEEN' in where_condition_ruta else params)
                top_vendedores = cursor.fetchall()
                
                # Unir resultados
                ventas = list(ventas_rutas) + list(ventas_local)
                
                # Calcular totales asegurando que nunca sean None
                total_facturas = float(sum(v.get('total_facturas') or 0 for v in ventas) or 0)
                total_vendido = float(sum(v.get('total_vendido') or 0 for v in ventas) or 0)
                total_rutas = float(sum(v.get('total_vendido') or 0 for v in ventas if v.get('tipo') == 'RUTA') or 0)
                total_local = float(sum(v.get('total_vendido') or 0 for v in ventas if v.get('tipo') == 'LOCAL') or 0)
                total_anuladas = float(sum(v.get('facturas_anuladas') or 0 for v in ventas) or 0)

                # Preparar datos para gráficos
                fechas = sorted(set([e['Fecha'] for e in evolucion_ruta] + [e['Fecha'] for e in evolucion_local]))
                datos_ruta = []
                datos_local = []

                for fecha in fechas:
                    ruta_valor = next((e['total_dia'] if e['total_dia'] is not None else 0 for e in evolucion_ruta if e['Fecha'] == fecha), 0)
                    local_valor = next((e['total_dia'] if e['total_dia'] is not None else 0 for e in evolucion_local if e['Fecha'] == fecha), 0)
                    datos_ruta.append(float(ruta_valor or 0))
                    datos_local.append(float(local_valor or 0))

                # Datos para gráfico de torta (Ruta vs Local)
                torta_data = [float(total_rutas or 0), float(total_local or 0)]

                return render_template(
                    'admin/ventas/facturas_ventas.html',
                    vista_actual='general',
                    ventas=ventas,
                    ventas_local=ventas_local,
                    total_facturas=total_facturas,
                    total_vendido=total_vendido,
                    total_rutas=total_rutas,
                    total_local=total_local,
                    total_anuladas=total_anuladas,
                    filtro_actual=filtro,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    fechas_grafico=[f.strftime('%Y-%m-%d') if hasattr(f, 'strftime') else str(f) for f in fechas],
                    datos_ruta_grafico=datos_ruta,
                    datos_local_grafico=datos_local,
                    torta_data=torta_data,
                    top_vendedores=top_vendedores
                )
            
            # ============ VISTA VENDEDORES ASIGNADOS ============
            elif vista == 'vendedores':
                # Preparar parámetros separados para cada consulta
                params_ruta = [session.get('empresa_id',1)]
                params_local = [session.get('empresa_id',1)]
                
                if params and len(params) > 0:
                    params_ruta.extend(params)
                    params_local.extend(params)
                
                # Construir las condiciones WHERE con formato adecuado
                where_condition_ruta_formatted = where_condition_ruta + " " if where_condition_ruta else ""
                where_condition_local_formatted = where_condition_local + " " if where_condition_local else ""
                
                # 1. Vendedores de RUTA con sus asignaciones
                query_vendedores_ruta = """
                    SELECT 
                        'RUTA' AS tipo_vendedor,
                        u.ID_Usuario,
                        u.NombreUsuario AS vendedor,
                        r.Nombre_Ruta AS ruta_asignada,
                        av.ID_Asignacion,
                        av.Fecha_Asignacion,
                        av.Fecha_Finalizacion,
                        av.Estado AS estado_asignacion,
                        av.Hora_Inicio,
                        av.Hora_Fin,
                        v.Placa AS vehiculo_placa,
                        v.Marca AS vehiculo_marca,
                        COUNT(DISTINCT fr.ID_FacturaRuta) AS total_facturas,
                        COALESCE(SUM(dfr.Total), 0) AS total_vendido,
                        SUM(CASE WHEN fr.Estado = 'Activa' THEN 1 ELSE 0 END) AS facturas_activas,
                        SUM(CASE WHEN fr.Estado = 'Anulada' THEN 1 ELSE 0 END) AS facturas_anuladas,
                        MAX(fr.Fecha) AS ultima_venta
                    FROM usuarios u
                    INNER JOIN asignacion_vendedores av ON u.ID_Usuario = av.ID_Usuario
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                    LEFT JOIN facturacion_ruta fr ON av.ID_Asignacion = fr.ID_Asignacion
                        """ + where_condition_ruta_formatted + """
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE u.ID_Empresa = %s
                        AND u.ID_Rol = (SELECT ID_Rol FROM roles WHERE Nombre_Rol = 'Vendedor' LIMIT 1)
                    GROUP BY u.ID_Usuario, av.ID_Asignacion, r.ID_Ruta, v.ID_Vehiculo
                    ORDER BY total_vendido DESC, u.NombreUsuario
                """
                
                # 2. Vendedores de LOCAL
                query_vendedores_local = """
                    SELECT 
                        'LOCAL' AS tipo_vendedor,
                        u.ID_Usuario,
                        u.NombreUsuario AS vendedor,
                        'Local General' AS ruta_asignada,
                        NULL AS ID_Asignacion,
                        NULL AS Fecha_Asignacion,
                        NULL AS Fecha_Finalizacion,
                        'Activa' AS estado_asignacion,
                        NULL AS Hora_Inicio,
                        NULL AS Hora_Fin,
                        NULL AS vehiculo_placa,
                        NULL AS vehiculo_marca,
                        COUNT(DISTINCT f.ID_Factura) AS total_facturas,
                        COALESCE(SUM(df.Total), 0) AS total_vendido,
                        SUM(CASE WHEN f.Estado = 'Activa' THEN 1 ELSE 0 END) AS facturas_activas,
                        SUM(CASE WHEN f.Estado = 'Anulada' THEN 1 ELSE 0 END) AS facturas_anuladas,
                        MAX(f.Fecha) AS ultima_venta
                    FROM usuarios u
                    INNER JOIN facturacion f ON u.ID_Usuario = f.ID_Usuario_Creacion
                    LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    WHERE u.ID_Empresa = %s
                        AND u.ID_Rol = (SELECT ID_Rol FROM roles WHERE Nombre_Rol = 'Vendedor' LIMIT 1)
                        """ + where_condition_local_formatted + """
                    GROUP BY u.ID_Usuario
                    ORDER BY total_vendido DESC, u.NombreUsuario
                """
                
                # Ejecutar consultas con parámetros correctos
                cursor.execute(query_vendedores_ruta, params_ruta)
                vendedores_ruta = cursor.fetchall()
                
                cursor.execute(query_vendedores_local, params_local)
                vendedores_local = cursor.fetchall()
                
                # Estadísticas generales
                total_vendedores_ruta = len(vendedores_ruta)
                total_vendedores_local = len(vendedores_local)
                total_vendido_ruta = sum(v.get('total_vendido') or 0 for v in vendedores_ruta)
                total_vendido_local = sum(v.get('total_vendido') or 0 for v in vendedores_local)
                total_anuladas = sum(v.get('facturas_anuladas') or 0 for v in vendedores_ruta + vendedores_local)
                
                return render_template(
                    'admin/ventas/facturas_ventas.html',
                    vista_actual='vendedores',
                    vendedores_ruta=vendedores_ruta,
                    vendedores_local=vendedores_local,
                    total_vendedores_ruta=total_vendedores_ruta,
                    total_vendedores_local=total_vendedores_local,
                    total_vendido_ruta=total_vendido_ruta,
                    total_vendido_local=total_vendido_local,
                    total_anuladas=total_anuladas,
                    filtro_actual=filtro,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin
                )
            
            # ============ VISTA DETALLE DE VENDEDOR ============
            elif vista == 'detalle_vendedor' and id_vendedor:
                # Verificar que el vendedor existe
                cursor.execute("""
                    SELECT u.ID_Usuario, u.NombreUsuario, u.Estado,
                           r.Nombre_Rol
                    FROM usuarios u
                    INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
                    WHERE u.ID_Usuario = %s AND u.ID_Empresa = %s
                """, (id_vendedor, session.get('empresa_id',1)))
                
                vendedor = cursor.fetchone()
                if not vendedor:
                    flash("Vendedor no encontrado", "danger")
                    return redirect(url_for('admin.admin_facturas_ventas', vista='vendedores'))
                
                # Condición de estado para facturas
                estado_ruta = ""
                estado_local = ""
                if estado_factura == 'activas':
                    estado_ruta = "AND fr.Estado = 'Activa'"
                    estado_local = "AND f.Estado = 'Activa'"
                elif estado_factura == 'anuladas':
                    estado_ruta = "AND fr.Estado = 'Anulada'"
                    estado_local = "AND f.Estado = 'Anulada'"
                
                # Preparar parámetros
                params_ruta_vendedor = [id_vendedor, session.get('empresa_id',1)]
                params_local_vendedor = [id_vendedor, session.get('empresa_id',1)]
                
                if params and len(params) > 0:
                    params_ruta_vendedor.extend(params)
                    params_local_vendedor.extend(params)
                
                # Ventas de RUTA del vendedor - CORREGIDO para manejar fechas NULL
                query_ventas_ruta = f"""
                    SELECT 
                        'RUTA' AS tipo_venta,
                        fr.ID_FacturaRuta AS id_factura,
                        COALESCE(fr.Fecha, fr.Fecha_Creacion, '1900-01-01') AS Fecha,
                        fr.Estado,
                        fr.Credito_Contado,
                        fr.Observacion,
                        fr.Fecha_Creacion,
                        fr.ID_Pedido,
                        COALESCE(c.Nombre, 'Cliente sin nombre') as Nombre_Cliente,
                        c.ID_Cliente,
                        r.Nombre_Ruta,
                        COUNT(dfr.ID_DetalleRuta) AS cantidad_productos,
                        COALESCE(SUM(dfr.Total), 0) AS total_factura
                    FROM facturacion_ruta fr
                    INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE av.ID_Usuario = %s 
                        AND fr.ID_Empresa = %s
                        {where_condition_ruta}
                        {estado_ruta}
                    GROUP BY fr.ID_FacturaRuta
                    ORDER BY COALESCE(fr.Fecha, fr.Fecha_Creacion, '1900-01-01') DESC, fr.Fecha_Creacion DESC
                """
                
                # Ventas de LOCAL del vendedor - CORREGIDO para manejar fechas NULL
                query_ventas_local = f"""
                    SELECT 
                        'LOCAL' AS tipo_venta,
                        f.ID_Factura AS id_factura,
                        COALESCE(f.Fecha, f.Fecha_Creacion, '1900-01-01') AS Fecha,
                        f.Estado,
                        f.Credito_Contado,
                        f.Observacion,
                        f.Fecha_Creacion,
                        f.ID_Pedido,
                        COALESCE(c.Nombre, 'Cliente sin nombre') as Nombre_Cliente,
                        c.ID_Cliente,
                        'Local General' AS Nombre_Ruta,
                        COUNT(df.ID_Detalle) AS cantidad_productos,
                        COALESCE(SUM(df.Total), 0) AS total_factura
                    FROM facturacion f
                    LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                    LEFT JOIN detalle_facturacion df ON f.ID_Factura = df.ID_Factura
                    WHERE f.ID_Usuario_Creacion = %s 
                        AND f.ID_Empresa = %s
                        {where_condition_local}
                        {estado_local}
                    GROUP BY f.ID_Factura
                    ORDER BY COALESCE(f.Fecha, f.Fecha_Creacion, '1900-01-01') DESC, f.Fecha_Creacion DESC
                """
                
                # Ejecutar consultas
                cursor.execute(query_ventas_ruta, params_ruta_vendedor)
                ventas_ruta_vendedor = cursor.fetchall()
                
                cursor.execute(query_ventas_local, params_local_vendedor)
                ventas_local_vendedor = cursor.fetchall()
                
                # Combinar todas las ventas
                todas_ventas = list(ventas_ruta_vendedor) + list(ventas_local_vendedor)
                
                # Estadísticas
                total_ventas = len(todas_ventas)
                total_ventas_activas = sum(1 for v in todas_ventas if v['Estado'] == 'Activa')
                total_ventas_anuladas = sum(1 for v in todas_ventas if v['Estado'] == 'Anulada')
                total_monto = sum(v['total_factura'] or 0 for v in todas_ventas)
                total_monto_activo = sum(v['total_factura'] or 0 for v in todas_ventas if v['Estado'] == 'Activa')
                
                return render_template(
                    'admin/ventas/facturas_ventas.html',
                    vista_actual='detalle_vendedor',
                    vendedor=vendedor,
                    ventas_vendedor=todas_ventas,
                    total_ventas=total_ventas,
                    total_ventas_activas=total_ventas_activas,
                    total_ventas_anuladas=total_ventas_anuladas,
                    total_monto=total_monto,
                    total_monto_activo=total_monto_activo,
                    filtro_actual=filtro,
                    estado_actual=estado_factura,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin
                )
            
            # ============ VISTA DETALLE DE FACTURA ============
            elif vista == 'detalle_factura':
                id_factura = request.args.get('id_factura', '')
                tipo_factura = request.args.get('tipo', 'ruta')
                id_vendedor_retorno = request.args.get('id_vendedor', '')
                
                if not id_factura:
                    flash("ID de factura requerido", "danger")
                    return redirect(url_for('admin.admin_facturas_ventas'))
                
                if tipo_factura == 'ruta':
                    # Cabecera de factura de ruta
                    cursor.execute("""
                        SELECT 
                            fr.*,
                            u.NombreUsuario as vendedor,
                            u.ID_Usuario as id_vendedor,
                            c.Nombre as Nombre_Cliente,
                            c.Direccion as direccion_cliente,
                            c.Telefono as telefono_cliente,
                            r.Nombre_Ruta,
                            av.Fecha_Asignacion,
                            v.Placa as vehiculo
                        FROM facturacion_ruta fr
                        INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                        INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                        INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                        INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                        LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                        WHERE fr.ID_FacturaRuta = %s AND fr.ID_Empresa = %s
                    """, (id_factura, session.get('empresa_id',1)))
                    factura_detalle = cursor.fetchone()
                    
                    # Detalle de productos
                    cursor.execute("""
                        SELECT 
                            dfr.*,
                            p.Descripcion AS Nombre_Producto,
                            p.COD_Producto as Codigo_Producto,
                            p.Unidad_Medida
                        FROM detalle_facturacion_ruta dfr
                        INNER JOIN productos p ON dfr.ID_Producto = p.ID_Producto
                        WHERE dfr.ID_FacturaRuta = %s
                    """, (id_factura,))
                    detalles_factura = cursor.fetchall()
                    
                else:  # local
                    cursor.execute("""
                        SELECT 
                            f.*,
                            u.NombreUsuario as vendedor,
                            u.ID_Usuario as id_vendedor,
                            c.Nombre as Nombre_Cliente,
                            c.Direccion as direccion_cliente,
                            c.Telefono as telefono_cliente
                        FROM facturacion f
                        INNER JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                        LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                        WHERE f.ID_Factura = %s AND f.ID_Empresa = %s
                    """, (id_factura, session.get('empresa_id',1)))
                    factura_detalle = cursor.fetchone()
                    
                    cursor.execute("""
                        SELECT 
                            df.*,
                            p.Descripcion AS Nombre_Producto,
                            p.COD_Producto as Codigo_Producto,
                            p.Unidad_Medida
                        FROM detalle_facturacion df
                        INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                        WHERE df.ID_Factura = %s
                    """, (id_factura,))
                    detalles_factura = cursor.fetchall()
                
                if not factura_detalle:
                    flash("Factura no encontrada", "danger")
                    return redirect(url_for('admin.admin_facturas_ventas'))
                
                # Verificar si ya fue anulada y obtener info
                anulacion_info = None
                if factura_detalle['Estado'] == 'Anulada':
                    cursor.execute("""
                        SELECT la.*, u.NombreUsuario as nombre_usuario_anula
                        FROM log_anulaciones la
                        INNER JOIN usuarios u ON la.ID_Usuario_Anula = u.ID_Usuario
                        WHERE la.ID_Factura = %s AND la.Tipo = %s
                        ORDER BY la.Fecha_Anulacion DESC
                        LIMIT 1
                    """, (id_factura, tipo_factura))
                    anulacion_info = cursor.fetchone()
                
                # Total de la factura
                total_factura = sum(d['Total'] or 0 for d in detalles_factura)
                
                return render_template(
                    'admin/ventas/facturas_ventas.html',
                    vista_actual='detalle_factura',
                    factura_detalle=factura_detalle,
                    detalles_factura=detalles_factura,
                    tipo_factura=tipo_factura,
                    total_factura=total_factura,
                    anulacion_info=anulacion_info,
                    id_vendedor=id_vendedor_retorno,
                    filtro_actual=filtro,
                    estado_actual=estado_factura
                )
            
            # Vista por defecto
            return redirect(url_for('admin.admin_facturas_ventas', vista='general'))
            
    except Exception as e:
        flash(f"Error al cargar ventas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/factura/anular', methods=['POST'])
@admin_required
@bitacora_decorator("FACTURA_ANULAR")
def admin_anular_factura():
    """
    Anular una factura y devolver productos al inventario
    Lógica: MODIFICA el movimiento original, NO crea uno nuevo
    """
    try:
        # Obtener datos
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        if not data:
            return jsonify({'success': False, 'message': 'No se recibieron datos'}), 400
        
        id_factura = data.get('id_factura')
        tipo = data.get('tipo', 'ruta')
        motivo = data.get('motivo', '').strip()
        id_vendedor = data.get('id_vendedor', '')
        
        # Validaciones
        if not id_factura:
            return jsonify({'success': False, 'message': 'ID de factura requerido'}), 400
        if not motivo:
            return jsonify({'success': False, 'message': 'Debe proporcionar un motivo de anulación'}), 400
        if len(motivo) < 10:
            return jsonify({'success': False, 'message': 'El motivo debe tener al menos 10 caracteres'}), 400
        
        try:
            id_factura = int(id_factura)
        except ValueError:
            return jsonify({'success': False, 'message': 'ID de factura inválido'}), 400
        
        with get_db_cursor() as cursor:
            user_id = current_user.id
            empresa_id = session.get('empresa_id', 1)
            
            if not user_id or not empresa_id:
                return jsonify({'success': False, 'message': 'Sesión inválida'}), 401
            
            # ============ OBTENER DATOS DE LA FACTURA ============
            if tipo == 'ruta':
                cursor.execute("""
                    SELECT 
                        fr.ID_FacturaRuta,
                        fr.Estado,
                        fr.ID_Asignacion,
                        fr.ID_Movimiento,
                        fr.ID_Pedido,
                        av.ID_Vehiculo,
                        av.ID_Ruta
                    FROM facturacion_ruta fr
                    INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                    WHERE fr.ID_FacturaRuta = %s AND fr.ID_Empresa = %s
                """, (id_factura, empresa_id))
                factura = cursor.fetchone()
                
                if not factura:
                    return jsonify({'success': False, 'message': 'Factura de ruta #{} no encontrada'.format(id_factura)}), 404
                
                cursor.execute("""
                    SELECT 
                        dfr.ID_Producto,
                        dfr.Cantidad,
                        dfr.Costo,
                        dfr.Precio,
                        dfr.Total,
                        p.Descripcion as Nombre_Producto,
                        p.COD_Producto as Codigo_Producto
                    FROM detalle_facturacion_ruta dfr
                    INNER JOIN productos p ON dfr.ID_Producto = p.ID_Producto
                    WHERE dfr.ID_FacturaRuta = %s
                """, (id_factura,))
                detalles = cursor.fetchall()
                
            else:
                cursor.execute("""
                    SELECT 
                        f.ID_Factura,
                        f.Estado,
                        f.IDCliente,
                        f.ID_Pedido
                    FROM facturacion f
                    WHERE f.ID_Factura = %s AND f.ID_Empresa = %s
                """, (id_factura, empresa_id))
                factura = cursor.fetchone()
                
                if not factura:
                    return jsonify({'success': False, 'message': 'Factura de local #{} no encontrada'.format(id_factura)}), 404
                
                cursor.execute("""
                    SELECT 
                        df.ID_Producto,
                        df.Cantidad,
                        df.Costo,
                        df.Total,
                        p.Descripcion as Nombre_Producto,
                        p.COD_Producto as Codigo_Producto
                    FROM detalle_facturacion df
                    INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                    WHERE df.ID_Factura = %s
                """, (id_factura,))
                detalles = cursor.fetchall()
            
            if factura['Estado'] == 'Anulada':
                return jsonify({'success': False, 'message': 'Esta factura ya está anulada'}), 400
            
            if not detalles:
                return jsonify({'success': False, 'message': 'La factura no tiene productos registrados'}), 400
            
            # ============ INICIAR TRANSACCIÓN ============
            cursor.execute("START TRANSACTION")
            
            try:
                motivo_completo = '[ANULADA {}] {}'.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), motivo)
                
                # ============ 1. ANULAR LA FACTURA ============
                if tipo == 'ruta':
                    cursor.execute("""
                        UPDATE facturacion_ruta 
                        SET Estado = 'Anulada', 
                            Observacion = CONCAT(IFNULL(Observacion, ''), '\n', %s)
                        WHERE ID_FacturaRuta = %s AND ID_Empresa = %s
                    """, (motivo_completo, id_factura, empresa_id))
                else:
                    cursor.execute("""
                        UPDATE facturacion 
                        SET Estado = 'Anulada', 
                            Observacion = CONCAT(IFNULL(Observacion, ''), '\n', %s)
                        WHERE ID_Factura = %s AND ID_Empresa = %s
                    """, (motivo_completo, id_factura, empresa_id))
                
                # ============ 2. PROCESAR MOVIMIENTO E INVENTARIO ============
                if tipo == 'ruta':
                    # Anular movimiento de ruta si existe
                    if factura.get('ID_Movimiento'):
                        cursor.execute("""
                            UPDATE movimientos_ruta_cabecera 
                            SET Estado = 'ANULADO', 
                                Motivo_Anulacion = %s, 
                                Fecha_Anulacion = NOW(), 
                                ID_Usuario_Anula = %s
                            WHERE ID_Movimiento = %s AND Estado = 'ACTIVO'
                        """, (motivo, user_id, factura['ID_Movimiento']))
                    
                    # Devolver al inventario de ruta
                    for detalle in detalles:
                        id_producto = detalle['ID_Producto']
                        cantidad = float(detalle['Cantidad'])
                        
                        cursor.execute("""
                            SELECT Cantidad FROM inventario_ruta 
                            WHERE ID_Asignacion = %s AND ID_Producto = %s
                        """, (factura['ID_Asignacion'], id_producto))
                        inv = cursor.fetchone()
                        
                        if inv:
                            cursor.execute("""
                                UPDATE inventario_ruta 
                                SET Cantidad = Cantidad + %s, Fecha_Actualizacion = NOW()
                                WHERE ID_Asignacion = %s AND ID_Producto = %s
                            """, (cantidad, factura['ID_Asignacion'], id_producto))
                        else:
                            cursor.execute("""
                                INSERT INTO inventario_ruta 
                                (ID_Asignacion, ID_Producto, Cantidad, Fecha_Actualizacion)
                                VALUES (%s, %s, %s, NOW())
                            """, (factura['ID_Asignacion'], id_producto, cantidad))
                    
                    # Si tiene vehículo, también devolver a bodega
                    if factura.get('ID_Vehiculo'):
                        cursor.execute("""
                            SELECT ID_Bodega, Nombre FROM bodegas 
                            WHERE ID_Empresa = %s AND Estado = 'Activa' LIMIT 1
                        """, (empresa_id,))
                        bodega = cursor.fetchone()
                        
                        if bodega:
                            for detalle in detalles:
                                id_producto = detalle['ID_Producto']
                                cantidad = float(detalle['Cantidad'])
                                
                                cursor.execute("""
                                    SELECT Existencias FROM inventario_bodega 
                                    WHERE ID_Bodega = %s AND ID_Producto = %s
                                """, (bodega['ID_Bodega'], id_producto))
                                inv_bodega = cursor.fetchone()
                                
                                if inv_bodega:
                                    cursor.execute("""
                                        UPDATE inventario_bodega 
                                        SET Existencias = Existencias + %s
                                        WHERE ID_Bodega = %s AND ID_Producto = %s
                                    """, (cantidad, bodega['ID_Bodega'], id_producto))
                                else:
                                    cursor.execute("""
                                        INSERT INTO inventario_bodega 
                                        (ID_Bodega, ID_Producto, Existencias)
                                        VALUES (%s, %s, %s)
                                    """, (bodega['ID_Bodega'], id_producto, cantidad))
                
                else:
                    # ============ LOCAL: MODIFICAR MOVIMIENTO ORIGINAL ============
                    # Buscar el movimiento original
                    cursor.execute("""
                        SELECT ID_Movimiento, ID_Bodega, Estado, ID_TipoMovimiento
                        FROM movimientos_inventario 
                        WHERE ID_Factura_Venta = %s AND ID_Empresa = %s 
                        AND (Estado = 'Activa' OR Estado = 'ACTIVA')
                        ORDER BY ID_Movimiento DESC
                        LIMIT 1
                    """, (id_factura, empresa_id))
                    movimiento_original = cursor.fetchone()
                    
                    if not movimiento_original:
                        raise Exception("No se encontró el movimiento de inventario original para la factura #{}".format(id_factura))
                    
                    id_movimiento_original = movimiento_original['ID_Movimiento']
                    id_bodega = movimiento_original['ID_Bodega']
                    
                    # MODIFICAR el movimiento original - cambiar tipo a ANULACIÓN (10) y estado a 'Anulada'
                    observacion_anulacion = 'ANULADA - Factura #{} - Motivo: {}'.format(id_factura, motivo)
                    
                    cursor.execute("""
                        UPDATE movimientos_inventario 
                        SET ID_TipoMovimiento = 10,
                            Estado = 'Anulada',
                            Observacion = %s,
                            Fecha_Modificacion = NOW(),
                            ID_Usuario_Modificacion = %s
                        WHERE ID_Movimiento = %s
                    """, (observacion_anulacion, user_id, id_movimiento_original))
                    
                    # ELIMINAR detalles anteriores del movimiento
                    cursor.execute("""
                        DELETE FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = %s
                    """, (id_movimiento_original,))
                    
                    # INSERTAR nuevos detalles en el MISMO movimiento (como devolución)
                    for detalle in detalles:
                        id_producto = detalle['ID_Producto']
                        cantidad = float(detalle['Cantidad'])
                        costo = float(detalle['Costo']) if detalle['Costo'] else 0
                        costo_unitario = costo / cantidad if cantidad > 0 else 0
                        total = float(detalle['Total']) if detalle['Total'] else 0
                        
                        cursor.execute("""
                            INSERT INTO detalle_movimientos_inventario 
                            (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                             Precio_Unitario, Subtotal, ID_Usuario_Creacion, Fecha_Creacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        """, (id_movimiento_original, id_producto, cantidad, 
                              costo_unitario, costo_unitario, total, user_id))
                        
                        # Devolver al inventario de bodega
                        cursor.execute("""
                            SELECT Existencias FROM inventario_bodega 
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (id_bodega, id_producto))
                        inv_bodega = cursor.fetchone()
                        
                        if inv_bodega:
                            cursor.execute("""
                                UPDATE inventario_bodega 
                                SET Existencias = Existencias + %s
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (cantidad, id_bodega, id_producto))
                        else:
                            cursor.execute("""
                                INSERT INTO inventario_bodega 
                                (ID_Bodega, ID_Producto, Existencias)
                                VALUES (%s, %s, %s)
                            """, (id_bodega, id_producto, cantidad))
                
                # ============ 3. CANCELAR PEDIDO SI EXISTE ============
                if factura.get('ID_Pedido'):
                    cursor.execute("""
                        UPDATE pedidos 
                        SET Estado = 'Cancelado',
                            Observacion = CONCAT(IFNULL(Observacion, ''), 
                                '\n[CANCELADO POR ANULACION DE FACTURA #', %s, ']')
                        WHERE ID_Pedido = %s
                    """, (id_factura, factura['ID_Pedido']))
                
                # ============ 4. REGISTRAR EN LOG ============
                cursor.execute("""
                    INSERT INTO log_anulaciones 
                    (ID_Factura, Tipo, Motivo, ID_Usuario_Anula, Fecha_Anulacion, ID_Empresa)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                """, (id_factura, tipo, motivo, user_id, empresa_id))
                
                # ============ CONFIRMAR ============
                cursor.execute("COMMIT")
                
                # Mensaje de éxito
                total_cantidad = sum(float(d['Cantidad']) for d in detalles)
                total_monto = sum(float(d['Total']) for d in detalles if d['Total'])
                
                if tipo == 'ruta':
                    mensaje = 'Factura de ruta #{} anulada. {} unidades devueltas al inventario.'.format(
                        id_factura, total_cantidad)
                else:
                    mensaje = 'Factura de local #{} anulada. Movimiento #{} modificado. {} unidades devueltas. Monto: C${:,.2f}'.format(
                        id_factura, id_movimiento_original, total_cantidad, total_monto)
                
                if id_vendedor:
                    redirect_url = url_for('admin.admin_facturas_ventas', vista='detalle_vendedor',
                                          id_vendedor=id_vendedor, filtro=request.args.get('filtro', 'mes'))
                else:
                    redirect_url = url_for('admin.admin_facturas_ventas', vista='general',
                                          filtro=request.args.get('filtro', 'mes'))
                
                return jsonify({'success': True, 'message': mensaje, 'redirect': redirect_url})
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e
                
    except Exception as e:
        print("Error al anular factura: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error al anular factura: {}'.format(str(e))}), 500

@admin_bp.route('/admin/ventas/buscar-clientes')
@admin_required
def buscar_clientes():
    """
    API para buscar clientes (autocompletado)
    AHORA INCLUYE: perfil_cliente para determinar qué precio aplicar
    Retorna clientes activos que coincidan con nombre, documento o teléfono
    """
    try:
        termino = request.args.get('q', '')
        
        if not termino or len(termino) < 2:
            return jsonify([])
        
        with get_db_cursor(True) as cursor:
            sql = """
            SELECT 
                ID_Cliente,
                Nombre,
                RUC_CEDULA as Documento,
                Telefono,
                Direccion,
                tipo_cliente as Tipo,
                perfil_cliente as Perfil,  -- NUEVO: incluimos el perfil
                ID_Ruta  -- NUEVO: incluimos la ruta asignada
            FROM clientes 
            WHERE Estado = 'ACTIVO'
            AND (Nombre LIKE %s OR RUC_CEDULA LIKE %s OR Telefono LIKE %s)
            ORDER BY Nombre
            LIMIT 20
            """
            
            termino_busqueda = f"%{termino}%"
            cursor.execute(sql, (termino_busqueda, termino_busqueda, termino_busqueda))
            clientes = cursor.fetchall()
            
            # Convertir a lista de diccionarios incluyendo el perfil
            resultados = []
            for cliente in clientes:
                # Determinar qué tipo de precio aplica según el perfil
                tipo_precio = {
                    'Ruta': 'Precio de Ruta',
                    'Mayorista': 'Precio Mayorista',
                    'Mercado': 'Precio de Mercado',
                    'Especial': 'Precio Especial (Mercado)'
                }.get(cliente['Perfil'], 'Precio de Mercado')
                
                resultados.append({
                    'id': cliente['ID_Cliente'],
                    'text': f"{cliente['Nombre']} - {cliente['Documento'] or 'Sin documento'} ({cliente['Perfil']})",
                    'nombre': cliente['Nombre'],
                    'documento': cliente['Documento'],
                    'telefono': cliente['Telefono'],
                    'direccion': cliente['Direccion'],
                    'tipo': cliente['Tipo'],
                    'perfil': cliente['Perfil'],  # NUEVO
                    'id_ruta': cliente['ID_Ruta'],  # NUEVO
                    'tipo_precio': tipo_precio  # NUEVO: para mostrar en el frontend
                })
            
            return jsonify(resultados)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/ventas/buscar-productos')
@admin_required
def buscar_productos():
    """
    API para buscar productos (autocompletado)
    AHORA INCLUYE: TODOS los precios (Mercado, Mayorista, Ruta)
    para poder elegir según el perfil del cliente
    """
    try:
        termino = request.args.get('q', '')
        tipo_cliente = request.args.get('tipo_cliente', '')
        perfil_cliente = request.args.get('perfil_cliente', 'Mercado')  # NUEVO: perfil del cliente
        
        if not termino or len(termino) < 2:
            return jsonify([])
        
        with get_db_cursor(True) as cursor:
            # Si hay tipo_cliente, filtrar por categorías visibles
            if tipo_cliente:
                sql = """
                SELECT 
                    p.ID_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    p.Unidad_Medida,
                    u.Descripcion as Unidad_Descripcion,
                    u.Abreviatura as Unidad_Abreviatura,
                    cp.Descripcion as Categoria_Descripcion,
                    COALESCE(SUM(ib.Existencias), 0) as Stock_Total
                FROM productos p
                LEFT JOIN unidades_medida u ON p.Unidad_Medida = u.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                INNER JOIN config_visibilidad_categorias cv ON p.ID_Categoria = cv.ID_Categoria
                WHERE (p.Descripcion LIKE %s OR p.COD_Producto LIKE %s)
                AND p.Estado = 'activo'
                AND cv.tipo_cliente = %s
                AND cv.visible = 1
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto, 
                         p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,
                         p.Unidad_Medida, u.Descripcion, u.Abreviatura, cp.Descripcion
                HAVING Stock_Total > 0
                ORDER BY p.Descripcion
                LIMIT 20
                """
                termino_busqueda = f"%{termino}%"
                cursor.execute(sql, (termino_busqueda, termino_busqueda, tipo_cliente))
            else:
                sql = """
                SELECT 
                    p.ID_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    p.Unidad_Medida,
                    u.Descripcion as Unidad_Descripcion,
                    u.Abreviatura as Unidad_Abreviatura,
                    cp.Descripcion as Categoria_Descripcion,
                    COALESCE(SUM(ib.Existencias), 0) as Stock_Total
                FROM productos p
                LEFT JOIN unidades_medida u ON p.Unidad_Medida = u.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE (p.Descripcion LIKE %s OR p.COD_Producto LIKE %s)
                AND p.Estado = 'activo'
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto, 
                         p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,
                         p.Unidad_Medida, u.Descripcion, u.Abreviatura, cp.Descripcion
                HAVING Stock_Total > 0
                ORDER BY p.Descripcion
                LIMIT 20
                """
                termino_busqueda = f"%{termino}%"
                cursor.execute(sql, (termino_busqueda, termino_busqueda))
            
            productos = cursor.fetchall()
            
            # Convertir a lista de diccionarios con TODOS los precios
            resultados = []
            for producto in productos:
                # Determinar el precio según el perfil del cliente (si se proporciona)
                precio_segun_perfil = 0
                if perfil_cliente == 'Ruta':
                    precio_segun_perfil = float(producto['Precio_Ruta'] or 0)
                elif perfil_cliente == 'Mayorista':
                    precio_segun_perfil = float(producto['Precio_Mayorista'] or 0)
                elif perfil_cliente == 'Mercado':
                    precio_segun_perfil = float(producto['Precio_Mercado'] or 0)
                elif perfil_cliente == 'Especial':
                    precio_segun_perfil = float(producto['Precio_Mercado'] or 0)
                else:
                    precio_segun_perfil = float(producto['Precio_Mercado'] or 0)
                
                resultados.append({
                    'id': producto['ID_Producto'],
                    'nombre': producto['Nombre_Producto'],
                    'codigo': producto['COD_Producto'],
                    # Todos los precios disponibles
                    'precio_mercado': float(producto['Precio_Mercado'] or 0),
                    'precio_mayorista': float(producto['Precio_Mayorista'] or 0),
                    'precio_ruta': float(producto['Precio_Ruta'] or 0),
                    # Precio según el perfil solicitado
                    'precio': precio_segun_perfil,
                    'perfil_aplicado': perfil_cliente,  # Para saber qué perfil se usó
                    'stock': float(producto['Stock_Total']) if producto['Stock_Total'] else 0,
                    'unidad_medida': producto['Unidad_Medida'],
                    'unidad_descripcion': producto['Unidad_Descripcion'] or 'Unidad',
                    'unidad_abreviatura': producto['Unidad_Abreviatura'] or '',
                    'categoria': producto['Categoria_Descripcion'] or ''
                })
            
            return jsonify(resultados)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/ventas/obtener-categorias-visibles')
@admin_required
def obtener_categorias_visibles():
    """
    API para obtener categorías visibles según tipo de cliente
    Útil para cargar selectores dinámicos en formularios
    """
    try:
        tipo_cliente = request.args.get('tipo_cliente')
        
        if not tipo_cliente:
            return jsonify({'error': 'Tipo de cliente no especificado'}), 400
        
        with get_db_cursor(True) as cursor:
            # Obtener categorías visibles para el tipo de cliente
            sql_categorias = """
            SELECT 
                cp.ID_Categoria,
                cp.Descripcion as Nombre_Categoria
            FROM categorias_producto cp
            INNER JOIN config_visibilidad_categorias cv ON cp.ID_Categoria = cv.ID_Categoria
            WHERE cv.tipo_cliente = %s 
            AND cv.visible = 1
            ORDER BY cp.Descripcion
            """
            
            cursor.execute(sql_categorias, (tipo_cliente,))
            categorias = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            categorias_lista = []
            for categoria in categorias:
                categorias_lista.append({
                    'id': categoria['ID_Categoria'],
                    'nombre': categoria['Nombre_Categoria']
                })
            
            return jsonify({'categorias': categorias_lista})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/ventas/obtener-productos-categoria')
@admin_required
def obtener_productos_categoria():
    """
    API para obtener productos de una categoría específica
    AHORA INCLUYE: TODOS los precios y filtra por perfil_cliente
    """
    try:
        categoria_id = request.args.get('categoria_id')
        tipo_cliente = request.args.get('tipo_cliente')
        perfil_cliente = request.args.get('perfil_cliente', 'Mercado')  # NUEVO
        
        if not categoria_id or not tipo_cliente:
            return jsonify({'error': 'Parámetros incompletos'}), 400
        
        with get_db_cursor(True) as cursor:
            # Verificar que la categoría es visible para este tipo de cliente
            sql_visibilidad = """
            SELECT visible FROM config_visibilidad_categorias 
            WHERE ID_Categoria = %s AND tipo_cliente = %s
            """
            cursor.execute(sql_visibilidad, (categoria_id, tipo_cliente))
            config = cursor.fetchone()
            
            if not config or not config['visible']:
                return jsonify({'productos': []})
            
            # Obtener productos activos de esta categoría con TODOS los precios
            sql_productos = """
            SELECT 
                p.ID_Producto,
                p.Descripcion as Nombre_Producto,
                p.COD_Producto,
                p.Precio_Mercado,
                p.Precio_Mayorista,
                p.Precio_Ruta,
                p.ID_Categoria,
                p.Unidad_Medida,
                u.Descripcion as Unidad_Descripcion,
                u.Abreviatura as Unidad_Abreviatura,
                c.Descripcion as Categoria_Descripcion,
                COALESCE(SUM(ib.Existencias), 0) as Stock_Total
            FROM productos p
            LEFT JOIN unidades_medida u ON p.Unidad_Medida = u.ID_Unidad
            LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
            LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
            WHERE p.ID_Categoria = %s 
            AND p.Estado = 'activo'
            GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto, 
                     p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,
                     p.ID_Categoria, p.Unidad_Medida, u.Descripcion, u.Abreviatura, 
                     c.Descripcion
            HAVING Stock_Total > 0
            ORDER BY p.Descripcion
            """
            
            cursor.execute(sql_productos, (categoria_id,))
            productos = cursor.fetchall()
            
            # Convertir a lista de diccionarios con todos los precios
            productos_lista = []
            for producto in productos:
                # Calcular precio según perfil para mostrar por defecto
                if perfil_cliente == 'Ruta':
                    precio_segun_perfil = float(producto['Precio_Ruta'] or 0)
                elif perfil_cliente == 'Mayorista':
                    precio_segun_perfil = float(producto['Precio_Mayorista'] or 0)
                else:  # Mercado o Especial
                    precio_segun_perfil = float(producto['Precio_Mercado'] or 0)
                
                productos_lista.append({
                    'id': producto['ID_Producto'],
                    'nombre': producto['Nombre_Producto'],
                    'codigo': producto['COD_Producto'],
                    # Todos los precios
                    'precio_mercado': float(producto['Precio_Mercado'] or 0),
                    'precio_mayorista': float(producto['Precio_Mayorista'] or 0),
                    'precio_ruta': float(producto['Precio_Ruta'] or 0),
                    # Precio según perfil (para mostrar por defecto)
                    'precio': precio_segun_perfil,
                    'perfil_aplicado': perfil_cliente,
                    'stock': float(producto['Stock_Total']) if producto['Stock_Total'] else 0,
                    'categoria_id': producto['ID_Categoria'],
                    'unidad_medida': producto['Unidad_Medida'],
                    'unidad_descripcion': producto['Unidad_Descripcion'] or 'Unidad',
                    'unidad_abreviatura': producto['Unidad_Abreviatura'] or '',
                    'categoria_descripcion': producto['Categoria_Descripcion'] or ''
                })
            
            return jsonify({'productos': productos_lista})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/ventas/obtener-stock-producto/<int:producto_id>')
@admin_required
def obtener_stock_producto(producto_id):
    """
    API para obtener stock detallado de un producto por bodega
    AHORA INCLUYE: información de precios del producto
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener stock por bodega
            sql_stock = """
            SELECT 
                ib.ID_Bodega,
                b.Nombre_Bodega,
                ib.Existencias
            FROM inventario_bodega ib
            LEFT JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
            WHERE ib.ID_Producto = %s
            AND ib.Existencias > 0
            ORDER BY b.Nombre_Bodega
            """
            
            cursor.execute(sql_stock, (producto_id,))
            stock_bodegas = cursor.fetchall()
            
            # Calcular stock total
            sql_total = """
            SELECT COALESCE(SUM(Existencias), 0) as Stock_Total
            FROM inventario_bodega 
            WHERE ID_Producto = %s
            """
            cursor.execute(sql_total, (producto_id,))
            stock_total_result = cursor.fetchone()
            stock_total = stock_total_result['Stock_Total'] if stock_total_result else 0
            
            # Obtener información completa del producto (con todos los precios)
            sql_producto = """
            SELECT 
                Descripcion, 
                COD_Producto,
                Precio_Mercado,
                Precio_Mayorista,
                Precio_Ruta,
                Unidad_Medida,
                Stock_Minimo
            FROM productos 
            WHERE ID_Producto = %s
            """
            cursor.execute(sql_producto, (producto_id,))
            producto_info = cursor.fetchone()
            
            return jsonify({
                'producto': producto_info['Descripcion'] if producto_info else 'Producto desconocido',
                'codigo': producto_info['COD_Producto'] if producto_info else '',
                'precios': {
                    'mercado': float(producto_info['Precio_Mercado'] or 0) if producto_info else 0,
                    'mayorista': float(producto_info['Precio_Mayorista'] or 0) if producto_info else 0,
                    'ruta': float(producto_info['Precio_Ruta'] or 0) if producto_info else 0
                },
                'unidad_medida': producto_info['Unidad_Medida'] if producto_info else None,
                'stock_minimo': float(producto_info['Stock_Minimo'] or 5) if producto_info else 5,
                'stock_total': float(stock_total),
                'bodegas': stock_bodegas
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/ventas/obtener-bodegas-empresa/<int:empresa_id>')
@admin_required
def obtener_bodegas_empresa(empresa_id):
    """
    API para obtener bodegas activas de una empresa
    """
    try:
        with get_db_cursor(True) as cursor:
            sql = """
            SELECT ID_Bodega, Nombre_Bodega 
            FROM bodegas 
            WHERE ID_Empresa = %s AND Estado = 'ACTIVO'
            ORDER BY Nombre_Bodega
            """
            cursor.execute(sql, (empresa_id,))
            bodegas = cursor.fetchall()
            
            return jsonify({'bodegas': bodegas})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/ventas/obtener-precio-segun-perfil')
@admin_required
def obtener_precio_segun_perfil():
    """
    API para obtener el precio de un producto según el perfil del cliente
    Útil para actualizar precios dinámicamente en el frontend
    """
    try:
        producto_id = request.args.get('producto_id')
        perfil_cliente = request.args.get('perfil_cliente', 'Mercado')
        
        if not producto_id:
            return jsonify({'error': 'ID de producto requerido'}), 400
        
        with get_db_cursor(True) as cursor:
            sql = """
            SELECT 
                Precio_Mercado,
                Precio_Mayorista,
                Precio_Ruta
            FROM productos 
            WHERE ID_Producto = %s AND Estado = 'activo'
            """
            
            cursor.execute(sql, (producto_id,))
            producto = cursor.fetchone()
            
            if not producto:
                return jsonify({'error': 'Producto no encontrado'}), 404
            
            # Determinar qué precio aplicar según el perfil
            if perfil_cliente == 'Ruta':
                precio = float(producto['Precio_Ruta'] or 0)
                tipo_precio = 'Precio Ruta'
            elif perfil_cliente == 'Mayorista':
                precio = float(producto['Precio_Mayorista'] or 0)
                tipo_precio = 'Precio Mayorista'
            else:  # Mercado o Especial
                precio = float(producto['Precio_Mercado'] or 0)
                tipo_precio = 'Precio Mercado'
            
            return jsonify({
                'success': True,
                'producto_id': producto_id,
                'perfil': perfil_cliente,
                'precio': precio,
                'tipo_precio': tipo_precio,
                'todos_los_precios': {
                    'mercado': float(producto['Precio_Mercado'] or 0),
                    'mayorista': float(producto['Precio_Mayorista'] or 0),
                    'ruta': float(producto['Precio_Ruta'] or 0)
                }
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/ventas/productos-por-categoria/<int:id_categoria>')
@admin_or_bodega_required
def obtener_productos_por_categoria_venta(id_categoria):
    """
    Endpoint para obtener productos filtrados por categoría (con los 3 precios)
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        print(f"🔍 [VENTAS] Filtrando productos - Categoría: {id_categoria}, Bodega: {id_bodega}")
        
        with get_db_cursor(True) as cursor:
            if id_categoria == 0:  # Todas las categorías
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion, 
                        COALESCE(ib.Existencias, 0) as Existencias,
                        p.Precio_Mercado,
                        p.Precio_Mayorista,
                        p.Precio_Ruta,
                        p.ID_Categoria,
                        c.Descripcion as Categoria
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo' 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    AND COALESCE(ib.Existencias, 0) > 0
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_bodega, id_empresa))
            else:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion, 
                        COALESCE(ib.Existencias, 0) as Existencias,
                        p.Precio_Mercado,
                        p.Precio_Mayorista,
                        p.Precio_Ruta,
                        p.ID_Categoria,
                        c.Descripcion as Categoria
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo' 
                    AND p.ID_Categoria = %s 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    AND COALESCE(ib.Existencias, 0) > 0
                    ORDER BY p.Descripcion
                """, (id_bodega, id_categoria, id_empresa))
            
            productos = cursor.fetchall()
            print(f"✅ [VENTAS] Productos encontrados: {len(productos)} para categoría {id_categoria}")
            
            productos_list = []
            for producto in productos:
                productos_list.append({
                    'ID_Producto': producto['ID_Producto'],
                    'COD_Producto': producto['COD_Producto'],
                    'Descripcion': producto['Descripcion'],
                    'Existencias': float(producto['Existencias']),
                    'Precio_Mercado': float(producto['Precio_Mercado'] or 0),
                    'Precio_Mayorista': float(producto['Precio_Mayorista'] or 0),
                    'Precio_Ruta': float(producto['Precio_Ruta'] or 0),
                    'ID_Categoria': producto['ID_Categoria'],
                    'Categoria': producto['Categoria']
                })
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f" [VENTAS] Error al obtener productos por categoría: {str(e)}")
        import traceback
        print(f" [VENTAS] Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/ventas/todos-productos')
@admin_or_bodega_required
def obtener_todos_productos_venta():
    """
    Endpoint para obtener TODOS los productos activos con stock (con los 3 precios)
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        print(f"🔍 [VENTAS] Cargando TODOS los productos con los 3 precios - Bodega: {id_bodega}")
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    COALESCE(ib.Existencias, 0) as Existencias,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    p.ID_Categoria,
                    c.Descripcion as Categoria
                FROM productos p
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                WHERE p.Estado = 'activo' 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND COALESCE(ib.Existencias, 0) > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_bodega, id_empresa))
            
            productos = cursor.fetchall()
            print(f"✅ [VENTAS] Total productos encontrados: {len(productos)}")
            
            productos_list = []
            for producto in productos:
                productos_list.append({
                    'ID_Producto': producto['ID_Producto'],
                    'COD_Producto': producto['COD_Producto'],
                    'Descripcion': producto['Descripcion'],
                    'Existencias': float(producto['Existencias']),
                    'Precio_Mercado': float(producto['Precio_Mercado'] or 0),
                    'Precio_Mayorista': float(producto['Precio_Mayorista'] or 0),
                    'Precio_Ruta': float(producto['Precio_Ruta'] or 0),
                    'ID_Categoria': producto['ID_Categoria'],
                    'Categoria': producto['Categoria']
                })
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f" [VENTAS] Error al obtener todos los productos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/ventas/bodega-principal')
@admin_or_bodega_required
def obtener_bodega_principal():
    """
    Endpoint para obtener la bodega principal
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE Estado = 1 
                AND (ID_Empresa = %s OR ID_Empresa IS NULL)
                ORDER BY ID_Bodega 
                LIMIT 1
            """, (id_empresa,))
            
            bodega = cursor.fetchone()
            
            if bodega:
                return jsonify({
                    'id_bodega': bodega['ID_Bodega'],
                    'nombre': bodega['Nombre']
                })
            else:
                return jsonify({'error': 'No hay bodegas activas'}), 404
                
    except Exception as e:
        print(f" [BODEGA] Error al obtener bodega principal: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/ventas/verificar-stock/<int:id_producto>')
@admin_or_bodega_required
def verificar_stock_producto(id_producto):
    """
    Endpoint para verificar stock en tiempo real y obtener precios del producto
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        print(f"🔍 [STOCK] Verificando stock - Producto: {id_producto}, Bodega: {id_bodega}")
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion,
                    p.COD_Producto,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    COALESCE(ib.Existencias, 0) as Existencias,
                    b.Nombre as Bodega
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                LEFT JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                WHERE p.ID_Producto = %s 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND p.Estado = 'activo'
            """, (id_bodega, id_producto, id_empresa))
            
            producto = cursor.fetchone()
            
            if producto:
                stock = float(producto['Existencias'])
                print(f"✅ [STOCK] Producto {id_producto}: {stock} unidades en {producto['Bodega']}")
                
                return jsonify({
                    'success': True,
                    'id_producto': producto['ID_Producto'],
                    'codigo': producto['COD_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': stock,
                    'bodega': producto['Bodega'],
                    'precios': {
                        'mercado': float(producto['Precio_Mercado'] or 0),
                        'mayorista': float(producto['Precio_Mayorista'] or 0),
                        'ruta': float(producto['Precio_Ruta'] or 0)
                    }
                })
            else:
                print(f" [STOCK] Producto {id_producto} no encontrado en bodega {id_bodega}")
                return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
                
    except Exception as e:
        print(f" [STOCK] Error al verificar stock: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/ventas/categorias-productos')
@admin_or_bodega_required
def obtener_categorias_productos_venta():
    """
    Endpoint para obtener todas las categorías
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            categorias_list = []
            for categoria in categorias:
                categorias_list.append({
                    'id': categoria['ID_Categoria'],
                    'descripcion': categoria['Descripcion']
                })
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f" [VENTAS] Error al obtener categorías: {str(e)}")
        return jsonify({'error': str(e)}), 500


