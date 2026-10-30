# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import (
    convertir_hora_db,
    procesar_asignacion,
    procesar_lista_asignaciones,
    obtener_asignacion_activa,
    calcular_saldo_caja_ruta
)

@vendedor_bp.route('/caja/mis_movimientos', methods=['GET'])
@vendedor_required
def mis_movimientos_caja():
    """Muestra los movimientos del vendedor actual regidos por su asignación activa"""
    try:
        id_vendedor = current_user.id
        fecha = datetime.now().strftime('%Y-%m-%d')
        
        # Obtener nombre del vendedor (con manejo seguro)
        nombre_vendedor = getattr(current_user, 'NombreUsuario', 
                                  getattr(current_user, 'username', 
                                         getattr(current_user, 'name', f"Vendedor {id_vendedor}")))
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa (todo el flujo se rige por la asignación vigente)
            asignacion = obtener_asignacion_activa(cursor, id_vendedor)
            
            if not asignacion:
                flash('No tienes una ruta activa asignada actualmente', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            # Verificar si ya hay apertura y cierre en esta asignación
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN 1 ELSE 0 END), 0) as tiene_apertura,
                    COALESCE(SUM(CASE WHEN Tipo = 'CIERRE' THEN 1 ELSE 0 END), 0) as tiene_cierre
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            estado_dia = cursor.fetchone()
            
            # Resumen de la asignación activa
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN Monto ELSE 0 END), 0) as Apertura,
                    COALESCE(SUM(CASE WHEN Tipo = 'VENTA' AND (Tipo_Pago = 'CONTADO' OR Tipo_Pago IS NULL) THEN Monto ELSE 0 END), 0) as Ventas_Contado,
                    COALESCE(COUNT(CASE WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CREDITO' THEN 1 END), 0) as Ventas_Credito_Count,
                    COALESCE(SUM(CASE WHEN Tipo = 'ABONO' THEN Monto ELSE 0 END), 0) as Total_Abonos,
                    COALESCE(COUNT(CASE WHEN Tipo = 'ABONO' THEN 1 END), 0) as Cantidad_Abonos,
                    COALESCE(SUM(CASE WHEN Tipo = 'GASTO' THEN Monto ELSE 0 END), 0) as Gastos,
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        WHEN Tipo = 'CIERRE' THEN 0
                        WHEN Tipo IN ('APERTURA', 'ABONO') THEN Monto
                        WHEN Tipo = 'VENTA' AND (Tipo_Pago = 'CONTADO' OR Tipo_Pago IS NULL) THEN Monto
                        ELSE 0 
                    END), 0) as Saldo_Actual,
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'VENTA' AND (Tipo_Pago = 'CONTADO' OR Tipo_Pago IS NULL) THEN Monto 
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
                ORDER BY m.Fecha DESC, m.ID_Movimiento DESC
            """, (asignacion['ID_Asignacion'],))
            
            movimientos = cursor.fetchall()
            
            # Estadísticas de la asignación
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
            
            # Calcular valores seguros para el template
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
                                 asignacion=asignacion,
                                 id_asignacion=asignacion['ID_Asignacion'],
                                 fecha=asignacion.get('Fecha_Asignacion_str') or fecha,
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
    """Procesa la apertura de caja desde el modal validando no duplicar aperturas"""
    try:
        data = request.get_json() or {}
        id_vendedor = current_user.id
        monto = float(data.get('monto', 0))
        observacion = (data.get('observacion') or '').strip()
        
        if monto < 0:
            return jsonify({'success': False, 'error': 'El monto de apertura no puede ser negativo'}), 400
        
        with get_db_cursor(commit=True) as cursor:
            asignacion = obtener_asignacion_activa(cursor, id_vendedor)
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa asignada'})
            
            # Prevenir doble apertura en la misma asignación
            cursor.execute("""
                SELECT ID_Movimiento
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s
                  AND Tipo = 'APERTURA'
                  AND Estado = 'ACTIVO'
                LIMIT 1
            """, (asignacion['ID_Asignacion'],))
            if cursor.fetchone():
                return jsonify({'success': False, 'error': 'La caja ya cuenta con una apertura activa en esta asignación'})
            
            # Limitar la longitud del concepto a 200 caracteres (longitud de columna varchar(200))
            concepto = f"Apertura de caja: {observacion}" if observacion else "Apertura de caja"
            concepto = concepto[:200]
            
            # Insertar apertura con Saldo_Acumulado inicializado
            cursor.execute("""
                INSERT INTO movimientos_caja_ruta 
                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Saldo_Acumulado, Estado)
                VALUES (%s, %s, 'APERTURA', %s, %s, %s, 'ACTIVO')
            """, (
                asignacion['ID_Asignacion'],
                id_vendedor,
                concepto,
                monto,
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
        data = request.get_json() or {}
        id_vendedor = current_user.id
        monto_real = float(data.get('monto_real', 0))
        observacion = (data.get('observacion') or '').strip()
        
        with get_db_cursor(commit=True) as cursor:
            asignacion = obtener_asignacion_activa(cursor, id_vendedor)
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa asignada'})
            
            saldo_esperado = calcular_saldo_caja_ruta(cursor, asignacion['ID_Asignacion'])
            diferencia = monto_real - saldo_esperado
            
            # Limitar la longitud del concepto a 200 caracteres (longitud de columna varchar(200))
            concepto = f"Cierre de caja - Diferencia: C$ {diferencia:,.2f}. {observacion}" if observacion else f"Cierre de caja - Diferencia: C$ {diferencia:,.2f}"
            concepto = concepto[:200]
            
            # Si ya existía un cierre previo para esta asignación, anularlo para no duplicar cierres
            cursor.execute("""
                UPDATE movimientos_caja_ruta
                SET Estado = 'ANULADO'
                WHERE ID_Asignacion = %s AND Tipo = 'CIERRE' AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))

            # Insertar cierre
            cursor.execute("""
                INSERT INTO movimientos_caja_ruta 
                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Saldo_Acumulado, Estado)
                VALUES (%s, %s, 'CIERRE', %s, %s, %s, 'ACTIVO')
            """, (
                asignacion['ID_Asignacion'],
                id_vendedor,
                concepto,
                monto_real,
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
    Ruta para gestionar los gastos de ruta/compras del vendedor durante su asignación activa.
    Incluye gastos en efectivo de caja y visualización de cargas de combustible por convenio.
    """
    usuario_actual = current_user.id
    nombre_ruta = "Ruta No Definida"
    
    # Para GET y POST necesitamos la asignación activa primero
    try:
        with get_db_cursor() as cursor:
            asignacion = obtener_asignacion_activa(cursor, usuario_actual)
            
            if not asignacion:
                flash('No tienes una ruta activa asignada actualmente', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            id_asignacion = asignacion['ID_Asignacion']
            nombre_ruta = asignacion['Nombre_Ruta'] or "Ruta Activa"
    except Exception as e:
        flash(f'Error al verificar asignación: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))
    
    # Procesar el formulario cuando es POST (Gasto General en Efectivo)
    if request.method == 'POST':
        concepto = request.form.get('concepto', '').strip()
        monto = request.form.get('monto', '').strip()
        tipo_pago = request.form.get('tipo_pago', 'CONTADO')
        
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
        
        try:
            with get_db_cursor(commit=True) as cursor:
                saldo_anterior = calcular_saldo_caja_ruta(cursor, id_asignacion)
                
                if monto > saldo_anterior:
                    flash(f'El monto del gasto (C$ {monto:,.2f}) supera el saldo actual en caja (C$ {saldo_anterior:,.2f})', 'error')
                    return redirect(url_for('vendedor.vendedor_gastos'))
                
                nuevo_saldo = saldo_anterior - monto
                
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta 
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Tipo_Pago, Saldo_Acumulado, Estado, Fecha)
                    VALUES (%s, %s, 'GASTO', %s, %s, %s, %s, 'ACTIVO', NOW())
                """, (id_asignacion, usuario_actual, concepto[:200], monto, tipo_pago, nuevo_saldo))
                
                flash('Gasto en efectivo registrado exitosamente', 'success')
            
        except Exception as e:
            flash(f'Error al registrar el gasto: {str(e)}', 'error')
            print(f"Error en vendedor_gastos POST: {e}")
        
        return redirect(url_for('vendedor.vendedor_gastos'))
    
    # Para GET: obtener los gastos en efectivo de la asignación, cargas de combustible (convenio) y vehículos disponibles
    try:
        with get_db_cursor() as cursor:
            id_empresa = asignacion.get('ID_Empresa') or session.get('id_empresa', 1)
            cursor.execute("""
                SELECT ID_Vehiculo, Placa, Marca, Modelo, Tipo_Combustible,
                       CONCAT(Placa, ' - ', Marca, ' ', Modelo) AS Descripcion
                FROM vehiculos
                WHERE ID_Empresa = %s AND Estado != 'Inactivo'
                ORDER BY Placa
            """, (id_empresa,))
            vehiculos_disponibles = cursor.fetchall()

            # 1. Obtener gastos en efectivo de esta asignación
            cursor.execute("""
                SELECT m.ID_Movimiento, m.Concepto, m.Monto, m.Tipo_Pago, 
                       m.Fecha,
                       m.Saldo_Acumulado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Asignacion = %s 
                AND m.Tipo = 'GASTO'
                AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC, m.ID_Movimiento DESC
            """, (id_asignacion,))
            
            gastos = cursor.fetchall()
            
            for gasto in gastos:
                if gasto.get('Monto') is not None:
                    gasto['Monto'] = float(gasto['Monto'])
                if gasto.get('Saldo_Acumulado') is not None:
                    gasto['Saldo_Acumulado'] = float(gasto['Saldo_Acumulado'])
                
                gasto['Es_Combustible'] = 'combustible' in (gasto.get('Concepto') or '').lower() or 'gasolina' in (gasto.get('Concepto') or '').lower() or 'diesel' in (gasto.get('Concepto') or '').lower()
                gasto['Es_Convenio'] = False
                
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
            
            # 2. Calcular total de gastos en efectivo de la asignación
            total_gastos = sum(float(g.get('Monto') or 0) for g in gastos)
            
            # 3. Obtener cargas de combustible por convenio (Estación San José) registradas durante la asignación
            fecha_asig = asignacion.get('Fecha_Asignacion') or datetime.now().date()
            cursor.execute("""
                SELECT gg.ID_Gasto, gg.Fecha, gg.Fecha_Registro, gg.Monto, gg.Descripcion,
                       gg.Metodo_Pago, v.Placa, v.Marca, v.Modelo,
                       gvd.Kilometraje, gvd.Taller
                FROM gastos_generales gg
                LEFT JOIN gastos_vehiculo_detalle gvd ON gg.ID_Gasto = gvd.ID_Gasto
                LEFT JOIN subcategorias_gasto sg ON gg.ID_Subcategoria = sg.ID_Subcategoria
                LEFT JOIN vehiculos v ON gg.ID_Vehiculo = v.ID_Vehiculo
                WHERE gg.ID_Usuario_Registro = %s
                  AND UPPER(gg.Estado) = 'ACTIVO'
                  AND gg.Fecha >= %s
                  AND (
                      UPPER(gvd.Tipo_Mantenimiento) = 'COMBUSTIBLE'
                      OR gg.Descripcion LIKE %s
                      OR sg.Nombre LIKE %s
                  )
                ORDER BY gg.ID_Gasto DESC
            """, (usuario_actual, fecha_asig, 'Carga de combustible%', '%Combustible%'))
            cargas_combustible = cursor.fetchall() or []
            
            for c in cargas_combustible:
                c['Monto'] = float(c.get('Monto') or 0)
                f_reg = c.get('Fecha_Registro') or c.get('Fecha')
                if isinstance(f_reg, datetime):
                    c['Hora'] = f_reg.strftime('%I:%M %p')
                elif hasattr(f_reg, 'strftime'):
                    c['Hora'] = f_reg.strftime('%d/%m/%Y')
                else:
                    c['Hora'] = str(f_reg or '--:--')
            
            total_combustible = sum(c['Monto'] for c in cargas_combustible)
            
            # 4. Obtener saldo actual estandarizado
            saldo_actual = calcular_saldo_caja_ruta(cursor, id_asignacion)
            
    except Exception as e:
        print(f"Error en vendedor_gastos GET: {e}")
        gastos = []
        cargas_combustible = []
        total_gastos = 0
        total_combustible = 0
        saldo_actual = 0
        vehiculos_disponibles = []
        flash('Error al cargar los gastos', 'error')
    
    return render_template('vendedor/gastos/gastos.html', 
                         gastos=gastos, 
                         cargas_combustible=cargas_combustible,
                         total_gastos=total_gastos,
                         total_combustible=total_combustible,
                         saldo_actual=saldo_actual,
                         asignacion=asignacion,
                         ruta=nombre_ruta,
                         vehiculos_disponibles=vehiculos_disponibles,
                         fecha_actual=datetime.now().strftime('%d/%m/%Y'))


@vendedor_bp.route('/vendedor/gastos/combustible', methods=['POST'])
@vendedor_required
def vendedor_gastos_combustible():

    usuario_actual = current_user.id
    
    try:
        with get_db_cursor() as cursor:
            asignacion = obtener_asignacion_activa(cursor, usuario_actual)
            
            if not asignacion:
                flash('No tienes una ruta activa asignada para registrar combustible', 'warning')
                return redirect(request.referrer or url_for('vendedor.vendedor_dashboard'))
                
            id_empresa = asignacion.get('ID_Empresa') or session.get('id_empresa', 1)
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
            placa_vehiculo = asignacion.get('Placa') or 'Vehículo'
            if id_vehiculo:
                cursor.execute("SELECT Placa, Marca, Modelo FROM vehiculos WHERE ID_Vehiculo = %s", (id_vehiculo,))
                v_info = cursor.fetchone()
                if v_info:
                    placa_vehiculo = v_info['Placa']
                    
            # 1. Buscar específicamente la subcategoría 'Combustible' que pertenece a 'Vehículos y Transporte'
            cursor.execute("""
                SELECT sg.ID_Subcategoria, sg.ID_Tipo_Gasto
                FROM subcategorias_gasto sg
                INNER JOIN tipos_gasto tg ON sg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE sg.Nombre LIKE %s
                  AND (tg.Nombre LIKE %s OR tg.Nombre LIKE %s OR tg.ID_Tipo_Gasto = 2)
                ORDER BY
                    CASE WHEN UPPER(TRIM(sg.Nombre)) = 'COMBUSTIBLE' THEN 0 ELSE 1 END,
                    CASE WHEN tg.Nombre LIKE %s OR tg.Nombre LIKE %s THEN 0 ELSE 1 END,
                    CASE WHEN UPPER(sg.Estado) = 'ACTIVO' THEN 0 ELSE 1 END,
                    CASE WHEN tg.ID_Empresa = %s THEN 0 ELSE 1 END
                LIMIT 1
            """, ('%Combustible%', '%Veh%', '%Transp%', '%Veh%', '%Transp%', id_empresa))
            sub_comb = cursor.fetchone()

            if not sub_comb:
                # Respaldo: buscar por nombre Combustible en subcategorias_gasto sin restringir el nombre del tipo
                cursor.execute("""
                    SELECT sg.ID_Subcategoria, sg.ID_Tipo_Gasto
                    FROM subcategorias_gasto sg
                    WHERE sg.Nombre LIKE %s
                    ORDER BY CASE WHEN UPPER(TRIM(sg.Nombre)) = 'COMBUSTIBLE' THEN 0 ELSE 1 END
                    LIMIT 1
                """, ('%Combustible%',))
                sub_comb = cursor.fetchone()

            if sub_comb:
                id_tipo_gasto_comb = sub_comb['ID_Tipo_Gasto']
                id_subcategoria_comb = sub_comb['ID_Subcategoria']
                # Corregir registros previos que se hayan guardado con otra subcategoría (ej. ID_Subcategoria = 1)
                cursor.execute("""
                    UPDATE gastos_generales gg
                    LEFT JOIN gastos_vehiculo_detalle gvd ON gg.ID_Gasto = gvd.ID_Gasto
                    SET gg.ID_Tipo_Gasto = %s,
                        gg.ID_Subcategoria = %s
                    WHERE (
                        gg.Descripcion LIKE %s
                        OR gg.Descripcion LIKE %s
                        OR UPPER(gvd.Tipo_Mantenimiento) = 'COMBUSTIBLE'
                        OR (gg.ID_Tipo_Gasto = %s AND gg.ID_Subcategoria = 1)
                    )
                      AND (gg.ID_Subcategoria != %s OR gg.ID_Subcategoria IS NULL OR gg.ID_Tipo_Gasto != %s)
                """, (
                    id_tipo_gasto_comb,
                    id_subcategoria_comb,
                    '%combustible%',
                    '%San Jos%',
                    id_tipo_gasto_comb,
                    id_subcategoria_comb,
                    id_tipo_gasto_comb,
                ))
            else:
                id_tipo_gasto_comb = 2
                id_subcategoria_comb = None

            # Prevenir inserción duplicada por doble clic rápido (últimos 4 segundos)
            cursor.execute("""
                SELECT 1 FROM gastos_generales 
                WHERE ID_Usuario_Registro = %s 
                  AND Monto = %s 
                  AND (ID_Vehiculo = %s OR (ID_Vehiculo IS NULL AND %s IS NULL))
                  AND Fecha_Registro >= NOW() - INTERVAL 4 SECOND
                LIMIT 1
            """, (usuario_actual, monto, id_vehiculo if id_vehiculo else None, id_vehiculo if id_vehiculo else None))
            
            if cursor.fetchone():
                flash('Este registro de combustible ya fue procesado hace un momento.', 'warning')
                return redirect(request.referrer or url_for('vendedor.vendedor_dashboard'))

            # Insertar en gastos_generales con la subcategoría real de Combustible
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
                    %s, %s, CURDATE(), %s, %s,
                    NULL, NULL, %s, 'TRANSFERENCIA',
                    %s, 'Activo', %s
                )
            """, (
                id_tipo_gasto_comb, id_subcategoria_comb, monto, descripcion_gasto[:500],
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
                
            flash(f'⛽ Carga de combustible registrada (Convenio Estación de Servicio San José) por C$ {monto:,.2f}', 'success')
    except Exception as e:
        flash(f'Error al registrar el gasto de combustible: {str(e)}', 'error')
        print(f"Error en vendedor_gastos_combustible POST: {e}")
        
    return redirect(request.referrer or url_for('vendedor.vendedor_gastos'))


