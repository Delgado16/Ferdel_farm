from decimal import Decimal
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import date, datetime, time, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator


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
            
            # Validar que haya al menos un método de pago
            if not metodos_pago_ids or len(metodos_pago_ids) == 0:
                error_msg = 'Debe seleccionar al menos un método de pago'
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
                print(f"💰 Saldo actual del cliente: C${saldo_actual_cliente:,.2f}")
                
                # VERIFICAR ESTADO DE CUENTA (facturas pendientes)
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
                
                # Calcular total de la venta primero
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
                
                # Procesar métodos de pago
                metodos_pago_list = []
                total_pagado = 0
                monto_efectivo = 0  # 🔥 NUEVA VARIABLE PARA EFECTIVO
                
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
                            
                            # 🔥 ACUMULAR SOLO EL EFECTIVO
                            if nombre_metodo.upper() in ['EFECTIVO', 'EFECTIVO CORDODAS', 'EFECTIVO DOLARES', 'CASH']:
                                monto_efectivo += monto
                
                print(f"📊 Total venta: C${total_venta:,.2f}")
                print(f"💵 Total pagado: C${total_pagado:,.2f}")
                print(f"💰 Monto en EFECTIVO: C${monto_efectivo:,.2f}")  # 🔥 NUEVO LOG
                print(f"💳 Otros métodos: C${total_pagado - monto_efectivo:,.2f}")  # 🔥 NUEVO LOG
                
                # Validaciones de pago
                if total_pagado > total_venta:
                    raise Exception(f'El monto total pagado (C${total_pagado:,.2f}) no puede exceder el total de la venta (C${total_venta:,.2f})')
                
                if tipo_venta == 'contado' and total_pagado < total_venta:
                    raise Exception(f'En ventas de contado debe pagarse el total. Pagado: C${total_pagado:,.2f}, Total: C${total_venta:,.2f}')
                
                # 1. Crear factura con métodos de pago
                import json
                metodos_pago_json = json.dumps(metodos_pago_list, ensure_ascii=False)
                
                cursor.execute("""
                    INSERT INTO facturacion (
                        Fecha, IDCliente, Credito_Contado, Observacion, 
                        metodos_pago, ID_Empresa, ID_Usuario_Creacion
                    )
                    VALUES (CURDATE(), %s, %s, %s, %s, %s, %s)
                """, (
                    id_cliente,
                    1 if tipo_venta == 'credito' else 0,
                    observacion,
                    metodos_pago_json,
                    id_empresa,
                    id_usuario
                ))
                
                # Obtener el ID de la factura
                cursor.execute("SELECT LAST_INSERT_ID() as id_factura")
                id_factura = cursor.fetchone()['id_factura']
                print(f"🧾 Factura #{id_factura} creada")
                
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
                    'CREDITO' if tipo_venta == 'credito' else 'CONTADO',
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
                
                # 6. Manejar crédito o contado
                saldo_pendiente = total_venta - total_pagado
                
                if tipo_venta == 'credito' and saldo_pendiente > 0:
                    # Actualizar saldo pendiente del cliente
                    nuevo_saldo = saldo_actual_cliente + saldo_pendiente
                    
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = %s,
                            Fecha_Ultimo_Movimiento = NOW(),
                            ID_Ultima_Factura = %s
                        WHERE ID_Cliente = %s
                    """, (nuevo_saldo, id_factura, id_cliente))
                    
                    print(f"💰 Actualizando saldo del cliente:")
                    print(f"   Saldo anterior: C${saldo_actual_cliente:,.2f}")
                    print(f"   + Saldo pendiente: C${saldo_pendiente:,.2f}")
                    print(f"   = Nuevo saldo: C${nuevo_saldo:,.2f}")
                    
                    # Insertar registro en cuentas por cobrar
                    cursor.execute("""
                        INSERT INTO cuentas_por_cobrar (
                            Fecha, ID_Cliente, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                            ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion
                        )
                        VALUES (CURDATE(), %s, %s, %s, DATE_ADD(CURDATE(), INTERVAL 30 DAY), 
                                1, %s, %s, %s, %s, %s)
                    """, (
                        id_cliente,
                        f'FAC-{id_factura:05d}',
                        f"Venta {perfil_cliente} - {observacion}",
                        saldo_pendiente,
                        id_empresa,
                        saldo_pendiente,
                        id_factura,
                        id_usuario
                    ))
                    print(f"💳 Cuenta por cobrar creada por C${saldo_pendiente:,.2f}")
                
                # 🔥 7. Registrar pago en caja SOLO si hay PAGO EN EFECTIVO
                if monto_efectivo > 0:
                    descripcion_pago = f"Venta {perfil_cliente} - Factura #{id_factura} - Cliente: {nombre_cliente}"
                    
                    # Si hay múltiples métodos, indicar claramente
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
                        monto_efectivo,  # 🔥 SOLO EL MONTO EN EFECTIVO
                        id_factura,
                        id_usuario,
                        f'FAC-{id_factura:05d}'
                    ))
                    print(f"💰 Pago en EFECTIVO registrado en caja física: C${monto_efectivo:,.2f}")
                else:
                    print(f"ℹ️ No hay pago en efectivo - No se registra movimiento en caja física")
                
                # Construir mensaje de éxito
                success_msg = f'✅ Venta {perfil_cliente} creada! Factura #{id_factura} - Total: C${total_venta:,.2f}'
                
                if total_pagado > 0:
                    success_msg += f' - Pagado: C${total_pagado:,.2f}'
                    if monto_efectivo > 0:
                        success_msg += f' (Efectivo: C${monto_efectivo:,.2f})'
                    if total_pagado - monto_efectivo > 0:
                        success_msg += f' (Otros: C${total_pagado - monto_efectivo:,.2f})'
                
                if saldo_pendiente > 0:
                    success_msg += f' - Saldo pendiente: C${saldo_pendiente:,.2f}'
                
                print(f"🎯 {success_msg}")
                flash(success_msg, 'success')
                
                return jsonify({
                    'success': True,
                    'message': success_msg,
                    'id_factura': id_factura,
                    'total_venta': total_venta,
                    'total_pagado': total_pagado,
                    'monto_efectivo': monto_efectivo,  # 🔥 NUEVO CAMPO
                    'saldo_pendiente': saldo_pendiente,
                    'metodos_pago': metodos_pago_list,
                    'perfil_cliente': perfil_cliente,
                    'cajillas_huevos': total_cajillas_huevos,
                    'separadores': separadores_totales,
                    'facturas_pendientes': facturas_pendientes,
                    'total_pendiente': total_pendiente,
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
        error_msg = f'❌ Error al procesar venta: {str(e)}'
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

@admin_bp.route('/api/facturas_pendientes_cliente/<int:id_cliente>', methods=['GET'])
@admin_or_bodega_required
def api_facturas_pendientes_cliente(id_cliente):
    """API para obtener las facturas pendientes de un cliente"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cxc.Num_Documento as documento,
                    DATE_FORMAT(cxc.Fecha, '%d/%m/%Y') as fecha,
                    DATE_FORMAT(cxc.Fecha_Vencimiento, '%d/%m/%Y') as vencimiento,
                    cxc.Monto_Movimiento as monto_original,
                    cxc.Saldo_Pendiente as saldo,
                    DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as dias_vencido
                FROM cuentas_por_cobrar cxc
                INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
                WHERE cxc.ID_Cliente = %s 
                AND c.ID_Empresa = %s
                AND cxc.Estado IN ('Pendiente', 'Vencida')
                AND cxc.Saldo_Pendiente > 0.01
                AND cxc.ID_Factura IS NOT NULL
                ORDER BY cxc.Fecha_Vencimiento ASC, cxc.Fecha ASC
            """, (id_cliente, id_empresa))
            
            facturas = cursor.fetchall()
            
            facturas_list = []
            for f in facturas:
                facturas_list.append({
                    'documento': f['documento'],
                    'fecha': f['fecha'],
                    'vencimiento': f['vencimiento'],
                    'monto_original': float(f['monto_original']),
                    'saldo': float(f['saldo']),
                    'dias_vencido': f['dias_vencido'] if f['dias_vencido'] else 0
                })
            
            return jsonify({
                'success': True,
                'facturas': facturas_list
            })
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/ventas/productos/cliente/<int:cliente_id>', methods=['GET'])
@admin_or_bodega_required
def api_productos_por_cliente(cliente_id):
    """API para obtener productos visibles para un cliente específico con los 3 tipos de precio"""
    
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        with get_db_cursor() as cursor:
            # 1. Obtener tipo y perfil del cliente
            cursor.execute("""
                SELECT tipo_cliente, perfil_cliente, Nombre 
                FROM clientes 
                WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
            """, (cliente_id,))
            
            cliente = cursor.fetchone()
            if not cliente:
                return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404
            
            tipo_cliente = cliente['tipo_cliente']
            perfil_cliente = cliente['perfil_cliente']
            
            # 2. Obtener productos visibles para ese tipo de cliente con los 3 precios
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
                    c.Descripcion as Categoria,
                    um.Descripcion as Unidad_Medida
                FROM productos p
                INNER JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                INNER JOIN config_visibilidad_categorias cfg 
                    ON c.ID_Categoria = cfg.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE cfg.tipo_cliente = %s
                  AND cfg.visible = 1
                  AND p.Estado = 'activo' 
                  AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                  AND COALESCE(ib.Existencias, 0) > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_bodega, tipo_cliente, id_empresa))
            
            productos = cursor.fetchall()
            
            # Contar productos por categoría
            cursor.execute("""
                SELECT c.Descripcion as categoria, COUNT(p.ID_Producto) as cantidad
                FROM productos p
                INNER JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                INNER JOIN config_visibilidad_categorias cfg 
                    ON c.ID_Categoria = cfg.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE cfg.tipo_cliente = %s
                  AND cfg.visible = 1
                  AND p.Estado = 'activo' 
                  AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                  AND COALESCE(ib.Existencias, 0) > 0
                GROUP BY c.ID_Categoria, c.Descripcion
            """, (id_bodega, tipo_cliente, id_empresa))
            
            categorias_count = cursor.fetchall()
            
            # Calcular el precio según el perfil para cada producto (para referencia)
            productos_con_precio_segun_perfil = []
            for producto in productos:
                producto_dict = dict(producto)
                # Determinar qué precio usar según el perfil
                if perfil_cliente == 'Ruta':
                    precio_aplicado = producto['Precio_Ruta'] or 0
                elif perfil_cliente == 'Mayorista':
                    precio_aplicado = producto['Precio_Mayorista'] or 0
                elif perfil_cliente == 'Mercado':
                    precio_aplicado = producto['Precio_Mercado'] or 0
                else:  # Especial u otros
                    precio_aplicado = producto['Precio_Mercado'] or 0
                
                producto_dict['Precio_Aplicado'] = float(precio_aplicado)
                producto_dict['Perfil_Aplicado'] = perfil_cliente
                productos_con_precio_segun_perfil.append(producto_dict)
            
            return jsonify({
                'success': True,
                'tipo_cliente': tipo_cliente,
                'perfil_cliente': perfil_cliente,
                'productos': productos_con_precio_segun_perfil,
                'categorias': categorias_count,
                'total': len(productos)
            })
            
    except Exception as e:
        print(f"❌ Error en API productos por cliente: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# RUTAS AUXILIARES SIMPLIFICADAS - UNA SOLA BODEGA
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
        print(f"❌ [VENTAS] Error al obtener productos por categoría: {str(e)}")
        import traceback
        print(f"❌ [VENTAS] Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/productos-por-cliente/<int:cliente_id>')
@login_required
def productos_por_cliente(cliente_id):
    """Obtener productos visibles para un cliente específico"""
    
    empresa_id = session.get('empresa_id',1)
    
    with get_db_cursor() as cursor:
        # 1. Obtener tipo de cliente
        cursor.execute("""
            SELECT tipo_cliente 
            FROM clientes 
            WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
        """, (cliente_id,))
        
        cliente = cursor.fetchone()
        if not cliente:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        tipo_cliente = cliente['tipo_cliente']
        
        # 2. Obtener productos visibles para ese tipo
        cursor.execute("""
            SELECT p.*, c.Descripcion as categoria
            FROM productos p
            INNER JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
            INNER JOIN config_visibilidad_categorias cfg 
                ON cat.ID_Categoria = cfg.ID_Categoria
            WHERE cfg.tipo_cliente = %s
              AND cfg.visible = 1
              AND p.Estado = 'activo'
              AND p.ID_Empresa = %s
            ORDER BY p.Descripcion
        """, (tipo_cliente, empresa_id))
        
        productos = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'tipo_cliente': tipo_cliente,
            'productos': productos
        })

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
                print(f"❌ [STOCK] Producto {id_producto} no encontrado en bodega {id_bodega}")
                return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
                
    except Exception as e:
        print(f"❌ [STOCK] Error al verificar stock: {str(e)}")
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
        print(f"❌ [VENTAS] Error al obtener categorías: {str(e)}")
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
        print(f"❌ [VENTAS] Error al obtener todos los productos: {str(e)}")
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
        print(f"❌ [BODEGA] Error al obtener bodega principal: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/ventas/ticket/<int:id_factura>')
@admin_or_bodega_required
def admin_generar_ticket(id_factura):
    try:
        with get_db_cursor(True) as cursor:
            # Obtener datos de la factura
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
            
            # Calcular total
            total_venta = sum(float(detalle['Subtotal'] or 0) for detalle in detalles)
            
            # Procesar métodos de pago
            import json
            metodos_pago = []
            total_pagado = 0
            
            if factura['metodos_pago']:
                try:
                    metodos_pago = json.loads(factura['metodos_pago'])
                    total_pagado = sum(float(p['monto']) for p in metodos_pago)
                except:
                    metodos_pago = []
                    total_pagado = 0
            
            # Si es contado pero no hay métodos registrados, mostrar efectivo
            if factura['Credito_Contado'] == 0 and not metodos_pago:
                metodos_pago = [{
                    'nombre': 'Efectivo',
                    'monto': total_venta,
                    'referencia': ''
                }]
                total_pagado = total_venta
            
            saldo_pendiente = total_venta - total_pagado if factura['Credito_Contado'] == 1 else 0
            
            # Obtener información del movimiento
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento
                FROM movimientos_inventario mi
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.ID_Factura_Venta = %s
            """, (id_factura,))
            movimiento = cursor.fetchone()
            
            # Verificar cuenta por cobrar
            cuenta_cobrar = None
            if saldo_pendiente > 0:
                cursor.execute("""
                    SELECT Saldo_Pendiente, Fecha_Vencimiento
                    FROM cuentas_por_cobrar 
                    WHERE ID_Factura = %s AND Saldo_Pendiente > 0
                """, (id_factura,))
                cuenta_cobrar = cursor.fetchone()
            
            hora_emision = datetime.now()
            
            ticket_data = {
                'id_factura': factura['ID_Factura'],
                'fecha': factura['Fecha'],
                'hora_emision': hora_emision,
                'cliente': factura['Cliente'] or 'Consumidor Final',
                'ruc_cliente': factura['RUC_Cliente'] or 'Consumidor Final',
                'tipo_venta': factura['Tipo_Venta_Formateado'],
                'observacion': factura['Observacion'],
                'usuario': factura['Usuario'] or 'Usuario No Especificado',
                'detalles': detalles,
                'total': total_venta,
                'total_pagado': total_pagado,
                'saldo_pendiente': saldo_pendiente,
                'metodos_pago': metodos_pago,
                'empresa': {
                    'nombre': factura['Nombre_Empresa'],
                    'ruc': factura['RUC_Empresa'],
                    'direccion': factura['Direccion_Empresa'],
                    'telefono': factura['Telefono_Empresa']
                },
                'movimiento': movimiento,
                'tiene_credito': saldo_pendiente > 0,
                'cuenta_cobrar': cuenta_cobrar
            }
            
            return render_template('admin/ventas/ticket_venta.html', 
                                 ticket=ticket_data)
                             
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
                    (SELECT COALESCE(SUM(Total), 0) 
                     FROM detalle_facturacion 
                     WHERE ID_Factura = f.ID_Factura) as Total_Factura,
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
                       AND ib.ID_Bodega = %s
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
            """, (factura['ID_Bodega'] or 1, factura['ID_Movimiento'], id_factura))
            
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
            
            # 6. Obtener historial de pagos si es crédito
            pagos = []
            if tiene_credito_pendiente:
                cursor.execute("""
                    SELECT 
                        Fecha_Pago,
                        Monto_Pago,
                        Observacion,
                        Forma_Pago,
                        Numero_Comprobante
                    FROM pagos_cuentascobrar
                    WHERE ID_Cuenta_Cobrar IN (
                        SELECT ID_Cuenta_Cobrar 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Factura = %s
                    )
                    ORDER BY Fecha_Pago DESC
                """, (id_factura,))
                pagos = cursor.fetchall()
            
            # 7. Obtener datos del movimiento de inventario (si existe)
            movimiento_info = None
            if factura['ID_Movimiento']:
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        DATE_FORMAT(mi.Fecha, '%d/%m/%Y') as Fecha_Formateada,
                        mi.Fecha,
                        mi.Observacion,
                        mi.ID_Usuario_Creacion,
                        mi.Estado,
                        mi.ID_Bodega,
                        DATE_FORMAT(mi.Fecha, '%d/%m/%Y %H:%i') as Fecha_Completa,
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
            print(f"❌ Error obteniendo datos de venta #{id_factura}: {str(e)}")
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
            error_msg = f'❌ Error al anular venta #{id_factura}: {str(e)}'
            print(error_msg)
            traceback.print_exc()
            flash(error_msg, 'error')
            return redirect(url_for('admin.admin_ventas_salidas'))

# CLIENTES ANTICIPOS
@admin_bp.route('/admin/ventas/anticipos/clientes-anticipos')
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS")   
def admin_clientes_anticipos():
    try:
        id_empresa = session.get('id_empresa', 1)
        if not id_empresa:
            flash('No se encontró información de la empresa', 'error')
            return redirect(url_for('admin_dashboard'))
            
        with get_db_cursor(True) as cursor:
            # Como anticipos_clientes no tiene ID_Empresa, debemos unir con clientes
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.Fecha_Anticipo as Fecha,
                    a.Monto_Pagado as Monto,
                    a.Saldo_Restante,
                    a.Cantidad_Cajas,
                    a.Cajas_Consumidas,
                    a.Estado,
                    a.Notas as Observacion,
                    c.Nombre as NombreCliente,
                    c.RUC_CEDULA as RUCCliente,
                    c.ID_Empresa,
                    c.Saldo_Anticipos,
                    c.Anticipo_Activo,
                    c.Limite_Anticipo_Cajas,
                    c.Cajas_Consumidas_Anticipo,
                    p.Descripcion as NombreProducto,
                    p.COD_Producto,
                    e.Nombre_Empresa,
                    DATEDIFF(NOW(), a.Fecha_Anticipo) as Dias_Transcurridos
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Empresa = %s
                ORDER BY a.Fecha_Anticipo DESC, a.ID_Anticipo DESC
                LIMIT 10
            """, (id_empresa,))
            anticipos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/clientes_anticipos.html', 
                                 anticipos=anticipos)
    except Exception as e:
        print(f"❌ Error obteniendo anticipos de clientes: {str(e)}")
        traceback.print_exc()
        flash('Error interno al obtener anticipos de clientes', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/ventas/anticipos/nuevo', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-NUEVO")
def admin_anticipo_nuevo():
    id_empresa = session.get('id_empresa', 1)
    if not id_empresa:
        flash('No se encontró información de la empresa', 'error')
        return redirect(url_for('admin.admin_dashboard'))
    
    if request.method == 'POST':
        try:
            id_cliente = request.form.get('id_cliente')
            id_producto = request.form.get('id_producto')
            cantidad_cajas = int(request.form.get('cantidad_cajas', 0))
            monto_pagado = float(request.form.get('monto_pagado', 0))
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            notas = request.form.get('notas', '')
            precio_especial = request.form.get('precio_especial', '').strip()
            calcular_precio_auto = request.form.get('calcular_precio_auto')
            
            # Validaciones
            if not id_cliente or not id_producto:
                flash('Cliente y producto son requeridos', 'error')
                return redirect(url_for('admin.admin_anticipo_nuevo'))
            
            if cantidad_cajas <= 0:
                flash('La cantidad de cajas debe ser mayor a 0', 'error')
                return redirect(url_for('admin.admin_anticipo_nuevo'))
            
            if monto_pagado <= 0:
                flash('El monto pagado debe ser mayor a 0', 'error')
                return redirect(url_for('admin.admin_anticipo_nuevo'))
            
            with get_db_cursor() as cursor:
                # Verificar que el cliente pertenece a la empresa
                cursor.execute("""
                    SELECT ID_Cliente, perfil_cliente, tipo_cliente, Anticipo_Activo
                    FROM clientes 
                    WHERE ID_Cliente = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'
                """, (id_cliente, id_empresa))
                
                cliente = cursor.fetchone()
                if not cliente:
                    flash('Cliente no encontrado o no pertenece a su empresa', 'error')
                    return redirect(url_for('admin.admin_anticipo_nuevo'))
                
                # Obtener información del producto (solo para descripción, NO para el precio)
                cursor.execute("""
                    SELECT 
                        p.ID_Producto,
                        p.Descripcion,
                        p.COD_Producto
                    FROM productos p
                    WHERE p.ID_Producto = %s AND p.ID_Empresa = %s AND p.Estado = 'activo'
                """, (id_producto, id_empresa))
                
                producto = cursor.fetchone()
                if not producto:
                    flash('Producto no encontrado o no pertenece a su empresa', 'error')
                    return redirect(url_for('admin.admin_anticipo_nuevo'))
                
                # Determinar precio unitario según el perfil del cliente
                precio_unitario = 0
                perfil_cliente = cliente['perfil_cliente']
                
                # LÓGICA PRINCIPAL: Según el perfil del cliente
                if perfil_cliente == 'Especial':
                    # CLIENTE PERFIL ESPECIAL: El usuario ingresa el precio
                    if calcular_precio_auto == 'on':
                        # Calcular precio automáticamente: monto_pagado / cantidad_cajas
                        precio_unitario = monto_pagado / cantidad_cajas
                        flash(f'💰 Precio calculado automáticamente: ${precio_unitario:.2f} por caja (${monto_pagado:,.2f} / {cantidad_cajas} cajas)', 'info')
                    elif precio_especial and float(precio_especial) > 0:
                        # Usar precio especial ingresado manualmente
                        precio_unitario = float(precio_especial)
                        flash(f'💰 Precio especial ingresado: ${precio_unitario:.2f} por caja', 'info')
                    else:
                        # Si no hay precio especial, calcular automáticamente como fallback
                        precio_unitario = monto_pagado / cantidad_cajas
                        flash(f'💰 Precio calculado automáticamente: ${precio_unitario:.2f} por caja', 'info')
                    
                    # Validar que el precio sea positivo
                    if precio_unitario <= 0:
                        flash('El precio por caja debe ser mayor a 0', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                        
                elif perfil_cliente == 'Mayorista':
                    # Obtener precio mayorista del producto
                    cursor.execute("SELECT Precio_Mayorista FROM productos WHERE ID_Producto = %s", (id_producto,))
                    precio_data = cursor.fetchone()
                    precio_unitario = float(precio_data['Precio_Mayorista']) if precio_data and precio_data['Precio_Mayorista'] else 0
                    
                    if precio_unitario <= 0:
                        flash('El producto no tiene precio mayorista configurado', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                    
                    # Verificar que el monto corresponda
                    monto_esperado = cantidad_cajas * precio_unitario
                    if abs(monto_pagado - monto_esperado) > 0.01:
                        flash(f'⚠️ Atención: El monto pagado (${monto_pagado:,.2f}) no corresponde con el precio mayorista (${monto_esperado:,.2f}). Se usará el monto ingresado.', 'warning')
                        
                elif perfil_cliente == 'Ruta':
                    # Obtener precio ruta del producto
                    cursor.execute("SELECT Precio_Ruta FROM productos WHERE ID_Producto = %s", (id_producto,))
                    precio_data = cursor.fetchone()
                    precio_unitario = float(precio_data['Precio_Ruta']) if precio_data and precio_data['Precio_Ruta'] else 0
                    
                    if precio_unitario <= 0:
                        flash('El producto no tiene precio ruta configurado', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                    
                    # Verificar que el monto corresponda
                    monto_esperado = cantidad_cajas * precio_unitario
                    if abs(monto_pagado - monto_esperado) > 0.01:
                        flash(f'⚠️ Atención: El monto pagado (${monto_pagado:,.2f}) no corresponde con el precio ruta (${monto_esperado:,.2f}). Se usará el monto ingresado.', 'warning')
                        
                else:  # perfil_cliente == 'Mercado' o cualquier otro
                    # Obtener precio mercado del producto
                    cursor.execute("SELECT Precio_Mercado FROM productos WHERE ID_Producto = %s", (id_producto,))
                    precio_data = cursor.fetchone()
                    precio_unitario = float(precio_data['Precio_Mercado']) if precio_data and precio_data['Precio_Mercado'] else 0
                    
                    if precio_unitario <= 0:
                        flash('El producto no tiene precio mercado configurado', 'error')
                        return redirect(url_for('admin.admin_anticipo_nuevo'))
                    
                    # Verificar que el monto corresponda
                    monto_esperado = cantidad_cajas * precio_unitario
                    if abs(monto_pagado - monto_esperado) > 0.01:
                        flash(f'⚠️ Atención: El monto pagado (${monto_pagado:,.2f}) no corresponde con el precio mercado (${monto_esperado:,.2f}). Se usará el monto ingresado.', 'warning')
                
                # Calcular saldo restante
                saldo_restante = monto_pagado
                
                # Insertar anticipo con el precio unitario determinado
                cursor.execute("""
                    INSERT INTO anticipos_clientes 
                    (ID_Cliente, ID_Producto, Cantidad_Cajas, Cajas_Consumidas, 
                     Monto_Pagado, Saldo_Restante, Precio_Unitario, Fecha_Anticipo, 
                     Fecha_Vencimiento, Estado, Notas)
                    VALUES (%s, %s, %s, 0, %s, %s, %s, NOW(), %s, 'ACTIVO', %s)
                """, (id_cliente, id_producto, cantidad_cajas, monto_pagado, 
                      saldo_restante, precio_unitario, fecha_vencimiento or None, notas))
                
                id_anticipo = cursor.lastrowid
                
                # Actualizar datos del cliente
                cursor.execute("""
                    UPDATE clientes 
                    SET Anticipo_Activo = 1,
                        Limite_Anticipo_Cajas = COALESCE(Limite_Anticipo_Cajas, 0) + %s,
                        Saldo_Anticipos = COALESCE(Saldo_Anticipos, 0) + %s,
                        Producto_Anticipado = %s
                    WHERE ID_Cliente = %s
                """, (cantidad_cajas, monto_pagado, id_producto, id_cliente))
                
                flash(f'✅ Anticipo registrado exitosamente. ID: {id_anticipo} - Precio por caja: ${precio_unitario:.2f}', 'success')
                return redirect(url_for('admin.admin_clientes_anticipos'))
                
        except Exception as e:
            print(f"❌ Error registrando anticipo: {str(e)}")
            traceback.print_exc()
            flash('Error interno al registrar el anticipo', 'error')
            return redirect(url_for('admin.admin_anticipo_nuevo'))
    
    # GET - Mostrar formulario
    try:
        with get_db_cursor(True) as cursor:
            # Obtener clientes activos de la empresa
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA, perfil_cliente, tipo_cliente,
                       COALESCE(Saldo_Anticipos, 0) as Saldo_Anticipos, 
                       COALESCE(Limite_Anticipo_Cajas, 0) as Limite_Anticipo_Cajas
                FROM clientes 
                WHERE ID_Empresa = %s AND Estado = 'ACTIVO'
                ORDER BY Nombre
            """, (id_empresa,))
            clientes = cursor.fetchall()
            
            # Obtener productos activos de la empresa
            cursor.execute("""
                SELECT ID_Producto, Descripcion, COD_Producto, 
                       COALESCE(Precio_Mercado, 0) as Precio_Mercado, 
                       COALESCE(Precio_Mayorista, 0) as Precio_Mayorista, 
                       COALESCE(Precio_Ruta, 0) as Precio_Ruta
                FROM productos 
                WHERE ID_Empresa = %s AND Estado = 'activo'
                ORDER BY Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/nuevo_anticipo.html',
                                 clientes=clientes, productos=productos)
    except Exception as e:
        print(f"❌ Error cargando formulario: {str(e)}")
        traceback.print_exc()
        flash('Error cargando el formulario', 'error')
        return redirect(url_for('admin.admin_clientes_anticipos'))

@admin_bp.route('/admin/ventas/anticipos/detalle/<int:id_anticipo>')
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-DETALLE")
def admin_anticipo_detalle(id_anticipo):
    try:
        id_empresa = session.get('id_empresa',1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    a.*,
                    c.Nombre as NombreCliente,
                    c.RUC_CEDULA,
                    c.Telefono,
                    c.Direccion,
                    c.perfil_cliente,
                    c.Saldo_Anticipos as Cliente_Saldo_Anticipos,
                    c.Limite_Anticipo_Cajas,
                    c.Cajas_Consumidas_Anticipo,
                    p.Descripcion as NombreProducto,
                    p.COD_Producto,
                    CASE 
                        WHEN c.perfil_cliente = 'Mayorista' THEN p.Precio_Mayorista
                        WHEN c.perfil_cliente = 'Ruta' THEN p.Precio_Ruta
                        ELSE p.Precio_Mercado
                    END as Precio_Actual
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Anticipo = %s AND c.ID_Empresa = %s
            """, (id_anticipo, id_empresa))
            
            anticipo = cursor.fetchone()
            
            if not anticipo:
                flash('Anticipo no encontrado', 'error')
                return redirect(url_for('admin.admin_clientes_anticipos'))
            
            return render_template('admin/ventas/anticipos/detalle_anticipo.html',
                                 anticipo=anticipo)
    except Exception as e:
        print(f"❌ Error obteniendo detalle: {str(e)}")
        traceback.print_exc()
        flash('Error al obtener el detalle del anticipo', 'error')
        return redirect(url_for('admin.admin_clientes_anticipos'))

@admin_bp.route('/admin/ventas/anticipos/cancelar/<int:id_anticipo>', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-CANCELAR")
def admin_anticipo_cancelar(id_anticipo):
    try:
        id_empresa = session.get('id_empresa', 1)
        motivo = request.form.get('motivo', 'Cancelado por usuario')
        
        with get_db_cursor() as cursor:
            # Obtener información del anticipo verificando empresa a través del cliente
            cursor.execute("""
                SELECT a.ID_Cliente, a.Cantidad_Cajas, a.Cajas_Consumidas, 
                       a.Monto_Pagado, a.Saldo_Restante, a.Estado
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                WHERE a.ID_Anticipo = %s AND c.ID_Empresa = %s AND a.Estado = 'ACTIVO'
            """, (id_anticipo, id_empresa))
            
            anticipo = cursor.fetchone()
            
            if not anticipo:
                flash('Anticipo no encontrado o ya está cancelado/completado', 'error')
                return redirect(url_for('admin.admin_clientes_anticipos'))
            
            # Cancelar anticipo
            cursor.execute("""
                UPDATE anticipos_clientes 
                SET Estado = 'CANCELADO', 
                    Notas = CONCAT(COALESCE(Notas, ''), '\n[', NOW(), '] Cancelado: ', %s)
                WHERE ID_Anticipo = %s
            """, (motivo, id_anticipo))
            
            # Calcular cajas no consumidas
            cajas_no_consumidas = anticipo['Cantidad_Cajas'] - anticipo['Cajas_Consumidas']
            
            # Actualizar datos del cliente (restar solo lo no consumido)
            cursor.execute("""
                UPDATE clientes 
                SET Limite_Anticipo_Cajas = COALESCE(Limite_Anticipo_Cajas, 0) - %s,
                    Saldo_Anticipos = COALESCE(Saldo_Anticipos, 0) - %s,
                    Anticipo_Activo = CASE 
                        WHEN (COALESCE(Limite_Anticipo_Cajas, 0) - %s) <= 0 THEN 0 
                        ELSE 1 
                    END
                WHERE ID_Cliente = %s
            """, (cajas_no_consumidas, anticipo['Monto_Pagado'], 
                  cajas_no_consumidas, anticipo['ID_Cliente']))
            
            flash('Anticipo cancelado exitosamente', 'success')
            return redirect(url_for('admin.admin_clientes_anticipos'))
            
    except Exception as e:
        print(f"❌ Error cancelando anticipo: {str(e)}")
        traceback.print_exc()
        flash('Error al cancelar el anticipo', 'error')
        return redirect(url_for('admin.admin_clientes_anticipos'))

# ENTREGAS DE CLIENTES POR ANTICIPO
@admin_bp.route('/admin/ventas/anticipos/entregas', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-ANTICIPOS-ENTREGAS")
def admin_anticipo_entregas():
    """Visualizar y realizar entregas de productos con anticipos (múltiples sucursales)"""
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            id_anticipo = request.form.get('id_anticipo')
            id_bodega = request.form.get('id_bodega')
            notas = request.form.get('notas', '')
            
            # Obtener arreglos de sucursales y cantidades
            sucursales = request.form.getlist('sucursales[]')
            cantidades = request.form.getlist('cantidades[]')
            
            # Validar datos básicos
            if not id_anticipo:
                flash('❌ Por favor seleccione un anticipo', 'error')
                return redirect(request.url)
            
            if not id_bodega:
                flash('❌ Por favor seleccione una bodega', 'error')
                return redirect(request.url)
            
            if not sucursales or not cantidades:
                flash('❌ Debe agregar al menos una entrega', 'error')
                return redirect(request.url)
            
            # Validar que los arreglos tengan la misma longitud
            if len(sucursales) != len(cantidades):
                flash('❌ Error en los datos de entregas', 'error')
                return redirect(request.url)
            
            # Validar que haya al menos una entrega válida
            entregas_validas = []
            for i in range(len(sucursales)):
                sucursal_id = sucursales[i]
                cantidad_str = cantidades[i]
                
                if not sucursal_id or not cantidad_str:
                    continue
                
                try:
                    cantidad = int(cantidad_str)
                    if cantidad > 0:
                        entregas_validas.append({
                            'sucursal_id': int(sucursal_id),
                            'cantidad': cantidad
                        })
                except ValueError:
                    continue
            
            if len(entregas_validas) == 0:
                flash('❌ No hay entregas válidas para procesar', 'error')
                return redirect(request.url)
            
            # Calcular total de cajas
            total_cajas = sum(e['cantidad'] for e in entregas_validas)
            
            # Obtener el ID del usuario actual
            id_usuario = current_user.id
            
            with get_db_cursor() as cursor:
                # 1. Obtener información completa del anticipo y cliente
                cursor.execute("""
                    SELECT 
                        a.ID_Anticipo, 
                        a.ID_Cliente, 
                        a.ID_Producto, 
                        a.Cantidad_Cajas as Anticipo_Total_Cajas,
                        a.Cajas_Consumidas as Anticipo_Cajas_Consumidas,
                        a.Precio_Unitario,
                        a.Monto_Pagado,
                        a.Saldo_Restante,
                        p.Descripcion as Nombre_Producto,
                        c.Nombre as Nombre_Cliente,
                        c.Telefono,
                        c.Saldo_Anticipos as Cliente_Saldo_Anticipos,
                        c.Cajas_Consumidas_Anticipo as Cliente_Cajas_Consumidas,
                        c.Anticipo_Activo,
                        c.Producto_Anticipado,
                        c.ID_Empresa
                    FROM anticipos_clientes a
                    INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                    INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                    WHERE a.ID_Anticipo = %s AND a.Estado = 'ACTIVO'
                """, (id_anticipo,))
                anticipo = cursor.fetchone()
                
                if not anticipo:
                    flash('❌ Anticipo no encontrado o inactivo', 'error')
                    return redirect(request.url)
                
                # 2. Verificar que la bodega existe y está activa
                cursor.execute("""
                    SELECT ID_Bodega, Nombre
                    FROM bodegas
                    WHERE ID_Bodega = %s AND Estado = 'activa'
                """, (id_bodega,))
                bodega = cursor.fetchone()
                
                if not bodega:
                    flash('❌ Bodega no encontrada o inactiva', 'error')
                    return redirect(request.url)
                
                # 3. Verificar cajas disponibles en el anticipo
                cajas_disponibles_antes = anticipo['Anticipo_Total_Cajas'] - anticipo['Anticipo_Cajas_Consumidas']
                
                if total_cajas > cajas_disponibles_antes:
                    flash(f'⚠️ Cajas insuficientes en el anticipo. Disponibles: {cajas_disponibles_antes}, Solicitadas: {total_cajas}', 'error')
                    return redirect(request.url)
                
                # 4. Verificar inventario en bodega
                cursor.execute("""
                    SELECT Existencias
                    FROM inventario_bodega
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega, anticipo['ID_Producto']))
                inventario = cursor.fetchone()
                
                if not inventario:
                    flash(f'⚠️ El producto {anticipo["Nombre_Producto"]} no tiene inventario en la bodega {bodega["Nombre"]}', 'error')
                    return redirect(request.url)
                
                existencias_actuales = float(inventario['Existencias'])
                
                if total_cajas > existencias_actuales:
                    flash(f'⚠️ Existencias insuficientes. Disponibles: {existencias_actuales} cajas', 'error')
                    return redirect(request.url)
                
                # 5. Calcular precio y total
                precio_unitario = float(anticipo['Precio_Unitario'])
                total_monto = total_cajas * precio_unitario
                
                # 6. REGISTRAR MOVIMIENTO DE INVENTARIO
                id_tipo_movimiento = 14  # Salida por Anticipo Cliente
                observacion_movimiento = f"Salida por anticipo - Cliente: {anticipo['Nombre_Cliente']} - Anticipo #{id_anticipo} - Bodega: {bodega['Nombre']} - Producto: {anticipo['Nombre_Producto']} - Total Cajas: {total_cajas}"
                if notas:
                    observacion_movimiento += f" - Notas: {notas}"
                
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (ID_TipoMovimiento, Fecha, Observacion, ID_Empresa, ID_Bodega, 
                     ID_Usuario_Creacion, Fecha_Creacion, Estado)
                    VALUES (%s, CURDATE(), %s, %s, %s, %s, NOW(), 'Activa')
                """, (id_tipo_movimiento, observacion_movimiento,
                      anticipo['ID_Empresa'], id_bodega, id_usuario))
                
                id_movimiento = cursor.lastrowid
                
                # 7. REGISTRAR DETALLE DEL MOVIMIENTO DE INVENTARIO
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario 
                    (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, 
                     Subtotal, ID_Usuario_Creacion, Fecha_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (id_movimiento, anticipo['ID_Producto'], total_cajas, 
                      precio_unitario, total_monto, id_usuario))
                
                # 8. REGISTRAR CADA ENTREGA POR SUCURSAL
                ids_entregas = []
                for entrega in entregas_validas:
                    cursor.execute("""
                        INSERT INTO entregas 
                        (ID_Cliente, ID_Sucursal, ID_Producto, Cantidad_Cajas, 
                         Precio_Unitario, Total, Usa_Anticipo, ID_Anticipo, 
                         ID_Usuario, Notas, Fecha_Entrega)
                        VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, NOW())
                    """, (anticipo['ID_Cliente'], entrega['sucursal_id'], anticipo['ID_Producto'], 
                          entrega['cantidad'], precio_unitario, entrega['cantidad'] * precio_unitario, 
                          id_anticipo, id_usuario, notas))
                    
                    id_entrega = cursor.lastrowid
                    ids_entregas.append(id_entrega)
                    
                    # Registrar detalle de cada entrega
                    cursor.execute("""
                        INSERT INTO detalle_entregas 
                        (ID_Entrega, ID_Producto, Cantidad_Cajas, Precio_Unitario, 
                         Total, Usa_Anticipo, ID_Anticipo)
                        VALUES (%s, %s, %s, %s, %s, 1, %s)
                    """, (id_entrega, anticipo['ID_Producto'], entrega['cantidad'], 
                          precio_unitario, entrega['cantidad'] * precio_unitario, id_anticipo))
                
                # 9. ACTUALIZAR EL ANTICIPO
                nuevas_cajas_consumidas = anticipo['Anticipo_Cajas_Consumidas'] + total_cajas
                cajas_restantes = anticipo['Anticipo_Total_Cajas'] - nuevas_cajas_consumidas
                nuevo_saldo_restante = cajas_restantes * precio_unitario
                
                nuevo_estado = 'COMPLETADO' if nuevas_cajas_consumidas >= anticipo['Anticipo_Total_Cajas'] else 'ACTIVO'
                
                cursor.execute("""
                    UPDATE anticipos_clientes 
                    SET Cajas_Consumidas = %s, 
                        Estado = %s,
                        Saldo_Restante = %s
                    WHERE ID_Anticipo = %s
                """, (nuevas_cajas_consumidas, nuevo_estado, nuevo_saldo_restante, id_anticipo))
                
                # 10. ACTUALIZAR DATOS DEL CLIENTE
                nuevas_cajas_consumidas_cliente = anticipo['Cliente_Cajas_Consumidas'] + total_cajas
                nuevo_saldo_anticipos_cliente = float(anticipo['Cliente_Saldo_Anticipos']) - total_monto
                
                anticipo_cliente_completado = nuevas_cajas_consumidas_cliente >= anticipo['Anticipo_Total_Cajas']
                nuevo_anticipo_activo = 0 if anticipo_cliente_completado else 1
                
                cursor.execute("""
                    UPDATE clientes 
                    SET Cajas_Consumidas_Anticipo = %s,
                        Saldo_Anticipos = %s,
                        Anticipo_Activo = %s,
                        Fecha_Ultimo_Movimiento = NOW()
                    WHERE ID_Cliente = %s
                """, (nuevas_cajas_consumidas_cliente, nuevo_saldo_anticipos_cliente, 
                      nuevo_anticipo_activo, anticipo['ID_Cliente']))
                
                # 11. DESCOTAR INVENTARIO DE LA BODEGA
                nuevas_existencias = existencias_actuales - total_cajas
                cursor.execute("""
                    UPDATE inventario_bodega 
                    SET Existencias = %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (nuevas_existencias, id_bodega, anticipo['ID_Producto']))
                
                # 12. Si el anticipo se completó, registrar en bitácora (CORREGIDO)
                if anticipo_cliente_completado:
                    # Obtener la IP del usuario
                    ip_acceso = request.remote_addr or '0.0.0.0'
                    
                    cursor.execute("""
                        INSERT INTO bitacora (ID_Usuario, Modulo, Accion, IP_Acceso, Fecha)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (id_usuario, 
                          'CLIENTES-ANTICIPOS-ENTREGAS', 
                          f'ANTICIPO_COMPLETADO - Cliente: {anticipo["Nombre_Cliente"]} (ID: {anticipo["ID_Cliente"]}) - Total cajas consumidas: {nuevas_cajas_consumidas_cliente} - Anticipo #{id_anticipo}',
                          ip_acceso))
                
                # Commit implícito por el context manager
                
                # Redirigir al ticket con auto-impresión
                flash(f'✅ {len(ids_entregas)} entregas registradas exitosamente!', 'success')
                return redirect(url_for('admin.ticket_entregas', id_anticipo=id_anticipo, autoPrint=1))
                
        except ValueError as e:
            flash(f'❌ Error en el formato de los datos: {str(e)}', 'error')
            return redirect(request.url)
        except Exception as e:
            flash(f'❌ Error al registrar la entrega: {str(e)}', 'error')
            return redirect(request.url)
    
    # Método GET - Mostrar la página con datos
    try:
        with get_db_cursor() as cursor:
            # Obtener ID de la empresa del usuario actual
            cursor.execute("SELECT ID_Empresa FROM usuarios WHERE ID_Usuario = %s", (current_user.id,))
            usuario = cursor.fetchone()
            empresa_id = usuario['ID_Empresa'] if usuario else None
            
            # 1. Obtener anticipos activos disponibles - VERSIÓN CORREGIDA
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.ID_Cliente,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    c.RUC_CEDULA,
                    c.perfil_cliente,
                    c.Saldo_Anticipos as Cliente_Saldo_Anticipos,
                    c.Cajas_Consumidas_Anticipo as Cliente_Cajas_Consumidas,
                    c.Anticipo_Activo,
                    c.Limite_Anticipo_Cajas,
                    a.ID_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    a.Cantidad_Cajas as Total_Cajas_Anticipo,
                    a.Cajas_Consumidas as Cajas_Consumidas_Anticipo,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Disponibles,
                    a.Precio_Unitario,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    DATE_FORMAT(a.Fecha_Anticipo, '%d/%m/%Y') as Fecha_Anticipo_Formato,
                    DATE_FORMAT(a.Fecha_Vencimiento, '%d/%m/%Y') as Fecha_Vencimiento_Formato,
                    DATEDIFF(a.Fecha_Vencimiento, CURDATE()) as Dias_Vencimiento,
                    CASE 
                        WHEN a.Fecha_Vencimiento < NOW() AND a.Estado = 'ACTIVO' THEN 'VENCIDO'
                        WHEN a.Fecha_Vencimiento IS NOT NULL AND a.Fecha_Vencimiento < DATE_ADD(NOW(), INTERVAL 7 DAY) THEN 'PRÓXIMO_A_VENCER'
                        ELSE 'VIGENTE'
                    END as Estado_Vencimiento
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.Estado = 'ACTIVO' 
                  AND (a.Cantidad_Cajas - a.Cajas_Consumidas) > 0
                ORDER BY c.Nombre, a.Fecha_Anticipo ASC
            """)
            anticipos_disponibles = cursor.fetchall()
            
            # 2. Obtener sucursales
            cursor.execute("""
                SELECT s.ID_Sucursal, s.Nombre_Sucursal, s.Direccion, s.Encargado,
                       c.Nombre as Nombre_Cliente, c.ID_Cliente
                FROM sucursales s
                INNER JOIN clientes c ON s.ID_Cliente = c.ID_Cliente
                WHERE s.Estado = 'ACTIVO' AND c.Estado = 'ACTIVO'
                ORDER BY c.Nombre, s.Nombre_Sucursal
            """)
            sucursales = cursor.fetchall()
            
            # 3. Obtener bodegas activas
            if empresa_id:
                cursor.execute("""
                    SELECT ID_Bodega, Nombre, Ubicacion, Estado
                    FROM bodegas
                    WHERE ID_Empresa = %s AND Estado = 'activa'
                    ORDER BY Nombre
                """, (empresa_id,))
            else:
                cursor.execute("""
                    SELECT ID_Bodega, Nombre, Ubicacion, Estado
                    FROM bodegas
                    WHERE Estado = 'activa'
                    ORDER BY Nombre
                """)
            bodegas = cursor.fetchall()
            
            if not bodegas:
                flash('⚠️ No hay bodegas activas configuradas para su empresa', 'warning')
            
            # 4. Obtener historial de entregas
            cursor.execute("""
                SELECT 
                    e.ID_Entrega,
                    DATE_FORMAT(e.Fecha_Entrega, '%d/%m/%Y %H:%i') as Fecha_Entrega_Formato,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono as Cliente_Telefono,
                    p.Descripcion as Nombre_Producto,
                    e.Cantidad_Cajas,
                    e.Precio_Unitario,
                    e.Total,
                    s.Nombre_Sucursal,
                    e.Notas,
                    e.Usa_Anticipo,
                    a.ID_Anticipo,
                    a.Saldo_Restante as Saldo_Restante_Anticipo,
                    u.NombreUsuario,
                    c.Saldo_Anticipos as Cliente_Saldo_Actual
                FROM entregas e
                INNER JOIN clientes c ON e.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON e.ID_Producto = p.ID_Producto
                INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                LEFT JOIN anticipos_clientes a ON e.ID_Anticipo = a.ID_Anticipo
                LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                WHERE e.Usa_Anticipo = 1
                ORDER BY e.Fecha_Entrega DESC
                LIMIT 50
            """)
            entregas_recientes = cursor.fetchall()
            
            # 5. Estadísticas
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT e.ID_Entrega) as Total_Entregas_Hoy,
                    COALESCE(SUM(e.Total), 0) as Monto_Total_Entregado_Hoy,
                    COUNT(DISTINCT a.ID_Anticipo) as Anticipos_Activos,
                    COALESCE(SUM(a.Cantidad_Cajas - a.Cajas_Consumidas), 0) as Cajas_Disponibles_Total,
                    COUNT(DISTINCT c.ID_Cliente) as Clientes_Con_Anticipos,
                    COALESCE(SUM(c.Saldo_Anticipos), 0) as Saldo_Total_Anticipos
                FROM entregas e
                RIGHT JOIN anticipos_clientes a ON e.ID_Anticipo = a.ID_Anticipo AND DATE(e.Fecha_Entrega) = CURDATE()
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                WHERE a.Estado = 'ACTIVO'
            """)
            estadisticas = cursor.fetchone()
            
            # Si estadisticas es None, inicializar con ceros
            if not estadisticas:
                estadisticas = {
                    'Total_Entregas_Hoy': 0,
                    'Monto_Total_Entregado_Hoy': 0,
                    'Anticipos_Activos': 0,
                    'Cajas_Disponibles_Total': 0,
                    'Clientes_Con_Anticipos': 0,
                    'Saldo_Total_Anticipos': 0
                }
            
            # 6. Anticipos casi agotados
            cursor.execute("""
                SELECT 
                    c.ID_Cliente,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    a.ID_Anticipo,
                    p.Descripcion as Nombre_Producto,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Restantes,
                    a.Precio_Unitario,
                    a.Saldo_Restante,
                    c.perfil_cliente
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.Estado = 'ACTIVO'
                  AND (a.Cantidad_Cajas - a.Cajas_Consumidas) <= 5
                  AND (a.Cantidad_Cajas - a.Cajas_Consumidas) > 0
                ORDER BY Cajas_Restantes ASC
                LIMIT 10
            """)
            anticipos_bajos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/anticipos_entregas.html',
                                 anticipos=anticipos_disponibles,
                                 sucursales=sucursales,
                                 bodegas=bodegas,
                                 entregas=entregas_recientes,
                                 estadisticas=estadisticas,
                                 anticipos_bajos=anticipos_bajos)
                                 
    except Exception as e:
        flash(f'❌ Error al cargar los datos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/ventas/anticipos/entregas/ticket/<int:id_anticipo>')
@admin_required
def ticket_entregas(id_anticipo):
    """Generar ticket SOLO con las entregas del día actual"""
    try:
        from datetime import datetime
        
        with get_db_cursor(True) as cursor:
            # Obtener información del anticipo y cliente
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.ID_Cliente,
                    a.ID_Producto,
                    a.Cantidad_Cajas as Total_Cajas_Anticipo,
                    a.Cajas_Consumidas as Cajas_Consumidas,
                    a.Precio_Unitario,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    a.Fecha_Anticipo,
                    a.Notas as Anticipo_Notas,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    c.Direccion as Direccion_Cliente,
                    c.RUC_CEDULA,
                    c.perfil_cliente,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Anticipo = %s
            """, (id_anticipo,))
            anticipo = cursor.fetchone()
            
            if not anticipo:
                flash('Anticipo no encontrado', 'error')
                return redirect(url_for('admin.admin_anticipo_entregas'))
            
            # Obtener SOLO las entregas de HOY
            cursor.execute("""
                SELECT 
                    e.ID_Entrega,
                    e.Cantidad_Cajas,
                    e.Fecha_Entrega,
                    e.Notas,
                    s.Nombre_Sucursal,
                    s.Direccion as Direccion_Sucursal,
                    u.NombreUsuario as Registrado_Por,
                    DATE_FORMAT(e.Fecha_Entrega, '%%d/%%m/%%Y') as Fecha_Entrega_Formato,
                    DATE_FORMAT(e.Fecha_Entrega, '%%H:%%i') as Hora_Entrega
                FROM entregas e
                INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                WHERE e.ID_Anticipo = %s AND DATE(e.Fecha_Entrega) = CURDATE()
                ORDER BY e.Fecha_Entrega ASC
            """, (id_anticipo,))
            entregas_hoy = cursor.fetchall()
            
            if not entregas_hoy:
                flash('No hay entregas registradas hoy para este anticipo', 'warning')
                return redirect(url_for('admin.admin_anticipo_entregas'))
            
            # Agrupar entregas por fecha (para el detalle)
            entregas_por_fecha = {}
            for e in entregas_hoy:
                fecha = e['Fecha_Entrega_Formato']
                if fecha not in entregas_por_fecha:
                    entregas_por_fecha[fecha] = []
                entregas_por_fecha[fecha].append(e)
            
            # Consolidar por sucursal
            sucursales_consolidadas = {}
            for e in entregas_hoy:
                nombre_sucursal = e['Nombre_Sucursal']
                if nombre_sucursal not in sucursales_consolidadas:
                    sucursales_consolidadas[nombre_sucursal] = {
                        'nombre': nombre_sucursal,
                        'total': 0
                    }
                sucursales_consolidadas[nombre_sucursal]['total'] += e['Cantidad_Cajas']
            
            sucursales_consolidadas = sorted(sucursales_consolidadas.values(), key=lambda x: x['nombre'])
            
            total_cajas_hoy = sum(e['Cantidad_Cajas'] for e in entregas_hoy)
            cajas_pendientes = anticipo['Total_Cajas_Anticipo'] - anticipo['Cajas_Consumidas']
            
            # Obtener bodega
            bodega_nombre = None
            cursor.execute("""
                SELECT b.Nombre
                FROM movimientos_inventario m
                INNER JOIN bodegas b ON m.ID_Bodega = b.ID_Bodega
                WHERE m.Observacion LIKE %s AND DATE(m.Fecha_Creacion) = CURDATE()
                LIMIT 1
            """, (f'%Anticipo #{id_anticipo}%',))
            bodega = cursor.fetchone()
            if bodega:
                bodega_nombre = bodega['Nombre']
            
            # Datos de la empresa
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, RUC, Direccion, Telefono
                FROM empresa
                LIMIT 1
            """)
            empresa = cursor.fetchone()
            
            # Notas combinadas
            notas_entregas = ' | '.join([e['Notas'] for e in entregas_hoy if e['Notas']]) if entregas_hoy else None
            
            return render_template('admin/ventas/anticipos/ticket_entregas.html',
                                 anticipo=anticipo,
                                 entregas=entregas_hoy,
                                 entregas_por_fecha=entregas_por_fecha,
                                 sucursales_consolidadas=sucursales_consolidadas,
                                 total_cajas_rango=total_cajas_hoy,
                                 cajas_pendientes=cajas_pendientes,
                                 empresa=empresa,
                                 bodega_nombre=bodega_nombre,
                                 notas_entregas=notas_entregas,
                                 titulo_rango=f"Hoy - {datetime.now().strftime('%d/%m/%Y')}",
                                 mostrar_detalle=False,
                                 fecha_actual=datetime.now())
                                 
    except Exception as e:
        flash(f'Error al generar ticket: {str(e)}', 'error')
        return redirect(url_for('admin.admin_anticipo_entregas'))

@admin_bp.route('/ventas/anticipos/proforma')
@admin_required
def proforma_anticipos_lista():
    """Lista de anticipos disponibles para ver proforma"""
    try:
        with get_db_cursor(True) as cursor:
            # Obtener todos los anticipos (activos, completados, cancelados)
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.Cantidad_Cajas as Total_Cajas,
                    a.Cajas_Consumidas,
                    (a.Cantidad_Cajas - a.Cajas_Consumidas) as Cajas_Pendientes,
                    a.Fecha_Anticipo,
                    a.Estado,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    p.Descripcion as Nombre_Producto,
                    DATE_FORMAT(a.Fecha_Anticipo, '%d/%m/%Y') as Fecha_Formato
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                ORDER BY a.Fecha_Anticipo DESC
            """)
            anticipos = cursor.fetchall()
            
            return render_template('admin/ventas/anticipos/proforma_lista.html',
                                 anticipos=anticipos,
                                 fecha_actual=datetime.now())
                                 
    except Exception as e:
        flash(f'Error al cargar anticipos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_anticipo_entregas'))

