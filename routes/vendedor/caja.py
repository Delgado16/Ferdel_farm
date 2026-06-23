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
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha))
            
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
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha))
            
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
                WHERE m.ID_Usuario = %s 
                  AND DATE(m.Fecha) = %s
                  AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
            """, (id_vendedor, fecha))
            
            movimientos = cursor.fetchall()
            
            # Estadísticas - CORREGIDO con COALESCE
            cursor.execute("""
                SELECT 
                    COALESCE(COUNT(DISTINCT ID_Cliente), 0) as clientes_Atendidos,
                    COALESCE(COUNT(CASE WHEN Tipo = 'VENTA' THEN 1 END), 0) as Total_Ventas,
                    COALESCE(COUNT(CASE WHEN Tipo = 'ABONO' THEN 1 END), 0) as Total_Abonos_Dia,
                    COALESCE(COUNT(CASE WHEN Tipo = 'GASTO' THEN 1 END), 0) as Total_Gastos_Dia
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha))
            
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
            
            # Calcular saldo esperado para el cierre (saldo_actual + gastos)
            saldo_esperado_cierre = resumen_seguro['saldo_actual'] + resumen_seguro['gastos']
            
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
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha_actual))
            
            saldo = cursor.fetchone()
            saldo_esperado = float(saldo['Saldo_Esperado'])
            diferencia = monto_real - saldo_esperado
            
            # Limitar la longitud del concepto a 200 caracteres (longitud de columna varchar(200))
            concepto = f"Cierre de caja - Diferencia: Gs. {diferencia:,.0f}. {observacion}" if observacion else f"Cierre de caja - Diferencia: Gs. {diferencia:,.0f}"
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
    
    # Para GET y POST necesitamos la asignación activa primero
    try:
        with get_db_cursor() as cursor:
            # Obtener la asignación activa del vendedor para hoy
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta, Fecha_Asignacion 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s 
                AND DATE(Fecha_Asignacion) = CURDATE() 
                AND Estado = 'ACTIVA'
                ORDER BY Fecha_Asignacion DESC 
                LIMIT 1
            """, (usuario_actual,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta asignada para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            id_asignacion = asignacion['ID_Asignacion']
    except Exception as e:
        flash(f'Error al verificar asignación: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))
    
    # Procesar el formulario cuando es POST
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
                # Obtener el saldo acumulado actual
                cursor.execute("""
                    SELECT Saldo_Acumulado 
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND Estado = 'ACTIVO'
                    ORDER BY Fecha DESC 
                    LIMIT 1
                """, (id_asignacion,))
                
                ultimo_movimiento = cursor.fetchone()
                
                # Convertir Decimal a float para la operación
                if ultimo_movimiento and ultimo_movimiento['Saldo_Acumulado'] is not None:
                    saldo_anterior = float(ultimo_movimiento['Saldo_Acumulado'])
                else:
                    saldo_anterior = 0.0
                
                # Calcular nuevo saldo (el gasto resta del saldo)
                nuevo_saldo = saldo_anterior - monto
                
                # Insertar el nuevo gasto
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta 
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Tipo_Pago, Saldo_Acumulado, Estado)
                    VALUES (%s, %s, 'GASTO', %s, %s, %s, %s, 'ACTIVO')
                """, (id_asignacion, usuario_actual, concepto, monto, tipo_pago, nuevo_saldo))
                
                flash('Gasto registrado exitosamente', 'success')
            
        except Exception as e:
            flash(f'Error al registrar el gasto: {str(e)}', 'error')
            print(f"Error en vendedor_gastos POST: {e}")
        
        return redirect(url_for('vendedor.vendedor_gastos'))
    
    # Para GET: obtener los gastos del día
    try:
        with get_db_cursor() as cursor:
            # Obtener todos los gastos del día para esta asignación
            cursor.execute("""
                SELECT m.ID_Movimiento, m.Concepto, m.Monto, m.Tipo_Pago, 
                       DATE_FORMAT(m.Fecha, '%%H:%%i') as Hora,
                       m.Saldo_Acumulado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Asignacion = %s 
                AND m.Tipo = 'GASTO'
                AND m.Estado = 'ACTIVO'
                AND DATE(m.Fecha) = CURDATE()
                ORDER BY m.Fecha DESC
            """, (id_asignacion,))
            
            gastos = cursor.fetchall()
            
            # Convertir Decimal a float para la plantilla
            for gasto in gastos:
                if gasto['Monto'] is not None:
                    gasto['Monto'] = float(gasto['Monto'])
                if gasto['Saldo_Acumulado'] is not None:
                    gasto['Saldo_Acumulado'] = float(gasto['Saldo_Acumulado'])
            
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
            
            # Obtener saldo actual
            cursor.execute("""
                SELECT Saldo_Acumulado
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                AND Estado = 'ACTIVO'
                ORDER BY Fecha DESC
                LIMIT 1
            """, (id_asignacion,))
            
            saldo_actual = cursor.fetchone()
            if saldo_actual and saldo_actual['Saldo_Acumulado'] is not None:
                saldo_actual = float(saldo_actual['Saldo_Acumulado'])
            else:
                saldo_actual = 0
            
    except Exception as e:
        print(f"Error en vendedor_gastos GET: {e}")
        gastos = []
        total_gastos = 0
        saldo_actual = 0
        flash('Error al cargar los gastos', 'error')
    
    return render_template('vendedor/gastos/gastos.html', 
                         gastos=gastos, 
                         total_gastos=total_gastos,
                         saldo_actual=saldo_actual,
                         asignacion=asignacion)

