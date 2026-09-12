# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import convertir_hora_db, procesar_asignacion, procesar_lista_asignaciones

@vendedor_bp.route('/caja/mis_movimientos', methods=['GET'])
@vendedor_required
def mis_movimientos_caja():
    """Muestra los movimientos del vendedor actual en su ruta"""
    try:
        id_vendedor = current_user.id
        fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        
        # Obtener nombre del vendedor (con manejo seguro)
        nombre_vendedor = getattr(current_user, 'NombreUsuario', 
                                  getattr(current_user, 'username', 
                                         getattr(current_user, 'name', f"Vendedor {id_vendedor}")))
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s 
                  AND av.Estado = 'Activa'
                  AND av.Fecha_Asignacion <= %s
                  AND (av.Fecha_Finalizacion >= %s OR av.Fecha_Finalizacion IS NULL)
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (id_vendedor, fecha, fecha))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta activa asignada para esta fecha', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            # Verificar si ya hay apertura y cierre hoy - CORREGIDO
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN 1 ELSE 0 END), 0) as tiene_apertura,
                    COALESCE(SUM(CASE WHEN Tipo = 'CIERRE' THEN 1 ELSE 0 END), 0) as tiene_cierre
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            estado_dia = cursor.fetchone()
            
            # Resumen del día - CORREGIDO con COALESCE
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN Monto ELSE 0 END), 0) as Apertura,
                    COALESCE(SUM(CASE WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CONTADO' THEN Monto ELSE 0 END), 0) as Ventas_Contado,
                    COALESCE(COUNT(CASE WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CREDITO' THEN 1 END), 0) as Ventas_Credito_Count,
                    COALESCE(SUM(CASE WHEN Tipo = 'ABONO' THEN Monto ELSE 0 END), 0) as Total_Abonos,
                    COALESCE(COUNT(CASE WHEN Tipo = 'ABONO' THEN 1 END), 0) as Cantidad_Abonos,
                    COALESCE(SUM(CASE WHEN Tipo = 'GASTO' THEN Monto ELSE 0 END), 0) as Gastos,
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        WHEN Tipo IN ('APERTURA', 'VENTA', 'ABONO') AND Tipo != 'CIERRE' THEN Monto 
                        ELSE 0 
                    END), 0) as Saldo_Actual,
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CONTADO' THEN Monto 
                        WHEN Tipo = 'ABONO' THEN Monto 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        ELSE 0 
                    END), 0) as Total_Movimientos
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            resumen = cursor.fetchone()
            
            # Movimientos detallados
            cursor.execute("""
                SELECT 
                    m.ID_Movimiento,
                    m.ID_Asignacion,
                    m.ID_Usuario,
                    DATE_FORMAT(m.Fecha, '%d/%m/%Y %H:%i') as Fecha_Formateada,
                    m.Fecha as Fecha_Original,
                    m.Tipo,
                    m.Concepto,
                    m.Monto,
                    m.Tipo_Pago,
                    m.ID_FacturaRuta,
                    m.ID_Cliente,
                    m.Saldo_Acumulado,
                    m.Estado as Estado_Movimiento,
                    c.Nombre as Nombre_Cliente,
                    c.RUC_CEDULA,
                    c.Telefono as Telefono_Cliente
                FROM movimientos_caja_ruta m
                LEFT JOIN clientes c ON m.ID_Cliente = c.ID_Cliente
                WHERE m.ID_Asignacion = %s 
                  AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
            """, (asignacion['ID_Asignacion'],))
            
            movimientos = cursor.fetchall()
            
            # Estadísticas - CORREGIDO con COALESCE
            cursor.execute("""
                SELECT 
                    COALESCE(COUNT(DISTINCT ID_Cliente), 0) as clientes_Atendidos,
                    COALESCE(COUNT(CASE WHEN Tipo = 'VENTA' THEN 1 END), 0) as Total_Ventas,
                    COALESCE(COUNT(CASE WHEN Tipo = 'ABONO' THEN 1 END), 0) as Total_Abonos_Dia,
                    COALESCE(COUNT(CASE WHEN Tipo = 'GASTO' THEN 1 END), 0) as Total_Gastos_Dia
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            estadisticas = cursor.fetchone()
            
            # Calcular valores seguros para el template - CORREGIDO
            tiene_apertura = int(estado_dia['tiene_apertura'] or 0) > 0
            tiene_cierre = int(estado_dia['tiene_cierre'] or 0) > 0
            
            # Asegurar que todos los valores del resumen sean números
            resumen_seguro = {
                'apertura': float(resumen['Apertura'] or 0),
                'ventas_contado': float(resumen['Ventas_Contado'] or 0),
                'ventas_credito_count': int(resumen['Ventas_Credito_Count'] or 0),
                'total_abonos': float(resumen['Total_Abonos'] or 0),
                'cantidad_abonos': int(resumen['Cantidad_Abonos'] or 0),
                'gastos': float(resumen['Gastos'] or 0),
                'saldo_actual': float(resumen['Saldo_Actual'] or 0),
                'total_movimientos': float(resumen['Total_Movimientos'] or 0)
            }
            
            # El saldo esperado para el cierre es exactamente el saldo actual en caja
            saldo_esperado_cierre = resumen_seguro['saldo_actual']
            
            # Estadísticas seguras
            estadisticas_seguras = {
                'clientes_atendidos': int(estadisticas['clientes_Atendidos'] or 0),
                'total_ventas': int(estadisticas['Total_Ventas'] or 0),
                'total_abonos_dia': int(estadisticas['Total_Abonos_Dia'] or 0),
                'total_gastos_dia': int(estadisticas['Total_Gastos_Dia'] or 0)
            }
            
            return render_template('vendedor/caja/mis_movimientos.html',
                                 vendedor=nombre_vendedor,
                                 ruta=asignacion['Nombre_Ruta'],
                                 id_asignacion=asignacion['ID_Asignacion'],
                                 fecha=fecha,
                                 tiene_apertura=tiene_apertura,
                                 tiene_cierre=tiene_cierre,
                                 resumen=resumen_seguro,
                                 saldo_esperado_cierre=saldo_esperado_cierre,
                                 estadisticas=estadisticas_seguras,
                                 movimientos=movimientos)
            
    except Exception as e:
        print(f"Error en mis_movimientos_caja: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar los movimientos: {str(e)}', 'danger')
        return redirect(url_for('vendedor.vendedor_dashboard'))


@vendedor_bp.route('/caja/apertura_modal', methods=['POST'])
@vendedor_required
def apertura_caja_modal():
    """Procesa la apertura de caja desde el modal"""
    try:
        data = request.get_json()
        id_vendedor = current_user.id
        monto = float(data.get('monto', 0))
        observacion = data.get('observacion', '')
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        
        with get_db_cursor(commit=True) as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s 
                  AND Estado = 'Activa'
                  AND Fecha_Asignacion <= %s
                  AND (Fecha_Finalizacion >= %s OR Fecha_Finalizacion IS NULL)
                LIMIT 1
            """, (id_vendedor, fecha_actual, fecha_actual))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'})
            
            # Limitar la longitud del concepto a 200 caracteres (longitud de columna varchar(200))
            concepto = f"Apertura de caja: {observacion}" if observacion else "Apertura de caja"
            concepto = concepto[:200]
            
            # Insertar apertura
            cursor.execute("""
                INSERT INTO movimientos_caja_ruta 
                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Estado)
                VALUES (%s, %s, 'APERTURA', %s, %s, 'ACTIVO')
            """, (
                asignacion['ID_Asignacion'],
                id_vendedor,
                concepto,
                monto
            ))
            
            return jsonify({'success': True, 'message': 'Apertura realizada con éxito'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@vendedor_bp.route('/caja/cierre_modal', methods=['POST'])
@vendedor_required
def cierre_caja_modal():
    """Procesa el cierre de caja desde el modal"""
    try:
        data = request.get_json()
        id_vendedor = current_user.id
        monto_real = float(data.get('monto_real', 0))
        observacion = data.get('observacion', '')
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        
        with get_db_cursor(commit=True) as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s 
                  AND Estado = 'Activa'
                  AND Fecha_Asignacion <= %s
                  AND (Fecha_Finalizacion >= %s OR Fecha_Finalizacion IS NULL)
                LIMIT 1
            """, (id_vendedor, fecha_actual, fecha_actual))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'})
            
            # Calcular saldo esperado
            cursor.execute("""
                SELECT COALESCE(SUM(CASE 
                    WHEN Tipo = 'GASTO' THEN -Monto 
                    WHEN Tipo IN ('APERTURA', 'VENTA', 'ABONO') THEN Monto 
                    ELSE 0 
                END), 0) as Saldo_Esperado
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            saldo = cursor.fetchone()
            saldo_esperado = float(saldo['Saldo_Esperado'])
            diferencia = monto_real - saldo_esperado
            
            # Limitar la longitud del concepto a 200 caracteres (longitud de columna varchar(200))
            concepto = f"Cierre de caja - Diferencia: C$ {diferencia:,.2f}. {observacion}" if observacion else f"Cierre de caja - Diferencia: C$ {diferencia:,.2f}"
            concepto = concepto[:200]
            
            # Insertar cierre
            cursor.execute("""
                INSERT INTO movimientos_caja_ruta 
                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Estado)
                VALUES (%s, %s, 'CIERRE', %s, %s, 'ACTIVO')
            """, (
                asignacion['ID_Asignacion'],
                id_vendedor,
                concepto,
                monto_real
            ))
            
            return jsonify({
                'success': True, 
                'message': 'Cierre realizado con éxito',
                'diferencia': diferencia,
                'saldo_esperado': saldo_esperado
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@vendedor_bp.route('/vendedor/gastos', methods=['GET', 'POST'])
@vendedor_required
def vendedor_gastos():
    """
    Ruta para gestionar los gastos de ruta/compras del vendedor durante su trayecto del dia.
    """
    
    # Obtener el ID del usuario actual (asumiendo que está en sesión)
    usuario_actual = current_user.id
    nombre_ruta = "Ruta No Definida"
    
    # Para GET y POST necesitamos la asignación activa primero
    try:
        with get_db_cursor() as cursor:
            # Obtener la asignación activa del vendedor (compatible con asignaciones continuas y datos de vehículo)
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, av.Fecha_Asignacion, r.Nombre_Ruta,
                       av.ID_Vehiculo, v.Placa, v.Marca, v.Modelo, v.Tipo_Combustible, av.ID_Empresa
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                WHERE av.ID_Usuario = %s 
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion <= CURDATE()
                AND (av.Fecha_Finalizacion >= CURDATE() OR av.Fecha_Finalizacion IS NULL)
                ORDER BY av.Fecha_Asignacion DESC 
                LIMIT 1
            """, (usuario_actual,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta activa asignada para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            id_asignacion = asignacion['ID_Asignacion']
            nombre_ruta = asignacion['Nombre_Ruta'] or "Ruta Activa"
    except Exception as e:
        flash(f'Error al verificar asignación: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))
    
    # Procesar el formulario cuando es POST (Gasto General)
    if request.method == 'POST':
        concepto = request.form.get('concepto', '').strip()
        monto = request.form.get('monto', '').strip()
        tipo_pago = request.form.get('tipo_pago', 'CONTADO')
        
        # Validaciones básicas
        if not concepto or not monto:
            flash('El concepto y el monto son obligatorios', 'error')
            return redirect(url_for('vendedor.vendedor_gastos'))
        
        try:
            monto = float(monto)
            if monto <= 0:
                flash('El monto debe ser mayor a cero', 'error')
                return redirect(url_for('vendedor.vendedor_gastos'))
        except ValueError:
            flash('El monto debe ser un número válido', 'error')
            return redirect(url_for('vendedor.vendedor_gastos'))
        
        # Usamos get_db_cursor con commit=True para que haga commit automático
        try:
            with get_db_cursor(commit=True) as cursor:
                # Obtener el saldo acumulado actual dinámicamente sumando todos los movimientos del día del usuario
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        WHEN Tipo IN ('APERTURA', 'VENTA', 'ABONO') AND Tipo != 'CIERRE' THEN Monto 
                        ELSE 0 
                    END), 0) as Saldo_Actual
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND Estado = 'ACTIVO'
                """, (id_asignacion,))
                
                ultimo_movimiento = cursor.fetchone()
                saldo_anterior = float(ultimo_movimiento['Saldo_Actual']) if ultimo_movimiento else 0.0
                
                # Validar que el gasto no exceda el saldo actual en caja
                if monto > saldo_anterior:
                    flash(f'El monto del gasto (C$ {monto:,.2f}) supera el saldo actual en caja (C$ {saldo_anterior:,.2f})', 'error')
                    return redirect(url_for('vendedor.vendedor_gastos'))
                
                # Calcular nuevo saldo (el gasto resta del saldo)
                nuevo_saldo = saldo_anterior - monto
                
                # Insertar el nuevo gasto en movimientos_caja_ruta
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta 
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Tipo_Pago, Saldo_Acumulado, Estado, Fecha)
                    VALUES (%s, %s, 'GASTO', %s, %s, %s, %s, 'ACTIVO', NOW())
                """, (id_asignacion, usuario_actual, concepto[:200], monto, tipo_pago, nuevo_saldo))
                
                flash('Gasto registrado exitosamente', 'success')
            
        except Exception as e:
            flash(f'Error al registrar el gasto: {str(e)}', 'error')
            print(f"Error en vendedor_gastos POST: {e}")
        
        return redirect(url_for('vendedor.vendedor_gastos'))
    
    # Para GET: obtener los gastos del día y lista de vehículos disponibles
    try:
        with get_db_cursor() as cursor:
            # Obtener vehículos disponibles para el modal de combustible
            id_empresa = asignacion.get('ID_Empresa') or 1
            cursor.execute("""
                SELECT ID_Vehiculo, Placa, Marca, Modelo, Tipo_Combustible,
                       CONCAT(Placa, ' - ', Marca, ' ', Modelo) AS Descripcion
                FROM vehiculos
                WHERE ID_Empresa = %s AND Estado != 'Inactivo'
                ORDER BY Placa
            """, (id_empresa,))
            vehiculos_disponibles = cursor.fetchall()

            # Obtener todos los gastos del día para esta asignación
            cursor.execute("""
                SELECT m.ID_Movimiento, m.Concepto, m.Monto, m.Tipo_Pago, 
                       m.Fecha,
                       m.Saldo_Acumulado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Asignacion = %s 
                AND m.Tipo = 'GASTO'
                AND m.Estado = 'ACTIVO'
                AND DATE(m.Fecha) = CURDATE()
                ORDER BY m.Fecha DESC
            """, (id_asignacion,))
            
            gastos = cursor.fetchall()
            
            # Formatear datos para la plantilla
            for gasto in gastos:
                if gasto.get('Monto') is not None:
                    gasto['Monto'] = float(gasto['Monto'])
                if gasto.get('Saldo_Acumulado') is not None:
                    gasto['Saldo_Acumulado'] = float(gasto['Saldo_Acumulado'])
                
                # Identificar si es gasto de combustible
                gasto['Es_Combustible'] = 'combustible' in (gasto.get('Concepto') or '').lower() or 'gasolina' in (gasto.get('Concepto') or '').lower() or 'diesel' in (gasto.get('Concepto') or '').lower()
                
                # Formatear Hora de forma robusta
                fecha_val = gasto.get('Fecha')
                if isinstance(fecha_val, datetime):
                    gasto['Hora'] = fecha_val.strftime('%I:%M %p')
                elif hasattr(fecha_val, 'strftime'):
                    gasto['Hora'] = fecha_val.strftime('%I:%M %p')
                elif isinstance(fecha_val, str):
                    try:
                        dt = datetime.strptime(fecha_val, '%Y-%m-%d %H:%M:%S')
                        gasto['Hora'] = dt.strftime('%I:%M %p')
                    except Exception:
                        try:
                            dt = datetime.strptime(fecha_val[:19], '%Y-%m-%dT%H:%M:%S')
                            gasto['Hora'] = dt.strftime('%I:%M %p')
                        except Exception:
                            gasto['Hora'] = fecha_val[11:16] if len(fecha_val) >= 16 else fecha_val
                elif fecha_val:
                    gasto['Hora'] = str(fecha_val)
                else:
                    gasto['Hora'] = '--:--'
            
            # Calcular total de gastos del día
            cursor.execute("""
                SELECT COALESCE(SUM(Monto), 0) as Total_Gastos
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                AND Tipo = 'GASTO'
                AND Estado = 'ACTIVO'
                AND DATE(Fecha) = CURDATE()
            """, (id_asignacion,))
            
            total_gastos = cursor.fetchone()['Total_Gastos']
            total_gastos = float(total_gastos) if total_gastos is not None else 0
            
            # Obtener saldo actual dinámicamente sumando todos los movimientos de la asignación del día
            cursor.execute("""
                SELECT COALESCE(SUM(CASE 
                    WHEN Tipo = 'GASTO' THEN -Monto 
                    WHEN Tipo IN ('APERTURA', 'VENTA', 'ABONO') AND Tipo != 'CIERRE' THEN Monto 
                    ELSE 0 
                END), 0) as Saldo_Actual
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                AND Estado = 'ACTIVO'
            """, (id_asignacion,))
            
            saldo_actual_res = cursor.fetchone()
            saldo_actual = float(saldo_actual_res['Saldo_Actual']) if saldo_actual_res else 0.0
            
    except Exception as e:
        print(f"Error en vendedor_gastos GET: {e}")
        gastos = []
        total_gastos = 0
        saldo_actual = 0
        vehiculos_disponibles = []
        flash('Error al cargar los gastos', 'error')
    
    return render_template('vendedor/gastos/gastos.html', 
                         gastos=gastos, 
                         total_gastos=total_gastos,
                         saldo_actual=saldo_actual,
                         asignacion=asignacion,
                         ruta=nombre_ruta,
                         vehiculos_disponibles=vehiculos_disponibles,
                         fecha_actual=datetime.now().strftime('%d/%m/%Y'))


@vendedor_bp.route('/vendedor/gastos/combustible', methods=['POST'])
@vendedor_required
def vendedor_gastos_combustible():
    """
    Ruta especializada para registrar gasto de combustible con auditoría vehicular completa.
    Actualiza:
    1. movimientos_caja_ruta (Tipo = 'GASTO')
    2. gastos_generales (Tipo: Vehículos, Subcategoría: Combustible)
    3. gastos_vehiculo_detalle (Kilometraje, Taller/Gasolinera, Tipo_Mantenimiento = 'COMBUSTIBLE')
    """
    usuario_actual = current_user.id
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Vehiculo, av.ID_Empresa,
                       v.Placa, v.Marca, v.Modelo, v.Tipo_Combustible
                FROM asignacion_vendedores av
                LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                WHERE av.ID_Usuario = %s 
                  AND av.Estado = 'Activa'
                  AND av.Fecha_Asignacion <= CURDATE()
                  AND (av.Fecha_Finalizacion >= CURDATE() OR av.Fecha_Finalizacion IS NULL)
                ORDER BY av.Fecha_Asignacion DESC 
                LIMIT 1
            """, (usuario_actual,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta activa asignada para registrar combustible', 'warning')
                return redirect(request.referrer or url_for('vendedor.vendedor_dashboard'))
                
            id_asignacion = asignacion['ID_Asignacion']
            id_empresa = asignacion.get('ID_Empresa') or 1
    except Exception as e:
        flash(f'Error al verificar asignación: {str(e)}', 'error')
        return redirect(request.referrer or url_for('vendedor.vendedor_dashboard'))
        
    # Extraer parámetros del formulario
    monto = request.form.get('monto', '').strip()
    id_vehiculo = request.form.get('id_vehiculo') or asignacion.get('ID_Vehiculo')
    kilometraje = request.form.get('kilometraje', '').strip() or None
    tipo_combustible = request.form.get('tipo_combustible', '').strip() or (asignacion.get('Tipo_Combustible') or 'Diesel')
    
    if not monto:
        flash('El monto de combustible es obligatorio', 'error')
        return redirect(request.referrer or url_for('vendedor.vendedor_gastos'))
        
    try:
        monto = float(monto)
        if monto <= 0:
            flash('El monto debe ser mayor a cero', 'error')
            return redirect(request.referrer or url_for('vendedor.vendedor_gastos'))
    except ValueError:
        flash('El monto debe ser un número válido', 'error')
        return redirect(request.referrer or url_for('vendedor.vendedor_gastos'))
        
    km_num = None
    if kilometraje:
        try:
            km_num = int(str(kilometraje).replace(',', '').replace('.', '').replace(' ', ''))
        except ValueError:
            km_num = None
            
    try:
        with get_db_cursor(commit=True) as cursor:
            # Obtener datos del vehículo seleccionado
            placa_vehiculo = asignacion.get('Placa') or 'Vehículo'
            if id_vehiculo:
                cursor.execute("SELECT Placa, Marca, Modelo FROM vehiculos WHERE ID_Vehiculo = %s", (id_vehiculo,))
                v_info = cursor.fetchone()
                if v_info:
                    placa_vehiculo = v_info['Placa']
                    
            # 1. Insertar en gastos_generales (ID_Tipo_Gasto = 2 [Vehículos], ID_Subcategoria = 1 [Combustible], Metodo_Pago = 'TRANSFERENCIA' por convenio)
            detalles_txt = ["Estación de Servicio San José"]
            if km_num:
                detalles_txt.append(f"Odómetro: {km_num:,} km")
            descripcion_gasto = f"Carga de combustible {tipo_combustible} para {placa_vehiculo} ({', '.join(detalles_txt)})"
            
            cursor.execute("""
                INSERT INTO gastos_generales (
                    ID_Tipo_Gasto, ID_Subcategoria, Fecha, Monto, Descripcion,
                    N_Factura, ID_Proveedor, ID_Vehiculo, Metodo_Pago, 
                    ID_Empresa, Estado, ID_Usuario_Registro
                ) VALUES (
                    2, 1, CURDATE(), %s, %s,
                    NULL, NULL, %s, 'TRANSFERENCIA',
                    %s, 'Activo', %s
                )
            """, (
                monto, descripcion_gasto[:500],
                id_vehiculo if id_vehiculo else None,
                id_empresa, usuario_actual
            ))
            id_gasto_general = cursor.lastrowid
            
            # 2. Insertar en gastos_vehiculo_detalle para auditoría vehicular
            if id_vehiculo:
                cursor.execute("""
                    INSERT INTO gastos_vehiculo_detalle (
                        ID_Gasto, ID_Vehiculo, Kilometraje, Tipo_Mantenimiento, Taller
                    ) VALUES (%s, %s, %s, 'COMBUSTIBLE', 'Estación de Servicio San José')
                """, (id_gasto_general, id_vehiculo, km_num))
                
            flash(f'⛽ Carga de combustible registrada (Estación de Servicio San José) por C$ {monto:,.2f}', 'success')
    except Exception as e:
        flash(f'Error al registrar el gasto de combustible: {str(e)}', 'error')
        print(f"Error en vendedor_gastos_combustible POST: {e}")
        
    return redirect(request.referrer or url_for('vendedor.vendedor_gastos'))