@admin_bp.route('/ventas/anticipos/proforma/api/<int:id_anticipo>')
@admin_required
def proforma_anticipo_api(id_anticipo):
    """API para obtener datos de la proforma en formato JSON"""
    try:
        
        # Obtener parámetros del filtro
        filtro = request.args.get('filtro', 'todas')
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        with get_db_cursor(True) as cursor:
            # 1. Obtener información del anticipo y cliente
            cursor.execute("""
                SELECT 
                    a.ID_Anticipo,
                    a.ID_Cliente,
                    a.ID_Producto,
                    a.Cantidad_Cajas as Total_Cajas_Anticipo,
                    a.Cajas_Consumidas as Cajas_Consumidas,
                    a.Precio_Unitario,
                    a.Monto_Pagado,
                    a.Saldo_Restante,
                    a.Fecha_Anticipo,
                    a.Notas as Anticipo_Notas,
                    c.Nombre as Nombre_Cliente,
                    c.Telefono,
                    c.Direccion as Direccion_Cliente,
                    c.RUC_CEDULA,
                    c.perfil_cliente,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto
                FROM anticipos_clientes a
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                INNER JOIN productos p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Anticipo = %s
            """, (id_anticipo,))
            anticipo = cursor.fetchone()
            
            if not anticipo:
                return jsonify({'error': 'Anticipo no encontrado'}), 404
            
            # 2. Determinar fechas según el filtro
            hoy = datetime.now().date()
            titulo_rango = ""
            
            if filtro == 'hoy':
                fecha_inicio = hoy.strftime('%Y-%m-%d')
                fecha_fin = hoy.strftime('%Y-%m-%d')
                titulo_rango = f"Hoy - {hoy.strftime('%d/%m/%Y')}"
            elif filtro == 'rango' and fecha_inicio and fecha_fin:
                fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
                titulo_rango = f"Del {fecha_inicio_obj.strftime('%d/%m/%Y')} al {fecha_fin_obj.strftime('%d/%m/%Y')}"
            else:
                fecha_inicio = None
                fecha_fin = None
                titulo_rango = "Historial Completo"
            
            # 3. Obtener entregas
            if fecha_inicio and fecha_fin:
                cursor.execute("""
                    SELECT 
                        e.ID_Entrega,
                        e.Cantidad_Cajas,
                        e.Fecha_Entrega,
                        e.Notas,
                        s.Nombre_Sucursal,
                        s.Direccion as Direccion_Sucursal,
                        u.NombreUsuario as Registrado_Por,
                        DATE_FORMAT(e.Fecha_Entrega, '%d/%m/%Y') as Fecha_Formato,
                        DATE_FORMAT(e.Fecha_Entrega, '%H:%i') as Hora_Entrega
                    FROM entregas e
                    INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                    LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                    WHERE e.ID_Anticipo = %s 
                      AND DATE(e.Fecha_Entrega) >= %s 
                      AND DATE(e.Fecha_Entrega) <= %s
                    ORDER BY e.Fecha_Entrega ASC
                """, (id_anticipo, fecha_inicio, fecha_fin))
            else:
                cursor.execute("""
                    SELECT 
                        e.ID_Entrega,
                        e.Cantidad_Cajas,
                        e.Fecha_Entrega,
                        e.Notas,
                        s.Nombre_Sucursal,
                        s.Direccion as Direccion_Sucursal,
                        u.NombreUsuario as Registrado_Por,
                        DATE_FORMAT(e.Fecha_Entrega, '%d/%m/%Y') as Fecha_Formato,
                        DATE_FORMAT(e.Fecha_Entrega, '%H:%i') as Hora_Entrega
                    FROM entregas e
                    INNER JOIN sucursales s ON e.ID_Sucursal = s.ID_Sucursal
                    LEFT JOIN usuarios u ON e.ID_Usuario = u.ID_Usuario
                    WHERE e.ID_Anticipo = %s
                    ORDER BY e.Fecha_Entrega ASC
                """, (id_anticipo,))
            
            entregas = cursor.fetchall()
            
            # 4. Calcular totales
            total_cajas_entregadas = sum(e['Cantidad_Cajas'] for e in entregas) if entregas else 0
            cajas_pendientes = anticipo['Total_Cajas_Anticipo'] - anticipo['Cajas_Consumidas']
            
            # 5. Consolidar por sucursal
            sucursales_consolidadas = {}
            for e in entregas:
                nombre = e['Nombre_Sucursal']
                if nombre not in sucursales_consolidadas:
                    sucursales_consolidadas[nombre] = 0
                sucursales_consolidadas[nombre] += e['Cantidad_Cajas']
            
            sucursales_lista = [{'nombre': k, 'total': v} for k, v in sucursales_consolidadas.items()]
            sucursales_lista.sort(key=lambda x: x['nombre'])
            
            # 6. Agrupar entregas por fecha
            entregas_por_fecha = {}
            for e in entregas:
                fecha = e['Fecha_Formato']
                if fecha not in entregas_por_fecha:
                    entregas_por_fecha[fecha] = []
                entregas_por_fecha[fecha].append({
                    'hora': e['Hora_Entrega'],
                    'sucursal': e['Nombre_Sucursal'],
                    'cantidad': e['Cantidad_Cajas']
                })
            
            # 7. Calcular porcentaje
            porcentaje_avance = (anticipo['Cajas_Consumidas'] / anticipo['Total_Cajas_Anticipo'] * 100) if anticipo['Total_Cajas_Anticipo'] > 0 else 0
            
            # 8. Datos de la empresa
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, RUC, Direccion, Telefono
                FROM empresa
                LIMIT 1
            """)
            empresa = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'anticipo': {
                    'id': anticipo['ID_Anticipo'],
                    'cliente': anticipo['Nombre_Cliente'],
                    'ruc': anticipo['RUC_CEDULA'] or 'No registra',
                    'telefono': anticipo['Telefono'] or 'No registra',
                    'direccion': anticipo['Direccion_Cliente'] or 'No registra',
                    'perfil': anticipo['perfil_cliente'],
                    'producto': anticipo['Nombre_Producto'],
                    'codigo': anticipo['COD_Producto'] or 'N/A',
                    'total_contratado': anticipo['Total_Cajas_Anticipo'],
                    'total_entregado': anticipo['Cajas_Consumidas'],
                    'fecha_anticipo': anticipo['Fecha_Anticipo'].strftime('%d/%m/%Y') if anticipo['Fecha_Anticipo'] else 'N/A',
                    'pendiente': cajas_pendientes,
                    'porcentaje': round(porcentaje_avance, 1)
                },
                'entregas': [{
                    'fecha': e['Fecha_Formato'],
                    'hora': e['Hora_Entrega'],
                    'sucursal': e['Nombre_Sucursal'],
                    'direccion': e['Direccion_Sucursal'] or '-',
                    'cantidad': e['Cantidad_Cajas'],
                    'registrado_por': e['Registrado_Por'] or 'Sistema',
                    'notas': e['Notas'] or '-'
                } for e in entregas],
                'sucursales_consolidadas': sucursales_lista,
                'total_cajas': total_cajas_entregadas,
                'total_entregas': len(entregas),
                'titulo_rango': titulo_rango,
                'empresa': {
                    'nombre': empresa['Nombre_Empresa'] if empresa else 'SISTEMA DE VENTAS',
                    'ruc': empresa['RUC'] if empresa else '000-000-000',
                    'direccion': empresa['Direccion'] if empresa else '',
                    'telefono': empresa['Telefono'] if empresa else ''
                },
                'fecha_actual': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# MONITORE DE VENDEDORES
@admin_bp.route('/monitoreo-vendedores')
@admin_required
@bitacora_decorator("MONITOREO-VENDEDORES")
def admin_monitoreo_vendedores():
    """Panel de monitoreo de vendedores - Vista principal y API"""
    try:
        vendedor_id = request.args.get('id', type=int)
        
        # Si es petición API (tiene id)
        if vendedor_id:
            with get_db_cursor(True) as cursor:
                fecha_str = request.args.get('fecha')
                if fecha_str:
                    try:
                        fecha_consulta = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                    except ValueError:
                        return jsonify({
                            'success': False, 
                            'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                        }), 400
                else:
                    fecha_consulta = date.today()
                
                # Obtener asignación activa del vendedor
                cursor.execute("""
                    SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Vehiculo, 
                           r.Nombre_Ruta, r.Descripcion,
                           av.Fecha_Asignacion, av.Hora_Inicio, av.Hora_Fin,
                           v.Placa as VehiculoPlaca
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                    WHERE av.ID_Usuario = %s 
                      AND av.Estado = 'Activa'
                      AND av.Fecha_Asignacion <= %s
                    ORDER BY av.Fecha_Asignacion DESC
                    LIMIT 1
                """, (vendedor_id, fecha_consulta))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    return jsonify({
                        'success': False, 
                        'error': 'El vendedor no tiene una ruta activa asignada en esta fecha'
                    }), 404
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ABONOS EN EFECTIVO (solo de la tabla abonos_detalle)
                cursor.execute("""
                    SELECT COALESCE(SUM(ad.Monto_Aplicado), 0) as total_abonos_efectivo
                    FROM abonos_detalle ad
                    LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE ad.ID_Asignacion = %s 
                      AND DATE(ad.Fecha) = %s
                      AND (mp.Nombre = 'Efectivo' OR mp.Nombre = 'CONTADO' OR ad.ID_MetodoPago IS NULL)
                """, (id_asignacion, fecha_consulta))
                abonos_efectivo = cursor.fetchone()['total_abonos_efectivo']
                abonos_efectivo = float(abonos_efectivo) if abonos_efectivo else 0.0
                
                # Ventas en efectivo
                cursor.execute("""
                    SELECT COALESCE(SUM(mrc.Monto_Efectivo), 0) as total_ventas_efectivo
                    FROM movimientos_ruta_cabecera mrc
                    WHERE mrc.ID_Asignacion = %s 
                      AND DATE(mrc.Fecha_Movimiento) = %s
                      AND mrc.Estado = 'ACTIVO'
                """, (id_asignacion, fecha_consulta))
                ventas_efectivo = cursor.fetchone()['total_ventas_efectivo']
                ventas_efectivo = float(ventas_efectivo) if ventas_efectivo else 0.0
                
                # GASTOS del día (¡NUEVO!)
                cursor.execute("""
                    SELECT COALESCE(SUM(Monto), 0) as total_gastos
                    FROM movimientos_caja_ruta
                    WHERE ID_Asignacion = %s 
                      AND DATE(Fecha) = %s
                      AND Tipo = 'GASTO'
                      AND Estado = 'ACTIVO'
                """, (id_asignacion, fecha_consulta))
                gastos = cursor.fetchone()['total_gastos']
                gastos = float(gastos) if gastos else 0.0
                
                # Total de efectivo en caja = ventas + abonos - gastos
                caja_total = ventas_efectivo + abonos_efectivo - gastos
                
                # LISTA DE ABONOS EN EFECTIVO (para mostrar en la tabla)
                cursor.execute("""
                    SELECT 
                        ad.Monto_Aplicado as monto,
                        ad.Fecha as fecha,
                        c.Nombre as cliente,
                        COALESCE(mp.Nombre, 'Efectivo') as metodo_pago
                    FROM abonos_detalle ad
                    JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                    LEFT JOIN metodos_pago mp ON ad.ID_MetodoPago = mp.ID_MetodoPago
                    WHERE ad.ID_Asignacion = %s 
                      AND DATE(ad.Fecha) = %s
                      AND (mp.Nombre = 'Efectivo' OR mp.Nombre = 'CONTADO' OR ad.ID_MetodoPago IS NULL)
                    ORDER BY ad.Fecha DESC
                """, (id_asignacion, fecha_consulta))
                abonos_hoy = cursor.fetchall()
                
                # LISTA DE GASTOS DEL DÍA (para mostrar)
                cursor.execute("""
                    SELECT 
                        ID_Movimiento,
                        Concepto,
                        Monto,
                        Fecha
                    FROM movimientos_caja_ruta
                    WHERE ID_Asignacion = %s 
                      AND DATE(Fecha) = %s
                      AND Tipo = 'GASTO'
                      AND Estado = 'ACTIVO'
                    ORDER BY Fecha DESC
                """, (id_asignacion, fecha_consulta))
                gastos_hoy = cursor.fetchall()
                
                # Inventario
                cursor.execute("""
                    SELECT ir.ID_Producto, p.Descripcion as NombreProducto, ir.Cantidad, p.Precio_Ruta as PrecioVenta
                    FROM inventario_ruta ir
                    JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    WHERE ir.ID_Asignacion = %s AND ir.Cantidad > 0
                """, (id_asignacion,))
                inventario = cursor.fetchall()
                
                # Facturas pendientes
                cursor.execute("""
                    SELECT fr.ID_FacturaRuta, c.Nombre as NombreCliente, fr.Observacion,
                           COALESCE(SUM(dfr.Cantidad * dfr.Precio), 0) as Total
                    FROM facturacion_ruta fr
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    LEFT JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    WHERE fr.ID_Asignacion = %s 
                      AND fr.Estado = 'Activa' 
                      AND fr.Credito_Contado = 2
                    GROUP BY fr.ID_FacturaRuta, c.Nombre, fr.Observacion
                    HAVING Total > 0
                """, (id_asignacion,))
                facturas_pendientes = cursor.fetchall()
                
                # Resumen
                cursor.execute("""
                    SELECT COUNT(*) as total_facturas,
                           COALESCE(SUM(dfr.Cantidad * dfr.Precio), 0) as total_vendido
                    FROM facturacion_ruta fr
                    JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE fr.ID_Asignacion = %s AND DATE(fr.Fecha) = %s
                """, (id_asignacion, fecha_consulta))
                resumen = cursor.fetchone()
                
                # Info vendedor
                cursor.execute("""
                    SELECT ID_Usuario, NombreUsuario 
                    FROM usuarios 
                    WHERE ID_Usuario = %s
                """, (vendedor_id,))
                vendedor_info = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'vendedor': {
                        'id': vendedor_info['ID_Usuario'], 
                        'nombre': vendedor_info['NombreUsuario']
                    },
                    'fecha_consulta': fecha_consulta.isoformat(),
                    'ruta': {
                        'nombre': asignacion['Nombre_Ruta'] or 'Sin nombre',
                        'vehiculo': asignacion.get('VehiculoPlaca', 'N/A'),
                        'hora_inicio': str(asignacion['Hora_Inicio']) if asignacion['Hora_Inicio'] else None,
                        'hora_fin': str(asignacion['Hora_Fin']) if asignacion['Hora_Fin'] else None
                    },
                    'caja': {
                        'ventas_efectivo': ventas_efectivo,
                        'abonos_efectivo': abonos_efectivo,
                        'gastos': gastos,
                        'total': caja_total
                    },
                    'inventario': [{
                        'nombre': i['NombreProducto'],
                        'cantidad': float(i['Cantidad']),
                        'precio': float(i['PrecioVenta'])
                    } for i in inventario],
                    'facturas_pendientes': [{
                        'cliente': f['NombreCliente'],
                        'total': float(f['Total'])
                    } for f in facturas_pendientes],
                    'abonos_hoy': [{
                        'cliente': a['cliente'],
                        'monto': float(a['monto']),
                        'metodo_pago': a['metodo_pago']
                    } for a in abonos_hoy],
                    'gastos_hoy': [{
                        'concepto': g['Concepto'],
                        'monto': float(g['Monto']),
                        'fecha': g['Fecha'].isoformat() if g['Fecha'] else None
                    } for g in gastos_hoy],
                    'resumen': {
                        'total_facturas': resumen['total_facturas'] or 0,
                        'total_vendido': float(resumen['total_vendido'] or 0),
                        'total_abonos': len(abonos_hoy),
                        'total_abonos_monto': sum(float(a['monto']) for a in abonos_hoy),
                        'total_gastos': gastos,
                        'total_gastos_cantidad': len(gastos_hoy)
                    }
                })
        
        # Cargar página principal
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT u.ID_Usuario, u.NombreUsuario
                FROM usuarios u
                INNER JOIN roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Empresa = %s 
                  AND r.Nombre_Rol = 'Vendedor' 
                  AND u.Estado = 'ACTIVO'
                ORDER BY u.NombreUsuario
            """, (session.get('empresa_id', 1),))
            vendedores = cursor.fetchall()
            
            hoy = date.today().isoformat()
            api_url = url_for('admin.admin_monitoreo_vendedores')
            
            return render_template(
                'admin/ventas/monitoreo/monitore_vendedores.html', 
                vendedores=vendedores, 
                hoy=hoy,
                api_url=api_url
            )
                                   
    except Exception as e:
        if request.args.get('id'):
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

