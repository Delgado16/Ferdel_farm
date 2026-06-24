# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import convertir_hora_db, procesar_asignacion, procesar_lista_asignaciones

@vendedor_bp.route('/api/productos', methods=['GET'])
@vendedor_required
def vendedor_api_productos():
    """
    API para obtener productos activos del vendedor
    Retorna JSON con los productos para usar en el formulario dinámico
    """
    id_empresa = session.get('id_empresa', 1)
    
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    p.Precio_Ruta,
                    IFNULL(um.Abreviatura, 'PZA') as Unidad,
                    IFNULL(c.Descripcion, 'S/C') as Categoria
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE p.Estado = 'activo'
                AND p.ID_Empresa = %s
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_empresa,))
            
            productos = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            productos_list = []
            for prod in productos:
                productos_list.append({
                    'id': prod['ID_Producto'],
                    'codigo': prod['COD_Producto'] or '',
                    'nombre': prod['Descripcion'],
                    'precio_ruta': float(prod['Precio_Ruta']) if prod['Precio_Ruta'] else 0,
                    'unidad': prod['Unidad'] or 'PZA',
                    'categoria': prod['Categoria'] or 'S/C'
                })
            
            return jsonify({
                'success': True,
                'productos': productos_list,
                'total': len(productos_list)
            })
            
    except Exception as e:
        print(f"Error en API productos: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vendedor_bp.route('/vendedor/ventas')
@vendedor_required
def vendedor_ventas():
    """Visualizar listado de ventas realizadas por el vendedor (solo del día actual)
    """
    try:
        id_vendedor = current_user.id
        id_empresa = session.get('empresa_id')
        
        with get_db_cursor(True) as cursor:
            # Obtener asignaciones del vendedor para el filtro
            cursor.execute("""
                SELECT av.ID_Asignacion, r.Nombre_Ruta, 
                       av.Fecha_Asignacion,
                       av.Estado as Estado_Asignacion
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s 
                ORDER BY av.Fecha_Asignacion DESC
            """, (id_vendedor,))
            asignaciones_raw = cursor.fetchall()
            
            # Formatear fechas de asignaciones
            asignaciones = []
            from datetime import datetime
            for a in asignaciones_raw:
                a_dict = dict(a)
                if a_dict.get('Fecha_Asignacion'):
                    if isinstance(a_dict['Fecha_Asignacion'], datetime):
                        a_dict['Fecha_Asignacion'] = a_dict['Fecha_Asignacion'].strftime('%d/%m/%Y')
                    else:
                        try:
                            fecha_obj = datetime.strptime(str(a_dict['Fecha_Asignacion']), '%Y-%m-%d')
                            a_dict['Fecha_Asignacion'] = fecha_obj.strftime('%d/%m/%Y')
                        except:
                            a_dict['Fecha_Asignacion'] = 'Fecha no disponible'
                else:
                    a_dict['Fecha_Asignacion'] = 'Fecha no disponible'
                asignaciones.append(a_dict)
            
            # Obtener ventas del día actual del vendedor
            ventas = []
            if asignaciones_raw:
                ids_asignacion = [a['ID_Asignacion'] for a in asignaciones_raw]
                placeholders = ','.join(['%s'] * len(ids_asignacion))
                
                hoy_local = date.today()
                
                cursor.execute(f"""
                    SELECT fr.ID_FacturaRuta, 
                           fr.Fecha,
                           fr.Fecha_Creacion,
                           fr.Credito_Contado,
                           fr.Observacion, 
                           fr.Estado, 
                           c.Nombre as Cliente, 
                           c.RUC_CEDULA,
                           c.Telefono,
                           r.Nombre_Ruta,
                           COALESCE(SUM(dfr.Total), 0) as Total_Venta,
                           CASE 
                               WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                               ELSE 'CRÉDITO'
                           END as Tipo_Venta,
                           CASE 
                               WHEN fr.Credito_Contado = 2 THEN (
                                   SELECT COALESCE(SUM(Saldo_Pendiente), 0)
                                   FROM cuentas_por_cobrar 
                                   WHERE Num_Documento = CONCAT('FAC-R', fr.ID_FacturaRuta)
                               )
                               ELSE 0
                           END as Saldo_Pendiente
                    FROM facturacion_ruta fr
                    INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE fr.ID_Asignacion IN ({placeholders})
                      AND DATE(fr.Fecha) = %s
                    GROUP BY fr.ID_FacturaRuta
                    ORDER BY fr.Fecha DESC, fr.ID_FacturaRuta DESC
                    LIMIT 15
                """, tuple(ids_asignacion) + (hoy_local,))
                ventas_raw = cursor.fetchall()
                
                # Formatear fechas de ventas
                for v in ventas_raw:
                    venta_dict = dict(v)
                    
                    # Formatear Fecha
                    if venta_dict.get('Fecha'):
                        if isinstance(venta_dict['Fecha'], datetime):
                            venta_dict['Fecha'] = venta_dict['Fecha'].strftime('%d/%m/%Y')
                        else:
                            try:
                                fecha_obj = datetime.strptime(str(venta_dict['Fecha']), '%Y-%m-%d')
                                venta_dict['Fecha'] = fecha_obj.strftime('%d/%m/%Y')
                            except:
                                venta_dict['Fecha'] = 'Fecha no disponible'
                    else:
                        venta_dict['Fecha'] = 'Fecha no disponible'
                    
                    # Formatear Fecha_Creacion y extraer Hora
                    if venta_dict.get('Fecha_Creacion'):
                        if isinstance(venta_dict['Fecha_Creacion'], datetime):
                            venta_dict['Hora'] = venta_dict['Fecha_Creacion'].strftime('%H:%M')
                            venta_dict['Fecha_Creacion'] = venta_dict['Fecha_Creacion'].strftime('%d/%m/%Y %H:%M')
                        else:
                            try:
                                fecha_obj = datetime.strptime(str(venta_dict['Fecha_Creacion']), '%Y-%m-%d %H:%M:%S')
                                venta_dict['Hora'] = fecha_obj.strftime('%H:%M')
                                venta_dict['Fecha_Creacion'] = fecha_obj.strftime('%d/%m/%Y %H:%M')
                            except:
                                try:
                                    fecha_obj = datetime.strptime(str(venta_dict['Fecha_Creacion']), '%Y-%m-%d')
                                    venta_dict['Hora'] = '00:00'
                                    venta_dict['Fecha_Creacion'] = fecha_obj.strftime('%d/%m/%Y') + ' 00:00'
                                except:
                                    venta_dict['Hora'] = 'Hora no disponible'
                                    venta_dict['Fecha_Creacion'] = 'Fecha no disponible'
                    else:
                        venta_dict['Hora'] = 'Hora no disponible'
                        venta_dict['Fecha_Creacion'] = 'Fecha no disponible'
                    
                    ventas.append(venta_dict)
            
            # Obtener fecha actual formateada para comparaciones
            ahora = datetime.now()
            fecha_actual = ahora.strftime('%d/%m/%Y')
            fecha_actual_iso = ahora.strftime('%Y-%m-%d')  # Para inputs date
            
        return render_template('vendedor/ventas/ventas.html', 
                             asignaciones=asignaciones,
                             ventas=ventas,
                             fecha_actual=fecha_actual,
                             fecha_actual_iso=fecha_actual_iso,  # IMPORTANTE: pasar esta variable
                             now=ahora)
                             
    except Exception as e:
        print(f"Error en vendedor_ventas: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar ventas: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))


@vendedor_bp.route('/venta/crear', methods=['GET', 'POST'])
@vendedor_required
def vendedor_venta_crear():
    """Crear una nueva venta en ruta con integración a caja, abonos y movimientos"""
    try:
        id_vendedor = int(current_user.id)
        id_empresa = session.get('empresa_id', 1)
        
        # Para GET - solo consultas
        if request.method == 'GET':
            with get_db_cursor() as cursor:
                # Obtener asignación activa del vendedor
                cursor.execute("""
                    SELECT av.*, r.Nombre_Ruta, u.NombreUsuario as Nombre_Vendedor
                    FROM asignacion_vendedores av
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE av.ID_Usuario = %s 
                    AND av.Estado = 'Activa'
                    AND r.ID_Empresa = %s
                    LIMIT 1
                """, (id_vendedor, id_empresa))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una ruta activa asignada', 'warning')
                    return redirect(url_for('vendedor.vendedor_dashboard'))
                
                # Obtener clientes de la empresa (filtrados por ruta)
                cursor.execute("""
                    SELECT ID_Cliente, Nombre, RUC_CEDULA, Telefono, Direccion,
                           tipo_cliente, perfil_cliente, COALESCE(Saldo_Pendiente_Total, 0) as Saldo_Pendiente_Total
                    FROM clientes 
                    WHERE Estado = 'ACTIVO' 
                    AND ID_Empresa = %s
                    AND (ID_Ruta = %s OR ID_Ruta IS NULL)
                    ORDER BY Nombre
                """, (asignacion['ID_Empresa'], asignacion['ID_Ruta']))
                clientes = cursor.fetchall()
                
                # Obtener inventario disponible con precios de ruta
                cursor.execute("""
                    SELECT ir.ID_Producto, 
                           p.COD_Producto, 
                           p.Descripcion as Nombre,
                           p.Precio_Ruta,
                           ir.Cantidad as Stock_Disponible,
                           um.Descripcion as Unidad_Medida
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    WHERE ir.ID_Asignacion = %s 
                    AND ir.Cantidad > 0
                    AND p.Estado = 'activo'
                    ORDER BY p.Descripcion
                """, (asignacion['ID_Asignacion'],))
                inventario = cursor.fetchall()
                
                # Obtener métodos de pago
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM metodos_pago
                    ORDER BY Nombre
                """)
                metodos_pago = cursor.fetchall()
                
                from datetime import date
                hoy_local = date.today()
                # Verificar si hay caja abierta hoy
                cursor.execute("""
                    SELECT COUNT(*) as tiene_caja_hoy
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND DATE(Fecha) = %s 
                    AND Tipo = 'APERTURA'
                    AND Estado = 'ACTIVO'
                """, (asignacion['ID_Asignacion'], hoy_local))
                tiene_caja_hoy = cursor.fetchone()['tiene_caja_hoy'] > 0
                
                # Verificar si hay una caja abierta de días anteriores SIN CIERRE
                cursor.execute("""
                    SELECT COUNT(*) as tiene_caja_activa
                    FROM movimientos_caja_ruta m1
                    WHERE m1.ID_Asignacion = %s 
                    AND m1.Tipo = 'APERTURA'
                    AND m1.Estado = 'ACTIVO'
                    AND NOT EXISTS (
                        SELECT 1 FROM movimientos_caja_ruta m2
                        WHERE m2.ID_Asignacion = m1.ID_Asignacion
                        AND m2.Tipo = 'CIERRE'
                        AND m2.Fecha > m1.Fecha
                        AND m2.Estado = 'ACTIVO'
                    )
                """, (asignacion['ID_Asignacion'],))
                tiene_caja_activa = cursor.fetchone()['tiene_caja_activa'] > 0
                
                # También verificar el último movimiento del día para asegurar que no haya cierre
                cursor.execute("""
                    SELECT Tipo, Estado, DATE(Fecha) as Fecha_Movimiento
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND DATE(Fecha) = %s
                    AND Estado = 'ACTIVO'
                    ORDER BY Fecha DESC
                    LIMIT 1
                """, (asignacion['ID_Asignacion'], hoy_local))
                ultimo_movimiento_hoy = cursor.fetchone()
                
                caja_abierta = tiene_caja_hoy or (tiene_caja_activa and (not ultimo_movimiento_hoy or ultimo_movimiento_hoy['Tipo'] != 'CIERRE'))
                
                # Fecha actual para el template
                fecha_actual = datetime.now().strftime('%d/%m/%Y')
                
                print(f"📊 Estado de caja - ID_Asignacion: {asignacion['ID_Asignacion']}")
                print(f"  - Tiene caja hoy: {tiene_caja_hoy}")
                print(f"  - Tiene caja activa sin cierre: {tiene_caja_activa}")
                print(f"  - Último movimiento hoy: {ultimo_movimiento_hoy}")
                print(f"  - Caja abierta: {caja_abierta}")
                
            return render_template('vendedor/ventas/venta_crear.html',
                                 asignacion=asignacion,
                                 clientes=clientes,
                                 inventario=inventario,
                                 metodos_pago=metodos_pago,
                                 fecha_actual=fecha_actual,
                                 caja_abierta=caja_abierta)
        
        # Para POST - operaciones de escritura con commit
        if request.method == 'POST':
            # Usar get_db_cursor con commit=True
            with get_db_cursor(commit=True) as cursor:
                # Obtener asignación activa del vendedor
                cursor.execute("""
                    SELECT av.*, r.Nombre_Ruta, u.NombreUsuario as Nombre_Vendedor
                    FROM asignacion_vendedores av
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE av.ID_Usuario = %s 
                    AND av.Estado = 'Activa'
                    AND r.ID_Empresa = %s
                    LIMIT 1
                """, (id_vendedor, id_empresa))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una ruta activa asignada', 'warning')
                    return redirect(url_for('vendedor.vendedor_dashboard'))
                
                # Procesar creación de venta
                id_cliente = request.form.get('cliente')
                tipo_venta = request.form.get('tipo_venta')  # '1'=Contado, '2'=Crédito
                observacion = request.form.get('observacion', '')
                productos_json = request.form.get('productos', '[]')
                
                # Obtener datos del abono si existe
                abono_monto = float(request.form.get('abono_monto', '0'))
                abono_metodo_pago = request.form.get('abono_metodo_pago', '')
                procesar_abono = request.form.get('procesar_abono', '0') == '1'
                try:
                    id_metodo_pago = int(abono_metodo_pago) if abono_metodo_pago else None
                except (ValueError, TypeError):
                    id_metodo_pago = None
                
                # Validar datos básicos
                if not id_cliente:
                    flash('Debe seleccionar un cliente', 'error')
                    return redirect(request.url)
                
                if not tipo_venta:
                    flash('Debe seleccionar el tipo de venta', 'error')
                    return redirect(request.url)
                
                # Parsear productos
                try:
                    productos = json.loads(productos_json)
                    print(f"Productos recibidos: {productos}")
                except Exception as e:
                    print(f"Error al parsear JSON: {e}")
                    productos = []
                
                if not productos:
                    flash('Debe agregar al menos un producto a la venta', 'error')
                    return redirect(request.url)
                
                # ===== SOLO PARA VENTAS DE CONTADO: VERIFICAR CAJA =====
                if tipo_venta == '1':  # Solo ventas de contado requieren caja
                    from datetime import date
                    hoy_local = date.today()
                    # Estrategia 1: Buscar apertura de hoy
                    cursor.execute("""
                        SELECT ID_Movimiento, Fecha, Saldo_Acumulado
                        FROM movimientos_caja_ruta 
                        WHERE ID_Asignacion = %s 
                        AND DATE(Fecha) = %s 
                        AND Tipo = 'APERTURA'
                        AND Estado = 'ACTIVO'
                        ORDER BY Fecha DESC 
                        LIMIT 1
                    """, (asignacion['ID_Asignacion'], hoy_local))
                    caja = cursor.fetchone()
                    
                    # Estrategia 2: Si no hay apertura hoy, buscar la última apertura activa sin cierre
                    if not caja:
                        cursor.execute("""
                            SELECT m1.ID_Movimiento, m1.Fecha, m1.Saldo_Acumulado
                            FROM movimientos_caja_ruta m1
                            WHERE m1.ID_Asignacion = %s 
                            AND m1.Tipo = 'APERTURA'
                            AND m1.Estado = 'ACTIVO'
                            AND NOT EXISTS (
                                SELECT 1 FROM movimientos_caja_ruta m2
                                WHERE m2.ID_Asignacion = m1.ID_Asignacion
                                AND m2.Tipo = 'CIERRE'
                                AND m2.Fecha > m1.Fecha
                                AND m2.Estado = 'ACTIVO'
                            )
                            ORDER BY m1.Fecha DESC
                            LIMIT 1
                        """, (asignacion['ID_Asignacion'],))
                        caja = cursor.fetchone()
                    
                    # Estrategia 3: Verificar si hay algún movimiento hoy (para asegurar que no haya cierre)
                    if caja:
                        cursor.execute("""
                            SELECT Tipo
                            FROM movimientos_caja_ruta 
                            WHERE ID_Asignacion = %s 
                            AND DATE(Fecha) = %s
                            AND Estado = 'ACTIVO'
                            ORDER BY Fecha DESC
                            LIMIT 1
                        """, (asignacion['ID_Asignacion'], hoy_local))
                        ultimo_hoy = cursor.fetchone()
                        
                        # Si el último movimiento de hoy es un CIERRE, la caja está cerrada
                        if ultimo_hoy and ultimo_hoy['Tipo'] == 'CIERRE':
                            caja = None
                            print("⚠️ La caja fue cerrada hoy, no se pueden realizar ventas de contado")
                    
                    # Si no hay caja válida, intentar crear una apertura automática
                    if not caja:
                        print("⚠️ No se encontró caja abierta, intentando crear apertura automática...")
                        
                        cursor.execute("""
                            SELECT ID_Movimiento
                            FROM movimientos_caja_ruta 
                            WHERE ID_Asignacion = %s 
                            AND DATE(Fecha) = %s 
                            AND Tipo = 'APERTURA'
                            LIMIT 1
                        """, (asignacion['ID_Asignacion'], hoy_local))
                        apertura_existente = cursor.fetchone()
                        
                        if apertura_existente:
                            # Si existe pero estaba inactiva, reactivarla
                            cursor.execute("""
                                UPDATE movimientos_caja_ruta 
                                SET Estado = 'ACTIVO'
                                WHERE ID_Movimiento = %s
                            """, (apertura_existente['ID_Movimiento'],))
                            caja = apertura_existente
                            print(f"✅ Apertura existente reactivada: {caja['ID_Movimiento']}")
                        else:
                            # Crear nueva apertura
                            try:
                                fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
                                
                                cursor.execute("""
                                    INSERT INTO movimientos_caja_ruta
                                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                                     Tipo_Pago, Saldo_Acumulado, Estado)
                                    VALUES (%s, %s, 'APERTURA', %s, 0.00, NULL, 0.00, 'ACTIVO')
                                """, (
                                    asignacion['ID_Asignacion'],
                                    id_vendedor,
                                    f"Apertura automática - {fecha_hora}"
                                ))
                                
                                cursor.execute("SELECT LAST_INSERT_ID() as ID_Movimiento")
                                caja = cursor.fetchone()
                                print(f"✅ Apertura automática creada con ID: {caja['ID_Movimiento']}")
                                
                            except Exception as e:
                                print(f"❌ Error al crear apertura: {e}")
                                flash('No se pudo abrir la caja', 'error')
                                return redirect(url_for('vendedor.vendedor_dashboard'))
                    
                    if not caja:
                        flash('No se pudo verificar/crear la apertura de caja', 'error')
                        return redirect(url_for('vendedor.vendedor_dashboard'))
                    
                    print(f"✅ Caja verificada - ID Movimiento: {caja['ID_Movimiento']}")
                
                # ===== OBTENER SALDO ANTERIOR DEL CLIENTE (ANTES DE LA VENTA) =====
                cursor.execute("""
                    SELECT COALESCE(Saldo_Pendiente_Total, 0) as Saldo_Anterior
                    FROM clientes 
                    WHERE ID_Cliente = %s AND ID_Empresa = %s
                """, (int(id_cliente), asignacion['ID_Empresa']))
                
                saldo_anterior_cliente = cursor.fetchone()
                saldo_anterior = float(saldo_anterior_cliente['Saldo_Anterior'] if saldo_anterior_cliente else 0)
                print(f"💰 Saldo anterior del cliente {id_cliente}: {saldo_anterior}")
                
                # Validar stock
                error_stock = False
                productos_sin_stock = []
                for prod in productos:
                    cursor.execute("""
                        SELECT Cantidad FROM inventario_ruta
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (asignacion['ID_Asignacion'], prod['id']))
                    stock = cursor.fetchone()
                    
                    if not stock or stock['Cantidad'] < prod['cantidad']:
                        cursor.execute("""
                            SELECT Descripcion FROM productos WHERE ID_Producto = %s
                        """, (prod['id'],))
                        prod_nombre = cursor.fetchone()
                        productos_sin_stock.append(prod_nombre["Descripcion"] if prod_nombre else f"Producto ID {prod['id']}")
                        error_stock = True
                
                if error_stock:
                    flash(f'Stock insuficiente para: {", ".join(productos_sin_stock)}', 'error')
                    return redirect(request.url)
                
                # Calcular total de la venta y subtotales
                total_venta = 0
                total_items = 0
                for prod in productos:
                    total_venta += prod['cantidad'] * prod['precio']
                    total_items += prod['cantidad']
                
                # ===== 1. INSERTAR FACTURA (INCLUYENDO SALDO ANTERIOR) =====
                from datetime import date
                cursor.execute("""
                    INSERT INTO facturacion_ruta 
                    (Fecha, ID_Cliente, ID_Asignacion, Credito_Contado, 
                     Observacion, Saldo_Anterior_Cliente, ID_Empresa, ID_Usuario_Creacion, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Activa')
                """, (date.today(), int(id_cliente), asignacion['ID_Asignacion'], int(tipo_venta), 
                      observacion, saldo_anterior, asignacion['ID_Empresa'], id_vendedor))
                
                id_factura = cursor.lastrowid
                print(f"✅ Factura de ruta creada con ID: {id_factura} (Saldo anterior guardado: {saldo_anterior})")
                
                ID_TIPO_MOVIMIENTO_VENTA = 2  
                
                documento_numero = f"VEN-{id_factura}" 
                
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera
                    (ID_Asignacion, ID_TipoMovimiento, Fecha_Movimiento, ID_Usuario_Registra,
                     Documento_Numero, ID_Cliente, Total_Productos, Total_Items,
                     Total_Subtotal, ID_Empresa, Estado)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    asignacion['ID_Asignacion'],      # ID_Asignacion
                    ID_TIPO_MOVIMIENTO_VENTA,         # ID_TipoMovimiento
                    id_vendedor,                      # ID_Usuario_Registra
                    documento_numero,                 # Documento_Numero
                    int(id_cliente),                  # ID_Cliente
                    total_venta,                      # Total_Productos (monto total)
                    total_items,                      # Total_Items (cantidad total de productos)
                    total_venta,                      # Total_Subtotal (subtotal)
                    asignacion['ID_Empresa'],         # ID_Empresa
                ))
                
                id_movimiento_cabecera = cursor.lastrowid
                print(f"✅ Movimiento registrado en cabecera con ID: {id_movimiento_cabecera}")
                
                # ===== 3. INSERTAR DETALLES EN movimientos_ruta_detalle Y ACTUALIZAR INVENTARIO =====
                for prod in productos:
                    total_linea = prod['cantidad'] * prod['precio']
                    
                    # Insertar en detalle de facturación
                    cursor.execute("""
                        INSERT INTO detalle_facturacion_ruta
                        (ID_FacturaRuta, ID_Producto, Cantidad, Precio, Total)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, prod['id'], prod['cantidad'], 
                          prod['precio'], total_linea))
                    
                    # Insertar en movimientos_ruta_detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_cabecera,   # ID_Movimiento
                        prod['id'],               # ID_Producto
                        prod['cantidad'],         # Cantidad
                        prod['precio'],           # Precio_Unitario
                        total_linea               # Subtotal
                    ))
                    
                    print(f"  - Detalle producto {prod['id']}: {prod['cantidad']} x {prod['precio']} = {total_linea}")
                    
                    # Actualizar inventario de ruta
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad - %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (prod['cantidad'], asignacion['ID_Asignacion'], prod['id']))
                
                print(f"✅ {len(productos)} productos registrados en detalle de movimientos")
                
                # ===== 4. REGISTRO EN CAJA (SOLO PARA VENTAS DE CONTADO) =====
                if tipo_venta == '1':  # CONTADO
                    # Calcular saldo actual de caja ANTES de insertar
                    cursor.execute("""
                        SELECT COALESCE(SUM(CASE 
                            WHEN Tipo = 'GASTO' THEN -Monto 
                            WHEN Tipo = 'CIERRE' THEN 0
                            ELSE Monto 
                        END), 0) as Saldo_Actual
                        FROM movimientos_caja_ruta 
                        WHERE ID_Asignacion = %s 
                          AND Estado = 'ACTIVO'
                          AND Tipo != 'CIERRE'
                    """, (asignacion['ID_Asignacion'],))
                    
                    saldo_result = cursor.fetchone()
                    saldo_actual = float(saldo_result['Saldo_Actual'] if saldo_result else 0)
                    nuevo_saldo = saldo_actual + total_venta
                    
                    cursor.execute("""
                        INSERT INTO movimientos_caja_ruta
                        (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                         Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                        VALUES (%s, %s, 'VENTA', %s, %s, %s, %s, %s, %s, 'ACTIVO')
                    """, (
                        asignacion['ID_Asignacion'],
                        id_vendedor,
                        f"Venta Contado Factura #{id_factura}",
                        total_venta,
                        'CONTADO',
                        id_factura,
                        int(id_cliente),
                        nuevo_saldo
                    ))
                    
                    print(f"✅ Movimiento en caja registrado: +{total_venta}")
                    
                    # Actualizar el monto efectivo en la cabecera del movimiento
                    cursor.execute("""
                        UPDATE movimientos_ruta_cabecera
                        SET Monto_Efectivo = %s
                        WHERE ID_Movimiento = %s
                    """, (total_venta, id_movimiento_cabecera))
                    
                else:  # CREDITO - NO SE REGISTRA NADA EN CAJA
                    print(f"✅ Venta a crédito #{id_factura} registrada SIN movimiento de caja (como debe ser)")
                
                # ===== 5. CREAR CUENTA POR COBRAR (si es crédito) =====
                if tipo_venta == '2':  # Crédito
                    try:
                        fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO cuentas_por_cobrar
                            (Fecha, ID_Cliente, Num_Documento, Observacion, Fecha_Vencimiento,
                             Tipo_Movimiento, Monto_Movimiento, ID_Empresa, Saldo_Pendiente,
                             ID_Factura, ID_FacturaRuta, ID_Usuario_Creacion, Estado)
                            VALUES (CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            int(id_cliente),                    # ID_Cliente
                            f"FAC-R{id_factura}",               # Num_Documento
                            observacion,                         # Observacion
                            fecha_vencimiento,                   # Fecha_Vencimiento
                            2,                                    # Tipo_Movimiento (2=Venta)
                            total_venta,                         # Monto_Movimiento
                            asignacion['ID_Empresa'],            # ID_Empresa
                            total_venta,                         # Saldo_Pendiente
                            None,                                # ID_Factura (NULL)
                            id_factura,                          # ID_FacturaRuta
                            id_vendedor,                         # ID_Usuario_Creacion
                            'Pendiente'                          # Estado
                        ))
                        
                        id_cuenta = cursor.lastrowid
                        print(f"✅ Cuenta por cobrar creada con ID: {id_cuenta}")
                        
                        # Actualizar saldo del cliente
                        cursor.execute("""
                            UPDATE clientes 
                            SET Saldo_Pendiente_Total = COALESCE(Saldo_Pendiente_Total, 0) + %s,
                                Fecha_Ultimo_Movimiento = NOW(),
                                ID_Ultima_Factura = %s
                            WHERE ID_Cliente = %s AND ID_Empresa = %s
                        """, (total_venta, id_factura, int(id_cliente), asignacion['ID_Empresa']))
                        
                        print(f"✅ Saldo del cliente actualizado: +{total_venta}")
                        
                    except Exception as e:
                        print(f"❌ Error al crear cuenta por cobrar: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        raise
                
                # ===== 6. PROCESAR ABONO (DESPUÉS DE LA FACTURA) =====
                if procesar_abono and abono_monto > 0:
                    try:
                        print(f"💰 Procesando abono de {abono_monto} para cliente {id_cliente}")
                        
                        # 6.1 Obtener facturas pendientes del cliente
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
                        
                        facturas_pendientes = cursor.fetchall()
                        
                        if not facturas_pendientes:
                            print("⚠️ No hay facturas pendientes para aplicar el abono")
                        else:
                            # 6.2 Calcular saldo actual de caja para el abono
                            cursor.execute("""
                                SELECT COALESCE(SUM(CASE 
                                    WHEN Tipo = 'GASTO' THEN -Monto 
                                    ELSE Monto 
                                END), 0) as Saldo_Actual
                                FROM movimientos_caja_ruta
                                WHERE ID_Asignacion = %s 
                                  AND Estado = 'ACTIVO'
                                  AND Tipo != 'CIERRE'
                            """, (asignacion['ID_Asignacion'],))
                            
                            saldo_result = cursor.fetchone()
                            saldo_actual_abono = float(saldo_result['Saldo_Actual'] if saldo_result else 0)
                            nuevo_saldo_caja = saldo_actual_abono + abono_monto
                            
                            # 6.3 Registrar movimiento de abono en caja (SÍ porque es efectivo real)
                            cursor.execute("""
                                INSERT INTO movimientos_caja_ruta
                                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                                 Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                                VALUES (%s, %s, 'ABONO', %s, %s, %s, %s, %s, %s, 'ACTIVO')
                            """, (
                                asignacion['ID_Asignacion'],
                                id_vendedor,
                                f"Abono a cuenta - Factura #{id_factura}",
                                abono_monto,
                                'CONTADO' if tipo_venta == '1' else 'CREDITO',
                                id_factura,
                                int(id_cliente),
                                nuevo_saldo_caja
                            ))
                            
                            id_movimiento_caja = cursor.lastrowid
                            
                            # 6.4 Distribuir el abono entre las facturas pendientes
                            monto_restante = abono_monto
                            monto_aplicado = 0
                            
                            for factura in facturas_pendientes:
                                if monto_restante <= 0:
                                    break
                                    
                                saldo_factura = float(factura['Saldo_Pendiente'])
                                monto_aplicar = min(monto_restante, saldo_factura)
                                nuevo_saldo_factura = saldo_factura - monto_aplicar
                                nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0 else 'Pendiente'
                                
                                # Actualizar factura
                                cursor.execute("""
                                    UPDATE cuentas_por_cobrar
                                    SET Saldo_Pendiente = %s, 
                                        Estado = %s
                                    WHERE ID_Movimiento = %s
                                """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                                
                                # Insertar en abonos_detalle
                                try:
                                    cursor.execute("""
                                        INSERT INTO abonos_detalle
                                        (ID_Movimiento_Caja, ID_Asignacion, ID_Usuario, ID_Cliente, 
                                         ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo,
                                         ID_MetodoPago)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        id_movimiento_caja,
                                        asignacion['ID_Asignacion'],
                                        id_vendedor,
                                        int(id_cliente),
                                        factura['ID_Movimiento'],
                                        monto_aplicar,
                                        saldo_factura,
                                        nuevo_saldo_factura,
                                        id_metodo_pago
                                    ))
                                except Exception as e:
                                    print(f"⚠️ No se pudo insertar en abonos_detalle: {e}")
                                
                                monto_restante -= monto_aplicar
                                monto_aplicado += monto_aplicar
                            
                            # 6.5 Actualizar saldo del cliente
                            cursor.execute("""
                                UPDATE clientes 
                                SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total, 0) - %s),
                                    Fecha_Ultimo_Pago = NOW()
                                WHERE ID_Cliente = %s AND ID_Empresa = %s
                            """, (monto_aplicado, int(id_cliente), asignacion['ID_Empresa']))
                            
                            print(f"✅ Abono de {abono_monto} procesado exitosamente")
                            print(f"   - Monto aplicado: {monto_aplicado}")
                            print(f"   - Vuelto: {monto_restante}")
                            
                    except Exception as e:
                        print(f"❌ Error al procesar abono: {str(e)}")
                        traceback.print_exc()
                        raise
                
                print(f"✅ Venta {id_factura} procesada exitosamente")
                print(f"✅ Movimiento cabecera {id_movimiento_cabecera} registrado con {len(productos)} detalles")
                
            # Fuera del context manager, los cambios ya están commiteados
            flash('Venta registrada exitosamente', 'success')
            
            # Redirigir al ticket
            return redirect(url_for('vendedor.vendedor_generar_ticket_ruta', 
                                  id_venta=id_factura, 
                                  autoPrint=1))
                             
    except Exception as e:
        print(f"❌ Error en vendedor_venta_crear: {str(e)}")
        traceback.print_exc()
        flash(f'Error al procesar la venta: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_ventas'))


