"""
Módulo de Caja Diaria - Gestión de movimientos y flujo de dinero
"""
from flask import render_template, redirect, url_for, request, flash
from flask_login import current_user
from datetime import datetime, date
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp


@admin_bp.route('/admin/caja')
@admin_required
def admin_caja():
    """Vista principal de caja - Muestra estado actual"""
    fecha_actual = datetime.now().date()
    
    with get_db_cursor(True) as cursor:
        # Estado de caja (Abierta/Cerrada)
        cursor.execute("""
            SELECT CASE 
                WHEN EXISTS (
                    SELECT 1 FROM caja_movimientos 
                    WHERE Tipo_Movimiento = 'ENTRADA' 
                    AND Descripcion LIKE '%%Apertura%%'
                    AND DATE(Fecha) = %s
                    AND Estado = 'ACTIVO'
                ) THEN 'ABIERTA'
                ELSE 'CERRADA'
            END as estado
        """, (fecha_actual,))
        estado = cursor.fetchone()['estado']
        
        # Resumen del día (solo movimientos ACTIVOS)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto ELSE 0 END), 0) as entradas,
                COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'SALIDA' THEN Monto ELSE 0 END), 0) as salidas,
                COALESCE(SUM(CASE 
                    WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto 
                    ELSE -Monto 
                END), 0) as saldo_dia
            FROM caja_movimientos
            WHERE DATE(Fecha) = %s
            AND Estado = 'ACTIVO'
        """, (fecha_actual,))
        
        resumen = cursor.fetchone()
        
        # Movimientos del día
        cursor.execute("""
            SELECT 
                ID_Movimiento,
                Fecha,
                Tipo_Movimiento,
                Descripcion,
                Monto,
                Referencia_Documento,
                Estado
            FROM caja_movimientos
            WHERE DATE(Fecha) = %s
            AND Estado = 'ACTIVO'
            AND (Descripcion NOT LIKE '%%Anulación%%' 
                 AND Descripcion NOT LIKE '%%Contramovimiento%%'
                 AND (Referencia_Documento IS NULL 
                      OR Referencia_Documento NOT LIKE '%%ANUL%%'))
            ORDER BY Fecha DESC
        """, (fecha_actual,))
        
        movimientos = cursor.fetchall()
    
    datos = {
        'fecha': fecha_actual.strftime('%d/%m/%Y'),
        'estado': estado,
        'entradas': float(resumen['entradas'] or 0),
        'salidas': float(resumen['salidas'] or 0),
        'saldo_dia': float(resumen['saldo_dia'] or 0),
        'movimientos': movimientos
    }
    
    return render_template('admin/caja/caja.html', caja=datos)


@admin_bp.route('/admin/caja/aperturar', methods=['POST'])
@admin_required
def admin_caja_aperturar():
    """Abre la caja con un monto inicial"""
    try:
        monto = float(request.form.get('monto_inicial', 0))
        
        if monto <= 0:
            flash('El monto debe ser mayor a 0', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        fecha_actual = datetime.now().date()
        
        with get_db_cursor(True) as cursor:
            # Verificar si ya hay apertura hoy
            cursor.execute("""
                SELECT 1 FROM caja_movimientos 
                WHERE Tipo_Movimiento = 'ENTRADA' 
                AND Descripcion LIKE '%%Apertura%%'
                AND DATE(Fecha) = %s
                AND Estado = 'ACTIVO'
                LIMIT 1
            """, (fecha_actual,))
            
            if cursor.fetchone():
                flash('La caja ya está aperturada hoy', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            # Registrar apertura
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, ID_Usuario, Estado)
                VALUES (NOW(), 'ENTRADA', %s, %s, %s, 'ACTIVO')
            """, (f"Apertura de caja", monto, current_user.id))
            
            flash(f'Caja aperturada con C${monto:.2f}', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except ValueError:
        flash('Monto inválido', 'error')
        return redirect(url_for('admin.admin_caja'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))


@admin_bp.route('/admin/caja/movimiento', methods=['POST'])
@admin_required
def admin_caja_movimiento():
    """Registra un movimiento manual de entrada o salida"""
    try:
        tipo = request.form.get('tipo_movimiento')
        descripcion = request.form.get('descripcion', '').strip()
        monto = float(request.form.get('monto', 0))
        referencia = request.form.get('referencia_documento', '').strip()
        
        # Validaciones básicas
        if tipo not in ['ENTRADA', 'SALIDA']:
            flash('Tipo de movimiento inválido', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        if monto <= 0:
            flash('El monto debe ser mayor a 0', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        if not descripcion:
            flash('Descripción requerida', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        with get_db_cursor(True) as cursor:
            # Para salidas, verificar que la caja esté abierta
            if tipo == 'SALIDA':
                fecha_actual = datetime.now().date()
                cursor.execute("""
                    SELECT 1 FROM caja_movimientos 
                    WHERE Tipo_Movimiento = 'ENTRADA' 
                    AND Descripcion LIKE '%%Apertura%%'
                    AND DATE(Fecha) = %s
                    AND Estado = 'ACTIVO'
                    LIMIT 1
                """, (fecha_actual,))
                
                if not cursor.fetchone():
                    flash('La caja no está aperturada', 'error')
                    return redirect(url_for('admin.admin_caja'))
            
            # Registrar movimiento
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, Referencia_Documento, ID_Usuario, Estado)
                VALUES (NOW(), %s, %s, %s, %s, %s, 'ACTIVO')
            """, (tipo, descripcion, monto, referencia, current_user.id))
            
            flash(f'Movimiento registrado: {descripcion}', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except ValueError:
        flash('Monto inválido', 'error')
        return redirect(url_for('admin.admin_caja'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))


@admin_bp.route('/admin/caja/cerrar', methods=['POST'])
@admin_required
def admin_caja_cerrar():
    """Cierra la caja del día"""
    try:
        with get_db_cursor(True) as cursor:
            fecha_actual = datetime.now().date()
            
            # Obtener saldo de cierre
            cursor.execute("""
                SELECT COALESCE(SUM(CASE 
                    WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto 
                    ELSE -Monto 
                END), 0) as saldo_final
                FROM caja_movimientos
                WHERE DATE(Fecha) = %s AND Estado = 'ACTIVO'
            """, (fecha_actual,))
            
            saldo = cursor.fetchone()['saldo_final'] or 0
            
            # Registrar cierre
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, ID_Usuario, Estado)
                VALUES (NOW(), 'SALIDA', %s, %s, %s, 'ACTIVO')
            """, ("Cierre de caja", saldo, current_user.id))
            
            flash(f'Caja cerrada. Saldo final: C${saldo:.2f}', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))


@admin_bp.route('/admin/caja/anular/<int:id_movimiento>', methods=['POST'])
@admin_required
def admin_caja_anular(id_movimiento):
    """Anula un movimiento de caja"""
    try:
        with get_db_cursor(True) as cursor:
            # Obtener movimiento
            cursor.execute("""
                SELECT Monto, Tipo_Movimiento FROM caja_movimientos
                WHERE ID_Movimiento = %s AND Estado = 'ACTIVO'
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            if not movimiento:
                flash('Movimiento no encontrado', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            # Marcar como anulado
            cursor.execute("""
                UPDATE caja_movimientos
                SET Estado = 'ANULADO'
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            # Registrar contramovimiento
            tipo_inverso = 'SALIDA' if movimiento['Tipo_Movimiento'] == 'ENTRADA' else 'ENTRADA'
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, Referencia_Documento, ID_Usuario, Estado)
                VALUES (NOW(), %s, %s, %s, %s, %s, 'ACTIVO')
            """, (tipo_inverso, f"Anulación de movimiento {id_movimiento}", 
                  movimiento['Monto'], f"ANUL-{id_movimiento}", current_user.id))
            
            flash('Movimiento anulado', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))


@admin_bp.route('/admin/caja/historial')
@admin_required
def admin_caja_historial():
    """Muestra historial de movimientos de caja"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    ID_Movimiento,
                    DATE(Fecha) as fecha,
                    Tipo_Movimiento,
                    Descripcion,
                    Monto,
                    Estado
                FROM caja_movimientos
                ORDER BY Fecha DESC
                LIMIT 100
            """)
            
            historial = cursor.fetchall()
        
        return render_template('admin/caja/historial.html', historial=historial)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))


@admin_bp.route('/admin/caja/reporte')
@admin_required
def admin_caja_reporte():
    """Reporte de caja por rango de fechas"""
    try:
        fecha_inicio_str = request.args.get('fecha_inicio')
        fecha_fin_str = request.args.get('fecha_fin')
        
        if fecha_inicio_str and fecha_fin_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            
            # Asegurar que fecha_inicio sea menor o igual a fecha_fin
            if fecha_inicio > fecha_fin:
                fecha_inicio, fecha_fin = fecha_fin, fecha_inicio
            
            with get_db_cursor(True) as cursor:
                # Reporte agrupado por día
                cursor.execute("""
                    SELECT 
                        DATE(Fecha) as fecha,
                        COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto ELSE 0 END), 0) as entradas,
                        COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'SALIDA' THEN Monto ELSE 0 END), 0) as salidas,
                        COUNT(*) as movimientos
                    FROM caja_movimientos
                    WHERE DATE(Fecha) BETWEEN %s AND %s
                    AND Estado = 'ACTIVO'
                    GROUP BY DATE(Fecha)
                    ORDER BY fecha DESC
                """, (fecha_inicio, fecha_fin))
                
                reporte = cursor.fetchall()
                
                # Totales generales del período
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto ELSE 0 END), 0) as entradas_total,
                        COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'SALIDA' THEN Monto ELSE 0 END), 0) as salidas_total,
                        COUNT(*) as total_movimientos
                    FROM caja_movimientos
                    WHERE DATE(Fecha) BETWEEN %s AND %s
                    AND Estado = 'ACTIVO'
                """, (fecha_inicio, fecha_fin))
                
                totales = cursor.fetchone()
            
            return render_template('admin/caja/reporte.html',
                                 fecha_inicio=fecha_inicio.strftime('%Y-%m-%d'),
                                 fecha_fin=fecha_fin.strftime('%Y-%m-%d'),
                                 reporte=reporte,
                                 entradas_total=float(totales['entradas_total'] or 0),
                                 salidas_total=float(totales['salidas_total'] or 0),
                                 movimientos_total=totales['total_movimientos'] or 0)
        
        return render_template('admin/caja/reporte.html')
            
    except ValueError:
        flash('Fechas inválidas', 'error')
        return redirect(url_for('admin.admin_caja_reporte'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))