#CUENTAS POR COBRAR
@admin_bp.route('/admin/ventas/cxcobrar/cuentas-por-cobrar')
@admin_required
@bitacora_decorator("CUENTAS-POR-COBRAR")
def admin_cuentascobrar():
    try:
        # Obtener parámetro de filtro de la URL
        filtro_estado = request.args.get('estado', 'pendientes')
        
        # Definir hoy al principio
        hoy = datetime.now().date()
        
        with get_db_cursor(True) as cursor:
            # Construir la consulta base con ambos tipos de documentos
            query = """
                SELECT 
                    c.ID_Movimiento,
                    c.Fecha,
                    cl.Nombre as NombreCliente,
                    cl.Telefono as TelefonoCliente,
                    c.Observacion,
                    c.Fecha_Vencimiento,
                    c.Monto_Movimiento,
                    c.Saldo_Pendiente,
                    c.ID_Factura,
                    c.ID_FacturaRuta,
                    -- Número de documento según el tipo
                    CASE 
                        WHEN c.ID_Factura IS NOT NULL THEN CONCAT('FAC-', LPAD(f.ID_Factura, 5, '0'))
                        WHEN c.ID_FacturaRuta IS NOT NULL THEN CONCAT('RUTA-', LPAD(fr.ID_FacturaRuta, 5, '0'))
                        ELSE 'S/D'
                    END as NumeroDocumento,
                    -- Tipo de documento
                    CASE 
                        WHEN c.ID_Factura IS NOT NULL THEN 'Factura'
                        WHEN c.ID_FacturaRuta IS NOT NULL THEN 'Factura Ruta'
                        ELSE 'Sin documento'
                    END as TipoDocumento,
                    e.Nombre_Empresa,
                    c.Estado as EstadoDB,
                    -- Calcular estado actual basado en saldo y fecha
                    CASE 
                        WHEN c.Saldo_Pendiente = 0 THEN 'Pagado'
                        WHEN c.Fecha_Vencimiento < CURDATE() AND c.Saldo_Pendiente > 0 THEN 'Vencido'
                        WHEN c.Saldo_Pendiente > 0 THEN 'Pendiente'
                        ELSE 'Desconocido'
                    END as EstadoCalculado,
                    DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as DiasVencido,
                    DATEDIFF(c.Fecha_Vencimiento, CURDATE()) as DiasRestantes,
                    -- Información adicional de factura de ruta
                    fr.Credito_Contado,
                    fr.Observacion as ObservacionRuta,
                    fr.Saldo_Anterior_Cliente
                FROM cuentas_por_cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN facturacion f ON c.ID_Factura = f.ID_Factura
                LEFT JOIN facturacion_ruta fr ON c.ID_FacturaRuta = fr.ID_FacturaRuta
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado != 'Anulada'  -- Excluir anuladas siempre
            """
            
            params = []
            
            # Aplicar filtros según el parámetro
            if filtro_estado == 'pagados':
                query += " AND c.Saldo_Pendiente = 0"
            elif filtro_estado == 'vencidos':
                query += " AND c.Fecha_Vencimiento < CURDATE() AND c.Saldo_Pendiente > 0"
            elif filtro_estado == 'pendientes':
                query += " AND c.Saldo_Pendiente > 0 AND c.Estado != 'Pagada'"
            # 'todos' no necesita filtro adicional
            
            # Ordenar según el filtro
            if filtro_estado == 'pendientes':
                query += """
                    ORDER BY 
                        CASE 
                            WHEN c.Fecha_Vencimiento >= CURDATE() THEN 1  -- Pendientes normales
                            WHEN c.Fecha_Vencimiento < CURDATE() THEN 2   -- Vencidas
                            ELSE 3
                        END,
                        c.Fecha_Vencimiento ASC,
                        c.Fecha DESC
                """
            elif filtro_estado == 'vencidos':
                query += """
                    ORDER BY 
                        c.Fecha_Vencimiento ASC,
                        DATEDIFF(CURDATE(), c.Fecha_Vencimiento) DESC
                """
            elif filtro_estado == 'pagados':
                query += """
                    ORDER BY 
                        c.Fecha DESC,
                        c.ID_Movimiento DESC
                """
            else:  # 'todos'
                query += """
                    ORDER BY 
                        CASE 
                            WHEN c.Saldo_Pendiente > 0 AND c.Fecha_Vencimiento >= CURDATE() THEN 1
                            WHEN c.Saldo_Pendiente > 0 AND c.Fecha_Vencimiento < CURDATE() THEN 2
                            WHEN c.Saldo_Pendiente = 0 THEN 3
                            ELSE 4
                        END,
                        c.Fecha_Vencimiento ASC,
                        c.Fecha DESC
                """
            
            cursor.execute(query, params)
            cuentas = cursor.fetchall()
            
            # Calcular totales
            total_pendiente = sum(cuenta['Monto_Movimiento'] for cuenta in cuentas)  # Monto original
            total_saldo = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas)      # Saldo actual
            
            # Calcular estadísticas basadas en datos reales
            cuentas_pagadas = [c for c in cuentas if c['Saldo_Pendiente'] == 0]
            cuentas_vencidas = [c for c in cuentas if c['Fecha_Vencimiento'] and 
                                c['Fecha_Vencimiento'] < hoy and 
                                c['Saldo_Pendiente'] > 0]
            cuentas_pendientes = [c for c in cuentas if c['Saldo_Pendiente'] > 0 and 
                                  c['Fecha_Vencimiento'] and 
                                  c['Fecha_Vencimiento'] >= hoy]
            
            return render_template('admin/ventas/cxcobrar/cuentas_cobrar.html',
                                 cuentas=cuentas,
                                 total_pendiente=total_pendiente,
                                 total_saldo=total_saldo,
                                 hoy=hoy,
                                 filtro_actual=filtro_estado,
                                 total_pagadas=len(cuentas_pagadas),
                                 total_vencidas=len(cuentas_vencidas),
                                 total_pendientes=len(cuentas_pendientes))
    except Exception as e:
        flash(f"Error al cargar cuentas por cobrar: {e}")
        return redirect(url_for('admin.admin_dashboard'))
    