@vendedor_bp.route('/vendedor/venta/<int:id_venta>/ticket')
@vendedor_required
def vendedor_generar_ticket_ruta(id_venta):
    """Generar ticket de venta de ruta con información de saldos"""
    try:
        id_vendedor = int(current_user.id)
        auto_print = request.args.get('autoPrint', 0)
        
        with get_db_cursor() as cursor:
            # Obtener datos de la venta de ruta (INCLUYENDO SALDO_ANTERIOR_CLIENTE)
            cursor.execute("""
                SELECT 
                    fr.ID_FacturaRuta as ID_Factura,
                    fr.Fecha,
                    fr.Fecha_Creacion,
                    fr.Observacion,
                    fr.Credito_Contado,
                    fr.Saldo_Anterior_Cliente,  -- ← NUEVO CAMPO
                    fr.ID_Usuario_Creacion,
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    c.Telefono as Telefono_Cliente,
                    c.Direccion as Direccion_Cliente,
                    COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Cliente_Actual,
                    u.NombreUsuario as Usuario,
                    e.ID_Empresa,
                    COALESCE(e.Nombre_Empresa, 'MI EMPRESA') as Nombre_Empresa,
                    COALESCE(e.RUC, 'RUC NO CONFIGURADO') as RUC_Empresa,
                    COALESCE(e.Direccion, '') as Direccion_Empresa,
                    COALESCE(e.Telefono, '') as Telefono_Empresa,
                    r.Nombre_Ruta,
                    CASE 
                        WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                        ELSE 'CREDITO'
                    END as Tipo_Venta_Formateado
                FROM facturacion_ruta fr
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN empresa e ON fr.ID_Empresa = e.ID_Empresa
                WHERE fr.ID_FacturaRuta = %s
                AND av.ID_Usuario = %s
            """, (id_venta, id_vendedor))
            
            factura = cursor.fetchone()
            
            if not factura:
                flash('Venta no encontrada o no tienes permiso para verla', 'error')
                return redirect(url_for('vendedor.vendedor_ventas'))
            
            # Formatear fechas
            fecha_formateada = factura['Fecha'].strftime('%d/%m/%Y') if factura['Fecha'] else ''
            hora_creacion = factura['Fecha_Creacion'].strftime('%H:%M:%S') if factura['Fecha_Creacion'] else ''
            
            # Obtener detalles de la venta
            cursor.execute("""
                SELECT 
                    df.ID_DetalleRuta as ID_Detalle,
                    df.Cantidad,
                    df.Precio,
                    df.Total as Subtotal,
                    p.ID_Producto,
                    COALESCE(p.COD_Producto, 'N/A') as COD_Producto,
                    COALESCE(p.Descripcion, 'PRODUCTO ELIMINADO') as Producto,
                    cat.Descripcion as Categoria,
                    um.Descripcion as Unidad
                FROM detalle_facturacion_ruta df
                LEFT JOIN productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE df.ID_FacturaRuta = %s
                ORDER BY df.ID_DetalleRuta
            """, (id_venta,))
            
            detalles = cursor.fetchall()
            
            if not detalles:
                flash('La venta no tiene detalles de productos', 'error')
                return redirect(url_for('vendedor.vendedor_venta_detalle', id_venta=id_venta))
            
            # Calcular total de la venta actual
            total_venta = 0
            for detalle in detalles:
                subtotal = float(detalle['Subtotal'] or 0)
                total_venta += subtotal
            
            # Calcular subtotales por producto
            for detalle in detalles:
                detalle['Subtotal_Calculado'] = float(detalle['Cantidad']) * float(detalle['Precio'])
                detalle['Cantidad_Formateada'] = f"{float(detalle['Cantidad']):g}"
                detalle['Precio_Formateado'] = f"C$ {float(detalle['Precio']):,.2f}"
                detalle['Subtotal_Formateado'] = f"C$ {float(detalle['Subtotal']):,.2f}"
            
            # Variables para información de crédito
            cuenta_cobrar = None
            facturas_pendientes = []
            saldo_anterior_total = 0
            abonos_detalle = []
            proximo_vencimiento = None
            abono_realizado = 0
            abonos_esta_factura = 0
            mostrar_seccion_credito = False
            mensaje_credito = ""
            
            # ===== USAR EL SALDO ANTERIOR GUARDADO EN LA FACTURA =====
            saldo_anterior_total = float(factura['Saldo_Anterior_Cliente'] or 0)
            print(f"📊 Usando saldo anterior guardado en factura: {saldo_anterior_total}")
            
            # Obtener TODAS las cuentas por cobrar pendientes del cliente (para mostrar en el ticket)
            cursor.execute("""
                SELECT 
                    cxc.ID_Movimiento,
                    cxc.Num_Documento,
                    cxc.Saldo_Pendiente,
                    cxc.Monto_Movimiento as Monto_Original,
                    cxc.Fecha_Vencimiento,
                    cxc.Estado,
                    DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as Dias_Vencido,
                    DATE_FORMAT(cxc.Fecha_Vencimiento, '%d/%m/%Y') as Fecha_Vencimiento_Formateada,
                    CASE 
                        WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 'VENCIDA'
                        ELSE 'PENDIENTE'
                    END as Estado_Calculado
                FROM cuentas_por_cobrar cxc
                WHERE cxc.ID_Cliente = %s 
                AND cxc.Estado IN ('Pendiente', 'Vencida')
                AND cxc.Saldo_Pendiente > 0
                ORDER BY 
                    CASE WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 0 ELSE 1 END,
                    cxc.Fecha_Vencimiento ASC
            """, (factura['ID_Cliente'],))
            
            facturas_pendientes = cursor.fetchall()
            
            # Obtener el abono que se realizó EN ESTA VENTA
            cursor.execute("""
                SELECT 
                    m.ID_Movimiento,
                    m.Fecha,
                    m.Monto,
                    m.Concepto,
                    DATE_FORMAT(m.Fecha, '%d/%m/%Y %H:%i') as Fecha_Hora,
                    m.Tipo_Pago,
                    m.Estado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Cliente = %s 
                AND m.ID_FacturaRuta = %s
                AND m.Tipo = 'ABONO'
                AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
                LIMIT 1
            """, (factura['ID_Cliente'], id_venta))
            
            abono_actual = cursor.fetchone()
            
            # Obtener abonos totales realizados para esta factura
            cursor.execute("""
                SELECT COALESCE(SUM(m.Monto), 0) as Total_Abonado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Cliente = %s 
                AND m.ID_FacturaRuta = %s
                AND m.Tipo = 'ABONO'
                AND m.Estado = 'ACTIVO'
            """, (factura['ID_Cliente'], id_venta))
            
            abonos_result = cursor.fetchone()
            abonos_esta_factura = float(abonos_result['Total_Abonado'] if abonos_result else 0)
            
            # Determinar el abono que dio el cliente en esta venta
            if abono_actual:
                abono_cliente = float(abono_actual['Monto'])
                concepto_abono = abono_actual['Concepto'] or 'ABONO A CUENTA'
                fecha_abono = abono_actual['Fecha_Hora']
            else:
                if factura['Credito_Contado'] == 1:
                    abono_cliente = total_venta
                    concepto_abono = 'PAGO CONTADO'
                    fecha_abono = datetime.now().strftime('%d/%m/%Y %H:%M')
                else:
                    abono_cliente = abonos_esta_factura
                    concepto_abono = 'ABONO A CUENTA' if abono_cliente > 0 else 'SIN ABONO'
                    fecha_abono = None
            
            # El nuevo saldo pendiente se calcula matemáticamente para ser histórico de esta venta
            nuevo_saldo_pendiente = saldo_anterior_total + total_venta - abono_cliente
            
            # Determinar si mostrar sección de crédito
            if saldo_anterior_total > 0 or abono_cliente > 0 or factura['Credito_Contado'] == 2:
                mostrar_seccion_credito = True
                if factura['Credito_Contado'] == 2:
                    if saldo_anterior_total > 0:
                        mensaje_credito = "NUEVA DEUDA + SALDO ANTERIOR"
                    else:
                        mensaje_credito = "NUEVA VENTA A CREDITO"
                else:
                    if saldo_anterior_total > 0:
                        mensaje_credito = "ABONO A DEUDAS PENDIENTES"
                    else:
                        mensaje_credito = "VENTA AL CONTADO"
            
            # Obtener el próximo vencimiento
            if facturas_pendientes:
                facturas_futuras = [f for f in facturas_pendientes 
                                  if f['Fecha_Vencimiento'] and f['Fecha_Vencimiento'] >= datetime.now().date()]
                if facturas_futuras:
                    proxima_factura = min(facturas_futuras, key=lambda x: x['Fecha_Vencimiento'])
                    if proxima_factura['Fecha_Vencimiento']:
                        proximo_vencimiento = proxima_factura['Fecha_Vencimiento'].strftime('%d/%m/%Y')
            
            # Obtener historial de abonos recientes del cliente
            cursor.execute("""
                SELECT 
                    m.Fecha,
                    m.Concepto,
                    m.Monto,
                    m.ID_Movimiento,
                    DATE_FORMAT(m.Fecha, '%d/%m/%Y') as Fecha_Formateada,
                    TIME_FORMAT(m.Fecha, '%H:%i') as Hora_Formateada
                FROM movimientos_caja_ruta m
                WHERE m.ID_Cliente = %s 
                AND m.Tipo = 'ABONO'
                AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
                LIMIT 5
            """, (factura['ID_Cliente'],))
            
            abonos_detalle = cursor.fetchall()
            
            # Formatear montos de abonos
            for abono in abonos_detalle:
                abono['Monto_Formateado'] = f"C$ {float(abono['Monto'] or 0):,.2f}"
            
            # Preparar datos para el ticket
            ticket_data = {
                'id_factura': f"R-{id_venta:06d}",
                'id_factura_numerico': id_venta,
                'fecha': factura['Fecha'],
                'hora_emision': datetime.now(),
                'fecha_factura': fecha_formateada,
                'hora_factura': hora_creacion,
                'ruta': factura['Nombre_Ruta'],
                'cliente': factura['Cliente'] or 'Consumidor Final',
                'ruc_cliente': factura['RUC_Cliente'] or 'Consumidor Final',
                'cliente_detalles': {
                    'nombre': factura['Cliente'] or 'Consumidor Final',
                    'ruc': factura['RUC_Cliente'] or 'Consumidor Final',
                    'telefono': factura['Telefono_Cliente'] or '',
                    'direccion': factura['Direccion_Cliente'] or ''
                },
                'tipo_venta': factura['Tipo_Venta_Formateado'],
                'tipo_venta_valor': factura['Credito_Contado'],
                'observacion': factura['Observacion'] or '',
                'usuario': factura['Usuario'] or 'Vendedor',
                'usuario_id': factura['ID_Usuario_Creacion'],
                'detalles': detalles,
                'total': total_venta,
                'total_formateado': f"C$ {total_venta:,.2f}",
                'subtotal_sin_descuento': total_venta,
                'descuento': 0,
                'empresa': {
                    'nombre': factura['Nombre_Empresa'],
                    'ruc': factura['RUC_Empresa'],
                    'direccion': factura['Direccion_Empresa'],
                    'telefono': factura['Telefono_Empresa'],
                },
                'tiene_credito': cuenta_cobrar is not None,
                'cuenta_cobrar': cuenta_cobrar
            }
            
            # Formatear valores para mostrar
            venta_realizada = total_venta
            venta_realizada_formateada = f"C$ {total_venta:,.2f}"
            
            saldo_anterior_formateado = f"C$ {saldo_anterior_total:,.2f}"
            abono_cliente_formateado = f"C$ {abono_cliente:,.2f}"
            nuevo_saldo_pendiente_formateado = f"C$ {nuevo_saldo_pendiente:,.2f}"
            
            # Calcular saldo total (venta + saldo anterior)
            saldo_total = venta_realizada + saldo_anterior_total
            
            return render_template('vendedor/ventas/ticket_venta_ruta.html',
                                 ticket=ticket_data,
                                 mostrar_seccion_credito=mostrar_seccion_credito,
                                 mensaje_credito=mensaje_credito,
                                 facturas_pendientes=facturas_pendientes if facturas_pendientes else [],
                                 abonos_detalle=abonos_detalle if abonos_detalle else [],
                                 proximo_vencimiento=proximo_vencimiento,
                                 # Variables para el formato solicitado
                                 venta_realizada=venta_realizada,
                                 venta_realizada_formateada=venta_realizada_formateada,
                                 saldo_anterior=saldo_anterior_total,
                                 saldo_anterior_formateado=saldo_anterior_formateado,
                                 saldo_total=saldo_total,
                                 abono_cliente=abono_cliente,
                                 abono_cliente_formateado=abono_cliente_formateado,
                                 concepto_abono=concepto_abono,
                                 fecha_abono=fecha_abono,
                                 nuevo_saldo_pendiente=nuevo_saldo_pendiente,
                                 nuevo_saldo_pendiente_formateado=nuevo_saldo_pendiente_formateado,
                                 auto_print=auto_print,
                                 now=datetime.now())
                             
    except Exception as e:
        print(f"Error en vendedor_generar_ticket_ruta: {str(e)}")
        traceback.print_exc()
        flash(f'Error al generar ticket: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_venta_detalle', id_venta=id_venta))