@admin_bp.route('/admin/ventas/cxcobrar/registrar-pago/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("REGISTRAR-PAGO-CXC")
def admin_registrar_pago(id_movimiento):
    if request.method == 'POST':
        try:
            # Convertir el monto del formulario a Decimal
            monto_pago_str = request.form['monto']
            monto_pago = Decimal(monto_pago_str)
            
            id_metodo_pago = request.form['metodo_pago']
            comentarios = request.form.get('comentarios', '')
            detalles_metodo = request.form.get('detalles_metodo', '')
            
            # Obtener el nombre del método de pago para validaciones
            metodo_pago_nombre = ''
            with get_db_cursor(True) as cursor:
                cursor.execute("SELECT Nombre FROM metodos_pago WHERE ID_MetodoPago = %s", (id_metodo_pago,))
                resultado = cursor.fetchone()
                if resultado:
                    metodo_pago_nombre = resultado['Nombre'].upper().strip()
                else:
                    flash("❌ Método de pago no válido")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            # Normalizar nombres para comparación (eliminar acentos y espacios)
            import unicodedata
            def normalize_text(text):
                text = text.upper().strip()
                # Eliminar acentos
                text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
                return text
            
            metodo_normalizado = normalize_text(metodo_pago_nombre)
            
            # Validar detalles según el método de pago
            # EFECTIVO o equivalentes
            if metodo_normalizado in ['EFECTIVO', 'CASH', 'CONTADO', 'EFECTIVO/CONTADO']:
                if detalles_metodo:
                    try:
                        # Extraer cantidad recibida del string
                        import re
                        recibido_match = re.search(r'recibido:\s*([\d,]+(?:\.\d+)?)', detalles_metodo.lower())
                        if recibido_match:
                            # Remover comas y convertir a Decimal
                            recibido_str = recibido_match.group(1).replace(',', '')
                            recibido = Decimal(recibido_str)
                            if recibido < monto_pago:
                                flash("❌ La cantidad recibida no puede ser menor al monto del pago")
                                return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
                    except Exception as e:
                        print(f"Error procesando detalles de efectivo: {e}")
                        # Continuar con el procesamiento aunque haya error en el parseo
            
            # TRANSFERENCIA o DEPÓSITO
            elif metodo_normalizado in ['TRANSFERENCIA', 'DEPOSITO', 'TRANSFERENCIA BANCARIA', 'DEPOSITO BANCARIO', 'TRANSFERENCIA/DEPOSITO']:
                if not detalles_metodo.strip():
                    flash("❌ Para pagos por transferencia/depósito debe proporcionar el número de transacción o referencia")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            # CHEQUE
            elif metodo_normalizado in ['CHEQUE', 'CHEQUES']:
                if not detalles_metodo.strip():
                    flash("❌ Para pagos con cheque debe proporcionar los detalles del cheque (número, banco, etc.)")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            # TARJETA (cualquier tipo)
            elif 'TARJETA' in metodo_normalizado or metodo_normalizado in ['CREDITO', 'DEBITO', 'VISA', 'MASTERCARD']:
                if not detalles_metodo.strip():
                    flash("❌ Para pagos con tarjeta debe proporcionar los detalles de la transacción (autorización, último dígitos, etc.)")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
            
            with get_db_cursor(True) as cursor:
                # Verificar saldo pendiente y datos de la cuenta
                cursor.execute("""
                    SELECT c.Saldo_Pendiente, c.ID_Cliente, c.Monto_Movimiento, 
                           cl.Nombre as NombreCliente, c.Num_Documento,
                           c.ID_Factura, c.Estado
                    FROM cuentas_por_cobrar c
                    LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                    WHERE c.ID_Movimiento = %s
                """, (id_movimiento,))
                resultado = cursor.fetchone()
                
                if not resultado:
                    flash("Cuenta por cobrar no encontrada")
                    return redirect(url_for('admin.admin_cuentascobrar'))
                
                # Verificar si ya está pagada
                if resultado['Estado'] == 'Pagada':
                    flash("❌ Esta cuenta ya ha sido pagada completamente")
                    return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
                # Verificar si está anulada
                if resultado['Estado'] == 'Anulada':
                    flash("❌ No se puede registrar pago en una cuenta anulada")
                    return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
                # Asegurar que saldo_actual sea Decimal
                saldo_actual = Decimal(str(resultado['Saldo_Pendiente']))
                id_cliente = resultado['ID_Cliente']
                
                # Validaciones con Decimal
                if monto_pago <= Decimal('0'):
                    flash("❌ El monto del pago debe ser mayor a cero")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
                
                if monto_pago > saldo_actual:
                    flash(f"❌ El monto del pago (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})")
                    return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
                
                # Registrar pago - convertir a float para la base de datos
                cursor.execute("""
                    INSERT INTO pagos_cuentascobrar 
                    (ID_Movimiento, Monto, ID_MetodoPago, Comentarios, Detalles_Metodo, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_movimiento,
                    float(monto_pago),
                    id_metodo_pago,
                    comentarios,
                    detalles_metodo,
                    current_user.id
                ))
                
                # Obtener el ID del pago recién insertado
                cursor.execute("SELECT LAST_INSERT_ID() as id_pago")
                id_pago = cursor.fetchone()['id_pago']
                print(f"💰 Pago registrado: #{id_pago}")
                
                # Calcular nuevo saldo
                nuevo_saldo = saldo_actual - monto_pago
                
                # Determinar nuevo estado
                if nuevo_saldo == Decimal('0'):
                    nuevo_estado = "Pagada"
                else:
                    # Si hay saldo pendiente, verificar si está vencida
                    cursor.execute("""
                        SELECT Fecha_Vencimiento 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Movimiento = %s
                    """, (id_movimiento,))
                    fecha_vencimiento = cursor.fetchone()['Fecha_Vencimiento']
                    
                    from datetime import date
                    hoy = date.today()
                    
                    if fecha_vencimiento and fecha_vencimiento < hoy:
                        nuevo_estado = "Vencida"
                    else:
                        nuevo_estado = "Pendiente"
                
                # Actualizar saldo pendiente Y estado en la tabla cuentas_por_cobrar
                cursor.execute("""
                    UPDATE cuentas_por_cobrar 
                    SET Saldo_Pendiente = %s,
                        Estado = %s
                    WHERE ID_Movimiento = %s
                """, (float(nuevo_saldo), nuevo_estado, id_movimiento))
                
                # ==============================================
                # ACTUALIZAR SALDO PENDIENTE CONSOLIDADO DEL CLIENTE
                # ==============================================
                # Primero, obtener el saldo pendiente actual del cliente
                cursor.execute("""
                    SELECT Saldo_Pendiente_Total 
                    FROM clientes 
                    WHERE ID_Cliente = %s
                """, (id_cliente,))
                cliente_data = cursor.fetchone()
                
                if cliente_data:
                    saldo_cliente_actual = Decimal(str(cliente_data['Saldo_Pendiente_Total']))
                    nuevo_saldo_cliente = saldo_cliente_actual - monto_pago
                    
                    # Actualizar el saldo pendiente total del cliente
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = %s,
                            Fecha_Ultimo_Pago = NOW()
                        WHERE ID_Cliente = %s
                    """, (float(nuevo_saldo_cliente), id_cliente))
                    
                    print(f"💰 Saldo del cliente #{id_cliente} actualizado: {float(saldo_cliente_actual):,.2f} → {float(nuevo_saldo_cliente):,.2f}")
                    
                    # Verificar si el cliente quedó con saldo cero
                    if nuevo_saldo_cliente == Decimal('0'):
                        print(f"✅ Cliente #{id_cliente} ha cancelado todas sus deudas")
                        flash(f"🎉 ¡Excelente! El cliente {resultado['NombreCliente']} ha cancelado TODAS sus deudas pendientes.")
                else:
                    print(f"⚠️ Cliente #{id_cliente} no encontrado al actualizar saldo pendiente total")
                
                # Verificar si el método de pago es EFECTIVO y registrar en caja
                if metodo_normalizado in ['EFECTIVO', 'CASH', 'CONTADO', 'EFECTIVO/CONTADO']:
                    nombre_cliente = resultado['NombreCliente'] if resultado['NombreCliente'] else f'Cliente ID: {id_cliente}'
                    num_documento = resultado['Num_Documento'] if resultado['Num_Documento'] else f'CXC-{id_movimiento:05d}'
                    
                    cursor.execute("""
                        INSERT INTO caja_movimientos (
                            Fecha, Tipo_Movimiento, Descripcion, Monto, 
                            ID_Pagos_cxc, ID_Usuario, Referencia_Documento
                        )
                        VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                    """, (
                        f'Pago CxC - {nombre_cliente} - Documento: {num_documento} - {comentarios if comentarios else "Pago registrado"}',
                        float(monto_pago),
                        id_pago,
                        current_user.id,
                        f'PAGO-CXC-{id_pago:05d}'
                    ))
                    print(f"💰 Entrada en caja registrada por pago en efectivo: C${float(monto_pago):,.2f}")
                
                # Guardar detalles del método de pago en comentarios adicionales si existe
                if detalles_metodo.strip():
                    cursor.execute("""
                        UPDATE pagos_cuentascobrar 
                        SET Comentarios = CONCAT(COALESCE(Comentarios, ''), 
                            CASE WHEN COALESCE(Comentarios, '') != '' THEN ' | ' ELSE '' END,
                            'Detalles: ', %s)
                        WHERE ID_Pago = %s
                    """, (detalles_metodo[:200], id_pago))
                
                # Mensaje final según el estado
                if nuevo_estado == "Pagada":
                    flash(f"✅ PAGO COMPLETO REGISTRADO. La cuenta ha sido marcada como PAGADA. Monto: C${float(monto_pago):,.2f}")
                    if detalles_metodo:
                        flash(f"📝 Detalles del pago: {detalles_metodo}")
                else:
                    flash(f"✅ Pago de ${float(monto_pago):,.2f} registrado exitosamente. Saldo restante de esta cuenta: C${float(nuevo_saldo):,.2f} - Estado: {nuevo_estado}")
                    if detalles_metodo:
                        flash(f"📝 Detalles del pago: {detalles_metodo}")
                    
                return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
        except ValueError as e:
            flash(f"❌ Error: El monto ingresado no es válido: {e}")
            return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
        except Exception as e:
            flash(f"❌ Error al registrar pago: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return redirect(url_for('admin.admin_registrar_pago', id_movimiento=id_movimiento))
    
    # GET: Cargar datos para el formulario
    try:
        with get_db_cursor(True) as cursor:
            # Datos de la cuenta con estado calculado
            cursor.execute("""
                SELECT 
                    c.*, 
                    cl.Nombre as NombreCliente,
                    cl.Telefono as TelefonoCliente,
                    cl.Direccion as DireccionCliente,
                    cl.RUC_CEDULA,
                    cl.Saldo_Pendiente_Total as Saldo_Total_Cliente,
                    e.Nombre_Empresa
                FROM cuentas_por_cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Movimiento = %s
            """, (id_movimiento,))
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash("Cuenta por cobrar no encontrada")
                return redirect(url_for('admin.admin_cuentascobrar'))
            
            # Verificar si ya está pagada
            if cuenta['Estado'] == 'Pagada' and cuenta['Saldo_Pendiente'] == 0:
                flash("⚠️ Esta cuenta ya está completamente pagada")
                return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
            
            # Verificar si está anulada
            if cuenta['Estado'] == 'Anulada':
                flash("⚠️ Esta cuenta está anulada, no se pueden registrar pagos")
                return redirect(url_for('admin.admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
            
            # Convertir Decimal a float para el template
            if cuenta['Saldo_Pendiente']:
                cuenta['Saldo_Pendiente'] = float(cuenta['Saldo_Pendiente'])
            if cuenta['Monto_Movimiento']:
                cuenta['Monto_Movimiento'] = float(cuenta['Monto_Movimiento'])
            if cuenta.get('Saldo_Total_Cliente'):
                cuenta['Saldo_Total_Cliente'] = float(cuenta['Saldo_Total_Cliente'])
            
            # Métodos de pago disponibles
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
            metodos_pago = cursor.fetchall()
            
            # Pasar la fecha actual para comparar vencimientos
            from datetime import datetime
            today = datetime.now().date()
            
            return render_template('admin/ventas/cxcobrar/registrar_pago.html',
                                 cuenta=cuenta, 
                                 metodos_pago=metodos_pago,
                                 today=today)
                                 
    except Exception as e:
        flash(f"❌ Error al cargar formulario de pago: {e}")
        import traceback
        print(traceback.format_exc())
        return redirect(url_for('admin.admin_cuentascobrar'))

@admin_bp.route('/admin/ventas/cxcobrar/detalle/<int:id_movimiento>')
@admin_required
@bitacora_decorator("DETALLE-CUENTA-COBRAR")
def admin_detalle_cuentacobrar(id_movimiento):
    try:
        with get_db_cursor(True) as cursor:
            # CONSULTA PRINCIPAL - TRAER FECHAS SIN FORMATEAR
            cursor.execute("""
                SELECT 
                    c.ID_Movimiento,
                    c.Fecha,  -- Fecha sin formatear
                    c.ID_Cliente,
                    c.Num_Documento,
                    c.Observacion,
                    c.Fecha_Vencimiento,  -- Fecha sin formatear
                    c.Tipo_Movimiento,
                    c.Monto_Movimiento,
                    c.ID_Empresa,
                    COALESCE(c.Saldo_Pendiente, 0) as Saldo_Pendiente,
                    c.ID_Factura,
                    c.ID_Usuario_Creacion,
                    COALESCE(cl.Nombre, 'Cliente no encontrado') as NombreCliente,
                    COALESCE(cl.RUC_CEDULA, 'N/A') as CedulaCliente,
                    COALESCE(cl.Telefono, 'N/A') as TelefonoCliente,
                    COALESCE(cl.Direccion, 'N/A') as DireccionCliente,
                    COALESCE(e.Nombre_Empresa, 'N/A') as Nombre_Empresa,
                    CASE 
                        WHEN f.ID_Factura IS NOT NULL THEN CONCAT('FAC-', LPAD(f.ID_Factura, 5, '0'))
                        ELSE 'N/A'
                    END as NumeroFactura,
                    f.Fecha as Fecha_Factura,  -- Fecha sin formatear
                    COALESCE(u.NombreUsuario, 'N/A') as UsuarioCreacion,
                    -- Estado de la cuenta
                    CASE 
                        WHEN COALESCE(c.Saldo_Pendiente, 0) = 0 THEN 'Cancelado'
                        WHEN c.Fecha_Vencimiento < CURDATE() AND COALESCE(c.Saldo_Pendiente, 0) > 0 THEN 'Vencido'
                        ELSE 'Pendiente'
                    END as Estado,
                    -- Días vencidos
                    CASE 
                        WHEN c.Fecha_Vencimiento IS NOT NULL 
                             AND c.Fecha_Vencimiento < CURDATE() 
                             AND COALESCE(c.Saldo_Pendiente, 0) > 0 
                        THEN DATEDIFF(CURDATE(), c.Fecha_Vencimiento)
                        ELSE 0
                    END as DiasVencido
                FROM cuentas_por_cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                LEFT JOIN facturacion f ON c.ID_Factura = f.ID_Factura
                LEFT JOIN usuarios u ON c.ID_Usuario_Creacion = u.ID_Usuario
                WHERE c.ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta_raw = cursor.fetchone()
            
            if not cuenta_raw:
                flash("❌ Error: Cuenta por cobrar no encontrada", "error")
                return redirect(url_for('admin.admin_cuentascobrar'))
            
            # FUNCIÓN PARA FORMATEAR FECHAS EN PYTHON (MÁS CONFIABLE)
            def formatear_fecha(fecha_input):
                if fecha_input is None:
                    return 'No especificada'
                
                try:
                    # Si es datetime de MySQL
                    if hasattr(fecha_input, 'strftime'):
                        return fecha_input.strftime('%d/%m/%Y')
                    
                    # Si es string
                    if isinstance(fecha_input, str):
                        # Intentar diferentes formatos
                        formatos = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y']
                        for formato in formatos:
                            try:
                                dt = datetime.strptime(fecha_input, formato)
                                return dt.strftime('%d/%m/%Y')
                            except ValueError:
                                continue
                    
                    # Si no se pudo formatear, devolver como string
                    return str(fecha_input)
                except Exception as e:
                    print(f"Error formateando fecha {fecha_input}: {e}")
                    return 'Formato inválido'
            
            # FUNCIÓN PARA FORMATEAR FECHAS EN FORMATO ISO (YYYY-MM-DD) PARA FORMULARIOS
            def formatear_fecha_iso(fecha_input):
                if fecha_input is None:
                    return ''
                
                try:
                    # Si es datetime de MySQL
                    if hasattr(fecha_input, 'strftime'):
                        return fecha_input.strftime('%Y-%m-%d')
                    
                    # Si es string
                    if isinstance(fecha_input, str):
                        # Intentar diferentes formatos
                        formatos = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%m/%d/%Y']
                        for formato in formatos:
                            try:
                                dt = datetime.strptime(fecha_input, formato)
                                return dt.strftime('%Y-%m-%d')
                            except ValueError:
                                continue
                    
                    # Si no se pudo formatear, devolver vacío
                    return ''
                except Exception as e:
                    print(f"Error formateando fecha ISO {fecha_input}: {e}")
                    return ''
            
            # CONVERTIR A DICCIONARIO Y AGREGAR FECHAS FORMATEADAS
            cuenta = dict(cuenta_raw)
            
            # Agregar campos formateados para display
            cuenta['Fecha_Formateada'] = formatear_fecha(cuenta['Fecha'])
            cuenta['Fecha_Vencimiento_Formateada'] = formatear_fecha(cuenta['Fecha_Vencimiento'])
            cuenta['FechaFactura_Formateada'] = formatear_fecha(cuenta['Fecha_Factura'])
            
            # Agregar campos ISO para formularios HTML (type="date")
            cuenta['Fecha_ISO'] = formatear_fecha_iso(cuenta['Fecha'])
            cuenta['Fecha_Vencimiento_ISO'] = formatear_fecha_iso(cuenta['Fecha_Vencimiento'])
            cuenta['FechaFactura_ISO'] = formatear_fecha_iso(cuenta['Fecha_Factura'])
            
            # DEBUG: Verificar datos
            print("=" * 60)
            print("DEBUG - INFORMACIÓN DE FECHAS:")
            print(f"ID Movimiento: {cuenta['ID_Movimiento']}")
            print(f"Fecha Original (DB): {cuenta['Fecha']} - Tipo: {type(cuenta['Fecha'])}")
            print(f"Fecha Formateada: {cuenta['Fecha_Formateada']}")
            print(f"Fecha Vencimiento Original: {cuenta['Fecha_Vencimiento']}")
            print(f"Fecha Vencimiento Formateada: {cuenta['Fecha_Vencimiento_Formateada']}")
            print(f"Fecha Factura Original: {cuenta['Fecha_Factura']}")
            print(f"Fecha Factura Formateada: {cuenta['FechaFactura_Formateada']}")
            print("=" * 60)
            
            # ==================================================
            # HISTORIAL UNIFICADO (PAGOS + ABONOS)
            # ==================================================
            cursor.execute("""
                SELECT 
                    'pago' as tipo_registro,
                    p.ID_Pago as id_registro,
                    p.ID_Movimiento,
                    p.Monto,
                    p.ID_MetodoPago,
                    p.Comentarios as Descripcion,
                    p.Detalles_Metodo,
                    p.ID_Usuario_Creacion,
                    p.Fecha,
                    COALESCE(mp.Nombre, 'Método no disponible') as MetodoPago,
                    COALESCE(u.NombreUsuario, 'Usuario no disponible') as UsuarioRegistro,
                    NULL as Saldo_Anterior,
                    NULL as Saldo_Nuevo,
                    NULL as ID_Movimiento_Caja,
                    NULL as ID_Asignacion,
                    NULL as ID_Cliente_Abono
                FROM pagos_cuentascobrar p
                LEFT JOIN metodos_pago mp ON p.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
                WHERE p.ID_Movimiento = %s
                
                UNION ALL
                
                SELECT 
                    'abono' as tipo_registro,
                    a.ID_Detalle as id_registro,
                    a.ID_CuentaCobrar as ID_Movimiento,
                    a.Monto_Aplicado as Monto,
                    NULL as ID_MetodoPago,
                    CONCAT('Abono registrado en caja/ruta. ID Mov Caja: ', COALESCE(a.ID_Movimiento_Caja, 0)) as Descripcion,
                    NULL as Detalles_Metodo,
                    a.ID_Usuario as ID_Usuario_Creacion,
                    a.Fecha,
                    'Abono en ruta' as MetodoPago,
                    COALESCE(u2.NombreUsuario, 'Usuario no disponible') as UsuarioRegistro,
                    a.Saldo_Anterior,
                    a.Saldo_Nuevo,
                    a.ID_Movimiento_Caja,
                    a.ID_Asignacion,
                    a.ID_Cliente
                FROM abonos_detalle a
                LEFT JOIN usuarios u2 ON a.ID_Usuario = u2.ID_Usuario
                WHERE a.ID_CuentaCobrar = %s
                
                ORDER BY Fecha DESC
            """, (id_movimiento, id_movimiento))
            
            historial_raw = cursor.fetchall()
            
            # FORMATEAR FECHAS Y PROCESAR HISTORIAL UNIFICADO
            historial = []
            for registro in historial_raw:
                registro_dict = dict(registro)
                fecha_reg = registro_dict['Fecha']
                
                # Formatear fecha
                if fecha_reg:
                    if hasattr(fecha_reg, 'strftime'):
                        registro_dict['FechaFormateada'] = fecha_reg.strftime('%d/%m/%Y %H:%M')
                        registro_dict['FechaSolo'] = fecha_reg.strftime('%d/%m/%Y')
                    else:
                        registro_dict['FechaFormateada'] = formatear_fecha(fecha_reg) + ' 00:00'
                        registro_dict['FechaSolo'] = formatear_fecha(fecha_reg)
                else:
                    registro_dict['FechaFormateada'] = 'Fecha no disponible'
                    registro_dict['FechaSolo'] = 'N/A'
                
                # Configurar tipo de registro para mostrar en template
                if registro_dict['tipo_registro'] == 'abono':
                    registro_dict['TipoDisplay'] = '💵 Abono en ruta'
                    registro_dict['MontoFormateado'] = f"{float(registro_dict['Monto']):,.2f}"
                    registro_dict['Icono'] = 'bi-cash-stack'
                    registro_dict['ColorBadge'] = 'success'
                else:
                    registro_dict['TipoDisplay'] = '💰 Pago registrado'
                    registro_dict['MontoFormateado'] = f"{float(registro_dict['Monto']):,.2f}"
                    registro_dict['Icono'] = 'bi-credit-card'
                    registro_dict['ColorBadge'] = 'primary'
                
                historial.append(registro_dict)
            
            # ==================================================
            # CÁLCULOS FINANCIEROS CON DATOS UNIFICADOS
            # ==================================================
            monto_movimiento = Decimal(str(cuenta['Monto_Movimiento'])) if cuenta['Monto_Movimiento'] else Decimal('0')
            saldo_pendiente = Decimal(str(cuenta['Saldo_Pendiente'])) if cuenta['Saldo_Pendiente'] else Decimal('0')
            
            # Sumar tanto pagos como abonos
            total_pagado = sum(Decimal(str(reg['Monto'])) for reg in historial) if historial else Decimal('0')
            
            # Validar consistencia
            saldo_teorico = monto_movimiento - total_pagado
            diferencia = abs(saldo_pendiente - saldo_teorico)
            tiene_inconsistencia = diferencia > Decimal('0.01')
            
            # Calcular estadísticas
            total_abonado = monto_movimiento - saldo_pendiente
            porcentaje_pagado = (total_abonado / monto_movimiento * 100) if monto_movimiento > 0 else 0
            
            # Obtener primer y último pago/abono
            primer_registro = historial[-1] if historial and len(historial) > 0 else None
            ultimo_registro = historial[0] if historial and len(historial) > 0 else None
            
            # Separar pagos y abonos para estadísticas específicas (opcional)
            solo_pagos = [reg for reg in historial if reg['tipo_registro'] == 'pago']
            solo_abonos = [reg for reg in historial if reg['tipo_registro'] == 'abono']
            
            total_pagos = sum(Decimal(str(reg['Monto'])) for reg in solo_pagos) if solo_pagos else Decimal('0')
            total_abonos = sum(Decimal(str(reg['Monto'])) for reg in solo_abonos) if solo_abonos else Decimal('0')
            
            # Preparar datos para template
            datos_template = {
                'cuenta': cuenta,
                'historial': historial,  # NUEVO: historial unificado
                'pagos': solo_pagos,  # Mantenido por compatibilidad
                'abonos': solo_abonos,  # NUEVO: solo abonos
                'total_pagado': float(total_pagado),
                'total_abonado': float(total_abonado),
                'total_pagos': float(total_pagos),
                'total_abonos': float(total_abonos),
                'porcentaje_pagado': round(float(porcentaje_pagado), 2),
                'tiene_inconsistencia': tiene_inconsistencia,
                'diferencia': float(diferencia),
                'primer_registro': primer_registro,
                'ultimo_registro': ultimo_registro,
                'primer_pago': primer_registro if primer_registro and primer_registro['tipo_registro'] == 'pago' else None,
                'ultimo_pago': ultimo_registro if ultimo_registro and ultimo_registro['tipo_registro'] == 'pago' else None,
                'monto_movimiento_formateado': float(monto_movimiento),
                'saldo_pendiente_formateado': float(saldo_pendiente),
                'saldo_teorico': float(saldo_teorico),
                'cantidad_pagos': len(solo_pagos),
                'cantidad_abonos': len(solo_abonos),
                'cantidad_total_movimientos': len(historial)
            }
            
            return render_template('admin/ventas/cxcobrar/detalle_cuenta.html', **datos_template)
                                 
    except Exception as e:
        flash(f"❌ Error al cargar detalle de cuenta: {str(e)}", "error")
        traceback.print_exc()
        return redirect(url_for('admin.admin_cuentascobrar'))

# PEDIDOS DE VENTA #
# RUTAS PARA PEDIDOS INDIVIDUALES (CLIENTES)
@admin_bp.route('/admin/ventas/nuevo-pedido')
@admin_required
@bitacora_decorator("NUEVO_PEDIDO")
def nuevo_pedido():
    """
    Formulario para crear un nuevo pedido individual
    Los precios se muestran según el perfil del cliente seleccionado
    """
    try:
        cliente_id = request.args.get('cliente')
        
        with get_db_cursor(True) as cursor:
            # Obtener clientes activos con su perfil
            sql_clientes = """
            SELECT 
                ID_Cliente, 
                Nombre, 
                Telefono, 
                Direccion, 
                RUC_CEDULA, 
                tipo_cliente, 
                perfil_cliente,
                ID_Ruta
            FROM clientes 
            WHERE Estado = 'ACTIVO'
            ORDER BY Nombre
            """
            cursor.execute(sql_clientes)
            clientes = cursor.fetchall()
            
            # Obtener empresas
            sql_empresas = "SELECT ID_Empresa, Nombre_Empresa FROM empresa ORDER BY Nombre_Empresa"
            cursor.execute(sql_empresas)
            empresas = cursor.fetchall()
            
            # Obtener perfiles disponibles para mostrar en el selector si es necesario
            perfiles = ['Ruta', 'Mayorista', 'Mercado', 'Especial']
            
            # Si se pasa un cliente específico, obtener sus datos
            cliente_seleccionado = None
            if cliente_id:
                sql_cliente = """
                SELECT 
                    ID_Cliente, 
                    Nombre, 
                    Telefono, 
                    Direccion, 
                    RUC_CEDULA, 
                    tipo_cliente, 
                    perfil_cliente,
                    ID_Ruta
                FROM clientes 
                WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
                """
                cursor.execute(sql_cliente, (cliente_id,))
                cliente_seleccionado = cursor.fetchone()

            # Definir opciones de prioridad
            prioridades = ['Urgente', 'Normal', 'Bajo']
            
            return render_template('admin/ventas/pedidos/nuevo_pedido.html',
                                 clientes=clientes,
                                 empresas=empresas,
                                 cliente_seleccionado=cliente_seleccionado,
                                 prioridades=prioridades,
                                 perfiles=perfiles,
                                 now=datetime.now().date())
            
    except Exception as e:
        flash(f"Error al cargar formulario de pedido: {e}", "error")
        return redirect(url_for('admin.admin_pedidos_venta'))

@admin_bp.route('/admin/ventas/crear-pedido', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PEDIDO")
def crear_pedido():
    """
    Crear un nuevo pedido individual
    Aplica el precio según el perfil_cliente del cliente:
    - perfil_cliente = 'Ruta' → Precio_Ruta
    - perfil_cliente = 'Mayorista' → Precio_Mayorista  
    - perfil_cliente = 'Mercado' → Precio_Mercado
    - perfil_cliente = 'Especial' → Precio_Mercado (por defecto)
    """
    try:
        data = request.get_json()
        user = current_user.id
        
        # Validar datos requeridos
        if not data.get('cliente_id'):
            return jsonify({'success': False, 'message': 'Se requiere un cliente'}), 400
        
        if not data.get('empresa_id'):
            return jsonify({'success': False, 'message': 'Se requiere una empresa'}), 400
        
        if not data.get('productos') or len(data['productos']) == 0:
            return jsonify({'success': False, 'message': 'Se requiere al menos un producto'}), 400
        
        fecha = data.get('fecha')
        tipo_entrega = data.get('tipo_entrega', 'Retiro en local')
        prioridad = data.get('prioridad', 'Normal')
        observacion = data.get('observacion', '')
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente existe y está activo (obtener perfil)
            sql_cliente = """
            SELECT 
                ID_Cliente, 
                tipo_cliente, 
                perfil_cliente 
            FROM clientes 
            WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
            """
            cursor.execute(sql_cliente, (data['cliente_id'],))
            cliente = cursor.fetchone()
            
            if not cliente:
                return jsonify({'success': False, 'message': 'Cliente no encontrado o inactivo'}), 400
            
            perfil_cliente = cliente['perfil_cliente']  # 'Ruta', 'Mayorista', 'Mercado', 'Especial'
            
            # Verificar que la empresa existe
            sql_empresa = "SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s"
            cursor.execute(sql_empresa, (data['empresa_id'],))
            empresa = cursor.fetchone()
            
            if not empresa:
                return jsonify({'success': False, 'message': 'Empresa no encontrada'}), 400
            
            # Crear el pedido
            sql_pedido = """
            INSERT INTO pedidos (
                Fecha, ID_Cliente, ID_Empresa, ID_Usuario_Creacion, 
                Estado, Observacion, Tipo_Entrega, Prioridad
            )
            VALUES (%s, %s, %s, %s, 'Pendiente', %s, %s, %s)
            """
            
            cursor.execute(sql_pedido, (
                fecha,
                data['cliente_id'],
                data['empresa_id'],
                user,
                observacion,
                tipo_entrega,
                prioridad
            ))
            
            pedido_id = cursor.lastrowid
            
            # Agregar productos al detalle del pedido
            for producto in data['productos']:
                # Verificar stock total disponible en inventario_bodega
                sql_stock_total = """
                SELECT COALESCE(SUM(Existencias), 0) as Stock_Total
                FROM inventario_bodega 
                WHERE ID_Producto = %s
                """
                cursor.execute(sql_stock_total, (producto['id'],))
                stock_total_result = cursor.fetchone()
                stock_total = stock_total_result['Stock_Total'] if stock_total_result else 0
                
                if stock_total < producto['cantidad']:
                    return jsonify({
                        'success': False, 
                        'message': f"Stock insuficiente para {producto['nombre']}. Disponible: {stock_total}"
                    }), 400
                
                # Obtener los tres precios del producto
                sql_precio = """
                SELECT 
                    Precio_Mercado,
                    Precio_Mayorista,
                    Precio_Ruta
                FROM productos 
                WHERE ID_Producto = %s AND Estado = 'activo'
                """
                cursor.execute(sql_precio, (producto['id'],))
                producto_info = cursor.fetchone()
                
                if not producto_info:
                    return jsonify({
                        'success': False, 
                        'message': f"Producto ID {producto['id']} no encontrado o inactivo"
                    }), 400
                
                # Determinar qué precio usar según el perfil del cliente
                if perfil_cliente == 'Ruta':
                    precio_unitario = producto_info['Precio_Ruta'] or 0
                elif perfil_cliente == 'Mayorista':
                    precio_unitario = producto_info['Precio_Mayorista'] or 0
                elif perfil_cliente == 'Mercado':
                    precio_unitario = producto_info['Precio_Mercado'] or 0
                elif perfil_cliente == 'Especial':
                    # Para clientes especiales, usamos precio de mercado por defecto
                    # pero podría ser un precio personalizado si se implementa después
                    precio_unitario = producto_info['Precio_Mercado'] or 0
                else:
                    # Por defecto, precio de mercado
                    precio_unitario = producto_info['Precio_Mercado'] or 0
                
                # Validar que el precio sea mayor a 0
                if precio_unitario <= 0:
                    return jsonify({
                        'success': False,
                        'message': f"El producto {producto['nombre']} no tiene precio válido para el perfil {perfil_cliente}"
                    }), 400
                
                # Calcular subtotal
                subtotal = precio_unitario * producto['cantidad']
                
                # Insertar detalle del pedido
                sql_detalle = """
                INSERT INTO detalle_pedidos (
                    ID_Pedido, ID_Producto, Precio_Unitario, 
                    Cantidad, Subtotal
                )
                VALUES (%s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql_detalle, (
                    pedido_id,
                    producto['id'],
                    precio_unitario,
                    producto['cantidad'],
                    subtotal
                ))
                
                # Descontar stock de las bodegas (FIFO)
                cantidad_a_descontar = producto['cantidad']
                
                sql_bodegas_stock = """
                SELECT ID_Bodega, Existencias 
                FROM inventario_bodega 
                WHERE ID_Producto = %s AND Existencias > 0
                ORDER BY ID_Bodega
                """
                cursor.execute(sql_bodegas_stock, (producto['id'],))
                bodegas_stock = cursor.fetchall()
                
                for bodega in bodegas_stock:
                    if cantidad_a_descontar <= 0:
                        break
                    
                    stock_disponible = bodega['Existencias']
                    id_bodega = bodega['ID_Bodega']
                    
                    if stock_disponible >= cantidad_a_descontar:
                        sql_update = """
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                        """
                        cursor.execute(sql_update, (cantidad_a_descontar, id_bodega, producto['id']))
                        cantidad_a_descontar = 0
                    else:
                        sql_update = """
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                        """
                        cursor.execute(sql_update, (stock_disponible, id_bodega, producto['id']))
                        cantidad_a_descontar -= stock_disponible
                
                if cantidad_a_descontar > 0:
                    raise Exception(f"No se pudo descontar todo el stock para el producto {producto['id']}")
            
            # Generar la URL para redirigir al detalle del pedido
            redirect_url = url_for('admin.ver_pedido', id_pedido=pedido_id)
            
            # Log para debugging
            print(f"✅ Pedido #{pedido_id} creado exitosamente con perfil {perfil_cliente}")
            print(f"   Redirigiendo a: {redirect_url}")
            
            return jsonify({
                'success': True, 
                'message': 'Pedido creado exitosamente',
                'pedido_id': pedido_id,
                'redirect_url': redirect_url,
                'perfil_cliente': perfil_cliente
            })
            
    except Exception as e:
        print(f"❌ Error al crear pedido: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# RUTAS PARA PEDIDOS CONSOLIDADOS (RUTAS)
@admin_bp.route('/admin/ventas/nuevo-pedido-consolidado', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("NUEVO_PEDIDO_CONSOLIDADO")
def nuevo_pedido_consolidado():
    """
    Crear un pedido consolidado - Carga total para una ruta específica
    Los consolidados SIEMPRE usan Precio_Ruta de los productos
    Independientemente del perfil del cliente (no aplica porque no hay cliente)
    """
    try:
        if request.method == 'POST':
            data = request.get_json()
            user = current_user.id
            
            # Validar datos requeridos
            if not data.get('empresa_id'):
                return jsonify({'success': False, 'message': 'Se requiere una empresa'}), 400
            
            if not data.get('id_ruta'):
                return jsonify({'success': False, 'message': 'Se requiere una ruta para el pedido consolidado'}), 400
            
            if not data.get('productos') or len(data['productos']) == 0:
                return jsonify({'success': False, 'message': 'Se requiere al menos un producto'}), 400
            
            fecha = data.get('fecha')
            observacion = data.get('observacion', '')
            prioridad = data.get('prioridad', 'Normal')
            id_ruta = data.get('id_ruta')
            
            with get_db_cursor() as cursor:
                # Verificar que la ruta existe y está activa
                cursor.execute("""
                    SELECT ID_Ruta, Nombre_Ruta, Descripcion 
                    FROM rutas 
                    WHERE ID_Ruta = %s AND Estado = 'Activa'
                """, (id_ruta,))
                ruta = cursor.fetchone()
                
                if not ruta:
                    return jsonify({'success': False, 'message': 'Ruta no encontrada o inactiva'}), 400
                
                # Crear el pedido consolidado - SIN CLIENTE, CON RUTA OBLIGATORIA
                sql_pedido = """
                INSERT INTO pedidos (
                    Fecha, ID_Cliente, ID_Empresa, ID_Ruta,
                    ID_Usuario_Creacion, Estado, Observacion, 
                    Tipo_Entrega, Prioridad, Tipo_Pedido, Es_Pedido_Ruta
                )
                VALUES (%s, NULL, %s, %s, %s, 'Pendiente', %s, 'Entrega a domicilio', %s, 'Consolidado', 'SI')
                """
                
                cursor.execute(sql_pedido, (
                    fecha,
                    data['empresa_id'],
                    id_ruta,
                    user,
                    observacion,
                    prioridad
                ))
                
                pedido_id = cursor.lastrowid
                
                # Agregar productos consolidados
                for producto in data['productos']:
                    if producto['cantidad'] <= 0:
                        return jsonify({
                            'success': False, 
                            'message': f"La cantidad para {producto['nombre']} debe ser mayor a 0"
                        }), 400
                    
                    # Verificar que el producto existe y tiene precio de ruta
                    cursor.execute("""
                        SELECT Precio_Ruta 
                        FROM productos 
                        WHERE ID_Producto = %s AND Estado = 'activo'
                    """, (producto['id'],))
                    
                    producto_info = cursor.fetchone()
                    if not producto_info:
                        return jsonify({
                            'success': False,
                            'message': f"Producto {producto['nombre']} no encontrado o inactivo"
                        }), 400
                    
                    if producto_info['Precio_Ruta'] is None or producto_info['Precio_Ruta'] <= 0:
                        return jsonify({
                            'success': False,
                            'message': f"Producto {producto['nombre']} no tiene precio de ruta definido"
                        }), 400
                    
                    # Insertar en pedidos_consolidados_productos
                    sql_consolidado = """
                    INSERT INTO pedidos_consolidados_productos (
                        ID_Pedido, ID_Producto, Cantidad_Total, ID_Usuario_Creacion
                    )
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        Cantidad_Total = Cantidad_Total + VALUES(Cantidad_Total)
                    """
                    
                    cursor.execute(sql_consolidado, (
                        pedido_id,
                        producto['id'],
                        producto['cantidad'],
                        user
                    ))
                
                return jsonify({
                    'success': True,
                    'message': f'Pedido consolidado creado para ruta: {ruta["Nombre_Ruta"]}',
                    'pedido_id': pedido_id,
                    'redirect_url': url_for('admin.ver_pedido', id_pedido=pedido_id)
                })
        
        # GET: Mostrar formulario
        with get_db_cursor(True) as cursor:
            # Obtener empresas
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa 
                FROM empresa 
                ORDER BY Nombre_Empresa
            """)
            empresas = cursor.fetchall()
            
            # Obtener rutas activas
            cursor.execute("""
                SELECT 
                    r.ID_Ruta,
                    r.Nombre_Ruta,
                    r.Descripcion,
                    COUNT(c.ID_Cliente) as Total_clientes
                FROM rutas r
                LEFT JOIN clientes c ON r.ID_Ruta = c.ID_Ruta AND c.Estado = 'ACTIVO'
                WHERE r.Estado = 'Activa'
                GROUP BY r.ID_Ruta, r.Nombre_Ruta, r.Descripcion
                ORDER BY r.Nombre_Ruta
            """)
            rutas = cursor.fetchall()
            
            prioridades = ['Urgente', 'Normal', 'Bajo']
            
            return render_template('admin/ventas/pedidos/nuevo_pedido_consolidado.html',
                                 empresas=empresas,
                                 rutas=rutas,
                                 prioridades=prioridades,
                                 now=datetime.now().date())
            
    except Exception as e:
        print(f"Error en nuevo_pedido_consolidado: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if request.method == 'POST':
            return jsonify({'success': False, 'message': str(e)}), 500
        else:
            flash(f"Error al cargar formulario de pedido consolidado: {e}", "error")
            return redirect(url_for('admin.admin_pedidos_venta'))

@admin_bp.route('/admin/ventas/distribuir-carga/<int:id_pedido>')
@admin_or_bodega_required
def distribuir_carga(id_pedido):
    """
    Muestra el formulario de distribución de carga consolidada a vendedores
    Solo para pedidos consolidados en estado Pendiente
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Pedido,
                    p.Fecha,
                    p.Estado,
                    p.Tipo_Pedido,
                    p.ID_Ruta,
                    r.Nombre_Ruta,
                    e.ID_Empresa
                FROM pedidos p
                LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.ID_Pedido = %s AND p.Tipo_Pedido = 'Consolidado'
            """, (id_pedido,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            if not pedido['ID_Ruta']:
                flash('El pedido no tiene una ruta asignada', 'error')
                return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 2. OBTENER VENDEDORES ACTIVOS DE LA RUTA
            # ============================================
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    u.ID_Usuario,
                    u.NombreUsuario
                FROM asignacion_vendedores av
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE av.ID_Ruta = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                ORDER BY u.NombreUsuario
            """, (pedido['ID_Ruta'],))
            
            vendedores = cursor.fetchall()
            
            # ============================================
            # 3. OBTENER PRODUCTOS DEL CONSOLIDADO
            # ============================================
            cursor.execute("""
                SELECT 
                    pcp.ID_Producto,
                    pcp.Cantidad_Total,
                    pr.Descripcion as Nombre_Producto,
                    pr.COD_Producto,
                    pr.Precio_Ruta as Precio_Venta
                FROM pedidos_consolidados_productos pcp
                INNER JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                WHERE pcp.ID_Pedido = %s
                ORDER BY pr.Descripcion
            """, (id_pedido,))
            
            productos = cursor.fetchall()
            
            return render_template('admin/ventas/pedidos/distribuir_carga.html',
                                 pedido=pedido,
                                 vendedores=vendedores,
                                 productos=productos,
                                 now=datetime.now())
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar datos: {str(e)}', 'error')
        return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))

@admin_bp.route('/admin/ventas/procesar-carga-consolidada/<int:id_pedido>', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("PROCESAR_CARGA_CONSOLIDADA")
def procesar_carga_consolidada(id_pedido):
    """
    Procesa la distribución de carga consolidada a vendedores
    - Crea movimientos de salida de bodega principal
    - Crea movimientos de entrada en rutas de vendedores
    - Actualiza inventario de rutas
    - SOLO CAMBIA EL ESTADO, NO ELIMINA DATOS
    """
    try:
        distribucion = []
        index = 0
        
        while True:
            id_vendedor = request.form.get(f'distribucion[{index}][id_vendedor]')
            id_producto = request.form.get(f'distribucion[{index}][id_producto]')
            cantidad = request.form.get(f'distribucion[{index}][cantidad]')
            
            if id_vendedor is None or id_producto is None or cantidad is None:
                break
                
            if float(cantidad) > 0:
                distribucion.append({
                    'id_vendedor': int(id_vendedor),
                    'id_producto': int(id_producto),
                    'cantidad': float(cantidad)
                })
            index += 1
        
        if not distribucion:
            flash('Debe asignar al menos un producto a un vendedor', 'error')
            return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
        
        with get_db_cursor() as cursor:
            # ============================================
            # 2. VERIFICAR PEDIDO
            # ============================================
            cursor.execute("""
                SELECT 
                    p.ID_Pedido,
                    p.ID_Ruta,
                    p.Estado,
                    r.Nombre_Ruta,
                    e.ID_Empresa,
                    b.ID_Bodega as Bodega_Origen
                FROM pedidos p
                LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN bodegas b ON b.ID_Empresa = e.ID_Empresa AND b.Estado = 'activa'
                WHERE p.ID_Pedido = %s AND p.Tipo_Pedido = 'Consolidado'
                LIMIT 1
            """, (id_pedido,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            if pedido['Estado'] != 'Pendiente':
                flash(f'El pedido debe estar Pendiente, no {pedido["Estado"]}', 'error')
                return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            if not pedido['ID_Ruta']:
                flash('El pedido no tiene una ruta asignada', 'error')
                return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 3. VERIFICAR VENDEDORES
            # ============================================
            vendedores_ids = list(set([item['id_vendedor'] for item in distribucion]))
            placeholders = ','.join(['%s'] * len(vendedores_ids))
            
            query_vendedores = f"""
                SELECT ID_Asignacion, ID_Usuario
                FROM asignacion_vendedores
                WHERE ID_Asignacion IN ({placeholders})
                AND Estado = 'Activa'
                AND Fecha_Asignacion = CURDATE()
            """
            cursor.execute(query_vendedores, vendedores_ids)
            
            vendedores_validos = cursor.fetchall()
            vendedores_dict = {v['ID_Asignacion']: v for v in vendedores_validos}
            
            for item in distribucion:
                if item['id_vendedor'] not in vendedores_dict:
                    flash('Uno o más vendedores no tienen asignación activa hoy', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 4. VERIFICAR PRODUCTOS
            # ============================================
            productos_ids = list(set([item['id_producto'] for item in distribucion]))
            placeholders = ','.join(['%s'] * len(productos_ids))
            
            query_productos = f"""
                SELECT 
                    pcp.ID_Producto,
                    pcp.Cantidad_Total,
                    pr.Precio_Ruta as Precio_Venta,
                    COALESCE(ib.Existencias, 0) as Stock_Disponible
                FROM pedidos_consolidados_productos pcp
                JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                LEFT JOIN inventario_bodega ib ON ib.ID_Bodega = %s AND ib.ID_Producto = pcp.ID_Producto
                WHERE pcp.ID_Pedido = %s
                AND pcp.ID_Producto IN ({placeholders})
            """
            
            params = [pedido['Bodega_Origen'], id_pedido] + productos_ids
            cursor.execute(query_productos, params)
            
            productos_consolidados = cursor.fetchall()
            productos_dict = {}
            
            for p in productos_consolidados:
                productos_dict[p['ID_Producto']] = {
                    'ID_Producto': p['ID_Producto'],
                    'Cantidad_Total': float(p['Cantidad_Total']),
                    'Precio_Venta': float(p['Precio_Venta']),
                    'Stock_Disponible': float(p['Stock_Disponible'])
                }
            
            from collections import defaultdict
            total_por_producto = defaultdict(float)
            
            for item in distribucion:
                total_por_producto[item['id_producto']] += item['cantidad']
            
            for id_producto, cantidad_solicitada in total_por_producto.items():
                if id_producto not in productos_dict:
                    flash('Producto no válido', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
                
                producto = productos_dict[id_producto]
                
                if cantidad_solicitada > producto['Cantidad_Total']:
                    flash(f'Cantidad excede el consolidado', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
                
                if cantidad_solicitada > producto['Stock_Disponible']:
                    flash(f'Stock insuficiente en bodega', 'error')
                    return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
            # ============================================
            # 5. MOVIMIENTO DE SALIDA DE BODEGA PRINCIPAL
            # ============================================
            TRASLADO_SALIDA = 12
            TRASLADO_ENTRADA = 13
            
            cursor.execute("""
                INSERT INTO movimientos_inventario (
                    ID_TipoMovimiento, ID_Bodega, Fecha, Observacion,
                    ID_Empresa, ID_Usuario_Creacion, Estado, ID_Pedido_Origen
                )
                VALUES (%s, %s, CURDATE(), %s, %s, %s, 'Activa', %s)
            """, (
                TRASLADO_SALIDA,
                pedido['Bodega_Origen'],
                f'SALIDA POR CARGA #{id_pedido} - {pedido["Nombre_Ruta"]}',
                pedido['ID_Empresa'],
                current_user.id,
                id_pedido
            ))
            
            movimiento_salida_id = cursor.lastrowid
            
            for id_producto, cantidad_total in total_por_producto.items():
                producto = productos_dict[id_producto]
                
                cursor.execute("""
                    UPDATE inventario_bodega 
                    SET Existencias = Existencias - %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (cantidad_total, pedido['Bodega_Origen'], id_producto))
                
                subtotal = cantidad_total * producto['Precio_Venta']
                
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario (
                        ID_Movimiento, ID_Producto, Cantidad,
                        Costo_Unitario, Precio_Unitario, Subtotal,
                        ID_Usuario_Creacion
                    )
                    VALUES (%s, %s, %s, 0, %s, %s, %s)
                """, (
                    movimiento_salida_id,
                    id_producto,
                    cantidad_total,
                    producto['Precio_Venta'],
                    subtotal,
                    current_user.id
                ))
            
            # ============================================
            # 6. DISTRIBUIR A VENDEDORES
            # ============================================
            distribucion_por_vendedor = defaultdict(list)
            
            for item in distribucion:
                distribucion_por_vendedor[item['id_vendedor']].append({
                    'id_producto': item['id_producto'],
                    'cantidad': item['cantidad'],
                    'precio': productos_dict[item['id_producto']]['Precio_Venta']
                })
            
            for id_vendedor, productos_vendedor in distribucion_por_vendedor.items():
                total_items = sum([p['cantidad'] for p in productos_vendedor])
                total_productos = len(productos_vendedor)
                total_subtotal = sum([p['cantidad'] * p['precio'] for p in productos_vendedor])
                
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera (
                        ID_Asignacion, 
                        ID_TipoMovimiento, 
                        Fecha_Movimiento,
                        ID_Usuario_Registra, 
                        Documento_Numero, 
                        ID_Pedido,
                        Total_Productos, 
                        Total_Items, 
                        Total_Subtotal,
                        ID_Empresa, 
                        Estado
                    )
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_vendedor,
                    TRASLADO_ENTRADA,
                    current_user.id,
                    f'CARGA-{id_pedido}',
                    id_pedido,
                    total_productos,
                    total_items,
                    total_subtotal,
                    pedido['ID_Empresa']
                ))
                
                movimiento_ruta_id = cursor.lastrowid
                
                for producto in productos_vendedor:
                    subtotal = producto['cantidad'] * producto['precio']
                    
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle (
                            ID_Movimiento, 
                            ID_Producto, 
                            Cantidad,
                            Precio_Unitario, 
                            Subtotal
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        movimiento_ruta_id,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['precio'],
                        subtotal
                    ))
                
                for producto in productos_vendedor:
                    cursor.execute("""
                        INSERT INTO inventario_ruta (
                            ID_Asignacion, 
                            ID_Producto, 
                            Cantidad, 
                            Fecha_Actualizacion
                        )
                        VALUES (%s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            Cantidad = Cantidad + VALUES(Cantidad),
                            Fecha_Actualizacion = NOW()
                    """, (
                        id_vendedor,
                        producto['id_producto'],
                        producto['cantidad']
                    ))
            
            # ============================================
            # 7. SOLO CAMBIAR EL ESTADO - NO ELIMINAR NADA
            # ============================================
            # Cambiar el estado del pedido a 'Entregado'
            cursor.execute("""
                UPDATE pedidos 
                SET Estado = 'Entregado'
                WHERE ID_Pedido = %s
            """, (id_pedido,))
            
            # ⚠️ IMPORTANTE: NO se elimina nada de pedidos_consolidados_productos
            # Los datos originales del consolidado permanecen intactos
            
            flash(f'✅ Carga #{id_pedido} procesada exitosamente - Pedido marcado como Entregado', 'success')
            
            return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))

# RUTAS COMUNES (APLICAN A AMBOS TIPOS DE PEDIDOS)
@admin_bp.route('/admin/ventas/pedidos-venta')
@admin_or_bodega_required
@bitacora_decorator("PEDIDOS-VENTA")
def admin_pedidos_venta():
    """
    Listado principal de pedidos (individuales y consolidados)
    Los precios se calculan según:
    - Individuales: usando CASE con perfil_cliente para elegir el precio correcto
    - Consolidados: siempre usan Precio_Ruta
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener el rol del usuario actual
            es_rol_bodega = current_user.rol == 'Bodega'
            
            # CONSULTA QUE USA perfil_cliente PARA ELEGIR EL PRECIO CORRECTO
            sql = """
            SELECT 
                p.ID_Pedido,
                p.Fecha,
                p.Estado,
                p.Tipo_Entrega,
                p.Observacion,
                p.Fecha_Creacion,
                p.Prioridad,
                p.Tipo_Pedido,
                p.Es_Pedido_Ruta,
                p.ID_Ruta,
                r.Nombre_Ruta,
                r.Descripcion as Descripcion_Ruta,
                c.ID_Cliente,
                c.Nombre as Nombre_Cliente,
                c.Telefono as Telefono_Cliente,
                c.Direccion as Direccion_Cliente,
                c.RUC_CEDULA as Documento_Cliente,
                c.tipo_cliente as Tipo_Cliente,
                c.perfil_cliente as Perfil_Cliente,
                c.Estado as Estado_Cliente,
                e.Nombre_Empresa,
                u.NombreUsuario as Usuario_Creacion,
                -- Calcular Total_Items según tipo de pedido
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        SELECT COALESCE(SUM(pcp.Cantidad_Total), 0)
                        FROM pedidos_consolidados_productos pcp
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(dp.Cantidad), 0)
                END as Total_Items,
                -- Calcular Total_Pedido según tipo de pedido y PERFIL DEL CLIENTE
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        -- CONSOLIDADOS: siempre usan Precio_Ruta
                        SELECT COALESCE(SUM(pcp.Cantidad_Total * pr.Precio_Ruta), 0)
                        FROM pedidos_consolidados_productos pcp
                        LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(
                        -- INDIVIDUALES: usan precio según perfil_cliente
                        dp.Cantidad * 
                        CASE c.perfil_cliente
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado  -- Especial usa precio de mercado por defecto
                            ELSE pr.Precio_Mercado
                        END
                    ), 0)
                END as Total_Pedido,
                -- Contador de items
                COUNT(DISTINCT CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN pcp.ID_Pedido_Consolidado_Producto 
                    ELSE dp.ID_Detalle_Pedido 
                END) as Numero_Items
            FROM pedidos p
            LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
            LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
            LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
            LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
            LEFT JOIN detalle_pedidos dp ON p.ID_Pedido = dp.ID_Pedido AND p.Tipo_Pedido != 'Consolidado'
            LEFT JOIN pedidos_consolidados_productos pcp ON p.ID_Pedido = pcp.ID_Pedido AND p.Tipo_Pedido = 'Consolidado'
            LEFT JOIN productos pr ON COALESCE(dp.ID_Producto, pcp.ID_Producto) = pr.ID_Producto
            WHERE 1=1
            """
            
            # Filtro para clientes activos (solo aplica cuando hay cliente)
            sql += " AND (c.ID_Cliente IS NULL OR c.Estado = 'ACTIVO')"
            
            # Si es rol Bodega, filtrar solo pedidos del día actual
            if es_rol_bodega:
                sql += " AND DATE(p.Fecha) = CURDATE()"
            
            # Group by y Order by
            sql += """
            GROUP BY 
                p.ID_Pedido, p.Fecha, p.Estado, p.Tipo_Entrega, p.Observacion,
                p.Fecha_Creacion, p.Prioridad, p.Tipo_Pedido, p.Es_Pedido_Ruta,
                p.ID_Ruta, r.Nombre_Ruta, r.Descripcion,
                c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                c.tipo_cliente, c.perfil_cliente, c.Estado, e.Nombre_Empresa, u.NombreUsuario
            ORDER BY 
                CASE 
                    WHEN p.Prioridad = 'Urgente' THEN 1
                    WHEN p.Prioridad = 'Normal' THEN 2
                    WHEN p.Prioridad = 'Bajo' THEN 3
                    ELSE 4
                END,
                p.Fecha DESC,
                p.ID_Pedido DESC
            """
            
            cursor.execute(sql)
            pedidos = cursor.fetchall()
            
            # Debug - imprimir cantidad de pedidos encontrados
            print(f"📊 Total pedidos encontrados: {len(pedidos)}")
            consolidados = [p for p in pedidos if p.get('Tipo_Pedido') == 'Consolidado']
            print(f"   - Individuales: {len(pedidos) - len(consolidados)}")
            print(f"   - Consolidados: {len(consolidados)}")
            
            # Obtener opciones de filtro
            estados = ['Pendiente', 'Aprobado', 'Entregado', 'Cancelado']
            tipos_entrega = ['Retiro en local', 'Entrega a domicilio']
            tipos_cliente = ['Comun', 'Especial']
            prioridades = ['Urgente', 'Normal', 'Bajo']
            tipos_pedido = ['Individual', 'Consolidado']
            opciones_ruta = ['SI', 'NO']
            perfiles_cliente = ['Ruta', 'Mayorista', 'Mercado', 'Especial']
            
            # Obtener lista de rutas para filtros
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE Estado = 'Activa' 
                ORDER BY Nombre_Ruta
            """)
            rutas = cursor.fetchall()
            
            # Estadísticas para Bodega
            stats = None
            if es_rol_bodega:
                estados.insert(2, 'En Proceso')
                fecha_hoy = datetime.now().strftime('%Y-%m-%d')
                pedidos_hoy = [p for p in pedidos if p.get('Fecha') and p['Fecha'].strftime('%Y-%m-%d') == fecha_hoy]
                urgentes_hoy = [p for p in pedidos_hoy if p.get('Prioridad') == 'Urgente']
                aprobados_hoy = [p for p in pedidos_hoy if p.get('Estado') == 'Aprobado']
                pendientes_hoy = [p for p in pedidos_hoy if p.get('Estado') == 'Pendiente']
                consolidados_hoy = [p for p in pedidos_hoy if p.get('Tipo_Pedido') == 'Consolidado']
                
                stats = {
                    'total_hoy': len(pedidos_hoy),
                    'urgentes_hoy': len(urgentes_hoy),
                    'aprobados_hoy': len(aprobados_hoy),
                    'pendientes_hoy': len(pendientes_hoy),
                    'consolidados_hoy': len(consolidados_hoy),
                    'fecha_hoy': fecha_hoy
                }
            
            return render_template('admin/ventas/pedidos/pedidos_venta.html',
                                 pedidos=pedidos,
                                 estados=estados,
                                 tipos_entrega=tipos_entrega,
                                 tipos_cliente=tipos_cliente,
                                 prioridades=prioridades,
                                 tipos_pedido=tipos_pedido,
                                 opciones_ruta=opciones_ruta,
                                 rutas=rutas,
                                 perfiles_cliente=perfiles_cliente,
                                 es_rol_bodega=es_rol_bodega,
                                 stats=stats,
                                 now=datetime.now())
            
    except Exception as e:
        print(f"❌ Error en admin_pedidos_venta: {str(e)}")
        traceback.print_exc()
        flash(f"Error al cargar pedidos de venta: {str(e)}", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/ventas/pedidos-venta/filtrar', methods=['POST'])
def filtrar_pedidos():
    """
    Filtro avanzado para el listado de pedidos
    Incluye filtro por perfil_cliente
    """
    try:
        estado = request.form.get('estado', 'todos')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        tipo_entrega = request.form.get('tipo_entrega', 'todos')
        tipo_cliente = request.form.get('tipo_cliente', 'todos')
        prioridad = request.form.get('prioridad', 'todos')
        tipo_pedido = request.form.get('tipo_pedido', 'todos')
        es_pedido_ruta = request.form.get('es_pedido_ruta', 'todos')
        id_ruta = request.form.get('id_ruta', 'todos')
        perfil_cliente = request.form.get('perfil_cliente', 'todos')
        documento_cliente = request.form.get('documento_cliente', '').strip()
        nombre_cliente = request.form.get('nombre_cliente', '').strip()
        
        condiciones = ["(c.ID_Cliente IS NULL OR c.Estado = 'ACTIVO')"]
        parametros = []
        
        if estado != 'todos':
            condiciones.append("p.Estado = %s")
            parametros.append(estado)
        
        if fecha_inicio:
            condiciones.append("p.Fecha >= %s")
            parametros.append(fecha_inicio)
        
        if fecha_fin:
            condiciones.append("p.Fecha <= %s")
            parametros.append(fecha_fin)
        
        if tipo_entrega != 'todos':
            condiciones.append("p.Tipo_Entrega = %s")
            parametros.append(tipo_entrega)
        
        if tipo_cliente != 'todos':
            condiciones.append("c.tipo_cliente = %s")
            parametros.append(tipo_cliente)
        
        if perfil_cliente != 'todos':
            condiciones.append("c.perfil_cliente = %s")
            parametros.append(perfil_cliente)
        
        if prioridad != 'todos':
            condiciones.append("p.Prioridad = %s")
            parametros.append(prioridad)
        
        if tipo_pedido != 'todos':
            condiciones.append("p.Tipo_Pedido = %s")
            parametros.append(tipo_pedido)
        
        if es_pedido_ruta != 'todos':
            condiciones.append("p.Es_Pedido_Ruta = %s")
            parametros.append(es_pedido_ruta)
        
        if id_ruta != 'todos':
            condiciones.append("p.ID_Ruta = %s")
            parametros.append(id_ruta)
        
        if documento_cliente:
            condiciones.append("c.RUC_CEDULA LIKE %s")
            parametros.append(f"%{documento_cliente}%")
        
        if nombre_cliente:
            condiciones.append("c.Nombre LIKE %s")
            parametros.append(f"%{nombre_cliente}%")
        
        with get_db_cursor(True) as cursor:
            # Obtener lista de rutas para el select
            cursor.execute("SELECT ID_Ruta, Nombre_Ruta FROM rutas WHERE Estado = 1 ORDER BY Nombre_Ruta")
            rutas = cursor.fetchall()
            
            sql_base = """
            SELECT 
                p.ID_Pedido,
                p.Fecha,
                p.Estado,
                p.Tipo_Entrega,
                p.Observacion,
                p.Fecha_Creacion,
                p.Prioridad,
                p.Tipo_Pedido,
                p.Es_Pedido_Ruta,
                p.ID_Ruta,
                r.Nombre_Ruta,
                c.ID_Cliente,
                c.Nombre as Nombre_Cliente,
                c.Telefono as Telefono_Cliente,
                c.RUC_CEDULA as Documento_Cliente,
                c.tipo_cliente as Tipo_Cliente,
                c.perfil_cliente as Perfil_Cliente,
                e.Nombre_Empresa,
                u.NombreUsuario as Usuario_Creacion,
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        SELECT COALESCE(SUM(pcp.Cantidad_Total), 0)
                        FROM pedidos_consolidados_productos pcp
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(dp.Cantidad), 0)
                END as Total_Items,
                CASE 
                    WHEN p.Tipo_Pedido = 'Consolidado' THEN (
                        -- CONSOLIDADOS: Precio_Ruta
                        SELECT COALESCE(SUM(pcp.Cantidad_Total * pr.Precio_Ruta), 0)
                        FROM pedidos_consolidados_productos pcp
                        JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                        WHERE pcp.ID_Pedido = p.ID_Pedido
                    )
                    ELSE COALESCE(SUM(
                        -- INDIVIDUALES: precio según perfil_cliente
                        dp.Cantidad * 
                        CASE c.perfil_cliente
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END
                    ), 0)
                END as Total_Pedido
            FROM pedidos p
            LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
            LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
            LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
            LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
            LEFT JOIN detalle_pedidos dp ON p.ID_Pedido = dp.ID_Pedido AND p.Tipo_Pedido != 'Consolidado'
            LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
            """
            
            if condiciones:
                sql_base += " WHERE " + " AND ".join(condiciones)
            
            sql_base += """
            GROUP BY p.ID_Pedido, p.Fecha, p.Estado, p.Tipo_Entrega, p.Observacion, 
                     p.Fecha_Creacion, p.Prioridad, p.Tipo_Pedido, p.Es_Pedido_Ruta,
                     p.ID_Ruta, r.Nombre_Ruta, c.ID_Cliente, c.Nombre, c.Telefono, 
                     c.RUC_CEDULA, c.tipo_cliente, c.perfil_cliente, e.Nombre_Empresa, u.NombreUsuario
            ORDER BY 
                CASE p.Prioridad
                    WHEN 'Urgente' THEN 1
                    WHEN 'Normal' THEN 2
                    WHEN 'Bajo' THEN 3
                    ELSE 4
                END,
                p.Fecha DESC, 
                p.ID_Pedido DESC
            """
            
            cursor.execute(sql_base, tuple(parametros))
            pedidos = cursor.fetchall()
            
            estados = ['Pendiente', 'Aprobado', 'Entregado', 'Cancelado']
            tipos_entrega = ['Retiro en local', 'Entrega a domicilio']
            tipos_cliente = ['Comun', 'Especial']
            prioridades = ['Urgente', 'Normal', 'Bajo']
            tipos_pedido = ['Individual', 'Consolidado']
            opciones_ruta = ['SI', 'NO']
            perfiles_cliente = ['Ruta', 'Mayorista', 'Mercado', 'Especial']
            
            return render_template('admin/ventas/pedidos/pedidos_venta.html',
                                 pedidos=pedidos,
                                 estados=estados,
                                 tipos_entrega=tipos_entrega,
                                 tipos_cliente=tipos_cliente,
                                 prioridades=prioridades,
                                 tipos_pedido=tipos_pedido,
                                 opciones_ruta=opciones_ruta,
                                 rutas=rutas,
                                 perfiles_cliente=perfiles_cliente,
                                 filtros_aplicados={
                                     'estado': estado,
                                     'fecha_inicio': fecha_inicio,
                                     'fecha_fin': fecha_fin,
                                     'tipo_entrega': tipo_entrega,
                                     'tipo_cliente': tipo_cliente,
                                     'perfil_cliente': perfil_cliente,
                                     'prioridad': prioridad,
                                     'tipo_pedido': tipo_pedido,
                                     'es_pedido_ruta': es_pedido_ruta,
                                     'id_ruta': id_ruta,
                                     'documento_cliente': documento_cliente,
                                     'nombre_cliente': nombre_cliente
                                 },
                                 now=datetime.now())
            
    except Exception as e:
        flash(f"Error al filtrar pedidos: {e}", "error")
        return redirect(url_for('admin.admin_pedidos_venta'))

@admin_bp.route('/ventas/pedido-venta/<int:id_pedido>')
@admin_or_bodega_required
def ver_pedido(id_pedido):
    """
    Ver detalle completo de un pedido
    - Individuales: muestra el precio según perfil_cliente del cliente
    - Consolidados: siempre muestra Precio_Ruta
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener información del pedido
            sql_pedido = """
            SELECT 
                p.*,
                c.ID_Cliente,
                c.Nombre as Nombre_Cliente,
                c.Telefono as Telefono_Cliente,
                c.Direccion as Direccion_Cliente,
                c.RUC_CEDULA as Documento_Cliente,
                c.tipo_cliente as Tipo_Cliente,
                c.perfil_cliente as Perfil_Cliente,
                c.Estado as Estado_Cliente,
                e.Nombre_Empresa,
                e.Direccion as Direccion_Empresa,
                e.Telefono as Telefono_Empresa,
                e.RUC as RUC_Empresa,
                u.NombreUsuario as Usuario_Creacion,
                r.Nombre_Ruta,
                r.Descripcion as Descripcion_Ruta
            FROM pedidos p
            LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
            LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
            LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
            LEFT JOIN rutas r ON p.ID_Ruta = r.ID_Ruta
            WHERE p.ID_Pedido = %s
            """
            
            cursor.execute(sql_pedido, (id_pedido,))
            pedido = cursor.fetchone()
            
            if not pedido:
                flash("Pedido no encontrado", "error")
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            # Obtener detalles según tipo de pedido
            if pedido['Tipo_Pedido'] == 'Consolidado':
                # PARA CONSOLIDADOS: SIEMPRE usar Precio_Ruta
                cursor.execute("""
                    SELECT 
                        pcp.ID_Pedido_Consolidado_Producto,
                        pcp.ID_Producto,
                        pcp.Cantidad_Total as Cantidad,
                        pcp.Fecha_Creacion,
                        u.NombreUsuario as Usuario_Creacion,
                        pr.COD_Producto,
                        pr.Descripcion as Nombre_Producto,
                        pr.Precio_Ruta as Precio_Unitario,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        pr.Unidad_Medida,
                        um.Descripcion as Unidad_Nombre,
                        um.Abreviatura as Unidad_Abreviatura,
                        cat.Descripcion as Categoria,
                        (pcp.Cantidad_Total * pr.Precio_Ruta) as Subtotal
                    FROM pedidos_consolidados_productos pcp
                    LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                    LEFT JOIN unidades_medida um ON pr.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cat ON pr.ID_Categoria = cat.ID_Categoria
                    LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                    WHERE pcp.ID_Pedido = %s
                    ORDER BY pr.Descripcion
                """, (id_pedido,))
                detalles = cursor.fetchall()
                
                # Calcular totales
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(pcp.Cantidad_Total), 0) as Total_Cantidad,
                        COALESCE(SUM(pcp.Cantidad_Total * pr.Precio_Ruta), 0) as Total_General,
                        COUNT(DISTINCT pcp.ID_Producto) as Total_Productos
                    FROM pedidos_consolidados_productos pcp
                    LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                    WHERE pcp.ID_Pedido = %s
                """, (id_pedido,))
                totales = cursor.fetchone()
                
            else:
                # PARA INDIVIDUALES: usar precio según perfil_cliente
                perfil_cliente = pedido.get('Perfil_Cliente', 'Mercado')
                
                cursor.execute("""
                    SELECT 
                        dp.*,
                        pr.COD_Producto,
                        pr.Descripcion as Nombre_Producto,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        pr.Unidad_Medida,
                        um.Descripcion as Unidad_Nombre,
                        um.Abreviatura as Unidad_Abreviatura,
                        cat.Descripcion as Categoria,
                        -- Mostrar el precio según el perfil del cliente
                        CASE %s
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END as Precio_Segun_Perfil,
                        -- Calcular subtotal según el perfil
                        COALESCE(dp.Subtotal, dp.Cantidad * 
                            CASE %s
                                WHEN 'Ruta' THEN pr.Precio_Ruta
                                WHEN 'Mayorista' THEN pr.Precio_Mayorista
                                WHEN 'Mercado' THEN pr.Precio_Mercado
                                WHEN 'Especial' THEN pr.Precio_Mercado
                                ELSE pr.Precio_Mercado
                            END) as Subtotal
                    FROM detalle_pedidos dp
                    LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
                    LEFT JOIN unidades_medida um ON pr.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cat ON pr.ID_Categoria = cat.ID_Categoria
                    WHERE dp.ID_Pedido = %s
                    ORDER BY dp.ID_Detalle_Pedido
                """, (perfil_cliente, perfil_cliente, id_pedido))
                detalles = cursor.fetchall()
                
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(dp.Cantidad), 0) as Total_Cantidad,
                        COALESCE(SUM(COALESCE(dp.Subtotal, 
                            dp.Cantidad * 
                            CASE %s
                                WHEN 'Ruta' THEN pr.Precio_Ruta
                                WHEN 'Mayorista' THEN pr.Precio_Mayorista
                                WHEN 'Mercado' THEN pr.Precio_Mercado
                                WHEN 'Especial' THEN pr.Precio_Mercado
                                ELSE pr.Precio_Mercado
                            END)), 0) as Total_General,
                        COUNT(DISTINCT dp.ID_Producto) as Total_Productos
                    FROM detalle_pedidos dp
                    LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
                    WHERE dp.ID_Pedido = %s
                """, (perfil_cliente, id_pedido))
                totales = cursor.fetchone()
            
            return render_template('admin/ventas/pedidos/detalle_pedido.html',
                                 pedido=pedido,
                                 detalles=detalles,
                                 totales=totales)
            
    except Exception as e:
        flash(f"Error al cargar el pedido: {str(e)}", "error")
        print(f"Error detallado: {traceback.format_exc()}")
        return redirect(url_for('admin.admin_pedidos_venta'))

@admin_bp.route('/admin/ventas/cambiar-estado/<int:id_pedido>', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("CAMBIAR_ESTADO_PEDIDO")
def cambiar_estado_pedido(id_pedido):
    """
    Cambiar estado de un pedido (Pendiente, Aprobado, Entregado, Cancelado)
    Registra el cambio en historial si la tabla existe
    """
    try:
        data = request.get_json()
        nuevo_estado = data.get('estado')
        
        if nuevo_estado not in ['Pendiente', 'Aprobado', 'Entregado', 'Cancelado']:
            return jsonify({'success': False, 'message': 'Estado inválido'}), 400
        
        with get_db_cursor() as cursor:
            # Verificar que el pedido existe
            cursor.execute("SELECT Estado, Tipo_Pedido FROM pedidos WHERE ID_Pedido = %s", (id_pedido,))
            pedido = cursor.fetchone()
            
            if not pedido:
                return jsonify({'success': False, 'message': 'Pedido no encontrado'}), 404
            
            # Actualizar estado
            sql = """
            UPDATE pedidos 
            SET Estado = %s,
                Fecha_Creacion = CASE 
                    WHEN %s = 'Entregado' THEN CURRENT_TIMESTAMP 
                    ELSE Fecha_Creacion 
                END
            WHERE ID_Pedido = %s
            """
            
            cursor.execute(sql, (nuevo_estado, nuevo_estado, id_pedido))
            
            # Registrar en historial (si existe tabla)
            try:
                cursor.execute("""
                    INSERT INTO pedidos_historial_estados 
                    (ID_Pedido, Estado_Anterior, Estado_Nuevo, ID_Usuario)
                    VALUES (%s, %s, %s, %s)
                """, (id_pedido, pedido['Estado'], nuevo_estado, current_user.id))
            except:
                pass  # La tabla puede no existir
            
            return jsonify({'success': True, 'message': 'Estado actualizado correctamente'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/admin/ventas/cancelar-pedido/<int:pedido_id>', methods=['POST'])
@admin_required
@bitacora_decorator("CANCELAR_PEDIDO")
def cancelar_pedido(pedido_id):
    """
    Cancelar un pedido y devolver el stock a inventario
    Solo aplica para pedidos en estado Pendiente o Aprobado
    """
    try:
        with get_db_cursor() as cursor:
            # Verificar que el pedido existe y está pendiente o aprobado
            sql_verificar = """
            SELECT Estado FROM pedidos 
            WHERE ID_Pedido = %s AND Estado IN ('Pendiente', 'Aprobado')
            """
            cursor.execute(sql_verificar, (pedido_id,))
            pedido = cursor.fetchone()
            
            if not pedido:
                return jsonify({'success': False, 'message': 'Pedido no encontrado o no se puede cancelar'}), 400
            
            # Obtener productos del pedido para devolver al stock
            sql_productos = """
            SELECT dp.ID_Producto, dp.Cantidad 
            FROM detalle_pedidos dp
            WHERE dp.ID_Pedido = %s
            """
            cursor.execute(sql_productos, (pedido_id,))
            productos = cursor.fetchall()
            
            # Devolver stock a las bodegas (se devuelve a la primera bodega disponible)
            for producto in productos:
                # Obtener bodegas de la empresa del pedido
                sql_bodegas = """
                SELECT b.ID_Bodega 
                FROM pedidos p
                JOIN bodegas b ON p.ID_Empresa = b.ID_Empresa
                WHERE p.ID_Pedido = %s AND b.Estado = 'ACTIVO'
                ORDER BY b.ID_Bodega
                LIMIT 1
                """
                cursor.execute(sql_bodegas, (pedido_id,))
                bodega = cursor.fetchone()
                
                if bodega:
                    # Actualizar inventario_bodega
                    sql_update = """
                    INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
                    """
                    cursor.execute(sql_update, (bodega['ID_Bodega'], producto['ID_Producto'], producto['Cantidad']))
            
            # Actualizar estado del pedido
            sql_actualizar = """
            UPDATE pedidos 
            SET Estado = 'Cancelado' 
            WHERE ID_Pedido = %s
            """
            cursor.execute(sql_actualizar, (pedido_id,))
            
            # Registrar en bitácora
            cursor.execute("""
                INSERT INTO bitacora (ID_Usuario, Accion, Descripcion, Fecha)
                VALUES (%s, 'CANCELAR_PEDIDO', %s, NOW())
            """, (session.get('user_id'), f'Pedido #{pedido_id} cancelado'))
            
            return jsonify({
                'success': True, 
                'message': 'Pedido cancelado exitosamente'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/admin/ventas/procesar-pedido/<int:id_pedido>', methods=['GET', 'POST'])
@admin_or_bodega_required
@bitacora_decorator("PROCESAR_VENTA_PEDIDO")
def admin_procesar_venta_pedido(id_pedido):
    """
    Procesar venta desde un pedido aprobado
    Respeta el perfil_cliente para elegir el precio correcto en individuales
    VERSIÓN MEJORADA CON VERIFICACIÓN DE STOCK ROBUSTA
    """
    try:
        # Obtener ID de empresa y usuario desde la sesión
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        if not id_empresa:
            flash('No se pudo determinar la empresa', 'error')
            return redirect(url_for('admin.admin_pedidos_venta'))
        
        if not id_usuario:
            flash('Usuario no autenticado', 'error')
            return redirect(url_for('admin.admin_pedidos_venta'))

        with get_db_cursor(True) as cursor:
            # Obtener información del pedido con perfil_cliente
            cursor.execute("""
                SELECT 
                    p.ID_Pedido,
                    p.Fecha,
                    p.Estado,
                    p.Tipo_Entrega,
                    p.Observacion,
                    p.Prioridad,
                    p.ID_Cliente,
                    p.ID_Empresa,
                    p.Tipo_Pedido,
                    c.Nombre as Nombre_Cliente,
                    c.RUC_CEDULA as Documento_Cliente,
                    c.tipo_cliente as Tipo_Cliente,
                    c.perfil_cliente as Perfil_Cliente,
                    c.Direccion as Direccion_Cliente,
                    c.Telefono as Telefono_Cliente,
                    e.Nombre_Empresa,
                    e.RUC as RUC_Empresa,
                    e.Direccion as Direccion_Empresa,
                    e.Telefono as Telefono_Empresa
                FROM pedidos p
                LEFT JOIN clientes c ON p.ID_Cliente = c.ID_Cliente
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.ID_Pedido = %s
            """, (id_pedido,))
            
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            # Validar que el pedido esté aprobado
            if pedido['Estado'] != 'Aprobado':
                flash('Solo se pueden procesar ventas de pedidos aprobados', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            perfil_cliente = pedido.get('Perfil_Cliente', 'Mercado')
            tipo_pedido = pedido.get('Tipo_Pedido')
            
            # Obtener los detalles del pedido según el tipo
            if tipo_pedido == 'Consolidado':
                # Para consolidados: obtener detalles con Precio_Ruta
                cursor.execute("""
                    SELECT 
                        pcp.ID_Pedido_Consolidado_Producto as ID_Detalle_Pedido,
                        pcp.ID_Producto,
                        pcp.Cantidad_Total as Cantidad,
                        pr.Precio_Ruta as Precio_Unitario,
                        (pcp.Cantidad_Total * pr.Precio_Ruta) as Subtotal,
                        pr.COD_Producto,
                        pr.Descripcion,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        cp.Descripcion as Categoria
                    FROM pedidos_consolidados_productos pcp
                    LEFT JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                    LEFT JOIN categorias_producto cp ON pr.ID_Categoria = cp.ID_Categoria
                    WHERE pcp.ID_Pedido = %s
                    ORDER BY pr.Descripcion
                """, (id_pedido,))
            else:
                # Para individuales: obtener detalles con precio según perfil
                cursor.execute("""
                    SELECT 
                        dp.ID_Detalle_Pedido,
                        dp.ID_Producto,
                        dp.Cantidad,
                        dp.Precio_Unitario,
                        dp.Subtotal,
                        pr.COD_Producto,
                        pr.Descripcion,
                        pr.Precio_Mercado,
                        pr.Precio_Mayorista,
                        pr.Precio_Ruta,
                        cp.Descripcion as Categoria,
                        CASE %s
                            WHEN 'Ruta' THEN pr.Precio_Ruta
                            WHEN 'Mayorista' THEN pr.Precio_Mayorista
                            WHEN 'Mercado' THEN pr.Precio_Mercado
                            WHEN 'Especial' THEN pr.Precio_Mercado
                            ELSE pr.Precio_Mercado
                        END as Precio_Segun_Perfil
                    FROM detalle_pedidos dp
                    LEFT JOIN productos pr ON dp.ID_Producto = pr.ID_Producto
                    LEFT JOIN categorias_producto cp ON pr.ID_Categoria = cp.ID_Categoria
                    WHERE dp.ID_Pedido = %s
                    ORDER BY dp.ID_Detalle_Pedido
                """, (perfil_cliente, id_pedido))
            
            detalles_pedido = cursor.fetchall()
            
            if not detalles_pedido:
                flash('El pedido no tiene productos', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            # Obtener el ID_TipoMovimiento para VENTAS
            cursor.execute("""
                SELECT ID_TipoMovimiento, Descripcion, Letra 
                FROM catalogo_movimientos 
                WHERE Descripcion LIKE '%Venta%' OR Letra = 'S' 
                LIMIT 1
            """)
            tipo_movimiento = cursor.fetchone()
            
            if not tipo_movimiento:
                flash('Error: No se encontró el tipo de movimiento para ventas', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            id_tipo_movimiento = tipo_movimiento['ID_TipoMovimiento']
            
            # Obtener bodega principal
            cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_principal = cursor.fetchone()
            if not bodega_principal:
                flash('Error: No hay bodegas activas en el sistema', 'error')
                return redirect(url_for('admin.admin_pedidos_venta'))
            
            id_bodega_principal = bodega_principal['ID_Bodega']
            
            # ============================================
            # VERIFICACIÓN DE STOCK MEJORADA
            # ============================================
            productos_sin_stock = []
            productos_sin_registro = []
            total_pedido = 0
            total_cajillas_huevos = 0
            ID_CATEGORIA_HUEVOS = 1  # AJUSTAR según tu sistema
            
            print(f"\n📦 INICIANDO VERIFICACIÓN DE STOCK")
            print(f"📦 Bodega: {bodega_principal['Nombre']} (ID: {id_bodega_principal})")
            print("="*60)
            
            for detalle in detalles_pedido:
                id_producto = detalle['ID_Producto']
                cantidad = float(detalle['Cantidad'])
                precio = float(detalle['Precio_Unitario'])
                nombre_producto = detalle.get('Descripcion', f'Producto ID:{id_producto}')
                
                # Verificar si existe registro de inventario y obtener stock
                cursor.execute("""
                    SELECT 
                        COALESCE(Existencias, 0) as Stock,
                        CASE 
                            WHEN ID_Producto IS NOT NULL THEN 1 
                            ELSE 0 
                        END as ExisteRegistro
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega_principal, id_producto))
                
                stock_info = cursor.fetchone()
                
                print(f"\n🔍 Producto: {nombre_producto} (ID:{id_producto})")
                print(f"   Cantidad solicitada: {cantidad}")
                
                if not stock_info or stock_info['ExisteRegistro'] == 0:
                    # No existe registro en inventario_bodega
                    print(f"   ❌ ERROR CRÍTICO: No hay registro de inventario para este producto")
                    productos_sin_registro.append({
                        'producto': nombre_producto,
                        'id_producto': id_producto,
                        'cantidad_solicitada': cantidad,
                        'motivo': 'Producto no registrado en inventario_bodega'
                    })
                    productos_sin_stock.append({
                        'producto': nombre_producto,
                        'stock_actual': 0,
                        'cantidad_solicitada': cantidad,
                        'motivo': 'Sin registro en inventario'
                    })
                else:
                    stock_actual = float(stock_info['Stock'])
                    
                    print(f"   Stock actual en sistema: {stock_actual}")
                    
                    # Comparación con tolerancia para decimales
                    if (stock_actual + 0.001) < cantidad:
                        print(f"   ❌ STOCK INSUFICIENTE!")
                        productos_sin_stock.append({
                            'producto': nombre_producto,
                            'stock_actual': stock_actual,
                            'cantidad_solicitada': cantidad,
                            'motivo': f'Stock insuficiente (disponible: {stock_actual}, necesita: {cantidad})'
                        })
                    else:
                        print(f"   ✅ Stock suficiente")
                
                # Calcular total del pedido
                total_pedido += cantidad * precio
                
                # Verificar si es producto de huevos
                cursor.execute("""
                    SELECT ID_Categoria 
                    FROM productos 
                    WHERE ID_Producto = %s
                """, (id_producto,))
                
                producto_data = cursor.fetchone()
                if producto_data and producto_data['ID_Categoria'] == ID_CATEGORIA_HUEVOS:
                    total_cajillas_huevos += cantidad
            
            print("\n" + "="*60)
            
            # Si hay productos sin stock, mostrar error detallado
            if productos_sin_stock:
                print(f"❌ VERIFICACIÓN DE STOCK FALLIDA")
                print(f"   Total de productos con problemas: {len(productos_sin_stock)}")
                
                # Crear mensaje de error detallado
                error_detalles = []
                for ps in productos_sin_stock:
                    error_detalles.append(f"{ps['producto']}: {ps['motivo']}")
                
                error_msg = f"No se puede procesar el pedido. Problemas de inventario:\n" + "\n".join(error_detalles)
                
                # Si es GET, mostrar en el template
                if request.method == 'GET':
                    return render_template('admin/ventas/pedidos/procesar_pedido.html',
                                        pedido=pedido,
                                        detalles_pedido=detalles_pedido,
                                        productos_sin_stock=productos_sin_stock,
                                        productos_sin_registro=productos_sin_registro,
                                        total_pedido=total_pedido,
                                        total_cajillas_huevos=total_cajillas_huevos,
                                        bodega_principal=bodega_principal,
                                        perfil_cliente=perfil_cliente,
                                        now=datetime.now(),
                                        current_user=current_user,
                                        error_stock=True)
                else:
                    flash(error_msg, 'error')
                    return redirect(url_for('admin.admin_procesar_venta_pedido', id_pedido=id_pedido))
            
            print(f"✅ VERIFICACIÓN DE STOCK EXITOSA")
            print(f"   Total productos: {len(detalles_pedido)}")
            print(f"   Total pedido: C${total_pedido:,.2f}")
            if total_cajillas_huevos > 0:
                print(f"   Cajillas de huevos: {total_cajillas_huevos}")
            print("="*60)
        
        # Si es GET, mostrar formulario de procesamiento
        if request.method == 'GET':
            return render_template('admin/ventas/pedidos/procesar_pedido.html',
                                pedido=pedido,
                                detalles_pedido=detalles_pedido,
                                productos_sin_stock=productos_sin_stock,
                                total_pedido=total_pedido,
                                total_cajillas_huevos=total_cajillas_huevos,
                                bodega_principal=bodega_principal,
                                perfil_cliente=perfil_cliente,
                                now=datetime.now(),
                                current_user=current_user)
        
        # Si es POST, procesar la venta
        if request.method == 'POST':
            print(f"\n📨 PROCESANDO VENTA DESDE PEDIDO #{id_pedido}...")
            print("="*60)
            
            tipo_venta = request.form.get('tipo_venta', 'contado')
            observacion_adicional = request.form.get('observacion_adicional', '')
            
            with get_db_cursor(True) as cursor:
                # VALIDACIÓN DE VISIBILIDAD DE PRODUCTOS
                print("🔍 Validando visibilidad de productos para el cliente...")
                
                # Obtener tipo de cliente
                cursor.execute("""
                    SELECT tipo_cliente 
                    FROM clientes 
                    WHERE ID_Cliente = %s
                """, (pedido['ID_Cliente'],))
                
                cliente_data = cursor.fetchone()
                if not cliente_data:
                    flash('Cliente no encontrado', 'error')
                    return redirect(url_for('admin.admin_pedidos_venta'))
                
                tipo_cliente = cliente_data['tipo_cliente']
                print(f"👤 Tipo de cliente: {tipo_cliente}")
                
                # Validar cada producto contra la visibilidad del cliente
                productos_invalidos = []
                for detalle in detalles_pedido:
                    producto_id = detalle['ID_Producto']
                    
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
                
                # Si hay productos no visibles, mostrar error
                if productos_invalidos:
                    productos_error = ", ".join([f"{p['nombre']} ({p['categoria']})" for p in productos_invalidos])
                    error_msg = f"Los siguientes productos no están disponibles para este cliente ({tipo_cliente}): {productos_error}"
                    print(f"❌ {error_msg}")
                    flash(error_msg, 'error')
                    return redirect(url_for('admin.admin_procesar_venta_pedido', id_pedido=id_pedido))
                
                print("✅ Validación de visibilidad completada")
                
                # VOLVER A VERIFICAR STOCK ANTES DE PROCESAR (por si acaso)
                print("🔍 Verificando stock nuevamente antes de procesar...")
                for detalle in detalles_pedido:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega_principal, id_producto))
                    
                    stock_data = cursor.fetchone()
                    if not stock_data or float(stock_data['Stock']) < cantidad - 0.001:
                        flash(f'Stock insuficiente para {detalle["Descripcion"]}. Por favor, verifique el inventario.', 'error')
                        return redirect(url_for('admin.admin_procesar_venta_pedido', id_pedido=id_pedido))
                
                print("✅ Verificación de stock final exitosa")
                
                # 1. Crear factura
                observacion_completa = f"Pedido #{id_pedido} - {pedido['Observacion'] or 'Sin observación'}"
                if observacion_adicional:
                    observacion_completa += f" | {observacion_adicional}"
                
                cursor.execute("""
                    INSERT INTO facturacion (
                        Fecha, IDCliente, Credito_Contado, Observacion, 
                        ID_Empresa, ID_Usuario_Creacion
                    )
                    VALUES (CURDATE(), %s, %s, %s, %s, %s)
                """, (
                    pedido['ID_Cliente'],
                    1 if tipo_venta == 'credito' else 0,
                    observacion_completa,
                    id_empresa,
                    id_usuario
                ))
                
                # Obtener el ID de la factura
                cursor.execute("SELECT LAST_INSERT_ID() as id_factura")
                id_factura = cursor.fetchone()['id_factura']
                print(f"🧾 Factura creada: #{id_factura}")
                
                # CONSTANTES
                ID_SEPARADOR = 11          # ID_Producto del separador
                ID_BODEGA_EMPAQUE = 1      # Bodega de donde se descuentan separadores
                
                total_venta = 0
                
                # 2. Procesar productos y crear detalles de facturación
                print("\n📝 Procesando productos...")
                for detalle in detalles_pedido:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    precio = float(detalle['Precio_Unitario'])
                    total_linea = cantidad * precio
                    total_venta += total_linea
                    
                    # Insertar detalle de facturación
                    cursor.execute("""
                        INSERT INTO detalle_facturacion (
                            ID_Factura, ID_Producto, Cantidad, Costo, Total
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, id_producto, cantidad, precio, total_linea))
                    
                    # Actualizar inventario del producto
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega_principal, id_producto))
                    
                    # Verificar que la actualización fue exitosa
                    if cursor.rowcount == 0:
                        raise Exception(f"No se pudo actualizar el inventario para el producto {detalle['Descripcion']} (ID: {id_producto})")
                    
                    print(f"  ✅ {detalle['Descripcion']}: {cantidad} x C${precio:,.2f} = C${total_linea:,.2f}")
                
                print(f"\n📊 Total venta: C${total_venta:,.2f}")
                
                # 3. CALCULAR SEPARADORES NECESARIOS
                separadores_totales = 0
                if total_cajillas_huevos > 0:
                    separadores_entre_cajillas = total_cajillas_huevos
                    separadores_base_extra = total_cajillas_huevos // 10
                    separadores_totales = separadores_entre_cajillas + separadores_base_extra
                    
                    print(f"\n🔢 CÁLCULO DE SEPARADORES:")
                    print(f"  Cajillas de huevos: {total_cajillas_huevos}")
                    print(f"  Separadores necesarios: {separadores_totales}")
                
                # 4. DESCONTAR SEPARADORES SI HAY PRODUCTOS DE HUEVOS
                if separadores_totales > 0:
                    print(f"\n🔧 Procesando separadores...")
                    
                    # Verificar stock de separadores
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                    
                    stock_separadores = cursor.fetchone()
                    stock_actual_separadores = float(stock_separadores['Stock']) if stock_separadores else 0
                    
                    if stock_actual_separadores >= separadores_totales:
                        # Restar separadores del inventario
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = Existencias - %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (separadores_totales, ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                        
                        # Registrar separador en detalle de factura (costo 0)
                        cursor.execute("""
                            INSERT INTO detalle_facturacion (
                                ID_Factura, ID_Producto, Cantidad, Costo, Total
                            )
                            VALUES (%s, %s, %s, 0, 0)
                        """, (id_factura, ID_SEPARADOR, separadores_totales))
                        
                        print(f"  ✅ Separadores descontados: {separadores_totales}")
                    else:
                        warning_msg = f'Stock insuficiente de separadores. Necesarios: {separadores_totales}, Disponibles: {stock_actual_separadores}'
                        print(f"  ⚠️ {warning_msg}")
                        observacion_completa += f" | [ADVERTENCIA: {warning_msg}]"
                
                # 5. Actualizar observación de factura si hubo advertencia
                cursor.execute("""
                    UPDATE facturacion 
                    SET Observacion = %s
                    WHERE ID_Factura = %s
                """, (observacion_completa, id_factura))
                
                # 6. Registrar movimiento de inventario (VENTA)
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
                    'CREDITO' if tipo_venta == 'credito' else 'CONTADO',
                    observacion_completa,
                    id_empresa,
                    id_usuario,
                    id_factura
                ))
                
                # Obtener el ID del movimiento de inventario
                cursor.execute("SELECT LAST_INSERT_ID() as id_movimiento")
                id_movimiento = cursor.fetchone()['id_movimiento']
                
                # 7. Insertar detalles del movimiento de inventario
                for detalle in detalles_pedido:
                    id_producto = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    precio = float(detalle['Precio_Unitario'])
                    subtotal = cantidad * precio
                    
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        id_producto,
                        cantidad,
                        precio,
                        precio,
                        subtotal,
                        id_usuario
                    ))
                
                # 8. Insertar detalle del movimiento para el separador
                if separadores_totales > 0:
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, 0, 0, 0, %s)
                    """, (
                        id_movimiento,
                        ID_SEPARADOR,
                        separadores_totales,
                        id_usuario
                    ))
                
                # 9. Si es crédito, crear cuenta por cobrar
                if tipo_venta == 'credito':
                    cursor.execute("""
                        INSERT INTO cuentas_por_cobrar (
                            Fecha, ID_Cliente, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                            ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion
                        )
                        VALUES (CURDATE(), %s, %s, %s, DATE_ADD(CURDATE(), INTERVAL 30 DAY), 
                                1, %s, %s, %s, %s, %s)
                    """, (
                        pedido['ID_Cliente'],
                        f'FAC-{id_factura:05d}',
                        observacion_completa,
                        total_venta,
                        id_empresa,
                        total_venta,
                        id_factura,
                        id_usuario
                    ))
                    print(f"💰 Cuenta por cobrar creada: FAC-{id_factura:05d}")
                
                # 10. Si es CONTADO, registrar entrada en caja
                if tipo_venta == 'contado':
                    cursor.execute("""
                        INSERT INTO caja_movimientos (
                            Fecha, Tipo_Movimiento, Descripcion, Monto, 
                            ID_Factura, ID_Usuario, Referencia_Documento
                        )
                        VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                    """, (
                        f'Venta desde pedido #{id_pedido} - Factura #{id_factura} - Cliente: {pedido["Nombre_Cliente"]}',
                        total_venta,
                        id_factura,
                        id_usuario,
                        f'FAC-{id_factura:05d}'
                    ))
                    print(f"💰 Movimiento de caja registrado: C${total_venta:,.2f}")
                
                # 11. Actualizar el estado del pedido a "Entregado"
                cursor.execute("""
                    UPDATE pedidos 
                    SET Estado = 'Entregado'
                    WHERE ID_Pedido = %s
                """, (id_pedido,))
                
                print(f"\n✅ Pedido #{id_pedido} actualizado a estado: Entregado")
                
                # 12. Guardar datos de la venta en la sesión para mostrarlos en el ticket
                session['venta_procesada'] = {
                    'id_factura': id_factura,
                    'id_pedido': id_pedido,
                    'total_venta': total_venta,
                    'tipo_venta': tipo_venta,
                    'nombre_cliente': pedido['Nombre_Cliente'],
                    'fecha': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                }
                
                print("="*60)
                print(f"🎯 Venta procesada exitosamente!")
                print(f"   Factura: #{id_factura}")
                print(f"   Total: C${total_venta:,.2f}")
                print("="*60)
                
                # 13. Redirigir directamente al ticket
                return redirect(url_for('admin.admin_generar_ticket', id_factura=id_factura))
                
    except Exception as e:
        error_msg = f'❌ Error al procesar venta desde pedido: {str(e)}'
        print(f"\n{error_msg}")
        import traceback
        print(f"Traceback completo:")
        print(traceback.format_exc())
        
        flash(error_msg, 'error')
        return redirect(url_for('admin.admin_pedidos_venta'))

# API ENDPOINTS (DATOS PARA AJAX)
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

# API ESPECÍFICAS PARA CONSOLIDADOS
@admin_bp.route('/api/rutas/<int:id_ruta>/vendedores-activos')
@login_required
def api_vendedores_activos(id_ruta):
    """
    API para obtener vendedores activos de una ruta en la fecha actual
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    u.ID_Usuario,
                    u.NombreUsuario
                FROM asignacion_vendedores av
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE av.ID_Ruta = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                ORDER BY u.NombreUsuario
            """, (id_ruta,))
            
            vendedores = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': vendedores
            })
    except Exception as e:
        print(f"Error API vendedores: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'data': []
        }), 500

@admin_bp.route('/api/pedidos/<int:id_pedido>/productos-consolidados')
@login_required
def api_productos_consolidados(id_pedido):
    """
    API para obtener productos de un pedido consolidado
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    pcp.ID_Producto,
                    pcp.Cantidad_Total,
                    pr.Descripcion as Nombre_Producto,
                    pr.COD_Producto,
                    pr.Precio_Mercado as Precio_Venta
                FROM pedidos_consolidados_productos pcp
                INNER JOIN productos pr ON pcp.ID_Producto = pr.ID_Producto
                WHERE pcp.ID_Pedido = %s
                ORDER BY pr.Descripcion
            """, (id_pedido,))
            
            productos = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': productos
            })
    except Exception as e:
        print(f"Error API productos: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'data': []
        }), 500