@vendedor_bp.route('/vendedor/venta/<int:id_venta>/detalle')
@vendedor_required
def vendedor_venta_detalle(id_venta):
    """Ver detalle completo de una venta específica
    """
    try:
        id_vendedor = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Verificar que la venta pertenezca al vendedor actual
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM facturacion_ruta fr
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                WHERE fr.ID_FacturaRuta = %s
                AND av.ID_Usuario = %s
            """, (id_venta, id_vendedor))
            verificar = cursor.fetchone()
            
            if verificar['total'] == 0:
                flash('Venta no encontrada o no tienes permiso para verla', 'error')
                return redirect(url_for('vendedor.vendedor_ventas'))
            
            # Obtener información general de la venta
            cursor.execute("""
                SELECT fr.ID_FacturaRuta,
                       fr.Fecha,
                       fr.Credito_Contado,
                       fr.Observacion,
                       fr.Estado,
                       fr.Fecha_Creacion,
                       c.ID_Cliente,
                       c.Nombre as Cliente,
                       c.RUC_CEDULA,
                       c.Telefono,
                       c.Direccion,
                       u.NombreUsuario as Vendedor,
                       u.NombreUsuario,
                       r.Nombre_Ruta,
                       av.Fecha_Asignacion,
                       CASE 
                           WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                           ELSE 'CRÉDITO'
                       END as Tipo_Venta,
                       COALESCE((
                           SELECT SUM(Saldo_Pendiente) 
                           FROM cuentas_por_cobrar 
                           WHERE Num_Documento = CONCAT('FAC-R', fr.ID_FacturaRuta)
                       ), 0) as Saldo_Pendiente
                FROM facturacion_ruta fr
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE fr.ID_FacturaRuta = %s
            """, (id_venta,))
            
            venta_data = cursor.fetchone()
            if not venta_data:
                flash('Venta no encontrada', 'error')
                return redirect(url_for('vendedor.vendedor_ventas'))
            
            # Convertir a diccionario
            venta = dict(venta_data)
            
            
            # Función helper para formatear fechas (opcional, para no repetir código)
            def formatear_fecha(valor, formato_salida='%d/%m/%Y', incluir_hora=False):
                if not valor:
                    return 'Fecha no disponible'
                
                if isinstance(valor, datetime):
                    return valor.strftime(formato_salida + (' %H:%M' if incluir_hora else ''))
                
                try:
                    if incluir_hora:
                        fecha_obj = datetime.strptime(str(valor), '%Y-%m-%d %H:%M:%S')
                    else:
                        fecha_obj = datetime.strptime(str(valor), '%Y-%m-%d')
                    return fecha_obj.strftime(formato_salida + (' %H:%M' if incluir_hora else ''))
                except:
                    return 'Fecha no disponible'
            
            # Formatear fechas
            venta['Fecha'] = formatear_fecha(venta.get('Fecha'))
            venta['Fecha_Creacion'] = formatear_fecha(venta.get('Fecha_Creacion'), incluir_hora=True)
            venta['Fecha_Asignacion'] = formatear_fecha(venta.get('Fecha_Asignacion'))
            
            # Obtener detalle de productos
            cursor.execute("""
                SELECT df.ID_DetalleRuta,
                       df.Cantidad,
                       df.Precio,
                       df.Total,
                       p.ID_Producto,
                       p.COD_Producto,
                       p.Descripcion as Producto,
                       um.Descripcion as Unidad_Medida
                FROM detalle_facturacion_ruta df
                INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE df.ID_FacturaRuta = %s
                ORDER BY df.ID_DetalleRuta
            """, (id_venta,))
            detalles = cursor.fetchall()
            
            # Calcular totales
            subtotal = 0
            for d in detalles:
                subtotal += float(d['Total'])
            
            # Obtener información de cuentas por cobrar si es crédito
            cuentas_cobrar = None
            pagos = []
            if venta['Credito_Contado'] == 2:
                cursor.execute("""
                    SELECT ID_Movimiento, 
                           Monto_Movimiento,
                           Saldo_Pendiente, 
                           Estado as Estado_CXC,
                           Fecha_Vencimiento,
                           DATEDIFF(CURDATE(), Fecha_Vencimiento) as Dias_Vencidos
                    FROM cuentas_por_cobrar
                    WHERE Num_Documento = %s
                """, (f"FAC-R{id_venta}",))
                
                cuenta_data = cursor.fetchone()
                if cuenta_data:
                    cuentas_cobrar = dict(cuenta_data)
                    cuentas_cobrar['Fecha_Vencimiento'] = formatear_fecha(cuentas_cobrar.get('Fecha_Vencimiento'))
                    
                    # Obtener pagos realizados si existen
                    cursor.execute("""
                        SELECT p.ID_Pago,
                               p.Fecha as Fecha_Pago,
                               p.Monto as Monto_Pagado,
                               mp.Nombre as Metodo_Pago,
                               p.Comentarios as Observacion
                        FROM pagos_cuentascobrar p
                        INNER JOIN metodos_pago mp ON p.ID_MetodoPago = mp.ID_MetodoPago
                        WHERE p.ID_Movimiento = %s
                        ORDER BY p.Fecha DESC
                    """, (cuentas_cobrar['ID_Movimiento'],))
                    
                    pagos_data = cursor.fetchall()
                    for pago in pagos_data:
                        pago_dict = dict(pago)
                        pago_dict['Fecha_Pago'] = formatear_fecha(pago_dict.get('Fecha_Pago'), incluir_hora=True)
                        pagos.append(pago_dict)
            
            # Obtener métodos de pago para el modal
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
            metodos_pago = cursor.fetchall()
            
        return render_template('vendedor/ventas/venta_detalle.html',
                             venta=venta,
                             detalles=detalles,
                             subtotal=subtotal,
                             cuentas_cobrar=cuentas_cobrar,
                             pagos=pagos,
                             metodos_pago=metodos_pago)
                             
    except Exception as e:
        print(f"Error en vendedor_venta_detalle: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar detalle: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_ventas'))


@vendedor_bp.route('/vendedor/venta/<int:id_venta>/anular', methods=['POST'])
@vendedor_required
def vendedor_venta_anular(id_venta):
    """Anular una venta (solo si es del día y está activa)
    """
    try:
        id_vendedor = current_user.id  # CORREGIDO: usar current_user.id
        motivo = request.form.get('motivo', 'Sin motivo especificado')
        
        with get_db_cursor(commit=True) as cursor:  # CORREGIDO: agregar commit=True
            from datetime import date
            # Verificar que la venta pertenezca al vendedor y sea del día
            cursor.execute("""
                SELECT fr.ID_FacturaRuta, fr.ID_Asignacion, fr.Credito_Contado,
                       dfr.ID_Producto, dfr.Cantidad
                FROM facturacion_ruta fr
                LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_FacturaRuta = %s 
                AND fr.ID_Usuario_Creacion = %s
                AND fr.Estado = 'Activa'
                AND DATE(fr.Fecha_Creacion) = %s
            """, (id_venta, id_vendedor, date.today()))
            venta_data = cursor.fetchall()
            
            if not venta_data:
                flash('No se puede anular la venta. Solo puedes anular ventas del día', 'error')
                return redirect(url_for('vendedor.vendedor_venta_detalle', id_venta=id_venta))
            
            # Devolver productos al inventario
            for item in venta_data:
                if item['ID_Producto']:
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad + %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (item['Cantidad'], item['ID_Asignacion'], item['ID_Producto']))
            
            # Si es crédito, anular cuenta por cobrar
            if venta_data[0]['Credito_Contado'] == 2:
                cursor.execute("""
                    UPDATE cuentas_por_cobrar 
                    SET Estado = 'Anulada'
                    WHERE Num_Documento = %s
                """, (f"FAC-R{id_venta}",))
            
            # Anular factura
            cursor.execute("""
                UPDATE facturacion_ruta 
                SET Estado = 'Anulada',
                    Observacion = CONCAT(COALESCE(Observacion, ''), ' | ANULADA: ', %s)
                WHERE ID_FacturaRuta = %s
            """, (motivo, id_venta))
            
            flash('Venta anulada exitosamente', 'success')
            
    except Exception as e:
        print(f"Error en vendedor_venta_anular: {str(e)}")
        flash(f'Error al anular venta: {str(e)}', 'error')
    
    return redirect(url_for('vendedor.vendedor_ventas'))


@vendedor_bp.route('/api/filtrar_ventas', methods=['POST'])
@vendedor_required
def api_filtrar_ventas():
    """API para filtrar ventas por fecha y ruta
    """
    try:
        id_vendedor = current_user.id
        fecha = request.form.get('fecha', 'hoy')
        id_ruta = request.form.get('ruta', '')  # Cambiado: valor por defecto vacío
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        
        with get_db_cursor(True) as cursor:
            # Primero obtener las asignaciones del vendedor
            cursor.execute("""
                SELECT ID_Asignacion 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s
            """, (id_vendedor,))
            asignaciones = cursor.fetchall()
            
            if not asignaciones:
                return jsonify({'success': True, 'ventas': []})
            
            ids_asignacion = [a['ID_Asignacion'] for a in asignaciones]
            placeholders = ','.join(['%s'] * len(ids_asignacion))
            
            # Construir condición de fecha
            fecha_cond = ""
            params = list(ids_asignacion)  # Iniciar con los IDs de asignación
            
            from datetime import datetime, timedelta
            
            if fecha == 'hoy':
                fecha_cond = "AND DATE(fr.Fecha) = CURDATE()"
            elif fecha == 'ayer':
                fecha_cond = "AND DATE(fr.Fecha) = CURDATE() - INTERVAL 1 DAY"
            elif fecha == 'semana':
                fecha_cond = "AND fr.Fecha >= CURDATE() - INTERVAL 7 DAY"
            elif fecha == 'mes':
                fecha_cond = "AND fr.Fecha >= CURDATE() - INTERVAL 30 DAY"
            elif fecha == 'personalizado' and fecha_inicio and fecha_fin:
                try:
                    # Intentar parsear en DD/MM/YYYY primero
                    try:
                        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%d/%m/%Y')
                        fecha_fin_obj = datetime.strptime(fecha_fin, '%d/%m/%Y')
                    except:
                        # Si falla, intentar en YYYY-MM-DD
                        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
                    
                    fecha_inicio_mysql = fecha_inicio_obj.strftime('%Y-%m-%d')
                    fecha_fin_mysql = fecha_fin_obj.strftime('%Y-%m-%d')
                    fecha_cond = "AND DATE(fr.Fecha) BETWEEN %s AND %s"
                    params.append(fecha_inicio_mysql)
                    params.append(fecha_fin_mysql)
                except Exception as e:
                    print(f"Error al parsear fechas: {e}")
                    fecha_cond = "AND DATE(fr.Fecha) = CURDATE()"
            
            # Construir condición de ruta
            ruta_cond = ""
            if id_ruta and id_ruta != '' and id_ruta != 'todas':
                # Validar que la ruta pertenezca al vendedor
                try:
                    if int(id_ruta) in ids_asignacion:
                        ruta_cond = "AND fr.ID_Asignacion = %s"
                        params.append(id_ruta)
                except:
                    pass
            
            # Consulta SQL
            query = f"""
                SELECT fr.ID_FacturaRuta, 
                       DATE_FORMAT(fr.Fecha, '%%d/%%m/%%Y') as Fecha,
                       fr.Fecha_Creacion,
                       fr.Credito_Contado,
                       fr.Observacion, 
                       fr.Estado, 
                       c.Nombre as Cliente, 
                       c.RUC_CEDULA,
                       c.Telefono,
                       r.Nombre_Ruta,
                       COALESCE(SUM(dfr.Total), 0) as Total_Venta,
                       CASE 
                           WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                           ELSE 'CRÉDITO'
                       END as Tipo_Venta,
                       CASE 
                           WHEN fr.Credito_Contado = 2 THEN (
                               SELECT COALESCE(SUM(Saldo_Pendiente), 0)
                               FROM cuentas_por_cobrar 
                               WHERE Num_Documento = CONCAT('FAC-R', fr.ID_FacturaRuta)
                           )
                           ELSE 0
                       END as Saldo_Pendiente
                FROM facturacion_ruta fr
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Asignacion IN ({placeholders})
                {fecha_cond}
                {ruta_cond}
                GROUP BY fr.ID_FacturaRuta
                ORDER BY fr.Fecha DESC, fr.ID_FacturaRuta DESC
            """
            
            cursor.execute(query, tuple(params))
            ventas_raw = cursor.fetchall()
            
            # Formatear para JSON
            ventas_list = []
            from datetime import datetime as dt
            
            for v in ventas_raw:
                # Calcular hora desde Fecha_Creacion
                hora = "00:00"
                if v.get('Fecha_Creacion'):
                    try:
                        if isinstance(v['Fecha_Creacion'], dt):
                            hora = v['Fecha_Creacion'].strftime('%H:%M')
                        else:
                            fecha_obj = dt.strptime(str(v['Fecha_Creacion']), '%Y-%m-%d %H:%M:%S')
                            hora = fecha_obj.strftime('%H:%M')
                    except:
                        hora = "00:00"
                
                ventas_list.append({
                    'ID_FacturaRuta': v['ID_FacturaRuta'],
                    'Fecha': v['Fecha'],
                    'Hora': hora,
                    'Cliente': v['Cliente'],
                    'RUC_CEDULA': v['RUC_CEDULA'] or 'N/A',
                    'Telefono': v['Telefono'] or '',
                    'Nombre_Ruta': v['Nombre_Ruta'],
                    'Total_Venta': float(v['Total_Venta']),
                    'Tipo_Venta': v['Tipo_Venta'],
                    'Estado': v['Estado'],
                    'Saldo_Pendiente': float(v['Saldo_Pendiente']) if v['Saldo_Pendiente'] else 0
                })
            
            return jsonify({'success': True, 'ventas': ventas_list})
            
    except Exception as e:
        print(f"Error en api_filtrar_ventas: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@vendedor_bp.route('/api/vendedor/verificar_stock_venta', methods=['POST'])
@vendedor_required
def api_verificar_stock_venta():
    """Verificar stock antes de sincronizar una venta offline"""
    try:
        data = request.get_json()
        productos = data.get('productos', [])
        id_asignacion = data.get('asignacion_id')
        
        with get_db_cursor() as cursor:
            errores = []
            for producto in productos:
                cursor.execute("""
                    SELECT ir.Cantidad, p.Descripcion
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    WHERE ir.ID_Asignacion = %s AND ir.ID_Producto = %s
                """, (id_asignacion, producto['id']))
                
                stock = cursor.fetchone()
                if not stock or float(stock['Cantidad']) < float(producto['cantidad']):
                    errores.append({
                        'producto_id': producto['id'],
                        'nombre': producto.get('nombre', stock['Descripcion'] if stock else 'Producto'),
                        'stock_disponible': float(stock['Cantidad']) if stock else 0,
                        'solicitado': float(producto['cantidad'])
                    })
            
            if errores:
                return jsonify({
                    'success': False,
                    'error': 'Stock insuficiente',
                    'detalles': errores
                }), 400
            
            return jsonify({'success': True})
            
    except Exception as e:
        print(f"Error en api_verificar_stock_venta: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@vendedor_bp.route('/api/vendedor/registrar_venta_offline', methods=['POST'])
@vendedor_required
def api_registrar_venta_offline():
    """Endpoint específico para registrar ventas offline sincronizadas"""
    try:
        id_vendedor = int(current_user.id)
        data = request.get_json()
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar asignación activa
            cursor.execute("""
                SELECT av.*, r.Nombre_Ruta, u.NombreUsuario as Nombre_Vendedor
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE av.ID_Usuario = %s 
                AND av.Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
            
            from datetime import date
            hoy_local = date.today()
            # Verificar/crear caja
            cursor.execute("""
                SELECT ID_Movimiento, Saldo_Acumulado
                FROM movimientos_caja_ruta 
                WHERE ID_Asignacion = %s 
                AND DATE(Fecha) = %s 
                AND Tipo = 'APERTURA'
                AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'], hoy_local))
            caja = cursor.fetchone()
            
            if not caja:
                # Crear apertura automática
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                     Tipo_Pago, Saldo_Acumulado, Estado)
                    VALUES (%s, %s, 'APERTURA', %s, 0.00, NULL, 0.00, 'ACTIVO')
                """, (
                    asignacion['ID_Asignacion'],
                    id_vendedor,
                    f"Apertura automática - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                ))
                
                cursor.execute("SELECT LAST_INSERT_ID() as ID_Movimiento")
                caja = cursor.fetchone()
            
            # Obtener saldo anterior del cliente
            cursor.execute("""
                SELECT COALESCE(Saldo_Pendiente_Total, 0) as Saldo_Anterior
                FROM clientes 
                WHERE ID_Cliente = %s
            """, (int(data['cliente_id']),))
            saldo_anterior = cursor.fetchone()['Saldo_Anterior']
            
            # Insertar factura
            cursor.execute("""
                INSERT INTO facturacion_ruta 
                (Fecha, ID_Cliente, ID_Asignacion, Credito_Contado, 
                 Observacion, Saldo_Anterior_Cliente, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Activa')
            """, (
                hoy_local,
                int(data['cliente_id']), 
                asignacion['ID_Asignacion'], 
                int(data['tipo_venta']),
                data.get('observacion', ''),
                saldo_anterior,
                asignacion['ID_Empresa'],
                id_vendedor
            ))
            
            id_factura = cursor.lastrowid
            
            # Insertar detalles y actualizar inventario
            total_venta = 0
            for producto in data['productos']:
                total_linea = float(producto['cantidad']) * float(producto['precio'])
                total_venta += total_linea
                
                cursor.execute("""
                    INSERT INTO detalle_facturacion_ruta
                    (ID_FacturaRuta, ID_Producto, Cantidad, Precio, Total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_factura, producto['id'], producto['cantidad'], 
                      producto['precio'], total_linea))
                
                # Actualizar inventario
                cursor.execute("""
                    UPDATE inventario_ruta 
                    SET Cantidad = Cantidad - %s
                    WHERE ID_Asignacion = %s AND ID_Producto = %s
                """, (producto['cantidad'], asignacion['ID_Asignacion'], producto['id']))
            
            # Registrar en caja según tipo de venta
            if data['tipo_venta'] == '1':  # Contado
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        ELSE Monto 
                    END), 0) as Saldo_Actual
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                      AND Estado = 'ACTIVO'
                      AND Tipo != 'CIERRE'
                """, (asignacion['ID_Asignacion'],))
                saldo_actual = float(cursor.fetchone()['Saldo_Actual'] or 0)
                nuevo_saldo = saldo_actual + total_venta
                
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                     Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                    VALUES (%s, %s, 'VENTA', %s, %s, 'CONTADO', %s, %s, %s, 'ACTIVO')
                """, (
                    asignacion['ID_Asignacion'],
                    id_vendedor,
                    f"Venta Contado Factura #{id_factura}",
                    total_venta,
                    id_factura,
                    int(data['cliente_id']),
                    nuevo_saldo
                ))
            else:  # Crédito
                # Crear cuenta por cobrar
                fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                cursor.execute("""
                    INSERT INTO cuentas_por_cobrar
                    (Fecha, ID_Cliente, Num_Documento, Observacion, Fecha_Vencimiento,
                     Tipo_Movimiento, Monto_Movimiento, ID_Empresa, Saldo_Pendiente,
                     ID_FacturaRuta, ID_Usuario_Creacion, Estado)
                    VALUES (CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente')
                """, (
                    int(data['cliente_id']),
                    f"FAC-R{id_factura}",
                    data.get('observacion', ''),
                    fecha_vencimiento,
                    2,  # Tipo_Movimiento (2=Venta)
                    total_venta,
                    asignacion['ID_Empresa'],
                    total_venta,
                    id_factura,
                    id_vendedor
                ))
                
                # Actualizar saldo del cliente
                cursor.execute("""
                    UPDATE clientes 
                    SET Saldo_Pendiente_Total = COALESCE(Saldo_Pendiente_Total, 0) + %s,
                        Fecha_Ultimo_Movimiento = NOW(),
                        ID_Ultima_Factura = %s
                    WHERE ID_Cliente = %s
                """, (total_venta, id_factura, int(data['cliente_id'])))
            
            # Procesar abono si existe
            if data.get('procesar_abono') == '1' and float(data.get('abono_monto', 0)) > 0:
                monto_abono = float(data['abono_monto'])
                try:
                    id_metodo_pago = int(data.get('abono_metodo_pago')) if data.get('abono_metodo_pago') else None
                except (ValueError, TypeError):
                    id_metodo_pago = None
                
                # Obtener facturas pendientes del cliente
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
                """, (int(data['cliente_id']),))
                
                facturas_pendientes = cursor.fetchall()
                
                if facturas_pendientes:
                    # Registrar movimiento de abono en caja
                    cursor.execute("""
                        SELECT COALESCE(SUM(CASE 
                            WHEN Tipo = 'GASTO' THEN -Monto 
                            ELSE Monto 
                        END), 0) as Saldo_Actual
                        FROM movimientos_caja_ruta
                        WHERE ID_Asignacion = %s 
                          AND Estado = 'ACTIVO'
                          AND Tipo != 'CIERRE'
                    """, (asignacion['ID_Asignacion'],))
                    saldo_actual = float(cursor.fetchone()['Saldo_Actual'] or 0)
                    nuevo_saldo_caja = saldo_actual + monto_abono
                    
                    cursor.execute("""
                        INSERT INTO movimientos_caja_ruta
                        (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                         Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                        VALUES (%s, %s, 'ABONO', %s, %s, %s, %s, %s, %s, 'ACTIVO')
                    """, (
                        asignacion['ID_Asignacion'],
                        id_vendedor,
                        f"Abono a cuenta - Factura #{id_factura}",
                        monto_abono,
                        'CONTADO' if data['tipo_venta'] == '1' else 'CREDITO',
                        id_factura,
                        int(data['cliente_id']),
                        nuevo_saldo_caja
                    ))
                    
                    id_movimiento_caja = cursor.lastrowid
                    
                    # Distribuir el abono
                    monto_restante = monto_abono
                    for factura in facturas_pendientes:
                        if monto_restante <= 0:
                            break
                            
                        saldo_factura = float(factura['Saldo_Pendiente'])
                        monto_aplicar = min(monto_restante, saldo_factura)
                        nuevo_saldo_factura = saldo_factura - monto_aplicar
                        nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0 else 'Pendiente'
                        
                        cursor.execute("""
                            UPDATE cuentas_por_cobrar
                            SET Saldo_Pendiente = %s, 
                                Estado = %s
                            WHERE ID_Movimiento = %s
                        """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                        
                        cursor.execute("""
                            INSERT INTO abonos_detalle
                            (ID_Movimiento_Caja, ID_Asignacion, ID_Usuario, ID_Cliente, 
                             ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo,
                             ID_MetodoPago)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento_caja,
                            asignacion['ID_Asignacion'],
                            id_vendedor,
                            int(data['cliente_id']),
                            factura['ID_Movimiento'],
                            monto_aplicar,
                            saldo_factura,
                            nuevo_saldo_factura,
                            id_metodo_pago
                        ))
                        
                        monto_restante -= monto_aplicar
                    
                    # Actualizar saldo del cliente
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total, 0) - %s),
                            Fecha_Ultimo_Pago = NOW()
                        WHERE ID_Cliente = %s
                    """, (monto_abono, int(data['cliente_id'])))
            
            return jsonify({
                'success': True,
                'id_venta': id_factura,
                'ticket_url': url_for('vendedor.vendedor_generar_ticket_ruta', id_venta=id_factura, autoPrint=1, _external=True)
            })
            
    except Exception as e:
        print(f"Error en api_registrar_venta_offline: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