## ASIGNACION RUTAS
@admin_bp.route('/admin/catalogos/rutas/asignacion')
@admin_required
def admin_asignacion_rutas():
    """Vista principal para gestionar asignaciones de rutas"""
    try:
        empresa_id = session.get('id_empresa', 1)

        if not empresa_id:
            flash('No se ha identificado la empresa', 'error')
            return redirect(url_for('admin.admin_dashboard'))
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener asignaciones activas
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    u.ID_Usuario,
                    u.NombreUsuario AS Vendedor,
                    r.Nombre_Ruta,
                    r.ID_Ruta,
                    v.ID_Vehiculo,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    CONCAT(v.Placa, ' - ', v.Marca, ' ', v.Modelo) AS Vehiculo_Completo,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado AS Estado_Asignacion,
                    ua.NombreUsuario AS Asignado_Por,
                    rol.Nombre_Rol AS Rol_Vendedor,
                    a.Hora_Inicio,
                    a.Hora_Fin,
                    a.ID_Usuario_Asigna
                FROM asignacion_vendedores a
                LEFT JOIN usuarios u ON a.ID_Usuario = u.ID_Usuario
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios ua ON a.ID_Usuario_Asigna = ua.ID_Usuario
                WHERE a.ID_Empresa = %s
                ORDER BY a.Fecha_Asignacion DESC, a.Estado
                LIMIT 10
            """, (empresa_id,))
            asignaciones_raw = cursor.fetchall()
            
            # Verificar el tipo de datos devuelto
            print(f"DEBUG: Tipo de asignaciones_raw: {type(asignaciones_raw)}")
            if asignaciones_raw:
                print(f"DEBUG: Primer elemento tipo: {type(asignaciones_raw[0])}")
                print(f"DEBUG: Claves del primer elemento (si es dict): {list(asignaciones_raw[0].keys()) if isinstance(asignaciones_raw[0], dict) else 'No es dict'}")
            
            # Procesar asignaciones para formatear correctamente
            asignaciones = []
            for asignacion in asignaciones_raw:
                # Crear una copia del diccionario si ya es un diccionario
                if isinstance(asignacion, dict):
                    asignacion_dict = asignacion.copy()
                else:
                    # Si es una tupla, convertir a diccionario
                    asignacion_dict = {}
                    for i, col in enumerate(cursor.description):
                        col_name = col[0]
                        value = asignacion[i]
                        asignacion_dict[col_name] = value
                
                # Formatear fechas
                if asignacion_dict.get('Fecha_Asignacion'):
                    fecha_val = asignacion_dict['Fecha_Asignacion']
                    if isinstance(fecha_val, (datetime, date)):
                        asignacion_dict['Fecha_Asignacion_fmt'] = fecha_val.strftime('%d/%m/%Y')
                    else:
                        # Convertir a string y tomar los primeros 10 caracteres
                        fecha_str = str(fecha_val)
                        asignacion_dict['Fecha_Asignacion_fmt'] = fecha_str[:10] if len(fecha_str) >= 10 else fecha_str
                else:
                    asignacion_dict['Fecha_Asignacion_fmt'] = None
                
                if asignacion_dict.get('Fecha_Finalizacion'):
                    fecha_val = asignacion_dict['Fecha_Finalizacion']
                    if isinstance(fecha_val, (datetime, date)):
                        asignacion_dict['Fecha_Finalizacion_fmt'] = fecha_val.strftime('%d/%m/%Y')
                    else:
                        # Convertir a string y tomar los primeros 10 caracteres
                        fecha_str = str(fecha_val)
                        asignacion_dict['Fecha_Finalizacion_fmt'] = fecha_str[:10] if len(fecha_str) >= 10 else fecha_str
                else:
                    asignacion_dict['Fecha_Finalizacion_fmt'] = None
                
                # Formatear horas
                if asignacion_dict.get('Hora_Inicio'):
                    hora_val = asignacion_dict['Hora_Inicio']
                    if isinstance(hora_val, timedelta):
                        total_seconds = int(hora_val.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        asignacion_dict['Hora_Inicio_fmt'] = f"{hours:02d}:{minutes:02d}"
                    elif isinstance(hora_val, time):
                        asignacion_dict['Hora_Inicio_fmt'] = hora_val.strftime('%H:%M')
                    else:
                        # Si es string, extraer solo la parte de tiempo
                        hora_str = str(hora_val)
                        if ':' in hora_str:
                            asignacion_dict['Hora_Inicio_fmt'] = hora_str[:5]
                        else:
                            asignacion_dict['Hora_Inicio_fmt'] = hora_str
                else:
                    asignacion_dict['Hora_Inicio_fmt'] = None
                
                if asignacion_dict.get('Hora_Fin'):
                    hora_val = asignacion_dict['Hora_Fin']
                    if isinstance(hora_val, timedelta):
                        total_seconds = int(hora_val.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        asignacion_dict['Hora_Fin_fmt'] = f"{hours:02d}:{minutes:02d}"
                    elif isinstance(hora_val, time):
                        asignacion_dict['Hora_Fin_fmt'] = hora_val.strftime('%H:%M')
                    else:
                        # Si es string, extraer solo la parte de tiempo
                        hora_str = str(hora_val)
                        if ':' in hora_str:
                            asignacion_dict['Hora_Fin_fmt'] = hora_str[:5]
                        else:
                            asignacion_dict['Hora_Fin_fmt'] = hora_str
                else:
                    asignacion_dict['Hora_Fin_fmt'] = None
                
                asignaciones.append(asignacion_dict)
            
            # Obtener vendedores disponibles
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND u.Estado = 'ACTIVO'
                AND rol.Nombre_Rol LIKE '%%Vendedor%%'
                AND NOT EXISTS (
                    SELECT 1 
                    FROM asignacion_vendedores av
                    WHERE av.ID_Usuario = u.ID_Usuario 
                    AND av.Estado = 'Activa'
                    AND av.ID_Empresa = %s
                )
                ORDER BY u.NombreUsuario
            """, (empresa_id, empresa_id))
            
            vendedores = cursor.fetchall()
            
            # Obtener rutas activas
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta
                FROM rutas
                WHERE ID_Empresa = %s AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (empresa_id,))
            rutas = cursor.fetchall()
            
            # Obtener vehículos disponibles
            cursor.execute("""
                SELECT 
                    ID_Vehiculo, 
                    Placa,
                    Marca,
                    Modelo,
                    CONCAT(Placa, ' - ', Marca, ' ', Modelo) AS Descripcion
                FROM vehiculos
                WHERE ID_Empresa = %s 
                AND Estado = 'Disponible'
                AND NOT EXISTS (
                    SELECT 1 
                    FROM asignacion_vendedores av 
                    WHERE av.ID_Vehiculo = vehiculos.ID_Vehiculo 
                    AND av.Estado = 'Activa' 
                    AND av.ID_Empresa = %s
                )
                ORDER BY Placa
            """, (empresa_id, empresa_id))
            vehiculos = cursor.fetchall()
            
            # Obtener usuarios que pueden asignar
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND u.Estado = 'ACTIVO'
                AND rol.Nombre_Rol IN ('Administrador', 'Supervisor', 'ADMINISTRADOR', 'SUPERVISOR')
                ORDER BY u.NombreUsuario
            """, (empresa_id,))
            asignadores = cursor.fetchall()
            
        return render_template(
            'admin/catalog/rutas/asignacion.html',
            asignaciones=asignaciones,
            vendedores=vendedores,
            rutas=rutas,
            vehiculos=vehiculos,
            asignadores=asignadores,
            hoy=datetime.now().strftime('%Y-%m-%d')
        )
        
    except Exception as e:
        flash(f'Error al cargar asignación de rutas: {str(e)}', 'error')
        # Para debugging detallado
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR DETALLADO: {error_details}")
        return redirect(url_for('admin.admin_dashboard'))
    
@admin_bp.route('/admin/catalogos/rutas/asignacion/crear', methods=['POST'])
@admin_required
def crear_asignacion_ruta():
    """Crear nueva asignación de ruta"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        # Obtener datos del formulario
        id_vendedor = request.form.get('id_usuario')
        id_ruta = request.form.get('id_ruta')
        id_vehiculo = request.form.get('id_vehiculo')
        fecha_asignacion = request.form.get('fecha_asignacion')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        id_asignador = current_user.id

        # Validaciones básicas
        if not id_vendedor or id_vendedor == '':
            flash('Debe seleccionar un vendedor', 'error')
            return redirect(url_for('admin.admin_asignacion_rutas'))
            
        if not id_ruta or id_ruta == '':
            flash('Debe seleccionar una ruta', 'error')
            return redirect(url_for('admin.admin_asignacion_rutas'))
            
        if not fecha_asignacion or fecha_asignacion == '':
            flash('Debe seleccionar una fecha', 'error')
            return redirect(url_for('admin.admin_asignacion_rutas'))
        
        # Convertir valores vacíos a None
        if id_vehiculo == '':
            id_vehiculo = None
        if hora_inicio == '':
            hora_inicio = None
        if hora_fin == '':
            hora_fin = None
        
        # Validar que el vendedor no tenga asignación activa en la misma fecha
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT ID_Asignacion 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s 
                AND Fecha_Asignacion = %s 
                AND Estado = 'Activa'
                AND ID_Empresa = %s
            """, (id_vendedor, fecha_asignacion, empresa_id))
            
            if cursor.fetchone():
                flash('El vendedor ya tiene una asignación activa para esta fecha', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
        
        # Crear la asignación en transacción separada
        with get_db_cursor(commit=True) as cursor:
            # Si se asignó vehículo, verificar disponibilidad
            if id_vehiculo:
                cursor.execute("""
                    SELECT Estado FROM vehiculos 
                    WHERE ID_Vehiculo = %s AND ID_Empresa = %s
                """, (id_vehiculo, empresa_id))
                vehiculo = cursor.fetchone()
                
                if not vehiculo or vehiculo['Estado'] != 'Disponible':
                    flash('El vehículo seleccionado no está disponible', 'error')
                    return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Crear la asignación CON NUEVOS CAMPOS
            cursor.execute("""
                INSERT INTO asignacion_vendedores 
                (ID_Usuario, ID_Ruta, ID_Vehiculo, Fecha_Asignacion, 
                 Estado, ID_Empresa, ID_Usuario_Asigna, Hora_Inicio, Hora_Fin)
                VALUES (%s, %s, %s, %s, 'Activa', %s, %s, %s, %s)
            """, (id_vendedor, id_ruta, id_vehiculo, 
                  fecha_asignacion, empresa_id, id_asignador,
                  hora_inicio, hora_fin))
            
            # Si se asignó vehículo, cambiar su estado
            if id_vehiculo:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'En Ruta' 
                    WHERE ID_Vehiculo = %s
                """, (id_vehiculo,))
            
        flash('Asignación creada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al crear asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))

@admin_bp.route('/admin/catalogos/rutas/asignacion/editar/<int:id>')
@admin_required
def editar_asignacion_ruta(id):
    """Vista para editar una asignación existente"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener la asignación específica - YA INCLUYE LOS NUEVOS CAMPOS EN a.*
            cursor.execute("""
                SELECT 
                    a.*,
                    u.ID_Usuario,
                    u.NombreUsuario AS Nombre_Vendedor,
                    r.Nombre_Ruta,
                    r.ID_Ruta,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    v.ID_Vehiculo,
                    rol.Nombre_Rol AS Rol_Vendedor
                FROM asignacion_vendedores a
                LEFT JOIN usuarios u ON a.ID_Usuario = u.ID_Usuario
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                WHERE a.ID_Asignacion = %s AND a.ID_Empresa = %s
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Obtener datos para el formulario
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta
                FROM rutas
                WHERE ID_Empresa = %s AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (empresa_id,))
            rutas = cursor.fetchall()
            
            # Obtener vehículos disponibles + el vehículo actual
            cursor.execute("""
                SELECT 
                    ID_Vehiculo, 
                    Placa,
                    Marca,
                    Modelo,
                    CONCAT(Placa, ' - ', Marca, ' ', Modelo) AS Descripcion,
                    Estado
                FROM vehiculos
                WHERE ID_Empresa = %s 
                AND (Estado = 'Disponible' OR ID_Vehiculo = %s)
                ORDER BY Placa
            """, (empresa_id, asignacion['ID_Vehiculo']))
            vehiculos = cursor.fetchall()
            
            # Obtener usuarios que pueden asignar
            cursor.execute("""
                SELECT 
                    u.ID_Usuario, 
                    u.NombreUsuario AS Nombre,
                    rol.Nombre_Rol AS Rol
                FROM usuarios u
                LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
                WHERE u.ID_Empresa = %s 
                AND rol.Nombre_Rol IN ('Administrador', 'Supervisor', 'ADMINISTRADOR', 'SUPERVISOR')
                AND u.Estado = 'ACTIVO'
                ORDER BY u.NombreUsuario
            """, (empresa_id,))
            asignadores = cursor.fetchall()
            
        return render_template(
            'admin/catalog/rutas/editar_asignacion.html',
            asignacion=asignacion,
            rutas=rutas,
            vehiculos=vehiculos,
            asignadores=asignadores
        )
        
    except Exception as e:
        flash(f'Error al cargar asignación para editar: {str(e)}', 'error')
        return redirect(url_for('admin.admin_asignacion_rutas'))

@admin_bp.route('/admin/catalogos/rutas/asignacion/actualizar/<int:id>', methods=['POST'])
@admin_required
def actualizar_asignacion_ruta(id):
    """Actualizar una asignación existente"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        # Obtener datos del formulario
        id_ruta = request.form.get('id_ruta')
        id_vehiculo = request.form.get('id_vehiculo')
        fecha_asignacion = request.form.get('fecha_asignacion')
        fecha_finalizacion = request.form.get('fecha_finalizacion')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        estado = request.form.get('estado')
        
        if not all([id_ruta, fecha_asignacion, estado]):
            flash('Los campos ruta, fecha y estado son requeridos', 'error')
            return redirect(url_for('admin.editar_asignacion_ruta', id=id))
        
        # Convertir valores vacíos a None
        if hora_inicio == '':
            hora_inicio = None
        if hora_fin == '':
            hora_fin = None
        
        with get_db_cursor(commit=True) as cursor:
            # Obtener asignación actual para comparar vehículo
            cursor.execute("""
                SELECT ID_Vehiculo, Estado 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
            asignacion_actual = cursor.fetchone()
            
            if not asignacion_actual:
                flash('Asignación no encontrada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Manejar cambio de vehículo
            vehiculo_actual = asignacion_actual['ID_Vehiculo']
            nuevo_vehiculo = id_vehiculo if id_vehiculo and id_vehiculo != '' else None
            
            if vehiculo_actual != nuevo_vehiculo:
                # Liberar vehículo anterior si existe
                if vehiculo_actual:
                    cursor.execute("""
                        UPDATE vehiculos 
                        SET Estado = 'Disponible' 
                        WHERE ID_Vehiculo = %s
                    """, (vehiculo_actual,))
                
                # Asignar nuevo vehículo
                if nuevo_vehiculo:
                    # Verificar que el nuevo vehículo esté disponible
                    cursor.execute("""
                        SELECT Estado FROM vehiculos 
                        WHERE ID_Vehiculo = %s AND ID_Empresa = %s
                    """, (nuevo_vehiculo, empresa_id))
                    vehiculo_nuevo = cursor.fetchone()
                    
                    if not vehiculo_nuevo or vehiculo_nuevo['Estado'] != 'Disponible':
                        flash('El vehículo seleccionado no está disponible', 'error')
                        return redirect(url_for('admin.editar_asignacion_ruta', id=id))
                    
                    cursor.execute("""
                        UPDATE vehiculos 
                        SET Estado = 'En Ruta' 
                        WHERE ID_Vehiculo = %s
                    """, (nuevo_vehiculo,))
            
            # Actualizar la asignación CON NUEVOS CAMPOS
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET ID_Ruta = %s,
                    ID_Vehiculo = %s,
                    Fecha_Asignacion = %s,
                    Fecha_Finalizacion = %s,
                    Estado = %s,
                    Hora_Inicio = %s,
                    Hora_Fin = %s
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id_ruta, nuevo_vehiculo, fecha_asignacion, 
                  fecha_finalizacion if fecha_finalizacion and fecha_finalizacion != '' else None, 
                  estado, hora_inicio, hora_fin, id, empresa_id))
            
            # Si se finaliza la asignación, liberar el vehículo si existe
            if estado == 'Finalizada' and nuevo_vehiculo:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (nuevo_vehiculo,))
            
        flash('Asignación actualizada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al actualizar asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))

@admin_bp.route('/admin/catalogos/rutas/asignacion/finalizar/<int:id>')
@admin_required
def finalizar_asignacion_ruta(id):
    """Finalizar una asignación activa"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=True) as cursor:
            # Obtener el vehículo asignado
            cursor.execute("""
                SELECT ID_Vehiculo 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Empresa = %s 
                AND Estado = 'Activa'
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o ya finalizada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Actualizar estado de la asignación CON HORA_FIN
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Estado = 'Finalizada',
                    Fecha_Finalizacion = CURDATE(),
                    Hora_Fin = CURTIME()
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
            # Liberar el vehículo si existe
            if asignacion['ID_Vehiculo']:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (asignacion['ID_Vehiculo'],))
            
        flash('Asignación finalizada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al finalizar asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))

@admin_bp.route('/admin/catalogos/rutas/asignacion/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_asignacion_ruta(id):
    """Eliminar una asignación (solo si está en estado Finalizada o Suspendida)"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar que la asignación exista y no esté activa
            cursor.execute("""
                SELECT ID_Vehiculo, Estado 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Empresa = %s
            """, (id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            if asignacion['Estado'] == 'Activa':
                flash('No se puede eliminar una asignación activa', 'error')
                return redirect(url_for('admin.admin_asignacion_rutas'))
            
            # Liberar vehículo si existe
            if asignacion['ID_Vehiculo']:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (asignacion['ID_Vehiculo'],))
            
            # Eliminar la asignación
            cursor.execute("""
                DELETE FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s AND ID_Empresa = %s
            """, (id, empresa_id))
            
        flash('Asignación eliminada exitosamente', 'success')
            
    except Exception as e:
        flash(f'Error al eliminar asignación: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_asignacion_rutas'))

@admin_bp.route('/api/asignaciones/disponibilidad')
@admin_required
def api_disponibilidad_asignaciones():
    """API para verificar disponibilidad de vendedores y vehículos en una fecha"""
    try:
        empresa_id = session.get('id_empresa')
        fecha = request.args.get('fecha')
        
        if not fecha:
            return jsonify({'error': 'Fecha requerida'}), 400
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener vendedores disponibles en esa fecha - CORREGIDA
            cursor.execute("""
            SELECT 
                u.ID_Usuario, 
                u.NombreUsuario AS Nombre,  -- ← Esto ya es el nombre del usuario
                rol.Nombre_Rol AS Rol
            FROM usuarios u
            LEFT JOIN roles rol ON u.ID_Rol = rol.ID_Rol
            WHERE u.ID_Empresa = %s 
            AND u.Estado = 'ACTIVO'
            AND u.ID_Rol = 4  -- Solo vendedores
            ORDER BY u.NombreUsuario
            """, (empresa_id, empresa_id, fecha, fecha))
            
            vendedores = cursor.fetchall()
            
            # Obtener vehículos disponibles en esa fecha - CORREGIDA
            cursor.execute("""
                SELECT 
                    v.ID_Vehiculo, 
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    CONCAT(v.Placa, ' - ', v.Marca, ' ', v.Modelo) AS Descripcion
                FROM vehiculos v
                WHERE v.ID_Empresa = %s 
                AND v.Estado = 'Disponible'
                AND v.ID_Vehiculo NOT IN (
                    SELECT ID_Vehiculo 
                    FROM asignacion_vendedores 
                    WHERE Fecha_Asignacion = %s 
                    AND Estado = 'Activa'
                    AND ID_Empresa = %s
                )
                ORDER BY v.Placa
            """, (empresa_id, fecha, empresa_id))
            
            vehiculos = cursor.fetchall()
            
        return jsonify({
            'vendedores': vendedores,
            'vehiculos': vehiculos
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/asignaciones/vendedor/<int:id_vendedor>')
@admin_required
def api_asignaciones_vendedor(id_vendedor):
    """API para obtener asignaciones de un vendedor específico"""
    try:
        empresa_id = session.get('id_empresa', 1)
        
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    r.Nombre_Ruta,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado,
                    v.Placa,
                    v.Marca,
                    v.Modelo
                FROM asignacion_vendedores a
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                WHERE a.ID_Usuario = %s 
                AND a.ID_Empresa = %s
                ORDER BY a.Fecha_Asignacion DESC
                LIMIT 10
            """, (id_vendedor, empresa_id))
            
            asignaciones = cursor.fetchall()
            
        return jsonify(asignaciones)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#VENTAS Y FACTURACION

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