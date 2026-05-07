"""
Blueprint de rutas del administrador (dashboard, usuarios, roles, caja)
"""
import csv
from decimal import Decimal
import io
import logging
import traceback
from venv import logger
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, app, jsonify, make_response, render_template, flash, redirect, session, url_for, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta, time, date
import json
import logging

from config.database import get_db_cursor
from auth.decorators import admin_required, admin_or_bodega_required
from helpers.bitacora import bitacora_decorator, registrar_bitacora


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Dashboard del administrador con KPIs y reportes"""
    try:
        with get_db_cursor() as cursor:
            # ============================================
            # 1. MÉTRICAS PRINCIPALES (KPIs)
            # ============================================
            
            # Usuarios activos
            cursor.execute("SELECT COUNT(*) as count FROM usuarios WHERE UPPER(Estado) = 'ACTIVO'")
            usuarios_count = cursor.fetchone()['count']
            
            # Empresas activas
            cursor.execute("SELECT COUNT(*) as count FROM empresa WHERE Estado = 'Activo'")
            empresas_count = cursor.fetchone()['count']
            
            # Ventas de hoy
            cursor.execute("""
                SELECT COALESCE(SUM(Ventas_Totales), 0) AS Total_Ventas_Hoy
                FROM (
                    SELECT SUM(df.Total) AS Ventas_Totales 
                    FROM detalle_facturacion df
                    INNER JOIN facturacion fac ON df.ID_Factura = fac.ID_Factura
                    WHERE DATE(fac.Fecha_Creacion) = CURDATE() AND fac.Estado = 'Activa'
                    UNION ALL
                    SELECT SUM(dfr.Total) AS Ventas_Totales 
                    FROM detalle_facturacion_ruta dfr
                    INNER JOIN facturacion_ruta facr ON dfr.ID_FacturaRuta = facr.ID_FacturaRuta
                    WHERE DATE(facr.Fecha_Creacion) = CURDATE() AND facr.Estado = 'Activa'
                ) AS Ventas
            """)
            ventas_hoy = cursor.fetchone()['Total_Ventas_Hoy'] or 0
            
            # Cobros de hoy
            cursor.execute("""
                SELECT COALESCE(SUM(Monto_Cobrado), 0) AS Total_Cobrado_Hoy
                FROM (
                    SELECT Monto_Aplicado AS Monto_Cobrado
                    FROM abonos_detalle
                    WHERE DATE(Fecha) = CURDATE()
                    
                    UNION ALL
                    
                    SELECT pc.Monto AS Monto_Cobrado
                    FROM pagos_cuentascobrar pc
                    INNER JOIN cuentas_por_cobrar cxc ON pc.ID_Movimiento = cxc.ID_Movimiento
                    WHERE DATE(pc.Fecha) = CURDATE()
                    AND cxc.Estado != 'Anulada'
                ) AS Cobros
            """)
            cobros_hoy = cursor.fetchone()['Total_Cobrado_Hoy'] or 0
            
            # Saldo pendiente total en cartera
            cursor.execute("""
                SELECT COALESCE(SUM(Saldo_Pendiente), 0) AS Saldo_Total_Pendiente
                FROM cuentas_por_cobrar
                WHERE Estado IN ('Pendiente', 'Vencida')
            """)
            saldo_pendiente = cursor.fetchone()['Saldo_Total_Pendiente'] or 0
            
            # Facturas vencidas
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM cuentas_por_cobrar
                WHERE Estado = 'Vencida' AND Saldo_Pendiente > 0
            """)
            facturas_vencidas = cursor.fetchone()['count'] or 0
            
            # Productos con stock bajo
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM inventario_bodega ib
                INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
                WHERE ib.Existencias <= p.Stock_Minimo
            """)
            productos_bajo_stock = cursor.fetchone()['count'] or 0
            
            # ============================================
            # 2. VENTAS DEL MES (para gráfico de líneas)
            # ============================================
            cursor.execute("""
                SELECT 
                    DAY(fac.Fecha_Creacion) AS Dia,
                    COALESCE(SUM(df.Total), 0) AS Total_Vendido
                FROM facturacion fac
                INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                WHERE MONTH(fac.Fecha_Creacion) = MONTH(CURDATE()) 
                  AND YEAR(fac.Fecha_Creacion) = YEAR(CURDATE())
                  AND fac.Estado = 'Activa'
                GROUP BY DAY(fac.Fecha_Creacion)
                ORDER BY Dia ASC
            """)
            ventas_mes = cursor.fetchall()
            
            # ============================================
            # 3. TOP CLIENTES DEUDORES
            # ============================================
            cursor.execute("""
                SELECT 
                    c.Nombre AS Cliente,
                    c.Telefono,
                    COALESCE(SUM(cxc.Saldo_Pendiente), 0) AS Deuda_Total
                FROM cuentas_por_cobrar cxc
                INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
                WHERE cxc.Estado IN ('Pendiente', 'Vencida')
                GROUP BY c.ID_Cliente
                ORDER BY Deuda_Total DESC
                LIMIT 5
            """)
            top_clientes = cursor.fetchall()
            
            # ============================================
            # 4. PRODUCTOS CON STOCK BAJO
            # ============================================
            cursor.execute("""
                SELECT 
                    p.Descripcion AS Producto,
                    p.COD_Producto,
                    ib.Existencias AS Stock_Actual,
                    p.Stock_Minimo,
                    (p.Stock_Minimo - ib.Existencias) AS Faltante
                FROM inventario_bodega ib
                INNER JOIN productos p ON ib.ID_Producto = p.ID_Producto
                WHERE ib.Existencias <= p.Stock_Minimo
                ORDER BY ib.Existencias ASC
                LIMIT 10
            """)
            productos_stock = cursor.fetchall()
            
            # ============================================
            # 5. GASTOS DEL MES POR CATEGORÍA
            # ============================================
            cursor.execute("""
                SELECT 
                    tg.Nombre AS Tipo_Gasto,
                    COALESCE(SUM(gg.Monto), 0) AS Total_Gastado
                FROM gastos_generales gg
                INNER JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE MONTH(gg.Fecha) = MONTH(CURDATE()) 
                  AND YEAR(gg.Fecha) = YEAR(CURDATE())
                  AND gg.Estado = 'Activo'
                GROUP BY tg.ID_Tipo_Gasto
                ORDER BY Total_Gastado DESC
                LIMIT 5
            """)
            gastos_mes = cursor.fetchall()
            
            # ============================================
            # PREPARAR DATOS PARA GRÁFICOS (JSON)
            # ============================================
            
            # Datos para gráfico de ventas del mes
            ventas_mes_data = {
                'dias': [v['Dia'] for v in ventas_mes],
                'totales': [float(v['Total_Vendido']) for v in ventas_mes]
            }
            
            # Datos para gráfico de gastos
            gastos_mes_data = {
                'categorias': [g['Tipo_Gasto'] for g in gastos_mes],
                'montos': [float(g['Total_Gastado']) for g in gastos_mes]
            }

            now = datetime.now()
            
            return render_template('admin/dashboard.html',
                                 # KPIs
                                 usuarios_count=usuarios_count,
                                 empresas_count=empresas_count,
                                 ventas_hoy=ventas_hoy,
                                 cobros_hoy=cobros_hoy,
                                 saldo_pendiente=saldo_pendiente,
                                 facturas_vencidas=facturas_vencidas,
                                 productos_bajo_stock=productos_bajo_stock,
                                 # Tablas
                                 top_clientes=top_clientes,
                                 productos_stock=productos_stock,
                                 # Datos para gráficos
                                 ventas_mes_json=json.dumps(ventas_mes_data),
                                 gastos_mes_json=json.dumps(gastos_mes_data),
                                 now=now)
                                 
    except Exception as e:
        flash(f"Error al cargar dashboard: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

# MODULO DE CAJA DE MOVIMIENTOS DE EFECTIVO #
# admin.py - Elimina la función format_hora que tenías antes

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
        
        # Movimientos del día - Traer fecha completa
        cursor.execute("""
            SELECT 
                ID_Movimiento,
                Fecha,  -- Traemos el datetime completo
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
        flash('❌ Monto inválido', 'error')
        return redirect(url_for('admin.admin_caja'))
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
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
            flash(' Tipo de movimiento inválido', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        if monto <= 0:
            flash(' El monto debe ser mayor a 0', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        if not descripcion:
            flash(' Descripción requerida', 'error')
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
                    flash(' No hay caja aperturada para realizar salidas', 'error')
                    return redirect(url_for('admin.admin_caja'))
            
            # IMPORTANTE: La consulta SQL debe tener 6 columnas especificadas
            # y 6 parámetros en VALUES
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, ID_Usuario, 
                 Referencia_Documento, Estado)
                VALUES (NOW(), %s, %s, %s, %s, %s, 'ACTIVO')
            """, (tipo, descripcion, monto, current_user.id, referencia))
            
            # Obtener el ID del movimiento recién insertado
            cursor.execute("SELECT LAST_INSERT_ID()")
            movimiento_id = cursor.fetchone()[0]
            
            tipo_texto = "Entrada" if tipo == 'ENTRADA' else "Salida"
            flash(f'✅ {tipo_texto} de ${monto:.2f} registrada correctamente (ID: {movimiento_id})', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except ValueError:
        flash(' Monto inválido', 'error')
        return redirect(url_for('admin.admin_caja'))
    except Exception as e:
        flash(f' Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))

@admin_bp.route('/admin/caja/cerrar', methods=['POST'])
@admin_required
def admin_caja_cerrar():
    """Cierra la caja del día calculando el saldo final"""
    try:
        fecha_actual = datetime.now().date()
        
        with get_db_cursor(True) as cursor:
            # Verificar si ya hay cierre hoy
            cursor.execute("""
                SELECT 1 FROM caja_movimientos 
                WHERE Tipo_Movimiento = 'SALIDA' 
                AND Descripcion LIKE '%%Cierre%%'
                AND DATE(Fecha) = %s
                AND Estado = 'ACTIVO'
                LIMIT 1
            """, (fecha_actual,))
            
            if cursor.fetchone():
                flash('❌ La caja ya está cerrada hoy', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            # Verificar que haya apertura
            cursor.execute("""
                SELECT 1 FROM caja_movimientos 
                WHERE Tipo_Movimiento = 'ENTRADA' 
                AND Descripcion LIKE '%%Apertura%%'
                AND DATE(Fecha) = %s
                AND Estado = 'ACTIVO'
                LIMIT 1
            """, (fecha_actual,))
            
            if not cursor.fetchone():
                flash('❌ No hay caja aperturada', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            # Calcular saldo final (suma solo movimientos ACTIVOS)
            cursor.execute("""
                SELECT COALESCE(SUM(CASE 
                    WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto 
                    ELSE -Monto 
                END), 0) as saldo
                FROM caja_movimientos
                WHERE DATE(Fecha) = %s
                AND Estado = 'ACTIVO'
            """, (fecha_actual,))
            
            saldo = float(cursor.fetchone()['saldo'])
            
            # Registrar cierre
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, ID_Usuario, Estado)
                VALUES (NOW(), 'SALIDA', %s, %s, %s, 'ACTIVO')
            """, (f"Cierre de caja", saldo, current_user.id))
            
            flash(f'✅ Caja cerrada. Saldo final: ${saldo:.2f}', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))

@admin_bp.route('/admin/caja/anular/<int:id_movimiento>', methods=['POST'])
@admin_required
def admin_caja_anular(id_movimiento):
    """Anula un movimiento creando un contramovimiento compensatorio"""
    try:
        motivo = request.form.get('motivo', '').strip()
        
        # Validar motivo
        if len(motivo) < 5:
            flash('❌ El motivo debe tener al menos 5 caracteres', 'error')
            return redirect(url_for('admin.admin_caja'))
        
        with get_db_cursor(True) as cursor:
            # Obtener el movimiento a anular
            cursor.execute("""
                SELECT Tipo_Movimiento, Descripcion, Monto, Estado
                FROM caja_movimientos 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            mov = cursor.fetchone()
            
            # Validaciones
            if not mov:
                flash('❌ Movimiento no encontrado', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            if mov['Estado'] == 'ANULADO':
                flash('❌ Este movimiento ya está anulado', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            # No permitir anular aperturas/cierres
            desc_lower = mov['Descripcion'].lower()
            if 'apertura' in desc_lower or 'cierre' in desc_lower:
                flash('❌ No se puede anular apertura o cierre de caja', 'error')
                return redirect(url_for('admin.admin_caja'))
            
            # Determinar tipo contrario para el contramovimiento
            tipo_contrario = 'SALIDA' if mov['Tipo_Movimiento'] == 'ENTRADA' else 'ENTRADA'
            
            # Crear contramovimiento (compensación)
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, ID_Usuario,
                 Referencia_Documento, Movimiento_Origen, Estado)
                VALUES (NOW(), %s, %s, %s, %s, 'ANULACION', %s, 'ACTIVO')
            """, (tipo_contrario, 
                  f"Anulación: {mov['Descripcion']}", 
                  mov['Monto'], 
                  current_user.id,
                  id_movimiento))
            
            # Marcar movimiento original como ANULADO
            cursor.execute("""
                UPDATE caja_movimientos 
                SET Estado = 'ANULADO',
                    Fecha_Anulacion = NOW(),
                    ID_Usuario_Anula = %s
                WHERE ID_Movimiento = %s
            """, (current_user.id, id_movimiento))
            
            flash('✅ Movimiento anulado correctamente', 'success')
            return redirect(url_for('admin.admin_caja'))
            
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))

@admin_bp.route('/admin/caja/historial')
@admin_required
def admin_caja_historial():
    """Muestra el historial completo de movimientos de una fecha específica"""
    fecha_str = request.args.get('fecha')
    
    try:
        # Obtener fecha (hoy por defecto)
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.now().date()
        
        # Fecha máxima para el input (hoy)
        fecha_maxima = datetime.now().date().strftime('%Y-%m-%d')
        
        with get_db_cursor(True) as cursor:
            # Consulta actualizada con Fecha completa
            cursor.execute("""
                SELECT 
                    ID_Movimiento,
                    Fecha,  -- ← Fecha completa para format_hora
                    Tipo_Movimiento,
                    Descripcion,
                    Monto,
                    Referencia_Documento,
                    Estado,
                    ID_Factura,
                    ID_Pagos_cxc
                FROM caja_movimientos
                WHERE DATE(Fecha) = %s
                ORDER BY Fecha DESC
            """, (fecha,))
            
            movimientos = cursor.fetchall()
            
            # Resumen (solo movimientos ACTIVOS)
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'ENTRADA' THEN Monto ELSE 0 END), 0) as entradas,
                    COALESCE(SUM(CASE WHEN Tipo_Movimiento = 'SALIDA' THEN Monto ELSE 0 END), 0) as salidas,
                    COUNT(*) as total
                FROM caja_movimientos
                WHERE DATE(Fecha) = %s
                AND Estado = 'ACTIVO'
            """, (fecha,))
            
            resumen = cursor.fetchone()
            
            # Calcular saldo_dia
            entradas = float(resumen['entradas'] or 0)
            salidas = float(resumen['salidas'] or 0)
            saldo_dia = entradas - salidas
            
            # Movimientos anulados
            cursor.execute("""
                SELECT COUNT(*) as total_anulados
                FROM caja_movimientos
                WHERE DATE(Fecha) = %s
                AND Estado = 'ANULADO'
            """, (fecha,))
            
            anulados = cursor.fetchone()
            
            # Estado de caja
            cursor.execute("""
                SELECT CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM caja_movimientos 
                        WHERE Tipo_Movimiento = 'SALIDA' 
                        AND Descripcion LIKE '%%Cierre%%'
                        AND DATE(Fecha) = %s
                        AND Estado = 'ACTIVO'
                    ) THEN 'CERRADA'
                    WHEN EXISTS (
                        SELECT 1 FROM caja_movimientos 
                        WHERE Tipo_Movimiento = 'ENTRADA' 
                        AND Descripcion LIKE '%%Apertura%%'
                        AND DATE(Fecha) = %s
                        AND Estado = 'ACTIVO'
                    ) THEN 'ABIERTA'
                    ELSE 'NO_APERTURADA'
                END as estado
            """, (fecha, fecha))
            
            estado_result = cursor.fetchone()
            estado = estado_result['estado'] if estado_result else 'NO_APERTURADA'
            
            # Fechas disponibles
            cursor.execute("""
                SELECT DISTINCT DATE(Fecha) as fecha
                FROM caja_movimientos
                WHERE DATE(Fecha) <= CURDATE()
                ORDER BY fecha DESC
                LIMIT 30
            """)
            fechas_disponibles = cursor.fetchall()
        
        return render_template('admin/caja/historial.html',
                             fecha=fecha.strftime('%Y-%m-%d'),
                             fecha_formateada=fecha.strftime('%d/%m/%Y'),
                             fecha_maxima=fecha_maxima,
                             movimientos=movimientos,
                             entradas=entradas,
                             salidas=salidas,
                             saldo_dia=saldo_dia,  # ← AQUÍ está la variable que faltaba
                             total=resumen['total'] or 0,
                             total_anulados=anulados['total_anulados'] or 0,
                             estado=estado,
                             fechas_disponibles=fechas_disponibles)
            
    except ValueError:
        flash('❌ Fecha inválida', 'error')
        return redirect(url_for('admin.admin_caja_historial', fecha=datetime.now().strftime('%Y-%m-%d')))
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))

@admin_bp.route('/admin/caja/reporte')
@admin_required
def admin_caja_reporte():
    """Genera reporte consolidado por rango de fechas"""
    fecha_inicio_str = request.args.get('fecha_inicio', '')
    fecha_fin_str = request.args.get('fecha_fin', '')
    
    try:
        # Establecer fechas por defecto (últimos 7 días)
        if not fecha_inicio_str or not fecha_fin_str:
            fecha_fin = datetime.now().date()
            fecha_inicio = fecha_fin - timedelta(days=7)
        else:
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
            
    except ValueError:
        flash('❌ Fechas inválidas', 'error')
        return redirect(url_for('admin.admin_caja_reporte'))
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_caja'))

####################
# MODULO DE VENTAS #
####################

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
                LIMIT 30 
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

        # Si es POST, procesar el formulario
        if request.method == 'POST':
            print("📨 Iniciando procesamiento de venta...")
            
            # Obtener datos del formulario
            id_cliente = request.form.get('id_cliente','').strip()
            tipo_venta = request.form.get('tipo_venta')
            observacion = request.form.get('observacion', '')
            realizar_abono = request.form.get('realizar_abono') == 'on'
            monto_abono = float(request.form.get('monto_abono', 0)) if realizar_abono else 0
            
            # Obtener productos del formulario
            productos_ids = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            precios = request.form.getlist('precio[]')
            
            print(f"Datos recibidos - Cliente: {id_cliente}, Tipo: {tipo_venta}, Abono: {realizar_abono} (C${monto_abono:,.2f})")
            print(f"Productos recibidos: {len(productos_ids)}")
            
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
                                    id_tipo_movimiento=id_tipo_movimiento)
            
            if realizar_abono and monto_abono <= 0:
                error_msg = 'Debe ingresar un monto de abono válido'
                print(f"❌ {error_msg}")
                flash(error_msg, 'error')
                return render_template('admin/ventas/crear_venta.html',
                                    clientes=clientes,
                                    bodega_principal=bodega_principal,
                                    productos=productos,
                                    categorias=categorias,
                                    empresa=empresa_data,
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
                                            id_tipo_movimiento=id_tipo_movimiento)
                
                print("✅ Validación de visibilidad completada")
                
                # 1. Crear factura
                cursor.execute("""
                    INSERT INTO facturacion (
                        Fecha, IDCliente, Credito_Contado, Observacion, 
                        ID_Empresa, ID_Usuario_Creacion
                    )
                    VALUES (CURDATE(), %s, %s, %s, %s, %s)
                """, (
                    id_cliente,
                    1 if tipo_venta == 'credito' else 0,
                    observacion,
                    id_empresa,
                    id_usuario
                ))
                
                # Obtener el ID de la factura
                cursor.execute("SELECT LAST_INSERT_ID() as id_factura")
                id_factura = cursor.fetchone()['id_factura']
                print(f"🧾 Factura #{id_factura} creada para cliente con perfil: {perfil_cliente}")
                
                total_venta = 0
                total_cajillas_huevos = 0
                
                # CONSTANTES
                ID_SEPARADOR = 11
                ID_CATEGORIA_HUEVOS = 1
                ID_BODEGA_EMPAQUE = 1
                
                # 2. Procesar productos
                for i in range(len(productos_ids)):
                    id_producto = int(productos_ids[i])
                    cantidad = float(cantidades[i]) if cantidades[i] else 0
                    precio = float(precios[i]) if precios[i] else 0
                    
                    if cantidad <= 0 or precio <= 0:
                        continue
                    
                    total_linea = cantidad * precio
                    total_venta += total_linea
                    
                    # Obtener datos del producto
                    cursor.execute("""
                        SELECT p.ID_Producto, p.COD_Producto, p.Descripcion, p.ID_Categoria,
                               c.Descripcion as Nombre_Categoria,
                               p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta
                        FROM productos p
                        LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                        WHERE p.ID_Producto = %s
                    """, (id_producto,))
                    
                    producto_data = cursor.fetchone()
                    
                    if not producto_data:
                        raise Exception(f"Producto con ID {id_producto} no encontrado")
                    
                    # Verificar stock
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega_principal, id_producto))
                    
                    stock = cursor.fetchone()
                    stock_actual = stock['Stock'] if stock else 0
                    
                    if stock_actual < cantidad:
                        raise Exception(f'Stock insuficiente para: {producto_data["Descripcion"]}. Stock actual: {stock_actual}')
                    
                    # Insertar detalle de facturación
                    cursor.execute("""
                        INSERT INTO detalle_facturacion (
                            ID_Factura, ID_Producto, Cantidad, Costo, Total
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, id_producto, cantidad, precio, total_linea))
                    
                    # Actualizar inventario
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega_principal, id_producto))
                    
                    print(f"  {cantidad} x C${precio} = C${total_linea}")
                    
                    # Detectar productos de huevos
                    if producto_data['ID_Categoria'] == ID_CATEGORIA_HUEVOS:
                        total_cajillas_huevos += cantidad
                
                print(f"📊 Total venta: C${total_venta:,.2f}")
                print(f"🥚 Total cajillas de huevos: {total_cajillas_huevos}")
                
                # 3. Calcular y descontar separadores
                separadores_totales = 0
                if total_cajillas_huevos > 0:
                    separadores_entre_cajillas = total_cajillas_huevos
                    separadores_base_extra = total_cajillas_huevos // 10
                    separadores_totales = separadores_entre_cajillas + separadores_base_extra
                    
                    print(f"📦 Separadores necesarios: {separadores_totales}")
                    
                    # Verificar stock de separadores
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                    
                    stock_separadores = cursor.fetchone()
                    stock_actual_separadores = stock_separadores['Stock'] if stock_separadores else 0
                    
                    if stock_actual_separadores >= separadores_totales:
                        # Restar separadores
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = Existencias - %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (separadores_totales, ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                        
                        # Registrar separador
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
                for i in range(len(productos_ids)):
                    id_producto = int(productos_ids[i])
                    cantidad = float(cantidades[i]) if cantidades[i] else 0
                    precio = float(precios[i]) if precios[i] else 0
                    
                    if cantidad <= 0 or precio <= 0:
                        continue
                    
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
                
                # 6. Insertar detalle del separador
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
                
                # 7. Manejar crédito o contado
                monto_abono_aplicado = 0
                
                if tipo_venta == 'credito':
                    # Actualizar saldo pendiente del cliente
                    nuevo_saldo = saldo_actual_cliente + total_venta
                    
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = %s,
                            Fecha_Ultimo_Movimiento = NOW(),
                            ID_Ultima_Factura = %s
                        WHERE ID_Cliente = %s
                    """, (nuevo_saldo, id_factura, id_cliente))
                    
                    print(f"💰 Actualizando saldo del cliente:")
                    print(f"   Saldo anterior: C${saldo_actual_cliente:,.2f}")
                    print(f"   + Monto venta: C${total_venta:,.2f}")
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
                        total_venta,
                        id_empresa,
                        total_venta,
                        id_factura,
                        id_usuario
                    ))
                    print(f"💳 Cuenta por cobrar creada")
                    
                    # Si hay abono, aplicarlo después de crear la cuenta por cobrar
                    if realizar_abono and monto_abono > 0:
                        print(f"💵 Procesando abono de C${monto_abono:,.2f}...")
                        
                        # Obtener facturas pendientes del cliente (incluyendo la que acabamos de crear)
                        cursor.execute("""
                            SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente,
                                   Fecha_Vencimiento
                            FROM cuentas_por_cobrar
                            WHERE ID_Cliente = %s 
                              AND Estado IN ('Pendiente', 'Vencida')
                              AND Saldo_Pendiente > 0
                              AND ID_Factura IS NOT NULL
                            ORDER BY Fecha_Vencimiento ASC, Fecha ASC
                        """, (id_cliente,))
                        
                        facturas_abono = cursor.fetchall()
                        
                        if facturas_abono:
                            monto_restante_abono = monto_abono
                            
                            for factura in facturas_abono:
                                if monto_restante_abono <= 0:
                                    break
                                
                                saldo_factura = float(factura['Saldo_Pendiente'])
                                monto_aplicar = min(monto_restante_abono, saldo_factura)
                                nuevo_saldo_factura = saldo_factura - monto_aplicar
                                nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0.01 else 'Pendiente'
                                
                                # Actualizar la factura
                                cursor.execute("""
                                    UPDATE cuentas_por_cobrar
                                    SET Saldo_Pendiente = %s, 
                                        Estado = %s
                                    WHERE ID_Movimiento = %s
                                """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                                
                                monto_restante_abono -= monto_aplicar
                                monto_abono_aplicado += monto_aplicar
                                
                                print(f"  Abono aplicado a {factura['Num_Documento']}: C${monto_aplicar:,.2f}")
                            
                            # Actualizar saldo total del cliente después del abono
                            if monto_abono_aplicado > 0:
                                cursor.execute("""
                                    UPDATE clientes 
                                    SET Saldo_Pendiente_Total = Saldo_Pendiente_Total - %s,
                                        Fecha_Ultimo_Pago = NOW()
                                    WHERE ID_Cliente = %s
                                """, (monto_abono_aplicado, id_cliente))
                                
                                print(f"💰 Saldo del cliente actualizado después del abono: -C${monto_abono_aplicado:,.2f}")
                
                elif tipo_venta == 'contado':
                    cursor.execute("""
                        INSERT INTO caja_movimientos (
                            Fecha, Tipo_Movimiento, Descripcion, Monto, 
                            ID_Factura, ID_Usuario, Referencia_Documento
                        )
                        VALUES (NOW(), 'ENTRADA', %s, %s, %s, %s, %s)
                    """, (
                        f'Venta {perfil_cliente} - Factura #{id_factura} - Cliente: {nombre_cliente}',
                        total_venta,
                        id_factura,
                        id_usuario,
                        f'FAC-{id_factura:05d}'
                    ))
                    print(f"💰 Entrada en caja registrada")
                    
                    # Si es contado y hay abono, procesarlo también
                    if realizar_abono and monto_abono > 0:
                        print(f"💵 Procesando abono de C${monto_abono:,.2f} en venta de contado...")
                        
                        cursor.execute("""
                            SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente
                            FROM cuentas_por_cobrar
                            WHERE ID_Cliente = %s 
                              AND Estado IN ('Pendiente', 'Vencida')
                              AND Saldo_Pendiente > 0
                              AND ID_Factura IS NOT NULL
                            ORDER BY Fecha_Vencimiento ASC, Fecha ASC
                        """, (id_cliente,))
                        
                        facturas_abono = cursor.fetchall()
                        
                        if facturas_abono:
                            monto_restante_abono = monto_abono
                            
                            for factura in facturas_abono:
                                if monto_restante_abono <= 0:
                                    break
                                
                                saldo_factura = float(factura['Saldo_Pendiente'])
                                monto_aplicar = min(monto_restante_abono, saldo_factura)
                                nuevo_saldo_factura = saldo_factura - monto_aplicar
                                nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0.01 else 'Pendiente'
                                
                                cursor.execute("""
                                    UPDATE cuentas_por_cobrar
                                    SET Saldo_Pendiente = %s, 
                                        Estado = %s
                                    WHERE ID_Movimiento = %s
                                """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                                
                                monto_restante_abono -= monto_aplicar
                                monto_abono_aplicado += monto_aplicar
                                
                                print(f"  Abono aplicado a {factura['Num_Documento']}: C${monto_aplicar:,.2f}")
                            
                            if monto_abono_aplicado > 0:
                                cursor.execute("""
                                    UPDATE clientes 
                                    SET Saldo_Pendiente_Total = GREATEST(0, Saldo_Pendiente_Total - %s),
                                        Fecha_Ultimo_Pago = NOW()
                                    WHERE ID_Cliente = %s
                                """, (monto_abono_aplicado, id_cliente))
                                
                                print(f"💰 Saldo del cliente actualizado después del abono: -C${monto_abono_aplicado:,.2f}")
                
                # Construir mensaje de éxito
                success_msg = f'✅ Venta {perfil_cliente} creada! Factura #{id_factura} - Total: C${total_venta:,.2f}'
                
                if tipo_venta == 'credito':
                    nuevo_saldo_final = saldo_actual_cliente + total_venta - monto_abono_aplicado
                    success_msg += f' - Saldo cliente: C${nuevo_saldo_final:,.2f}'
                
                if monto_abono_aplicado > 0:
                    success_msg += f' - Abono aplicado: C${monto_abono_aplicado:,.2f}'
                
                print(f"🎯 {success_msg}")
                flash(success_msg, 'success')
                
                return jsonify({
                    'success': True,
                    'message': success_msg,
                    'id_factura': id_factura,
                    'total_venta': total_venta,
                    'perfil_cliente': perfil_cliente,
                    'cajillas_huevos': total_cajillas_huevos,
                    'separadores': separadores_totales,
                    'abono_aplicado': monto_abono_aplicado,
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
                            id_tipo_movimiento=id_tipo_movimiento)
            
    except Exception as e:
        error_msg = f'❌ Error al procesar venta: {str(e)}'
        print(f"{error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        
        if request.method == 'POST':
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
            # Obtener datos de la factura desde la base de datos
            cursor.execute("""
                SELECT 
                    f.ID_Factura,
                    f.Fecha,
                    f.Observacion,
                    f.Credito_Contado,
                    f.ID_Usuario_Creacion,
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
            
            # Verificar que hay detalles
            if not detalles:
                flash('La factura no tiene detalles de productos', 'error')
                return redirect(url_for('admin.admin_ventas_salidas'))
            
            # Calcular total
            total_venta = sum(float(detalle['Subtotal'] or 0) for detalle in detalles)
            
            # Obtener información del movimiento de inventario
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
            
            # Verificar si tiene cuenta por cobrar
            cursor.execute("""
                SELECT 
                    Saldo_Pendiente,
                    Fecha_Vencimiento
                FROM cuentas_por_cobrar 
                WHERE ID_Factura = %s AND Saldo_Pendiente > 0
            """, (id_factura,))
            cuenta_cobrar = cursor.fetchone()
            
            # Obtener hora exacta actual para el ticket
            hora_emision = datetime.now()
            
            # Preparar datos para el ticket
            ticket_data = {
                'id_factura': factura['ID_Factura'],
                'fecha': factura['Fecha'],  # Fecha original de la factura
                'hora_emision': hora_emision,  # Hora exacta de emisión del ticket
                'cliente': factura['Cliente'] or 'Consumidor Final',
                'ruc_cliente': factura['RUC_Cliente'] or 'Consumidor Final',
                'tipo_venta': factura['Tipo_Venta_Formateado'],
                'observacion': factura['Observacion'],
                'usuario': factura['Usuario'] or 'Usuario No Especificado',
                'detalles': detalles,
                'total': total_venta,
                'empresa': {
                    'nombre': factura['Nombre_Empresa'],
                    'ruc': factura['RUC_Empresa'],
                    'direccion': factura['Direccion_Empresa'],
                    'telefono': factura['Telefono_Empresa']
                },
                'movimiento': movimiento,
                'tiene_credito': cuenta_cobrar is not None,
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
            # 1. Obtener información general de la factura - VERSIÓN CORREGIDA
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
                    -- Formatear tipo de venta (CORRECTO - usa facturacion.Credito_Contado)
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado,
                    -- Campo adicional para compatibilidad
                    f.Credito_Contado as Tipo_Venta_Numerico,
                    -- Estado de factura (varias versiones para compatibilidad)
                    f.Estado as Estado_Factura,  -- 'Activa'/'Anulada'
                    UPPER(f.Estado) as Estado_Factura_Formateado,  -- 'ACTIVA'/'ANULADA'
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 1
                        ELSE 0
                    END as Estado_Factura_Numerico,
                    -- Estado del movimiento (varias versiones para compatibilidad)
                    COALESCE(mi.Estado, 'NO APLICA') as Estado_Movimiento_Formateado,  -- 'Activa'/'Anulada'/'NO APLICA'
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
            
            # 2. Obtener detalles de los productos vendidos - VERSIÓN CORREGIDA
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
                     LIMIT 1),  -- ← AÑADIR LIMIT 1
                    'UNIDAD'
                ) as Unidad_Medida,
                -- CORRECCIÓN: Añadir LIMIT 1 en ambas subconsultas
                COALESCE(
                    (SELECT Existencias 
                     FROM inventario_bodega ib
                     WHERE ib.ID_Producto = p.ID_Producto 
                       AND ib.ID_Bodega = %s
                     LIMIT 1),  -- ← AÑADIR LIMIT 1
                    0
                ) as Existencia_Actual,
                COALESCE(
                    (SELECT dmi.Cantidad 
                     FROM detalle_movimientos_inventario dmi
                     WHERE dmi.ID_Producto = p.ID_Producto
                       AND dmi.ID_Movimiento = %s
                     LIMIT 1),  -- ← AÑADIR LIMIT 1
                    df.Cantidad
                ) as Cantidad_Movimiento
            FROM detalle_facturacion df
            INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
            LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
            WHERE df.ID_Factura = %s
            ORDER BY df.ID_Detalle
        """, (factura['ID_Bodega'] or 1, factura['ID_Movimiento'], id_factura))
            
            detalles = cursor.fetchall()
            
            # 3. Calcular totales
            total_productos = len(detalles)
            total_venta = sum(float(detalle.get('Subtotal', 0)) for detalle in detalles)
            
            # 4. Verificar si tiene crédito pendiente
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
            
            # 5. Obtener historial de pagos si es crédito
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
            
            # 6. Obtener datos del movimiento de inventario (si existe) - VERSIÓN CORREGIDA
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
            
            return render_template('admin/ventas/detalle_venta.html',
                                 factura=factura,
                                 detalles=detalles,
                                 movimiento_info=movimiento_info,
                                 total_productos=total_productos,
                                 total_venta=total_venta,
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
                    flash('Anticipo no encontrado o inactivo', 'error')
                    return redirect(request.url)
                
                # 2. Verificar que la bodega existe y está activa
                cursor.execute("""
                    SELECT ID_Bodega, Nombre
                    FROM bodegas
                    WHERE ID_Bodega = %s AND Estado = 'activa' AND ID_Empresa = %s
                """, (id_bodega, anticipo['ID_Empresa']))
                bodega = cursor.fetchone()
                
                if not bodega:
                    flash('Bodega no encontrada o inactiva', 'error')
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
                
                # 12. Si el anticipo se completó, registrar en bitácora
                if anticipo_cliente_completado:
                    cursor.execute("""
                        INSERT INTO bitacora (ID_Usuario, Accion, Tabla_Afectada, ID_Registro, Detalles, Fecha)
                        VALUES (%s, 'ANTICIPO_COMPLETADO', 'clientes', %s, %s, NOW())
                    """, (id_usuario, anticipo['ID_Cliente'], 
                          f"Anticipo completado para el cliente {anticipo['Nombre_Cliente']}. Total cajas consumidas: {nuevas_cajas_consumidas_cliente}"))
                
                # Redirigir al ticket con auto-impresión
                flash(f'✅ {len(ids_entregas)} entregas registradas exitosamente!', 'success')
                return redirect(url_for('admin.ticket_entregas', id_anticipo=id_anticipo, autoPrint=1))
                
        except ValueError as e:
            flash(f'Error en el formato de los datos: {str(e)}', 'error')
            return redirect(request.url)
        except Exception as e:
            flash(f'Error al registrar la entrega: {str(e)}', 'error')
            return redirect(request.url)
    
    # Método GET - Mostrar la página con datos
    try:
        with get_db_cursor(True) as cursor:
            # Obtener ID de la empresa del usuario actual
            cursor.execute("SELECT ID_Empresa FROM usuarios WHERE ID_Usuario = %s", (current_user.id,))
            usuario = cursor.fetchone()
            empresa_id = usuario['ID_Empresa'] if usuario else None
            
            # 1. Obtener anticipos activos disponibles
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
                    DATE_FORMAT(a.Fecha_Anticipo, '%%d/%%m/%%Y') as Fecha_Anticipo_Formato,
                    DATE_FORMAT(a.Fecha_Vencimiento, '%%d/%%m/%%Y') as Fecha_Vencimiento_Formato,
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
                  AND a.Cajas_Consumidas < a.Cantidad_Cajas
                  AND c.Anticipo_Activo = 1
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
            cursor.execute("""
                SELECT ID_Bodega, Nombre, Ubicacion, Estado
                FROM bodegas
                WHERE ID_Empresa = %s AND Estado = 'activa'
                ORDER BY Nombre
            """, (empresa_id,))
            bodegas = cursor.fetchall()
            
            if not bodegas:
                flash('No hay bodegas activas configuradas para su empresa', 'warning')
            
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
                    COUNT(DISTINCT c.ID_Cliente) as clientes_Con_Anticipos,
                    COALESCE(SUM(c.Saldo_Anticipos), 0) as Saldo_Total_Anticipos
                FROM entregas e
                RIGHT JOIN anticipos_clientes a ON e.ID_Anticipo = a.ID_Anticipo AND DATE(e.Fecha_Entrega) = CURDATE()
                INNER JOIN clientes c ON a.ID_Cliente = c.ID_Cliente
                WHERE a.Estado = 'ACTIVO'
            """)
            estadisticas = cursor.fetchone()
            
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
        flash(f'Error al cargar los datos: {str(e)}', 'error')
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

#==================#
# PEDIDOS DE VENTA #
#==================#
# ============================================
# RUTAS PARA PEDIDOS INDIVIDUALES (CLIENTES)
# ============================================

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

# ============================================
# RUTAS PARA PEDIDOS CONSOLIDADOS (RUTAS)
# ============================================

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
            # ============================================
            # 1. OBTENER DATOS DEL PEDIDO
            # ============================================
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
        return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))


@admin_bp.route('/admin/ventas/procesar-carga-consolidada/<int:id_pedido>', methods=['POST'])
@admin_or_bodega_required
@bitacora_decorator("PROCESAR_CARGA_CONSOLIDADA")
def procesar_carga_consolidada(id_pedido):
    """
    Procesa la distribución de carga consolidada a vendedores
    - Crea movimientos de salida de bodega principal
    - Crea movimientos de entrada en rutas de vendedores
    - Actualiza inventario de rutas
    - Actualiza estado del pedido consolidado
    """
    try:
        # ============================================
        # 1. OBTENER DATOS DEL FORMULARIO
        # ============================================
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
                return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))
            
            if not pedido['ID_Ruta']:
                flash('El pedido no tiene una ruta asignada', 'error')
                return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))
            
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
                    return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))
            
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
                    return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))
                
                producto = productos_dict[id_producto]
                
                if cantidad_solicitada > producto['Cantidad_Total']:
                    flash(f'Cantidad excede el consolidado', 'error')
                    return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))
                
                if cantidad_solicitada > producto['Stock_Disponible']:
                    flash(f'Stock insuficiente en bodega', 'error')
                    return redirect(url_for('admin.admin_ver_pedido', id_pedido=id_pedido))
            
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
            # 6. DISTRIBUIR A VENDEDORES (CORREGIDO)
            # ============================================
            # 6.1 Agrupar productos por vendedor
            from collections import defaultdict
            distribucion_por_vendedor = defaultdict(list)
            
            for item in distribucion:
                distribucion_por_vendedor[item['id_vendedor']].append({
                    'id_producto': item['id_producto'],
                    'cantidad': item['cantidad'],
                    'precio': productos_dict[item['id_producto']]['Precio_Venta']
                })
            
            # 6.2 Procesar cada vendedor (UNA cabecera por vendedor)
            for id_vendedor, productos_vendedor in distribucion_por_vendedor.items():
                # Calcular totales para este vendedor
                total_items = sum([p['cantidad'] for p in productos_vendedor])  # Suma de cantidades
                total_productos = len(productos_vendedor)  # Número de productos distintos
                total_subtotal = sum([p['cantidad'] * p['precio'] for p in productos_vendedor])
                
                # Insertar UNA cabecera por vendedor
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
                    f'CARGA-{id_pedido}',  # Documento único por pedido
                    id_pedido,
                    total_productos,   # Cantidad de productos distintos
                    total_items,       # Suma total de unidades
                    total_subtotal,    # Suma total de subtotales
                    pedido['ID_Empresa']
                ))
                
                movimiento_ruta_id = cursor.lastrowid
                
                # Insertar TODOS los detalles para este vendedor
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
                
                # Actualizar inventario de ruta (sumar todas las cantidades de este vendedor)
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
            # 7. ACTUALIZAR PEDIDO CONSOLIDADO
            # ============================================
            for id_producto, cantidad_solicitada in total_por_producto.items():
                producto = productos_dict[id_producto]
                cantidad_restante = producto['Cantidad_Total'] - cantidad_solicitada
                
                if cantidad_restante > 0:
                    cursor.execute("""
                        UPDATE pedidos_consolidados_productos
                        SET Cantidad_Total = %s
                        WHERE ID_Pedido = %s AND ID_Producto = %s
                    """, (cantidad_restante, id_pedido, id_producto))
                else:
                    cursor.execute("""
                        DELETE FROM pedidos_consolidados_productos
                        WHERE ID_Pedido = %s AND ID_Producto = %s
                    """, (id_pedido, id_producto))
            
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM pedidos_consolidados_productos
                WHERE ID_Pedido = %s
            """, (id_pedido,))
            
            pedido_actualizado = cursor.fetchone()
            
            if pedido_actualizado['total'] == 0:
                cursor.execute("""
                    UPDATE pedidos SET Estado = 'Entregado'
                    WHERE ID_Pedido = %s
                """, (id_pedido,))
                flash(f'✅ Carga #{id_pedido} completada', 'success')
            else:
                flash(f'✅ Distribución parcial - Quedan {pedido_actualizado["total"]} productos', 'success')
            
            return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.ver_pedido', id_pedido=id_pedido))


# ============================================
# RUTAS COMUNES (APLICAN A AMBOS TIPOS DE PEDIDOS)
# ============================================

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

@admin_bp.route('/admin/ventas/pedido-venta/<int:id_pedido>')
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
            
            # Verificar stock de productos
            productos_sin_stock = []
            total_pedido = 0
            total_cajillas_huevos = 0
            ID_CATEGORIA_HUEVOS = 1  # AJUSTAR según tu sistema
            
            for detalle in detalles_pedido:
                id_producto = detalle['ID_Producto']
                cantidad = float(detalle['Cantidad'])
                precio = float(detalle['Precio_Unitario'])
                
                # Verificar stock
                cursor.execute("""
                    SELECT COALESCE(Existencias, 0) as Stock 
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega_principal, id_producto))
                
                stock = cursor.fetchone()
                stock_actual = stock['Stock'] if stock else 0
                
                if stock_actual < cantidad:
                    productos_sin_stock.append({
                        'producto': detalle['Descripcion'],
                        'stock_actual': stock_actual,
                        'cantidad_solicitada': cantidad
                    })
                
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
            print(f"📨 Procesando venta desde pedido #{id_pedido}...")
            
            tipo_venta = request.form.get('tipo_venta', 'contado')
            observacion_adicional = request.form.get('observacion_adicional', '')
            
            with get_db_cursor(True) as cursor:
                # ✅ VALIDACIÓN DE VISIBILIDAD DE PRODUCTOS
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
                    
                    print(f"  {detalle['Descripcion']}: {cantidad} x C${precio} = C${total_linea}")
                
                print(f"📊 Total venta: C${total_venta:,.2f}")
                
                # 3. CALCULAR SEPARADORES NECESARIOS
                separadores_totales = 0
                if total_cajillas_huevos > 0:
                    separadores_entre_cajillas = total_cajillas_huevos
                    separadores_base_extra = total_cajillas_huevos // 10
                    separadores_totales = separadores_entre_cajillas + separadores_base_extra
                    
                    print(f"🔢 CÁLCULO DE SEPARADORES:")
                    print(f"  Cajillas: {total_cajillas_huevos}")
                    print(f"  Separadores totales necesarios: {separadores_totales}")
                
                # 4. DESCONTAR SEPARADORES SI HAY PRODUCTOS DE HUEVOS
                if separadores_totales > 0:
                    print(f"🔧 Descontando {separadores_totales} separadores...")
                    
                    # Verificar stock de separadores
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (ID_BODEGA_EMPAQUE, ID_SEPARADOR))
                    
                    stock_separadores = cursor.fetchone()
                    stock_actual_separadores = stock_separadores['Stock'] if stock_separadores else 0
                    
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
                
                # 11. Actualizar el estado del pedido a "Entregado"
                cursor.execute("""
                    UPDATE pedidos 
                    SET Estado = 'Entregado'
                    WHERE ID_Pedido = %s
                """, (id_pedido,))
                
                print(f"📝 Pedido #{id_pedido} actualizado a estado: Entregado")
                
                # 12. Guardar datos de la venta en la sesión para mostrarlos en el ticket
                session['venta_procesada'] = {
                    'id_factura': id_factura,
                    'id_pedido': id_pedido,
                    'total_venta': total_venta,
                    'tipo_venta': tipo_venta,
                    'nombre_cliente': pedido['Nombre_Cliente'],
                    'fecha': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                }
                
                # 13. Redirigir directamente al ticket SIN mensaje flash
                print(f"🎯 Venta procesada exitosamente! Redirigiendo al ticket #{id_factura}")
                return redirect(url_for('admin.admin_generar_ticket', id_factura=id_factura))
                
    except Exception as e:
        error_msg = f'❌ Error al procesar venta desde pedido: {str(e)}'
        print(f"{error_msg}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        flash(error_msg, 'error')
        return redirect(url_for('admin.admin_pedidos_venta'))


# ============================================
# API ENDPOINTS (DATOS PARA AJAX)
# ============================================

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


# ============================================
# API ESPECÍFICAS PARA CONSOLIDADOS
# ============================================

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

## VEHICULOS
@admin_bp.route('/admin/vehiculos/vehiculos')
@admin_required
def admin_vehiculos():
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT v.*, e.Nombre_Empresa as Nombre_Empresa 
                FROM vehiculos v
                LEFT JOIN empresa e ON v.ID_Empresa = e.ID_Empresa
                ORDER BY v.Fecha_Creacion DESC
            """)
            vehiculos = cursor.fetchall()
            
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
        # Inyectar current_year directamente
        from datetime import datetime
        current_year = datetime.now().year
        
        return render_template('admin/catalog/vehiculo/vehiculo.html', 
                             vehiculos=vehiculos, 
                             empresas=empresas,
                             current_year=current_year)  # Agregar aquí
        
    except Exception as e:
        flash(f'Error al cargar vehículos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/vehiculos/crear', methods=['POST'])
@admin_required
def crear_vehiculo():
    try:
        # Obtener datos del formulario
        placa = request.form.get('placa')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        anio = request.form.get('anio')
        id_empresa = request.form.get('id_empresa')
        tipo_combustible = request.form.get('tipo_combustible')
        fecha_vencimiento_seguro = request.form.get('fecha_vencimiento_seguro')
        
        # Validar datos requeridos
        if not all([placa, id_empresa]):
            flash('Placa y Empresa son campos requeridos', 'error')
            return redirect(url_for('admin.admin_vehiculos'))
        
        with get_db_cursor() as cursor:
            # Verificar si la placa ya existe para esta empresa
            cursor.execute("""
                SELECT ID_Vehiculo FROM vehiculos 
                WHERE Placa = %s AND ID_Empresa = %s
            """, (placa, id_empresa))
            
            if cursor.fetchone():
                flash('La placa ya existe para esta empresa', 'error')
                return redirect(url_for('admin.admin_vehiculos'))
            
            # Insertar nuevo vehículo
            cursor.execute("""
                INSERT INTO vehiculos 
                (Placa, Marca, Modelo, Anio, ID_Empresa, Tipo_Combustible, Fecha_Vencimiento_Seguro)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (placa, marca, modelo, anio, id_empresa, tipo_combustible, fecha_vencimiento_seguro))
            
            flash('Vehículo creado exitosamente', 'success')
            return redirect(url_for('admin.admin_vehiculos'))
            
    except Exception as e:
        flash(f'Error al crear vehículo: {str(e)}', 'error')
        return redirect(url_for('admin.admin_vehiculos'))
    
@admin_bp.route('/admin/vehiculos/<int:id>')
@admin_required
def obtener_vehiculo(id):
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT v.*, e.Nombre_Empresa as Nombre_Empresa 
                FROM vehiculos v
                LEFT JOIN empresa e ON v.ID_Empresa = e.ID_Empresa
                WHERE v.ID_Vehiculo = %s
            """, (id,))
            
            vehiculo = cursor.fetchone()
            
            if not vehiculo:
                return jsonify({'error': 'Vehículo no encontrado'}), 404
            
            # Convertir a diccionario y manejar fechas
            vehiculo_dict = dict(vehiculo)
            vehiculo_dict['Fecha_Vencimiento_Seguro'] = vehiculo['Fecha_Vencimiento_Seguro'].isoformat() if vehiculo['Fecha_Vencimiento_Seguro'] else None
            
            return jsonify(vehiculo_dict)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/vehiculos/editar/<int:id>')
@admin_required
def mostrar_editar_vehiculo(id):
    """Muestra el formulario de edición de vehículo (GET)"""
    try:
        with get_db_cursor(True) as cursor:
            # Obtener datos del vehículo
            cursor.execute("""
                SELECT v.*, e.Nombre_Empresa as Nombre_Empresa 
                FROM vehiculos v
                LEFT JOIN empresa e ON v.ID_Empresa = e.ID_Empresa
                WHERE v.ID_Vehiculo = %s
            """, (id,))
            
            vehiculo = cursor.fetchone()
            
            if not vehiculo:
                flash('Vehículo no encontrado', 'error')
                return redirect(url_for('admin.admin_vehiculos'))
            
            # Obtener lista de empresas activas
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
        # Inyectar current_year
        from datetime import datetime
        current_year = datetime.now().year
        
        # Asegurar que el año sea un entero (year en MySQL puede devolver como decimal)
        if vehiculo['Anio']:
            vehiculo['Anio'] = int(vehiculo['Anio'])
        
        return render_template('admin/catalog/vehiculo/vehiculo_editar.html', 
                             vehiculo=vehiculo, 
                             empresas=empresas,
                             current_year=current_year)
            
    except Exception as e:
        flash(f'Error al cargar formulario de edición: {str(e)}', 'error')
        return redirect(url_for('admin_vehiculos'))

@admin_bp.route('/admin/vehiculos/editar/<int:id>', methods=['POST'])
@admin_required
def procesar_editar_vehiculo(id):
    """Procesa el formulario de edición de vehículo (POST)"""
    try:
        # Obtener datos del formulario
        placa = request.form.get('placa')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        anio = request.form.get('anio')
        id_empresa = request.form.get('id_empresa')
        tipo_combustible = request.form.get('tipo_combustible')
        fecha_vencimiento_seguro = request.form.get('fecha_vencimiento_seguro')
        estado = request.form.get('estado')  # Nuevo campo para estado
        
        # Validar datos requeridos
        if not all([placa, id_empresa, estado]):
            flash('Placa, Empresa y Estado son campos requeridos', 'error')
            return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))
        
        # Validar que el estado sea válido
        estados_validos = ['Disponible', 'En Ruta', 'Mantenimiento', 'Inactivo']
        if estado not in estados_validos:
            flash('Estado inválido', 'error')
            return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))
        
        with get_db_cursor() as cursor:
            # Verificar si la placa ya existe para otra empresa u otro vehículo
            cursor.execute("""
                SELECT ID_Vehiculo FROM vehiculos 
                WHERE Placa = %s AND ID_Empresa = %s AND ID_Vehiculo != %s
            """, (placa, id_empresa, id))
            
            if cursor.fetchone():
                flash('La placa ya existe para esta empresa en otro vehículo', 'error')
                return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))
            
            # Actualizar vehículo con todos los campos incluyendo estado
            cursor.execute("""
                UPDATE vehiculos 
                SET Placa = %s,
                    Marca = %s,
                    Modelo = %s,
                    Anio = %s,
                    ID_Empresa = %s,
                    Tipo_Combustible = %s,
                    Fecha_Vencimiento_Seguro = %s,
                    Estado = %s
                WHERE ID_Vehiculo = %s
            """, (placa, marca, modelo, anio, id_empresa, tipo_combustible, 
                  fecha_vencimiento_seguro, estado, id))
            
            flash('Vehículo actualizado exitosamente', 'success')
            return redirect(url_for('admin.admin_vehiculos'))
            
    except Exception as e:
        flash(f'Error al actualizar vehículo: {str(e)}', 'error')
        return redirect(url_for('admin.mostrar_editar_vehiculo', id=id))

@admin_bp.route('/admin/vehiculos/cambiar-estado/<int:id>', methods=['POST'])
@admin_required
def cambiar_estado_vehiculo(id):
    """Cambia el estado del vehículo entre Activo/Inactivo (POST)"""
    try:
        # Obtener el nuevo estado del formulario
        nuevo_estado = request.form.get('nuevo_estado')
        
        if not nuevo_estado:
            flash('Estado no especificado', 'error')
            return redirect(url_for('admin.admin_vehiculos'))
        
        with get_db_cursor() as cursor:
            # Verificar que el vehículo existe
            cursor.execute("""
                SELECT Estado FROM vehiculos WHERE ID_Vehiculo = %s
            """, (id,))
            
            resultado = cursor.fetchone()
            if not resultado:
                flash('Vehículo no encontrado', 'error')
                return redirect(url_for('admin.admin_vehiculos'))
            
            # Actualizar solo el estado
            cursor.execute("""
                UPDATE vehiculos 
                SET Estado = %s
                WHERE ID_Vehiculo = %s
            """, (nuevo_estado, id))
            
            flash(f'Estado del vehículo actualizado a {nuevo_estado}', 'success')
            return redirect(url_for('admin.admin_vehiculos'))
            
    except Exception as e:
        flash(f'Error al cambiar estado del vehículo: {str(e)}', 'error')
        return redirect(url_for('admin.admin_vehiculos'))
 

## ASIGNACION RUTAS
# Rutas para asignación de rutas
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
    

@admin_bp.route('/admin/facturas/ventas', methods=['GET'])
@admin_required
@bitacora_decorator("FACTURAS_VENTAS")
def admin_facturas_ventas():
    try:
        # Obtener parámetros de filtro
        filtro = request.args.get('filtro', 'mes')
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        
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
            
            # 1. Consulta para ventas de RUTA (todas las rutas)
            query_rutas = f"""
                SELECT 
                    'RUTA' AS tipo,
                    r.Nombre_Ruta AS entidad,
                    COALESCE(
                        (SELECT u.NombreUsuario 
                         FROM asignacion_vendedores av2 
                         INNER JOIN usuarios u ON av2.ID_Usuario = u.ID_Usuario
                         WHERE av2.ID_Ruta = r.ID_Ruta 
                         ORDER BY av2.Fecha_Asignacion DESC 
                         LIMIT 1),
                        'Sin asignar'
                    ) AS vendedor,
                    COUNT(DISTINCT fr.ID_FacturaRuta) AS total_facturas,
                    COALESCE(SUM(dfr.Total), 0) AS total_vendido,
                    MAX(fr.Fecha) AS ultima_fecha,
                    r.Estado AS estado_ruta
                FROM rutas r
                LEFT JOIN asignacion_vendedores av ON r.ID_Ruta = av.ID_Ruta
                LEFT JOIN facturacion_ruta fr ON av.ID_Asignacion = fr.ID_Asignacion 
                    AND fr.Estado = 'Activa'
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
                    u.NombreUsuario AS vendedor,
                    COUNT(DISTINCT f.ID_Factura) AS total_facturas,
                    COALESCE(SUM(df.Total), 0) AS total_vendido,
                    MAX(f.Fecha) AS ultima_fecha,
                    'Activo' AS estado_ruta
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
                    {where_condition_ruta.replace('fr.Fecha =', 'fr.Fecha =') if where_condition_ruta else ''}
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
                    {where_condition_local.replace('f.Fecha =', 'f.Fecha =') if where_condition_local else ''}
                GROUP BY f.Fecha
                ORDER BY f.Fecha
            """
            
            # 4. Top 5 vendedores
            query_top_vendedores = f"""
                (SELECT 
                    u.NombreUsuario AS vendedor,
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
            
            # Calcular totales
            total_facturas = sum(v.get('total_facturas') or 0 for v in ventas)
            total_vendido = sum(v.get('total_vendido') or 0 for v in ventas)
            total_rutas = sum(v.get('total_vendido') or 0 for v in ventas if v.get('tipo') == 'RUTA')
            total_local = sum(v.get('total_vendido') or 0 for v in ventas if v.get('tipo') == 'LOCAL')
            
            # Preparar datos para gráficos
            fechas = sorted(set([e['Fecha'] for e in evolucion_ruta] + [e['Fecha'] for e in evolucion_local]))
            datos_ruta = []
            datos_local = []
            
            for fecha in fechas:
                ruta_valor = next((e['total_dia'] for e in evolucion_ruta if e['Fecha'] == fecha), 0)
                local_valor = next((e['total_dia'] for e in evolucion_local if e['Fecha'] == fecha), 0)
                datos_ruta.append(float(ruta_valor))
                datos_local.append(float(local_valor))
            
            # Datos para gráfico de torta (Ruta vs Local)
            torta_data = [float(total_rutas), float(total_local)]
            
            return render_template(
                'admin/ventas/facturas_ventas.html',
                ventas=ventas,
                total_facturas=total_facturas,
                total_vendido=total_vendido,
                total_rutas=total_rutas,
                total_local=total_local,
                filtro_actual=filtro,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                fechas_grafico=[f.strftime('%Y-%m-%d') if hasattr(f, 'strftime') else str(f) for f in fechas],
                datos_ruta_grafico=datos_ruta,
                datos_local_grafico=datos_local,
                torta_data=torta_data,
                top_vendedores=top_vendedores
            )
            
    except Exception as e:
        flash(f"Error al cargar ventas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

# MODULO DE COMPRAS #
@admin_bp.route('/admin/compras/compras-entradas', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS")
def admin_compras_entradas():
    # ========== EXTRAER FILTROS DEL REQUEST ==========
    fecha_str = request.args.get('fecha')
    estado_filtro = request.args.get('estado', 'todas').upper()
    tipo_filtro = request.args.get('tipo', '').upper()
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else None
        
        with get_db_cursor() as cursor:
            # ========== CONSTRUIR CONDICIONES WHERE DINÁMICAMENTE ==========
            where_conditions = []
            params = []
            
            # Condición base de catálogo de movimientos (siempre presente)
            where_conditions.append("(cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')")
            
            # Filtro por estado
            if estado_filtro == 'ACTIVAS':
                where_conditions.append("mi.Estado = 'Activa'")
            elif estado_filtro == 'ANULADAS':
                where_conditions.append("mi.Estado = 'Anulada'")
            elif estado_filtro == 'TODAS':
                # No aplicar filtro de estado específico
                pass
            else:
                # Por defecto, mostrar solo activas
                where_conditions.append("mi.Estado = 'Activa'")
            
            # Filtro por tipo de compra (Contado/Crédito)
            if tipo_filtro == 'CONTADO':
                where_conditions.append("mi.Tipo_Compra = 'CONTADO'")
            elif tipo_filtro == 'CREDITO':
                where_conditions.append("mi.Tipo_Compra = 'CREDITO'")
            
            # Filtro por fecha (opcional)
            if fecha and fecha_str:
                where_conditions.append("DATE(mi.Fecha) = %s")
                params.append(fecha)
            
            # Construir WHERE clause - IMPORTANTE: siempre comenzar con WHERE y usar AND
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # ========== CONSULTA 1: Obtener entradas con filtros ==========
            query = f"""
                SELECT 
                    mi.ID_Movimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    mi.Fecha_Creacion,
                    p.Nombre as Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Estado,
                    COALESCE(detalle.Total_Productos, 0) as Total_Productos,
                    COALESCE(detalle.Total_Compra, 0) as Total_Compra,
                    -- Campos formateados para mostrar en la tabla
                    DATE_FORMAT(mi.Fecha, '%%d/%%m/%%Y') as Fecha_Formateada,
                    DATE_FORMAT(mi.Fecha_Creacion, '%%H:%%i') as Hora_Formateada,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'ACTIVA'
                        WHEN mi.Estado = 'Anulada' THEN 'ANULADA'
                        ELSE UPPER(mi.Estado)
                    END as Estado_Formateado,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'badge-success'
                        WHEN mi.Estado = 'Anulada' THEN 'badge-danger'
                        ELSE 'badge-secondary'
                    END as Estado_Clase,
                    CASE 
                        WHEN mi.Tipo_Compra = 'CONTADO' THEN 'CONTADO'
                        WHEN mi.Tipo_Compra = 'CREDITO' THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Compra_Formateado
                FROM movimientos_inventario mi
                LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN (
                    SELECT 
                        ID_Movimiento,
                        COUNT(*) as Total_Productos,
                        SUM(COALESCE(Subtotal, 0)) as Total_Compra
                    FROM detalle_movimientos_inventario
                    GROUP BY ID_Movimiento
                ) detalle ON mi.ID_Movimiento = detalle.ID_Movimiento
                {where_clause}
                ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
                LIMIT 30
            """
            
            print("SQL Query:", query)  # Para depuración
            print("Params:", params)     # Para depuración
            
            cursor.execute(query, tuple(params))
            compras = cursor.fetchall()
            
            # Procesar resultados para convertir a diccionario y asegurar valores
            compras_procesadas = []
            for compra in compras:
                compra_dict = dict(compra)
                # Asegurar que los campos tengan valores por defecto
                compra_dict['Fecha_Formateada'] = compra_dict.get('Fecha_Formateada', 'N/A')
                compra_dict['Hora_Formateada'] = compra_dict.get('Hora_Formateada', '')
                compra_dict['Total_Productos'] = compra_dict.get('Total_Productos') or 0
                compra_dict['Total_Compra'] = float(compra_dict.get('Total_Compra') or 0)
                compras_procesadas.append(compra_dict)
            
            # ========== CONSULTAS DE RESUMEN FINANCIERO (TODAS ACTIVAS) ==========
            
            # **CONSULTA 2: Capital Invertido TOTAL (Contado + Crédito) - SOLO ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Total
                FROM movimientos_inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND (cm.Descripcion LIKE '%compra%' OR cm.Descripcion LIKE '%COMPRA%')
            """)
            resultado_total = cursor.fetchone()
            capital_total = float(resultado_total['Capital_Total']) if resultado_total and resultado_total['Capital_Total'] else 0.0
            
            # **CONSULTA 3: Capital Invertido SOLO AL CONTADO - SOLO ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Contado
                FROM movimientos_inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Tipo_Compra = 'CONTADO'
                    AND (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND (cm.Descripcion LIKE '%compra%' OR cm.Descripcion LIKE '%COMPRA%')
            """)
            resultado_contado = cursor.fetchone()
            capital_contado = float(resultado_contado['Capital_Contado']) if resultado_contado and resultado_contado['Capital_Contado'] else 0.0
            
            # **CONSULTA 4: Capital en CRÉDITO (deudas pendientes) - SOLO ACTIVAS**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Credito
                FROM movimientos_inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Tipo_Compra = 'CREDITO'
                    AND (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND (cm.Descripcion LIKE '%compra%' OR cm.Descripcion LIKE '%COMPRA%')
            """)
            resultado_credito = cursor.fetchone()
            capital_credito = float(resultado_credito['Capital_Credito']) if resultado_credito and resultado_credito['Capital_Credito'] else 0.0
            
            # Validar consistencia
            capital_total_calculado = capital_contado + capital_credito
            diferencia = abs(capital_total - capital_total_calculado)
            
            if diferencia > 0.01:
                print(f"⚠️ ADVERTENCIA: Discrepancia detectada en compras")
                print(f"   Total BD: {capital_total}, Contado: {capital_contado}, Crédito: {capital_credito}")
                print(f"   Suma manual: {capital_total_calculado}, Diferencia: {diferencia}")
                capital_total = capital_total_calculado
            
            # ========== ESTADÍSTICAS PARA LOS FILTROS ==========
            
            # Obtener estadísticas por estado
            cursor.execute("""
                SELECT 
                    mi.Estado,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(dmi.Subtotal), 0) as total_monto
                FROM movimientos_inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                GROUP BY mi.Estado
            """)
            estadisticas_estado = cursor.fetchall()
            
            # Obtener estadísticas por tipo de compra
            cursor.execute("""
                SELECT 
                    mi.Tipo_Compra,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(dmi.Subtotal), 0) as total_monto
                FROM movimientos_inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND mi.Estado = 'Activa'
                GROUP BY mi.Tipo_Compra
            """)
            estadisticas_tipo = cursor.fetchall()
            
            # ========== ESTADÍSTICAS PARA LAS ENTRADAS MOSTRADAS ==========
            total_compras = len(compras_procesadas)
            total_invertido_lista = sum(float(compra.get('Total_Compra') or 0) for compra in compras_procesadas)
            total_productos_mostrados = sum(int(compra.get('Total_Productos') or 0) for compra in compras_procesadas)
            contado_mostradas = sum(1 for compra in compras_procesadas if compra.get('Tipo_Compra') == 'CONTADO')
            credito_mostradas = sum(1 for compra in compras_procesadas if compra.get('Tipo_Compra') == 'CREDITO')
            activas_mostradas = sum(1 for compra in compras_procesadas if compra.get('Estado') == 'Activa')
            anuladas_mostradas = sum(1 for compra in compras_procesadas if compra.get('Estado') == 'Anulada')
            
            return render_template('admin/compras/compras_entradas.html',
                                 # Datos de la tabla
                                 compras=compras_procesadas,
                                 
                                 # Estadísticas de las compras MOSTRADAS
                                 total_compras=total_compras,
                                 total_invertido=total_invertido_lista,
                                 total_productos=total_productos_mostrados,
                                 compras_contado=contado_mostradas,
                                 compras_credito=credito_mostradas,
                                 compras_activas=activas_mostradas,
                                 compras_anuladas=anuladas_mostradas,
                                 
                                 # Resumen financiero TOTAL
                                 capital_total=capital_total,
                                 capital_contado=capital_contado,
                                 capital_credito=capital_credito,
                                 
                                 # Filtros actuales
                                 fecha_filtro=fecha,
                                 estado_filtro=estado_filtro,
                                 tipo_filtro=tipo_filtro,
                                 
                                 # Estadísticas para mostrar en los filtros
                                 estadisticas_estado=estadisticas_estado,
                                 estadisticas_tipo=estadisticas_tipo)
                                 
    except Exception as e:
        flash(f'Error al cargar entradas de compras: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/compras/compras-entradas/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-CREAR")
def admin_crear_compra():
    try:
        if request.method == 'GET':
            id_empresa = session.get('id_empresa', 1)
            
            with get_db_cursor(True) as cursor:  
                cursor.execute("SELECT ID_Proveedor, Nombre FROM proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
                proveedores = cursor.fetchall()
                
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                # CONSULTA MODIFICADA: Eliminamos Precio_Venta de la consulta
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.ID_Categoria, 
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    WHERE p.Estado = 'activo'
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_empresa,))
                productos = cursor.fetchall()
                
                return render_template('admin/compras/crear_compra.html',
                                    proveedores=proveedores,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias)
        
        elif request.method == 'POST':
            # Obtener datos del formulario
            id_usuario_creacion = current_user.id
            id_tipo_movimiento = 1
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario - AHORA SOLO CON PRODUCTO, CANTIDAD Y COSTO
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            costos_unitarios = request.form.getlist('costos_unitarios[]')
            
            print(f"Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_creacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin.admin_crear_compra'))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin.admin_crear_compra'))
            
            # Construir lista de productos - AHORA SIN PRECIO_VENTA
            for i in range(len(producto_ids)):
                if producto_ids[i] and cantidades[i] and costos_unitarios[i]:
                    cantidad = round(float(cantidades[i]), 2)
                    costo_unitario = round(float(costos_unitarios[i]), 2)
                    
                    # El precio_unitario ahora será igual al costo_unitario
                    # para mantener compatibilidad con la estructura de la BD
                    precio_unitario = costo_unitario
                    
                    productos.append({
                        'id_producto': producto_ids[i],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'precio_unitario': precio_unitario  # Se mantiene igual al costo
                    })
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_creacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin.admin_crear_compra'))
            
            # USAR TRANSACCIÓN CON COMMIT
            with get_db_cursor(commit=True) as cursor:
                # Calcular total de la compra
                total_compra = sum(
                    producto['cantidad'] * producto['costo_unitario'] 
                    for producto in productos
                )
                
                # Insertar movimiento principal
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        ID_TipoMovimiento, N_Factura_Externa, Fecha, ID_Proveedor, 
                        Tipo_Compra, Observacion, ID_Empresa, ID_Bodega, 
                        ID_Usuario_Creacion, ID_Usuario_Modificacion, Estado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_proveedor if id_proveedor else None,
                    tipo_compra,
                    observacion,
                    session.get('id_empresa', 1),
                    id_bodega,
                    id_usuario,
                    id_usuario,
                    1  # Estado activo/completado
                ))
                
                id_movimiento = cursor.lastrowid
                print(f"Movimiento creado con ID: {id_movimiento}")
                
                # Insertar detalles del movimiento - AHORA CON PRECIO_UNITARIO IGUAL AL COSTO
                for producto in productos:
                    subtotal = round(producto['cantidad'] * producto['costo_unitario'], 2)
                    
                    # Insertar detalle del movimiento
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                            Precio_Unitario, Subtotal, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['costo_unitario'],
                        producto['precio_unitario'],  # Ahora es igual al costo
                        subtotal,
                        id_usuario
                    ))
                    
                    # Actualizar inventario_bodega (existencias por bodega)
                    cursor.execute("""
                        SELECT ID_Producto FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega, producto['id_producto']))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        # Actualizar existencias si ya existe
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = Existencias + %s 
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (producto['cantidad'], id_bodega, producto['id_producto']))
                    else:
                        # Insertar nuevo registro si no existe
                        cursor.execute("""
                            INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                        """, (id_bodega, producto['id_producto'], producto['cantidad']))
                
                    # CREAR CUENTA POR PAGAR SI ES CRÉDITO
                    if tipo_compra == 'CREDITO' and id_proveedor:
                        if not fecha_vencimiento:
                            from datetime import datetime, timedelta
                            fecha_compra = datetime.strptime(fecha, '%Y-%m-%d')
                            fecha_vencimiento = (fecha_compra + timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO cuentas_por_pagar (
                                ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, Observacion,
                                Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                                Saldo_Pendiente, ID_Usuario_Creacion, Estado
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento,
                            fecha,
                            id_proveedor,
                            n_factura_externa or '',
                            observacion or 'Compra a crédito',
                            fecha_vencimiento,
                            id_tipo_movimiento,
                            total_compra,
                            session.get('id_empresa', 1),
                            total_compra,
                            id_usuario,
                            'Pendiente'
                        ))
                
                flash(f'Compra creada exitosamente', 'success')
                return redirect(url_for('admin.admin_compras_entradas'))            
    except Exception as e:
        print(f"Error completo al crear compra: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Error al crear compra: {str(e)}', 'error')
        return redirect(url_for('admin.admin_crear_compra'))

@admin_bp.route('/compras/productos-por-categoria/<int:id_categoria>')
@admin_required
def obtener_productos_por_categoria_compra(id_categoria):
    """
    Obtiene productos filtrados por categoría usando inventario_bodega
    RUTA FUNCIONANDO: ✅ (MODIFICADA: SIN PRECIO_VENTA)
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener bodega de la empresa
            cursor.execute("""
                SELECT ID_Bodega FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 1 LIMIT 1
            """, (id_empresa,))
            bodega_result = cursor.fetchone()
            
            if not bodega_result:
                return jsonify({'error': 'No se encontró bodega para la empresa'}), 404
            
            id_bodega = bodega_result['ID_Bodega']
            
            if id_categoria == 0:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.ID_Categoria,
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                        AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo'
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_bodega, id_empresa))
            else:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.ID_Categoria,
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                        AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo'
                    AND p.ID_Categoria = %s 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY p.Descripcion
                """, (id_bodega, id_categoria, id_empresa))
            
            productos = cursor.fetchall()
            productos_list = [{
                'id': p['ID_Producto'],
                'codigo': p['COD_Producto'],
                'descripcion': p['Descripcion'],
                'existencias': float(p['Existencias']),
                'id_categoria': p['ID_Categoria'],
                'categoria': p['Categoria'],
                'unidad_medida': p['Unidad_Medida'],
                'simbolo_medida': p['Simbolo_Medida']
            } for p in productos]
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener productos: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/compras/verificar-existencias/<int:id_producto>')
@admin_required
def verificar_existencias_producto(id_producto):
    """
    Verifica existencias de un producto usando inventario_bodega
    RUTA FUNCIONANDO: ✅
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener bodega de la empresa
            cursor.execute("""
                SELECT ID_Bodega FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 1 LIMIT 1
            """, (id_empresa,))
            bodega_result = cursor.fetchone()
            
            if not bodega_result:
                return jsonify({'error': 'No se encontró bodega'}), 404
            
            id_bodega = bodega_result['ID_Bodega']
            
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion,
                    COALESCE(p.Precio_Mercado, 0) as Precio_Venta,
                    um.Descripcion as Unidad_Medida,
                    COALESCE(ib.Existencias, 0) as Existencias
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE p.ID_Producto = %s 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND p.Estado = 'activo'
            """, (id_bodega, id_producto, id_empresa))
            
            producto = cursor.fetchone()
            
            if producto:
                return jsonify({
                    'id_producto': producto['ID_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']),
                    'precio_venta': float(producto['Precio_Venta']),
                    'unidad_medida': producto['Unidad_Medida']
                })
            else:
                return jsonify({'error': 'Producto no encontrado'}), 404
                
    except Exception as e:
        print(f"❌ Error al verificar existencias: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/compras/categorias-productos')
@admin_required
def obtener_categorias_productos_compra():
    """
    Obtiene todas las categorías de productos
    RUTA FUNCIONANDO: ✅
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            categorias_list = [{
                'id': c['ID_Categoria'],
                'descripcion': c['Descripcion']
            } for c in categorias]
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f"❌ Error al obtener categorías: {str(e)}")
        return jsonify({'error': str(e)}), 500

def obtener_id_bodega_empresa(id_empresa=None):
    """
    Obtiene el ID de la bodega principal de una empresa
    FUNCIÓN AUXILIAR: ✅
    """
    if id_empresa is None:
        id_empresa = session.get('id_empresa', 1)
    
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Bodega 
                FROM bodegas 
                WHERE ID_Empresa = %s 
                AND Estado = 1
                LIMIT 1
            """, (id_empresa,))
            
            result = cursor.fetchone()
            return result['ID_Bodega'] if result else None
    except Exception as e:
        print(f"❌ Error al obtener bodega: {str(e)}")
        return None

@admin_bp.route('/compras/compras-entradas/anular/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-ANULAR")
def admin_anular_compra(id_movimiento):
    """Anular una compra existente - Versión SIMPLIFICADA (solo cambiar estado)"""
    
    # Si es GET, mostrar información de la compra
    if request.method == 'GET':
        try:
            with get_db_cursor(commit=False) as cursor:
                # Consulta básica sin validaciones complejas
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.N_Factura_Externa,
                        mi.Fecha,
                        mi.Tipo_Compra,
                        mi.Estado,
                        p.Nombre as Proveedor,
                        b.Nombre as Bodega,
                        COALESCE((
                            SELECT COUNT(*) 
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ), 0) as Total_Productos,
                        COALESCE((
                            SELECT SUM(COALESCE(Subtotal, 0))
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ), 0) as Total_Compra
                    FROM movimientos_inventario mi
                    LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    WHERE mi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                compra = cursor.fetchone()
                
                if not compra:
                    return jsonify({'success': False, 'error': 'Compra no encontrada'}), 404
                
                if compra['Estado'] != 'Activa':
                    estado_texto = "anulada" if compra['Estado'] == 'Anulada' else compra['Estado'].lower()
                    return jsonify({'success': False, 'error': f'La compra #{id_movimiento} ya está {estado_texto}'}), 400
                
                carga_completa = request.args.get('completa', '0') == '1'
                total_compra = float(compra['Total_Compra'] or 0)
                
                datos_respuesta = {
                    'success': True,
                    'compra': {
                        'id': compra['ID_Movimiento'],
                        'factura': compra['N_Factura_Externa'] or 'Sin factura',
                        'tipo_compra': compra['Tipo_Compra'],
                        'fecha': compra['Fecha'].strftime('%d/%m/%Y') if compra['Fecha'] else 'N/A',
                        'total_compra': total_compra,
                        'total_formateado': f"C${total_compra:,.2f}",
                        'proveedor': compra['Proveedor'] or 'Proveedor General',
                        'bodega': compra['Bodega'] or 'N/A',
                        'estado': compra['Estado'],
                        'total_productos': compra['Total_Productos'] or 0,
                        'carga_completa': carga_completa,
                        'stock_suficiente': True  # Siempre True porque no validamos stock
                    }
                }
                
                if carga_completa:
                    cursor.execute("""
                        SELECT 
                            p.COD_Producto,
                            p.Descripcion,
                            p.Unidad_Medida,
                            dmi.Cantidad,
                            dmi.Costo_Unitario,
                            dmi.Subtotal,
                            0 as Stock_Actual  # No verificamos stock
                        FROM detalle_movimientos_inventario dmi
                        INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                        WHERE dmi.ID_Movimiento = %s
                        ORDER BY p.Descripcion
                    """, (id_movimiento,))
                    
                    productos = cursor.fetchall()
                    
                    if productos:
                        productos_formateados = []
                        total_cantidad = 0
                        
                        for producto in productos:
                            cantidad = float(producto['Cantidad'] or 0)
                            
                            productos_formateados.append({
                                'codigo': producto['COD_Producto'],
                                'descripcion': producto['Descripcion'],
                                'unidad': producto['Unidad_Medida'],
                                'cantidad': cantidad,
                                'costo_unitario': float(producto['Costo_Unitario'] or 0),
                                'subtotal': float(producto['Subtotal'] or 0),
                                'stock_actual': 0,  # No verificamos
                                'suficiente_stock': True  # Siempre True
                            })
                            total_cantidad += cantidad
                        
                        datos_respuesta['compra']['productos'] = productos_formateados
                        datos_respuesta['compra']['total_cantidad'] = total_cantidad
                        datos_respuesta['compra']['stock_suficiente'] = True
                
                return jsonify(datos_respuesta)
                
        except Exception as e:
            print(f"Error en GET anular compra {id_movimiento}: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Error al obtener datos: {str(e)}'}), 500
    
    # Si es POST, procesar la anulación (SOLO CAMBIAR ESTADO)
    elif request.method == 'POST':
        try:
            # Obtener datos del formulario
            id_usuario_anulacion = current_user.id
            motivo_anulacion = request.form.get('motivo_anulacion', '').strip()
            
            # Validaciones básicas
            if not id_usuario_anulacion:
                flash('Error: No se especificó el usuario que realiza la anulación', 'error')
                return redirect(url_for('admin.admin_compras_entradas'))
            
            try:
                id_usuario = int(id_usuario_anulacion)
            except (ValueError, TypeError):
                flash('Error: ID de usuario inválido', 'error')
                return redirect(url_for('admin.admin_compras_entradas'))
            
            if not motivo_anulacion:
                motivo_anulacion = f"Compra anulada por usuario ID {id_usuario}"
            
            # TRANSACCIÓN SIMPLIFICADA - Solo cambiar estado
            with get_db_cursor(commit=True) as cursor:
                # 1. Verificar que el movimiento existe y está activo
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.Estado,
                        mi.N_Factura_Externa,
                        mi.Observacion,
                        COALESCE((
                            SELECT SUM(Subtotal) 
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ), 0) as Total_Compra
                    FROM movimientos_inventario mi
                    WHERE mi.ID_Movimiento = %s
                    FOR UPDATE
                """, (id_movimiento,))
                
                movimiento = cursor.fetchone()
                
                if not movimiento:
                    flash('Error: Compra no encontrada', 'error')
                    return redirect(url_for('admin.admin_compras_entradas'))
                
                if movimiento['Estado'] != 'Activa':
                    flash(f'Error: La compra ya está {movimiento["Estado"].lower()}', 'error')
                    return redirect(url_for('admin.admin_compras_entradas'))
                
                n_factura_externa = movimiento['N_Factura_Externa']
                total_compra = float(movimiento['Total_Compra'] or 0)
                
                # 2. Actualizar observación con el motivo de anulación
                nueva_observacion = (
                    f"{movimiento['Observacion'] or ''}\n"
                    f"[ANULADA] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                    f"por usuario {id_usuario}. Motivo: {motivo_anulacion}"
                )
                
                if len(nueva_observacion) > 65535:
                    nueva_observacion = nueva_observacion[:65530] + "..."
                
                # 3. SIMPLEMENTE cambiar el estado a 'Anulada'
                cursor.execute("""
                    UPDATE movimientos_inventario 
                    SET Estado = 'Anulada',
                        ID_Usuario_Modificacion = %s,
                        Fecha_Modificacion = NOW(),
                        Observacion = %s
                    WHERE ID_Movimiento = %s
                """, (id_usuario, nueva_observacion, id_movimiento))
                
                # 4. Registrar en bitácora (opcional)
                try:
                    cursor.execute("""
                        INSERT INTO bitacora 
                        (ID_Usuario, Fecha, Modulo, Accion, IP_Acceso)
                        VALUES (%s, NOW(), 'COMPRAS', 'ANULACION_COMPRA_SIMPLE', %s)
                    """, (id_usuario, request.remote_addr or '127.0.0.1'))
                except Exception as e:
                    print(f"Nota: No se pudo registrar en bitácora: {e}")
                
                # 5. Mensaje de éxito
                mensaje = Markup(
                    f"✅ <strong>Compra anulada exitosamente</strong><br>"
                    f"• Número de compra: #{id_movimiento}<br>"
                    f"• Factura: {n_factura_externa or 'N/A'}<br>"
                    f"• Total compra: C${total_compra:,.2f}<br>"
                    f"• Motivo: {motivo_anulacion[:100]}<br>"
                    f"<small class='text-muted'>Nota: Solo se cambió el estado, el inventario no se modificó</small>"
                )
                
                flash(mensaje, 'success')
            
            return redirect(url_for('admin.admin_compras_entradas'))
            
        except Exception as e:
            print(f"Error al anular compra {id_movimiento}: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error al anular compra: {str(e)}', 'error')
            return redirect(url_for('admin.admin_compras_entradas'))
    
@admin_bp.route('/admin/compras/compras-entradas/detalle-completo/<int:id_movimiento>', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-DETALLE-COMPLETO")
def admin_detalle_compra_completo(id_movimiento):
    try:
        with get_db_cursor(True) as cursor:
            # CONSULTA PRINCIPAL CORREGIDA
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.ID_TipoMovimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    mi.ID_Proveedor,
                    p.Nombre as Proveedor,
                    p.RUC_CEDULA as RUC_Proveedor,
                    p.Direccion as Direccion_Proveedor,
                    p.Telefono as Telefono_Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    mi.ID_Bodega,
                    b.Nombre as Bodega,
                    b.Ubicacion as Direccion_Bodega,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Fecha_Creacion,
                    u_mod.NombreUsuario as Usuario_Modificacion,
                    mi.Fecha_Modificacion,
                    mi.Estado,
                    (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                     WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Compra,
                    (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                     WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Productos
                FROM movimientos_inventario mi
                LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN usuarios u_mod ON mi.ID_Usuario_Modificacion = u_mod.ID_Usuario
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash('Compra no encontrada', 'error')
                return redirect(url_for('admin.admin_compras_entradas'))
            
            # DETALLES CORREGIDOS - SIN LOTE Y FECHA_VENCIMIENTO
            cursor.execute("""
                SELECT 
                    dmi.ID_Detalle_Movimiento,
                    dmi.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto_Desc,
                    COALESCE(ib.Existencias, 0) as Existencias_Actuales,
                    dmi.Cantidad,
                    dmi.Costo_Unitario,
                    dmi.Precio_Unitario,
                    dmi.Subtotal,
                    um.Descripcion as Unidad_Medida,
                    um.Abreviatura as Simbolo_Medida
                FROM detalle_movimientos_inventario dmi
                INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON dmi.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (movimiento['ID_Bodega'], id_movimiento))
            
            detalles = cursor.fetchall()
            
            # CUENTAS POR PAGAR CORREGIDA
            cursor.execute("""
                SELECT 
                    ID_Cuenta,
                    Fecha_Vencimiento,
                    Monto_Movimiento,
                    Saldo_Pendiente
                FROM cuentas_por_pagar 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta_por_pagar = cursor.fetchone()
            
            # Calcular total de cantidad
            total_cantidad = sum([detalle['Cantidad'] for detalle in detalles]) if detalles else 0
            
            now = datetime.now().date()
            
            return render_template(
                'admin/compras/detalle_compra.html',
                movimiento=movimiento,
                detalles=detalles,
                cuenta_por_pagar=cuenta_por_pagar,
                total_cantidad=total_cantidad,
                now=now,
                title="Detalles de Compra"
            )
                                
    except Exception as e:
        print(f"Error al cargar detalle completo de compra: {str(e)}")
        flash(f'Error al cargar detalles: {str(e)}', 'error')
        return redirect(url_for('admin.admin_compras_entradas'))

# CUENTAS POR PAGAR 
@admin_bp.route('/admin/compras/cxpagar/cuentas-por-pagar', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-CUENTAS-POR-PAGAR")
def admin_cuentas_por_pagar():
    try:
        # Obtener parámetro de filtro de estado
        filtro_estado = request.args.get('estado', 'Pendiente')
        
        with get_db_cursor(True) as cursor:
            # Construir consulta dinámica según filtro
            query = """
                SELECT 
                    cpp.ID_Cuenta,
                    cpp.Fecha,
                    cpp.ID_Proveedor,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    cpp.Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    cpp.Estado,
                    u.NombreUsuario as Usuario_Creacion,
                    DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) as dias_vencimiento
                FROM cuentas_por_pagar cpp
                LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON cpp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE 1=1
            """
            
            params = []
            
            # Aplicar filtro de estado
            if filtro_estado == 'Pendiente':
                query += " AND cpp.Estado = 'Pendiente' AND cpp.Saldo_Pendiente > 0"
            elif filtro_estado == 'Pagada':
                query += " AND cpp.Estado = 'Pagada'"
            elif filtro_estado == 'Anulada':
                query += " AND cpp.Estado = 'Anulada'"
            elif filtro_estado == 'Todas':
                # No aplicar filtro
                pass
                
            query += " ORDER BY cpp.Fecha_Vencimiento ASC"
            
            cursor.execute(query, params)
            cuentas = cursor.fetchall()
            
            # Calcular estadísticas solo para cuentas pendientes
            cuentas_pendientes = [c for c in cuentas if c['Estado'] == 'Pendiente']
            total_pendiente = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas_pendientes if cuenta['Saldo_Pendiente'])
            cuentas_vencidas = sum(1 for cuenta in cuentas_pendientes if cuenta['dias_vencimiento'] and cuenta['dias_vencimiento'] < 0)
            
            # Calcular totales de la tabla actual
            total_monto = sum(cuenta['Monto_Movimiento'] for cuenta in cuentas if cuenta['Monto_Movimiento'])
            total_saldo = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas if cuenta['Saldo_Pendiente'])
            
            hoy = datetime.now()
            
            return render_template('admin/compras/cxpagar/cuentas_por_pagar.html', 
                                 cuentas=cuentas,
                                 total_pendiente=total_pendiente,
                                 cuentas_vencidas=cuentas_vencidas,
                                 filtro_estado=filtro_estado,
                                 total_cuentas=len(cuentas),
                                 total_monto=total_monto,
                                 total_saldo=total_saldo,
                                 hoy=hoy)
    except Exception as e:
        print(f"Error al cargar cuentas por pagar: {str(e)}")
        flash(f'Error al cargar cuentas por pagar: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/compras/cuentas-por-pagar/pagar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-REGISTRAR-PAGO")
def registrar_pago_cuenta():
    try:
        if request.method == 'GET':
            # Cargar métodos de pago para el formulario
            with get_db_cursor(True) as cursor:
                cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
                metodos_pago = cursor.fetchall()
                
                # Obtener información de la cuenta si se proporciona ID
                id_cuenta = request.args.get('id_cuenta')
                cuenta_info = None
                if id_cuenta:
                    cursor.execute("""
                        SELECT 
                            cpp.ID_Cuenta,
                            cpp.Saldo_Pendiente,
                            cpp.ID_Proveedor,
                            p.Nombre as Proveedor,
                            cpp.Num_Documento,
                            cpp.Monto_Movimiento,
                            cpp.Estado  -- NUEVO: Incluir el campo Estado
                        FROM cuentas_por_pagar cpp
                        LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                        WHERE cpp.ID_Cuenta = %s
                        AND cpp.Estado = 'Pendiente'  -- NUEVO: Solo cuentas pendientes
                    """, (id_cuenta,))
                    cuenta_info = cursor.fetchone()
                    
                    # Validar que la cuenta existe y está pendiente
                    if not cuenta_info:
                        flash('Cuenta no encontrada o ya está pagada/anulada', 'error')
                        return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                return render_template('admin/compras/cxpagar/registrar_pago.html',
                                     metodos_pago=metodos_pago,
                                     cuenta_info=cuenta_info)
        
        elif request.method == 'POST':
            # Procesar el pago
            id_cuenta = request.form['id_cuenta']
            monto_pago = float(request.form['monto_pago'])
            fecha_pago = request.form['fecha_pago']
            id_metodo_pago = request.form['id_metodo_pago']
            detalles_metodo = request.form.get('detalles_metodo', '')
            comentarios = request.form.get('comentarios_pago', '')
            id_usuario = session.get('user_id', 1)
            
            with get_db_cursor() as cursor:
                # Obtener información completa de la cuenta
                cursor.execute("""
                    SELECT 
                        cpp.Saldo_Pendiente,
                        cpp.ID_Proveedor,
                        p.Nombre as Proveedor,
                        cpp.Num_Documento,
                        cpp.Monto_Movimiento,
                        cpp.Estado,  -- NUEVO: Incluir el campo Estado
                        cpp.ID_Movimiento  -- Para referencia
                    FROM cuentas_por_pagar cpp
                    LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                    WHERE cpp.ID_Cuenta = %s
                """, (id_cuenta,))
                
                cuenta = cursor.fetchone()
                
                if not cuenta:
                    flash('Cuenta no encontrada', 'error')
                    return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                # NUEVO: Validar que la cuenta esté pendiente
                if cuenta['Estado'] != 'Pendiente':
                    flash(f'Esta cuenta ya está {cuenta["Estado"].lower()}. No se pueden registrar más pagos.', 'error')
                    return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
                saldo_actual = float(cuenta['Saldo_Pendiente'])
                proveedor = cuenta['Proveedor']
                num_documento = cuenta['Num_Documento']
                monto_total = float(cuenta['Monto_Movimiento'])
                
                # Validaciones
                if monto_pago <= 0:
                    flash('El monto a pagar debe ser mayor a cero', 'error')
                    return redirect(url_for('admin.registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                if monto_pago > saldo_actual:
                    flash(f'El monto a pagar (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})', 'error')
                    return redirect(url_for('admin.registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                # Calcular nuevo saldo
                nuevo_saldo = saldo_actual - monto_pago
                
                # Determinar el nuevo estado
                nuevo_estado = 'Pagada' if nuevo_saldo == 0 else 'Pendiente'
                
                # Registrar el pago en la tabla pagos_cuentaspagar
                cursor.execute("""
                    INSERT INTO pagos_cuentaspagar 
                    (ID_Cuenta, Fecha, Monto, ID_MetodoPago, Detalles_Metodo, Comentarios, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_cuenta, f"{fecha_pago} 00:00:00", monto_pago, id_metodo_pago, 
                      detalles_metodo, comentarios, id_usuario))
                
                # Actualizar saldo pendiente y estado en la cuenta
                cursor.execute("""
                    UPDATE cuentas_por_pagar 
                    SET Saldo_Pendiente = %s,
                        Estado = %s  -- NUEVO: Actualizar el estado
                    WHERE ID_Cuenta = %s
                """, (nuevo_saldo, nuevo_estado, id_cuenta))
                
                # Mensaje de éxito
                if nuevo_saldo == 0:
                    mensaje = f'¡Cuenta completamente pagada! Se registró pago de ${monto_pago:,.2f} para {proveedor}.'
                else:
                    mensaje = f'Pago de ${monto_pago:,.2f} registrado correctamente para {proveedor}. Saldo restante: ${nuevo_saldo:,.2f}'
                
                flash(mensaje, 'success')
                return redirect(url_for('admin.admin_cuentas_por_pagar'))
                
    except Exception as e:
        print(f"Error al registrar pago: {str(e)}")
        flash(f'Error al registrar pago: {str(e)}', 'error')
        return redirect(url_for('admin.admin_cuentas_por_pagar'))

# Ruta para ver historial de pagos de una cuenta
@admin_bp.route('/admin/compras/cuentas-por-pagar/<int:id_cuenta>/pagos', methods=['GET'])
@admin_required
def historial_pagos_cuenta(id_cuenta):
    """Muestra el historial de pagos de una cuenta específica"""
    try:
        with get_db_cursor(True) as cursor:
            # 1. Obtener información básica de la cuenta
            cursor.execute("""
                SELECT 
                    cpp.ID_Cuenta,
                    DATE(cpp.Fecha) as Fecha,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    DATE(cpp.Fecha_Vencimiento) as Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    cpp.Estado
                FROM cuentas_por_pagar cpp
                LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                WHERE cpp.ID_Cuenta = %s
            """, (id_cuenta,))
            
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash('Cuenta no encontrada', 'error')
                return redirect(url_for('admin.admin_cuentas_por_pagar'))
            
            # 2. Obtener historial de pagos (ajustado a tu estructura)
            cursor.execute("""
                SELECT 
                    pcp.ID_Pago,
                    DATE(pcp.Fecha) as Fecha_Pago,
                    TIME(pcp.Fecha) as Hora_Pago,
                    pcp.Monto,
                    mp.Nombre as Metodo_Pago,
                    pcp.Detalles_Metodo,
                    pcp.Comentarios,
                    u.NombreUsuario as Usuario_Registro
                FROM pagos_cuentaspagar pcp
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE pcp.ID_Cuenta = %s
                ORDER BY pcp.Fecha DESC
            """, (id_cuenta,))
            
            pagos = cursor.fetchall()
            
            # 3. Calcular total pagado
            total_pagado = 0.0
            for pago in pagos:
                if pago['Monto']:
                    total_pagado += float(pago['Monto'])
            
            # 4. Renderizar template
            return render_template('admin/compras/cxpagar/historial_pagos.html', 
                                cuenta=cuenta,
                                pagos=pagos,
                                total_pagado=total_pagado,
                                total_cuenta=float(cuenta['Monto_Movimiento']) if cuenta['Monto_Movimiento'] else 0.0)
            
    except Exception as e:
        print(f"Error al cargar historial de pagos (ID: {id_cuenta}): {str(e)}")
        flash(f'Error al cargar historial de pagos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_cuentas_por_pagar'))

##GASTOS
@admin_bp.route('/admin/gastos-operativos', methods=['GET'])
@admin_required
@bitacora_decorator("GASTOS")
def admin_gastos_operativos():
    try:
        # ========== PARÁMETROS DE FILTRO ==========
        filtro_periodo = request.args.get('filtro_periodo', 'dia')
        fecha_especifica = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        semana_num = request.args.get('semana', str(datetime.now().isocalendar()[1]))
        anio_semana = request.args.get('anio_semana', datetime.now().strftime('%Y'))
        mes_filtro = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        anio_filtro = request.args.get('anio', datetime.now().strftime('%Y'))
        
        # Filtros adicionales
        tipo_gasto_id = request.args.get('tipo_gasto', '')
        origen = request.args.get('origen', '')
        proveedor_id = request.args.get('proveedor', '')
        
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            
            # ========== 1. VERIFICAR QUÉ CAMPOS EXISTEN EN LA VISTA ==========
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'vista_gastos_unificados'
            """)
            columnas_existentes = [row['COLUMN_NAME'] for row in cursor.fetchall()]
            
            # Construir SELECT dinámicamente
            select_fields = ['origen', 'tipo_gasto', 'subcategoria', 'fecha', 'monto', 'factura', 'proveedor', 'vehiculo', 'id_gasto']
            
            if 'id_proveedor' in columnas_existentes:
                select_fields.append('id_proveedor')
            else:
                select_fields.append('NULL as id_proveedor')
            
            if 'id_categoria_inv' in columnas_existentes:
                select_fields.append('id_categoria_inv')
            
            query_base = f"""
            SELECT {', '.join(select_fields)}
            FROM vista_gastos_unificados
            WHERE ID_Empresa = %s
            """
            
            params = [id_empresa]
            fecha_inicio_semana = None
            fecha_fin_semana = None
            
            # Filtro de período
            if filtro_periodo == 'dia':
                query_base += " AND fecha = %s"
                params.append(fecha_especifica)
                titulo_periodo = f"Gastos del día {datetime.strptime(fecha_especifica, '%Y-%m-%d').strftime('%d/%m/%Y')}"
                
            elif filtro_periodo == 'semana':
                año = int(anio_semana)
                semana = int(semana_num)
                fecha_inicio_semana = datetime.strptime(f'{año}-W{semana}-1', '%Y-W%W-%w').date()
                fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
                query_base += " AND fecha BETWEEN %s AND %s"
                params.extend([fecha_inicio_semana, fecha_fin_semana])
                titulo_periodo = f"Gastos de la semana {semana_num} ({fecha_inicio_semana.strftime('%d/%m')} - {fecha_fin_semana.strftime('%d/%m/%Y')})"
                
            elif filtro_periodo == 'mes':
                año, mes = mes_filtro.split('-')
                query_base += " AND YEAR(fecha) = %s AND MONTH(fecha) = %s"
                params.extend([año, mes])
                nombre_mes = datetime(int(año), int(mes), 1).strftime('%B %Y')
                titulo_periodo = f"Gastos de {nombre_mes}"
                
            elif filtro_periodo == 'acumulado':
                query_base += " AND YEAR(fecha) = %s AND fecha <= CURDATE()"
                params.append(anio_filtro)
                titulo_periodo = f"Gastos Acumulados {anio_filtro} (Enero - {datetime.now().strftime('%B')})"
                
            elif filtro_periodo == 'anual':
                query_base += " AND YEAR(fecha) = %s"
                params.append(anio_filtro)
                titulo_periodo = f"Gastos del año {anio_filtro}"
                
            elif filtro_periodo == 'todo':
                query_base += " AND fecha >= '2020-01-01'"
                titulo_periodo = "TODOS LOS GASTOS (Histórico completo)"
            
            # Filtros adicionales
            if tipo_gasto_id and tipo_gasto_id.isdigit():
                query_base += " AND id_tipo = %s"
                params.append(int(tipo_gasto_id))
            
            if origen:
                query_base += " AND origen = %s"
                params.append(origen)
            
            if proveedor_id and proveedor_id.isdigit() and 'id_proveedor' in columnas_existentes:
                query_base += " AND id_proveedor = %s"
                params.append(int(proveedor_id))
            
            # Orden
            query_base += " ORDER BY fecha DESC, monto DESC"
            
            cursor.execute(query_base, params)
            resultados = cursor.fetchall()
            
            # Calcular total del período
            total_periodo = sum(float(r['monto'] or 0) for r in resultados)
            
            # ========== 2. TOTALES ACUMULADOS ==========
            query_totales = """
            SELECT 
                'total_compras' AS concepto,
                COALESCE(SUM(dmi.Cantidad * dmi.Costo_Unitario), 0) AS total
            FROM movimientos_inventario mi
            LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
            WHERE mi.Estado = 'Activa' AND mi.ID_TipoMovimiento = 1 AND mi.ID_Empresa = %s
            
            UNION ALL
            
            SELECT 
                'total_gastos' AS concepto,
                COALESCE(SUM(gg.Monto), 0) AS total
            FROM gastos_generales gg
            WHERE gg.Estado = 'Activo' AND gg.ID_Empresa = %s
            """
            cursor.execute(query_totales, [id_empresa, id_empresa])
            totales_acumulados = {row['concepto']: float(row['total'] or 0) for row in cursor.fetchall()}
            
            # ========== 3. LISTAS PARA FILTROS ==========
            
            # Tipos de gasto disponibles
            cursor.execute("""
                SELECT DISTINCT id_tipo, tipo_gasto 
                FROM vista_gastos_unificados 
                WHERE ID_Empresa = %s AND tipo_gasto IS NOT NULL
                ORDER BY tipo_gasto
            """, [id_empresa])
            tipos_gasto_disponibles = cursor.fetchall()
            
            # Proveedores disponibles
            if 'id_proveedor' in columnas_existentes:
                cursor.execute("""
                    SELECT DISTINCT id_proveedor, proveedor 
                    FROM vista_gastos_unificados 
                    WHERE ID_Empresa = %s AND proveedor IS NOT NULL
                    ORDER BY proveedor
                """, [id_empresa])
                proveedores_lista = cursor.fetchall()
            else:
                proveedores_lista = []
            
            años_disponibles = range(2020, datetime.now().year + 2)
            semanas_disponibles = range(1, 54)
            
            return render_template(
                'admin/gastos/gastos_operativos.html',
                # Filtros actuales
                filtro_periodo=filtro_periodo,
                fecha_especifica=fecha_especifica,
                semana_num=semana_num,
                anio_semana=anio_semana,
                mes_filtro=mes_filtro,
                anio_filtro=anio_filtro,
                tipo_gasto_id=tipo_gasto_id,
                origen=origen,
                proveedor_id=proveedor_id,
                # Datos principales
                resultados=resultados,
                total_periodo=total_periodo,
                titulo_periodo=titulo_periodo,
                totales_acumulados=totales_acumulados,
                # Listas para filtros
                tipos_gasto_disponibles=tipos_gasto_disponibles,
                proveedores_lista=proveedores_lista,
                años_disponibles=años_disponibles,
                semanas_disponibles=semanas_disponibles,
                titulo="Control de Gastos - Compras + Gastos Generales"
            )
            
    except Exception as e:
        logger.error(f"Error en gastos operativos: {str(e)}")
        flash(f'Error al cargar los gastos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/gastos/registrar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("REGISTRO_GASTO")
def registrar_gasto():
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Obtener listas para selects
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE Estado = 'Activo' AND ID_Empresa = %s
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Proveedor, Nombre 
                FROM proveedores 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            proveedores = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Vehiculo, Placa, Marca, Modelo 
                FROM vehiculos 
                WHERE ID_Empresa = %s AND Estado != 'Inactivo'
                ORDER BY Placa
            """, [id_empresa])
            vehiculos = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                id_subcategoria = request.form.get('id_subcategoria') or None
                fecha = request.form.get('fecha')
                monto = request.form.get('monto')
                descripcion = request.form.get('descripcion')
                n_factura = request.form.get('n_factura') or None
                id_proveedor = request.form.get('id_proveedor') or None
                id_vehiculo = request.form.get('id_vehiculo') or None
                metodo_pago = request.form.get('metodo_pago')
                # observaciones = request.form.get('observaciones') or None  # ELIMINADO
                
                # Validaciones
                if not id_tipo_gasto:
                    flash('Debe seleccionar un tipo de gasto', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                if not fecha:
                    flash('Debe ingresar una fecha', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                if not monto or float(monto) <= 0:
                    flash('Debe ingresar un monto válido', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                # Insertar gasto (SIN Observaciones)
                cursor.execute("""
                    INSERT INTO gastos_generales (
                        ID_Tipo_Gasto, ID_Subcategoria, Fecha, Monto, Descripcion,
                        N_Factura, ID_Proveedor, ID_Vehiculo, Metodo_Pago, 
                        ID_Empresa, ID_Usuario_Registro
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_gasto, id_subcategoria, fecha, monto, descripcion,
                    n_factura, id_proveedor, id_vehiculo, metodo_pago,
                    id_empresa, id_usuario
                ))
                
                id_gasto = cursor.lastrowid
                
                # Si es gasto de vehículo, registrar detalle adicional
                if id_vehiculo:
                    kilometraje = request.form.get('kilometraje') or None
                    tipo_mantenimiento = request.form.get('tipo_mantenimiento') or None
                    taller = request.form.get('taller') or None
                    
                    cursor.execute("""
                        INSERT INTO gastos_vehiculo_detalle (
                            ID_Gasto, ID_Vehiculo, Kilometraje, Tipo_Mantenimiento, Taller
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (id_gasto, id_vehiculo, kilometraje, tipo_mantenimiento, taller))
                
                flash(f'Gasto registrado exitosamente. Total: C${float(monto):,.2f}', 'success')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            return render_template(
                'admin/gastos/registrar_gastos.html',
                tipos_gasto=tipos_gasto,
                proveedores=proveedores,
                vehiculos=vehiculos,
                hoy=datetime.now().strftime('%Y-%m-%d'),
                titulo="Registrar Nuevo Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al registrar gasto: {str(e)}")
        flash(f'Error al registrar gasto: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

@admin_bp.route('/admin/gastos/get_subcategorias', methods=['GET'])
@admin_required
def get_subcategorias():
    try:
        id_tipo_gasto = request.args.get('id_tipo_gasto')
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Subcategoria, Nombre 
                FROM subcategorias_gasto 
                WHERE ID_Tipo_Gasto = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_tipo_gasto])
            subcategorias = cursor.fetchall()
            
        return jsonify({'success': True, 'subcategorias': subcategorias})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/admin/gastos/ver/<int:id_gasto>', methods=['GET'])
@admin_required
def ver_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    gg.*,
                    tg.Nombre AS tipo_gasto_nombre,
                    sg.Nombre AS subcategoria_nombre,
                    pr.Nombre AS proveedor_nombre,
                    v.Placa AS vehiculo_placa,
                    u.NombreUsuario AS usuario_registro_nombre
                FROM gastos_generales gg
                LEFT JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                LEFT JOIN subcategorias_gasto sg ON gg.ID_Subcategoria = sg.ID_Subcategoria
                LEFT JOIN proveedores pr ON gg.ID_Proveedor = pr.ID_Proveedor
                LEFT JOIN vehiculos v ON gg.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios u ON gg.ID_Usuario_Registro = u.ID_Usuario
                WHERE gg.ID_Gasto = %s AND gg.ID_Empresa = %s
            """, [id_gasto, id_empresa])
            gasto = cursor.fetchone()
            
            if not gasto:
                flash('Gasto no encontrado', 'error')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            # Obtener detalle de vehículo si aplica
            detalle_vehiculo = None
            if gasto['ID_Vehiculo']:
                cursor.execute("""
                    SELECT * FROM gastos_vehiculo_detalle WHERE ID_Gasto = %s
                """, [id_gasto])
                detalle_vehiculo = cursor.fetchone()
            
            return render_template(
                'admin/gastos/ver_gasto.html',
                gasto=gasto,
                detalle_vehiculo=detalle_vehiculo,
                titulo="Detalle del Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al ver gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

@admin_bp.route('/admin/gastos/anular/<int:id_gasto>', methods=['POST'])
@admin_required
@bitacora_decorator("ANULAR_GASTO")
def anular_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                UPDATE gastos_generales 
                SET Estado = 'Anulado', 
                    ID_Usuario_Registro = %s,
                    Observaciones = CONCAT(IFNULL(Observaciones, ''), ' [ANULADO por usuario ', %s, ']')
                WHERE ID_Gasto = %s AND ID_Empresa = %s
            """, [id_usuario, id_usuario, id_gasto, id_empresa])
            
            if cursor.rowcount == 0:
                flash('No se pudo anular el gasto', 'error')
            else:
                flash('Gasto anulado correctamente', 'success')
                
    except Exception as e:
        logger.error(f"Error al anular gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_gastos_operativos'))

## MODULOS DEL ADMINISTRADOR ##
# CATALOGOS ROLES
@admin_bp.route('/admin/roles')
@admin_required
@bitacora_decorator("ROLES")
def admin_roles():
    """Listar todos los roles"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM roles ORDER BY Estado DESC, ID_Rol")
            roles = cursor.fetchall()
            return render_template('admin/catalog/rol/roles.html', roles=roles)
    except Exception as e:
        flash(f"Error al cargar roles: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    
@admin_bp.route('/admin/roles/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_ROL")
def crear_rol():
    """Crear un nuevo rol (formulario tradicional)"""
    try:
        nombre_rol = request.form.get('nombre_rol')
        
        if not nombre_rol or nombre_rol.strip() == '':
            flash("El nombre del rol es requerido", "danger")
            return redirect(url_for('admin.admin_roles'))
        
        # Validar si el rol ya existe
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ID_Rol FROM roles WHERE Nombre_Rol = %s", (nombre_rol.strip(),))
            if cursor.fetchone():
                flash("Ya existe un rol con ese nombre", "warning")
                return redirect(url_for('admin.admin_roles'))
        
        # Crear el nuevo rol
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO roles (Nombre_Rol, Estado) VALUES (%s, 'Activo')",
                (nombre_rol.strip(),)
            )
        
        flash("Rol creado exitosamente", "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al crear rol: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))

@admin_bp.route('/admin/roles/editar/<int:id_rol>', methods=['POST'])
@admin_required
@bitacora_decorator("EDITAR_ROL")
def editar_rol(id_rol):
    """Editar un rol existente (formulario tradicional)"""
    try:
        nombre_rol = request.form.get('nombre_rol')
        estado = request.form.get('estado')
        
        if not nombre_rol or nombre_rol.strip() == '':
            flash("El nombre del rol es requerido", "danger")
            return redirect(url_for('admin.admin_roles'))
        
        # Validar si el rol existe
        with get_db_cursor() as cursor:
            cursor.execute("SELECT Nombre_Rol FROM roles WHERE ID_Rol = %s", (id_rol,))
            rol_existente = cursor.fetchone()
            
            if not rol_existente:
                flash("Rol no encontrado", "danger")
                return redirect(url_for('admin.admin_roles'))
            
            # Validar si el nuevo nombre ya existe en otro rol
            cursor.execute(
                "SELECT ID_Rol FROM roles WHERE Nombre_Rol = %s AND ID_Rol != %s", 
                (nombre_rol.strip(), id_rol)
            )
            if cursor.fetchone():
                flash("Ya existe otro rol con ese nombre", "warning")
                return redirect(url_for('admin.admin_roles'))
        
        # Actualizar el rol
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE roles SET Nombre_Rol = %s, Estado = %s WHERE ID_Rol = %s",
                (nombre_rol.strip(), estado, id_rol)
            )
        
        flash("Rol actualizado exitosamente", "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al actualizar rol: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))

@admin_bp.route('/admin/roles/cambiar_estado/<int:id_rol>', methods=['POST'])
@admin_required
@bitacora_decorator("CAMBIAR_ESTADO_ROL")
def cambiar_estado_rol(id_rol):
    """Cambiar estado de Activo a Inactivo o viceversa (formulario tradicional)"""
    try:
        with get_db_cursor() as cursor:
            # Primero obtenemos el estado actual
            cursor.execute("SELECT Estado, Nombre_Rol FROM roles WHERE ID_Rol = %s", (id_rol,))
            rol = cursor.fetchone()
            
            if not rol:
                flash("Rol no encontrado", "danger")
                return redirect(url_for('admin.admin_roles'))
            
            # Cambiamos el estado
            nuevo_estado = 'Inactivo' if rol['Estado'] == 'Activo' else 'Activo'
            nombre_rol = rol['Nombre_Rol']
            
            cursor.execute(
                "UPDATE roles SET Estado = %s WHERE ID_Rol = %s",
                (nuevo_estado, id_rol)
            )
        
        mensaje = f"Rol '{nombre_rol}' {nuevo_estado.lower()} correctamente"
        flash(mensaje, "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al cambiar estado: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))

@admin_bp.route('/admin/roles/eliminar/<int:id_rol>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR_ROL")
def eliminar_rol(id_rol):
    """Eliminar un rol (formulario tradicional)"""
    try:
        with get_db_cursor() as cursor:
            # Verificar si el rol existe
            cursor.execute("SELECT Estado, Nombre_Rol FROM roles WHERE ID_Rol = %s", (id_rol,))
            rol = cursor.fetchone()
            
            if not rol:
                flash("Rol no encontrado", "danger")
                return redirect(url_for('admin.admin_roles'))
            
            # Verificar si el rol está activo
            if rol['Estado'] == 'Activo':
                flash("No se puede eliminar un rol activo. Primero debe inactivarlo.", "warning")
                return redirect(url_for('admin.admin_roles'))
            
            # Verificar si hay usuarios asociados al rol
            cursor.execute("SELECT COUNT(*) as count FROM usuarios WHERE ID_Rol = %s", (id_rol,))
            usuarios_asociados = cursor.fetchone()['count']
            
            if usuarios_asociados > 0:
                flash(f"No se puede eliminar el rol porque tiene {usuarios_asociados} usuario(s) asociado(s).", "warning")
                return redirect(url_for('admin.admin_roles'))
        
        # Si pasa las validaciones, eliminar
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM roles WHERE ID_Rol = %s", (id_rol,))
        
        flash(f"Rol '{rol['Nombre_Rol']}' eliminado exitosamente", "success")
        return redirect(url_for('admin.admin_roles'))
        
    except Exception as e:
        flash(f"Error al eliminar rol: {str(e)}", "danger")
        return redirect(url_for('admin.admin_roles'))
    
# CATALOGOS USUARIOS
@admin_bp.route('/admin/usuarios')
@admin_required
@bitacora_decorator("USUARIOS")
def admin_usuarios():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa FROM usuarios u
                JOIN roles r ON u.ID_Rol = r.ID_Rol
                JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
            """)
            usuarios = cursor.fetchall()
            
            cursor.execute("SELECT * FROM roles")
            roles = cursor.fetchall()
            
            cursor.execute("SELECT * FROM empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/usuarios.html', usuarios=usuarios, roles=roles, empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar usuarios: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/catalog/crear-usuario', methods=['POST'])
@admin_required
@bitacora_decorator("USUARIOS")
def crear_usuario():
    username = request.form.get('username')
    password = request.form.get('password')
    rol_id = request.form.get('rol_id')
    empresa_id = request.form.get('empresa_id')

    if not all([username, password, rol_id, empresa_id]):
        flash("Todos los campos son requeridos", "danger")
        return redirect(url_for('admin.admin_usuarios'))

    hashed_password = generate_password_hash(password)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuarios (NombreUsuario, Contraseña, ID_Rol, ID_Empresa, Estado)
                VALUES (%s, %s, %s, %s, 'Activo')
            """, (username, hashed_password, rol_id, empresa_id))
            registrar_bitacora(modulo="USUARIOS", accion=f"CREAR_USUARUI: {username}")
            flash("Usuario creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear usuario: {e}", "danger")
    
    return redirect(url_for('admin.admin_usuarios'))

@admin_bp.route('/admin/catalog/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(user_id):
    try:
        with get_db_cursor() as cursor:
            if request.method == 'GET':
                # Obtener datos del usuario a editar
                cursor.execute("""
                    SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa 
                    FROM usuarios u
                    JOIN roles r ON u.ID_Rol = r.ID_Rol
                    JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
                    WHERE u.ID_Usuario = %s
                """, (user_id,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    flash("Usuario no encontrado", "danger")
                    return redirect(url_for('admin.admin_usuarios'))
                
                # Obtener roles y empresas para el formulario
                cursor.execute("SELECT * FROM roles")
                roles = cursor.fetchall()
                
                cursor.execute("SELECT * FROM empresa")
                empresas = cursor.fetchall()
                
                return render_template('admin/catalog/editar_usuario.html', 
                                     usuario=usuario, 
                                     roles=roles, 
                                     empresas=empresas)
            
            elif request.method == 'POST':
                # Procesar el formulario de edición
                username = request.form.get('username')
                rol_id = request.form.get('rol_id')
                empresa_id = request.form.get('empresa_id')
                estado = request.form.get('estado')
                password = request.form.get('password')
                
                if not all([username, rol_id, empresa_id, estado]):
                    flash("Todos los campos son requeridos", "danger")
                    return redirect(url_for('admin.editar_usuario', user_id=user_id))
                
                # Construir la consulta dinámicamente
                update_fields = []
                update_values = []
                
                update_fields.append("NombreUsuario = %s")
                update_values.append(username)
                
                update_fields.append("ID_Rol = %s")
                update_values.append(rol_id)
                
                update_fields.append("ID_Empresa = %s")
                update_values.append(empresa_id)
                
                update_fields.append("Estado = %s")
                update_values.append(estado)
                
                # Si se proporcionó una nueva contraseña, actualizarla
                if password:
                    hashed_password = generate_password_hash(password)
                    update_fields.append("Contraseña = %s")
                    update_values.append(hashed_password)
                
                # Agregar el ID al final de los valores
                update_values.append(user_id)
                
                # Ejecutar la actualización
                query = f"UPDATE usuarios SET {', '.join(update_fields)} WHERE ID_Usuario = %s"
                cursor.execute(query, update_values)
                
                flash("Usuario actualizado exitosamente", "success")
                return redirect(url_for('admin.admin_usuarios'))
                
    except Exception as e:
        flash(f"Error al editar usuario: {e}", "danger")
        return redirect(url_for('admin.admin_usuarios'))

# CATALOGO BITACORA
@admin_bp.route('/admin/bitacora')
@admin_required
def admin_bitacora():
    """Vista principal de la bitácora del sistema"""
    try:
        modulo = request.args.get('modulo')
        fecha_desde = request.args.get('fecha_desde')
        fecha_hasta = request.args.get('fecha_hasta')
        
        with get_db_cursor() as cursor:
            # Construir query con filtros
            query = """
                SELECT b.*, u.NombreUsuario 
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                WHERE 1=1
            """
            params = []
            
            if modulo:
                query += " AND b.Modulo = %s"
                params.append(modulo)
                
            if fecha_desde:
                query += " AND DATE(b.Fecha) >= %s"
                params.append(fecha_desde)
                
            if fecha_hasta:
                query += " AND DATE(b.Fecha) <= %s"
                params.append(fecha_hasta)
            
            query += " ORDER BY b.Fecha DESC LIMIT 200"
            
            cursor.execute(query, params)
            registros = cursor.fetchall()
            
            # Obtener módulos únicos para el dropdown
            cursor.execute("SELECT DISTINCT Modulo FROM bitacora WHERE Modulo IS NOT NULL ORDER BY Modulo")
            modulos = cursor.fetchall()
            
            return render_template('admin/bitacora.html', 
                                 registros=registros, 
                                 modulos=modulos)
            
    except Exception as e:
        flash(f"Error al cargar bitácora: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/bitacora/limpiar', methods=['POST'])
@admin_required
def limpiar_bitacora():
    """Limpiar registros antiguos de la bitácora"""
    try:
        with get_db_cursor(commit=True) as cursor:
            # Mantener solo los últimos 1000 registros
            cursor.execute("""
                DELETE FROM bitacora 
                WHERE ID_Bitacora NOT IN (
                    SELECT ID_Bitacora FROM (
                        SELECT ID_Bitacora FROM bitacora 
                        ORDER BY Fecha DESC 
                        LIMIT 1000
                    ) AS temp
                )
            """)
            
            registros_eliminados = cursor.rowcount
            registrar_bitacora(modulo="BITACORA", accion=f"LIMPIAR_BITACORA: {registros_eliminados} registros eliminados")
            
            flash(f"Bitácora limpiada exitosamente. Se eliminaron {registros_eliminados} registros antiguos.", "success")
            
    except Exception as e:
        flash(f"Error al limpiar bitácora: {e}", "danger")
    
    return redirect(url_for('admin.admin_bitacora'))

@admin_bp.route('/admin/bitacora/exportar')
@admin_required
def exportar_bitacora():
    """Exportar bitácora a CSV"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT b.Fecha, u.NombreUsuario, b.Modulo, b.Accion, b.IP_Acceso
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                ORDER BY b.Fecha DESC
            """)
            registros = cursor.fetchall()
            
            # Crear respuesta CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Fecha', 'Usuario', 'Módulo', 'Acción', 'IP'])
            
            for registro in registros:
                writer.writerow([
                    registro['Fecha'].strftime('%Y-%m-%d %H:%M:%S'),
                    registro['NombreUsuario'] or 'Sistema',
                    registro['Modulo'] or 'N/A',
                    registro['Accion'] or 'N/A',
                    registro['IP_Acceso'] or 'N/A'
                ])
            
            # Registrar exportación
            registrar_bitacora(modulo="BITACORA", accion="EXPORTAR_BITACORA_CSV")
            
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=bitacora_sistema.csv"
            response.headers["Content-type"] = "text/csv"
            return response
            
    except Exception as e:
        flash(f"Error al exportar bitácora: {e}", "danger")
        return redirect(url_for('admin.admin_bitacora'))

#CONFIGURACION EMPRESA
@admin_bp.route('/admin/config/visibilidad', methods=['GET', 'POST'])
@admin_required
def config_visibilidad():
    """Configurar visibilidad de categorías"""
    
    if request.method == 'POST':
        try:
            with get_db_cursor(commit=True) as cursor:
                # Procesar TODAS las categorías
                cursor.execute("SELECT ID_Categoria FROM categorias_producto")
                todas_categorias = cursor.fetchall()
                
                for cat in todas_categorias:
                    categoria_id = cat['ID_Categoria']
                    
                    # Para clientes Comunes
                    key_comun = f"cat_{categoria_id}_Comun"
                    visible_comun = 1 if key_comun in request.form else 0
                    
                    cursor.execute("""
                        INSERT INTO config_visibilidad_categorias 
                        (tipo_cliente, ID_Categoria, visible) 
                        VALUES ('Comun', %s, %s)
                        ON DUPLICATE KEY UPDATE visible = %s
                    """, (categoria_id, visible_comun, visible_comun))
                    
                    # Para clientes Especiales
                    key_especial = f"cat_{categoria_id}_Especial"
                    visible_especial = 1 if key_especial in request.form else 0
                    
                    cursor.execute("""
                        INSERT INTO config_visibilidad_categorias 
                        (tipo_cliente, ID_Categoria, visible) 
                        VALUES ('Especial', %s, %s)
                        ON DUPLICATE KEY UPDATE visible = %s
                    """, (categoria_id, visible_especial, visible_especial))
                
                flash('✅ Configuración guardada exitosamente', 'success')
                return redirect(url_for('admin.config_visibilidad'))
                
        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'danger')
    
    # GET: Mostrar formulario
    with get_db_cursor() as cursor:
        # Consulta CORREGIDA - sin productos_activos
        cursor.execute("""
            SELECT 
                c.ID_Categoria,
                c.Descripcion as nombre,
                COALESCE(cfg_comun.visible, 0) as comun_visible,
                COALESCE(cfg_especial.visible, 0) as especial_visible
            FROM categorias_producto c
            LEFT JOIN config_visibilidad_categorias cfg_comun 
                ON c.ID_Categoria = cfg_comun.ID_Categoria 
                AND cfg_comun.tipo_cliente = 'Comun'
            LEFT JOIN config_visibilidad_categorias cfg_especial 
                ON c.ID_Categoria = cfg_especial.ID_Categoria 
                AND cfg_especial.tipo_cliente = 'Especial'
            ORDER BY c.Descripcion
        """)
        categorias = cursor.fetchall()
    
    return render_template('admin/config/visibilidad.html', categorias=categorias)

# RUTA PARA VENTAS - Obtener productos según cliente
@admin_bp.route('/api/productos-por-cliente/<int:cliente_id>')
@login_required
def productos_por_cliente(cliente_id):
    """Obtener productos visibles para un cliente específico"""
    
    empresa_id = session.get('empresa_id')
    
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

#CATALOGO EMPRESA
@admin_bp.route('/admin/catalog/empresa/empresas', methods=['GET'])
@admin_required
@bitacora_decorator("EMPRESA")
def admin_empresas():
    """Listar todas las empresas"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, Direccion, Telefono, Estado, RUC 
                FROM empresa 
                ORDER BY Nombre_Empresa
            """)
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/empresa/empresas.html', empresas=empresas)
    except Exception as e:
        flash(f'Error al cargar empresas: {str(e)}', 'error')
        return render_template('admin/catalog/empresa/empresas.html', empresas=[])

@admin_bp.route('/admin/catalog/empresa/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EMPRESA_CREAR")
def crear_empresa():
    """Crear nueva empresa (GET: mostrar modal, POST: procesar formulario)"""
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre_empresa')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ruc = request.form.get('ruc')
            estado = request.form.get('estado', 'Activo')
            
            # Validaciones básicas
            if not nombre:
                flash('El nombre de la empresa es obligatorio', 'error')
                return redirect(url_for('admin.admin_empresas'))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO empresa (Nombre_Empresa, Direccion, Telefono, RUC, Estado)
                    VALUES (%s, %s, %s, %s, %s)
                """, (nombre, direccion, telefono, ruc, estado))
                
            flash('Empresa creada exitosamente', 'success')
            return redirect(url_for('admin.admin_empresas'))
            
        except Exception as e:
            flash(f'Error al crear empresa: {str(e)}', 'error')
            return redirect(url_for('admin.admin_empresas'))
    
    # GET: Redirigir a la página principal (el modal está en empresas.html)
    return redirect(url_for('admin.admin_empresas'))

@admin_bp.route('/admin/catalog/empresa/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EMPRESA_EDITAR")
def editar_empresa(id):
    """Editar empresa (GET: mostrar formulario, POST: procesar edición)"""
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre_empresa')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ruc = request.form.get('ruc')
            estado = request.form.get('estado')
            
            if not nombre:
                flash('El nombre de la empresa es obligatorio', 'error')
                return redirect(url_for('admin.editar_empresa', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE empresa 
                    SET Nombre_Empresa = %s, Direccion = %s, Telefono = %s, 
                        RUC = %s, Estado = %s
                    WHERE ID_Empresa = %s
                """, (nombre, direccion, telefono, ruc, estado, id))
                
            flash('Empresa actualizada exitosamente', 'success')
            return redirect(url_for('admin.admin_empresas'))
            
        except Exception as e:
            flash(f'Error al actualizar empresa: {str(e)}', 'error')
            return redirect(url_for('admin.editar_empresa', id=id))
    
    # GET: Mostrar formulario de edición
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, Direccion, Telefono, Estado, RUC 
                FROM empresa 
                WHERE ID_Empresa = %s
            """, (id,))
            empresa = cursor.fetchone()
            
            if not empresa:
                flash('Empresa no encontrada', 'error')
                return redirect(url_for('admin.admin_empresas'))
                
            return render_template('admin/catalog/empresa/editar_empresa.html', empresa=empresa)
            
    except Exception as e:
        flash(f'Error al cargar empresa: {str(e)}', 'error')
        return redirect(url_for('admin.admin_empresas'))

# CATALOGO CLIENTES
@admin_bp.route('/admin/catalog/client/clientes', methods=['GET'])
@admin_required
@bitacora_decorator("CLIENTES")
def admin_clientes():
    # Valores por defecto
    clientes = []
    rutas = []
    productos = []
    page = 1
    per_page = 20
    total = 0
    total_pages = 1
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Obtener rutas activas para el formulario
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (id_empresa,))
            rutas = cursor.fetchall()
            
            # Obtener productos activos para el selector de producto anticipado
            cursor.execute("""
                SELECT ID_Producto, Descripcion as Nombre
                FROM productos 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activo'
                ORDER BY Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            # Validar página
            if page < 1:
                page = 1
            
            offset = (page - 1) * per_page
            
            # Consulta base ACTUALIZADA con todas las nuevas columnas de anticipos
            base_query = """
                SELECT c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                       c.ID_Empresa, c.ID_Ruta, c.Saldo_Pendiente_Total,
                       c.Fecha_Ultimo_Movimiento, c.ID_Ultima_Factura, c.Fecha_Ultimo_Pago,
                       c.Estado, c.Fecha_Creacion, c.ID_Usuario_Creacion,
                       c.tipo_cliente, c.perfil_cliente,
                       c.Anticipo_Activo, c.Limite_Anticipo_Cajas, 
                       c.Cajas_Consumidas_Anticipo, c.Saldo_Anticipos, c.Producto_Anticipado,
                       e.Nombre_Empresa, r.Nombre_Ruta,
                       p.Descripcion as Nombre_Producto_Anticipado, p.COD_Producto as Codigo_Producto_Anticipado
                FROM clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                LEFT JOIN productos p ON c.Producto_Anticipado = p.ID_Producto
                WHERE c.Estado = 'ACTIVO' 
                AND c.ID_Empresa = %s
                AND e.Estado = 'Activo'
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total ACTUALIZADO
            count_query = """
                SELECT COUNT(*) as total 
                FROM clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado = 'ACTIVO' 
                AND c.ID_Empresa = %s
                AND e.Estado = 'Activo'
            """
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Calcular total de páginas
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            
            # Validar que la página no exceda el total
            if page > total_pages and total_pages > 0:
                page = total_pages
                offset = (page - 1) * per_page
            
            # Obtener datos con paginación
            if total > 0:
                data_query = base_query + " ORDER BY c.Nombre LIMIT %s OFFSET %s"
                params.extend([per_page, offset])
                
                cursor.execute(data_query, params)
                clientes = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/client/clientes: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los clientes. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/client/clientes.html", 
                        clientes=clientes, 
                        rutas=rutas,
                        productos=productos,
                        page=page,
                        per_page=per_page,
                        total=total,
                        total_pages=total_pages,
                        search=search_query)

@admin_bp.route('/admin/catalog/client/crear-cliente', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-CREAR")
def admin_crear_cliente():
    try:
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        direccion = request.form.get("direccion", "").strip()
        ruc_cedula = request.form.get("ruc_cedula", "").strip()
        tipo_cliente = request.form.get("tipo_cliente", "Comun").strip()
        perfil_cliente = request.form.get("perfil_cliente", "Mercado").strip()
        id_ruta = request.form.get("id_ruta", "").strip()
        
        # NUEVOS CAMPOS DE ANTICIPO
        anticipo_activo = request.form.get("anticipo_activo", "0").strip()
        limite_anticipo_cajas = request.form.get("limite_anticipo_cajas", "0").strip()
        saldo_anticipos = request.form.get("saldo_anticipos", "0").strip()
        producto_anticipado = request.form.get("producto_anticipado", "").strip()
        
        id_usuario = current_user.id
        id_empresa = session.get('id_empresa', 1)

        # Validaciones básicas
        if not nombre:
            flash("El nombre del cliente es obligatorio.", "danger")
            return redirect(url_for("admin.admin_clientes"))
        
        if not telefono:
            flash("El teléfono del cliente es obligatorio.", "danger")
            return redirect(url_for("admin.admin_clientes"))
        
        if not id_usuario:
            flash("Error de autenticación. Por favor, inicie sesión nuevamente.", "danger")
            return redirect(url_for("admin.admin_clientes"))
        
        # NUEVAS VALIDACIONES DE ANTICIPO
        anticipo_activo = 1 if anticipo_activo == "1" else 0
        
        try:
            limite_anticipo_cajas = int(limite_anticipo_cajas) if limite_anticipo_cajas else 0
            if limite_anticipo_cajas < 0:
                limite_anticipo_cajas = 0
        except ValueError:
            limite_anticipo_cajas = 0
        
        try:
            saldo_anticipos = float(saldo_anticipos) if saldo_anticipos else 0
            if saldo_anticipos < 0:
                saldo_anticipos = 0
        except ValueError:
            saldo_anticipos = 0
        
        if producto_anticipado:
            try:
                producto_anticipado = int(producto_anticipado)
                if producto_anticipado <= 0:
                    producto_anticipado = None
            except (ValueError, TypeError):
                producto_anticipado = None
        else:
            producto_anticipado = None
        
        # Validar tipo de cliente
        if tipo_cliente not in ['Comun', 'Especial']:
            tipo_cliente = 'Comun'
        
        # Validar perfil de cliente
        if perfil_cliente not in ['Ruta', 'Mayorista', 'Mercado', 'Especial']:
            perfil_cliente = 'Mercado'
        
        # Validar ID_Ruta (puede ser opcional)
        if id_ruta:
            try:
                id_ruta = int(id_ruta)
                if id_ruta <= 0:
                    id_ruta = None
            except (ValueError, TypeError):
                id_ruta = None
        else:
            id_ruta = None
        
        with get_db_cursor() as cursor:
            # Verificar que la empresa existe y está activa
            cursor.execute(
                "SELECT 1 FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", 
                (id_empresa,)
            )
            empresa_activa = cursor.fetchone()
            
            if not empresa_activa:
                flash("Empresa no válida o inactiva.", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # Si se proporcionó una ruta, verificar que existe y pertenece a la empresa
            if id_ruta:
                cursor.execute(
                    """SELECT 1 FROM rutas 
                    WHERE ID_Ruta = %s 
                    AND ID_Empresa = %s 
                    AND Estado = 'Activa'""",
                    (id_ruta, id_empresa)
                )
                ruta_valida = cursor.fetchone()
                if not ruta_valida:
                    flash("La ruta seleccionada no es válida o está inactiva.", "danger")
                    return redirect(url_for("admin.admin_clientes"))
            
            # Si se proporcionó un producto anticipado, verificar que existe
            if producto_anticipado:
                cursor.execute(
                    """SELECT 1 FROM productos 
                    WHERE ID_Producto = %s AND ID_Empresa = %s AND Estado = 'Activo'""",
                    (producto_anticipado, id_empresa)
                )
                producto_valido = cursor.fetchone()
                if not producto_valido:
                    flash("El producto anticipado seleccionado no es válido.", "danger")
                    return redirect(url_for("admin.admin_clientes"))
            
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    """SELECT 1 FROM clientes 
                    WHERE RUC_CEDULA = %s 
                    AND ID_Empresa = %s 
                    AND Estado = 'ACTIVO'""", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un cliente con este RUC/Cédula", "danger")
                    return redirect(url_for("admin.admin_clientes"))

            # Validación adicional para anticipos activos
            if anticipo_activo == 1:
                if limite_anticipo_cajas == 0 and saldo_anticipos == 0 and not producto_anticipado:
                    flash("Si activa anticipos, debe configurar al menos: límite de cajas, saldo o producto anticipado.", "danger")
                    return redirect(url_for("admin.admin_clientes"))

            # Insertar nuevo cliente con todos los campos incluyendo anticipos
            cursor.execute("""
                INSERT INTO clientes 
                (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, 
                 ID_Usuario_Creacion, tipo_cliente, perfil_cliente, ID_Ruta,
                 Saldo_Pendiente_Total, Estado,
                 Anticipo_Activo, Limite_Anticipo_Cajas, Saldo_Anticipos, 
                 Producto_Anticipado, Cajas_Consumidas_Anticipo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, 
                  id_usuario, tipo_cliente, perfil_cliente, id_ruta,
                  0.00, 'ACTIVO',
                  anticipo_activo, limite_anticipo_cajas, saldo_anticipos,
                  producto_anticipado, 0))
            
            flash("Cliente agregado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al crear cliente: {str(e)}", exc_info=True)
        flash("Error al guardar el cliente", "danger")
    
    return redirect(url_for("admin.admin_clientes"))

@admin_bp.route('/admin/catalog/client/editar-cliente/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-EDITAR")
def admin_editar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Obtener rutas activas para el formulario
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (id_empresa,))
            rutas = cursor.fetchall()
            
            # Obtener productos activos para el selector de producto anticipado
            cursor.execute("""
                SELECT ID_Producto, Descripcion, COD_Producto
                FROM productos 
                WHERE ID_Empresa = %s 
                AND Estado = 'Activo'
                ORDER BY Descripcion
            """, (id_empresa,))
            productos = cursor.fetchall()
            
            # Verificar que el cliente existe y obtener todos sus datos incluyendo anticipos
            cursor.execute(
                """SELECT c.ID_Cliente, c.Nombre, c.Telefono, c.Direccion, c.RUC_CEDULA,
                          c.ID_Empresa, c.ID_Ruta, c.Saldo_Pendiente_Total,
                          c.Fecha_Ultimo_Movimiento, c.ID_Ultima_Factura, c.Fecha_Ultimo_Pago,
                          c.Estado, c.Fecha_Creacion, c.ID_Usuario_Creacion,
                          c.tipo_cliente, c.perfil_cliente,
                          c.Anticipo_Activo, c.Limite_Anticipo_Cajas, 
                          c.Cajas_Consumidas_Anticipo, c.Saldo_Anticipos, c.Producto_Anticipado,
                          r.Nombre_Ruta
                   FROM clientes c
                   INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                   LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                   WHERE c.ID_Cliente = %s 
                   AND c.ID_Empresa = %s 
                   AND e.Estado = 'Activo'
                """,
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # MÉTODO GET - Mostrar formulario
            if request.method == 'GET':
                return render_template("admin/catalog/client/editar_clientes.html", 
                                     cliente=cliente, 
                                     rutas=rutas,
                                     productos=productos)
            
            # MÉTODO POST - Procesar formulario
            elif request.method == 'POST':
                nombre = request.form.get("nombre", "").strip()
                telefono = request.form.get("telefono", "").strip()
                direccion = request.form.get("direccion", "").strip()
                ruc_cedula = request.form.get("ruc_cedula", "").strip()
                estado = request.form.get("estado", "ACTIVO").strip()
                tipo_cliente = request.form.get("tipo_cliente", "Comun").strip()
                perfil_cliente = request.form.get("perfil_cliente", "Mercado").strip()
                id_ruta = request.form.get("id_ruta", "").strip()
                
                # NUEVOS CAMPOS DE ANTICIPO
                anticipo_activo = request.form.get("anticipo_activo", "0").strip()
                limite_anticipo_cajas = request.form.get("limite_anticipo_cajas", "0").strip()
                saldo_anticipos = request.form.get("saldo_anticipos", "0").strip()
                producto_anticipado = request.form.get("producto_anticipado", "").strip()
                cajas_consumidas = request.form.get("cajas_consumidas_anticipo", "0").strip()

                # Validaciones básicas
                if not nombre:
                    flash("El nombre del cliente es obligatorio.", "danger")
                    return render_template("admin/catalog/client/editar_clientes.html", 
                                         cliente=cliente, rutas=rutas, productos=productos)
                
                if not telefono:
                    flash("El teléfono del cliente es obligatorio.", "danger")
                    return render_template("admin/catalog/client/editar_clientes.html", 
                                         cliente=cliente, rutas=rutas, productos=productos)
                
                # Validar estado
                if estado not in ['ACTIVO', 'INACTIVO']:
                    estado = 'ACTIVO'
                
                # Validar tipo de cliente
                if tipo_cliente not in ['Comun', 'Especial']:
                    tipo_cliente = 'Comun'
                
                # Validar perfil de cliente
                if perfil_cliente not in ['Ruta', 'Mayorista', 'Mercado', 'Especial']:
                    perfil_cliente = 'Mercado'
                
                # NUEVAS VALIDACIONES DE ANTICIPO
                anticipo_activo = 1 if anticipo_activo == "1" else 0
                
                try:
                    limite_anticipo_cajas = int(limite_anticipo_cajas) if limite_anticipo_cajas else 0
                    if limite_anticipo_cajas < 0:
                        limite_anticipo_cajas = 0
                except ValueError:
                    limite_anticipo_cajas = 0
                
                try:
                    saldo_anticipos = float(saldo_anticipos) if saldo_anticipos else 0
                    if saldo_anticipos < 0:
                        saldo_anticipos = 0
                except ValueError:
                    saldo_anticipos = 0
                
                try:
                    cajas_consumidas = int(cajas_consumidas) if cajas_consumidas else 0
                    if cajas_consumidas < 0:
                        cajas_consumidas = 0
                    # Validar que no exceda el límite
                    if cajas_consumidas > limite_anticipo_cajas and limite_anticipo_cajas > 0:
                        cajas_consumidas = limite_anticipo_cajas
                except ValueError:
                    cajas_consumidas = 0
                
                if producto_anticipado:
                    try:
                        producto_anticipado = int(producto_anticipado)
                        if producto_anticipado <= 0:
                            producto_anticipado = None
                    except (ValueError, TypeError):
                        producto_anticipado = None
                else:
                    producto_anticipado = None
                
                # Validar ID_Ruta
                if id_ruta:
                    try:
                        id_ruta = int(id_ruta)
                        if id_ruta <= 0:
                            id_ruta = None
                    except (ValueError, TypeError):
                        id_ruta = None
                        
                    if id_ruta:
                        cursor.execute(
                            """SELECT 1 FROM rutas 
                            WHERE ID_Ruta = %s 
                            AND ID_Empresa = %s 
                            AND Estado = 'Activa'""",
                            (id_ruta, id_empresa)
                        )
                        ruta_valida = cursor.fetchone()
                        if not ruta_valida:
                            flash("La ruta seleccionada no es válida o está inactiva.", "danger")
                            return render_template("admin/catalog/client/editar_clientes.html", 
                                                 cliente=cliente, rutas=rutas, productos=productos)
                else:
                    id_ruta = None
                
                # Validar producto anticipado
                if producto_anticipado:
                    cursor.execute(
                        """SELECT 1 FROM productos 
                        WHERE ID_Producto = %s AND ID_Empresa = %s AND Estado = 'Activo'""",
                        (producto_anticipado, id_empresa)
                    )
                    producto_valido = cursor.fetchone()
                    if not producto_valido:
                        flash("El producto anticipado seleccionado no es válido.", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", 
                                             cliente=cliente, rutas=rutas, productos=productos)
                
                # Validación adicional para anticipos activos
                if anticipo_activo == 1:
                    if limite_anticipo_cajas == 0 and saldo_anticipos == 0 and not producto_anticipado:
                        flash("Si activa anticipos, debe configurar al menos: límite de cajas, saldo o producto anticipado.", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", 
                                             cliente=cliente, rutas=rutas, productos=productos)

                # Verificar si el RUC/Cédula ya existe en otro cliente activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        """SELECT 1 FROM clientes 
                        WHERE RUC_CEDULA = %s 
                        AND ID_Cliente != %s 
                        AND ID_Empresa = %s 
                        AND Estado = 'ACTIVO'""",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro cliente activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", 
                                             cliente=cliente, rutas=rutas, productos=productos)

                # UPDATE ACTUALIZADO con campos de anticipo
                cursor.execute("""
                    UPDATE clientes 
                    SET Nombre = %s, 
                        Telefono = %s, 
                        Direccion = %s, 
                        RUC_CEDULA = %s, 
                        Estado = %s,
                        tipo_cliente = %s,
                        perfil_cliente = %s,
                        ID_Ruta = %s,
                        Anticipo_Activo = %s,
                        Limite_Anticipo_Cajas = %s,
                        Saldo_Anticipos = %s,
                        Producto_Anticipado = %s,
                        Cajas_Consumidas_Anticipo = %s
                    WHERE ID_Cliente = %s 
                    AND ID_Empresa = %s
                """, (nombre, telefono, direccion, ruc_cedula, estado, 
                      tipo_cliente, perfil_cliente, id_ruta,
                      anticipo_activo, limite_anticipo_cajas, saldo_anticipos,
                      producto_anticipado, cajas_consumidas, id, id_empresa))
                
                # Registrar en bitácora
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Cliente {accion} correctamente.", "success")
                
                return redirect(url_for("admin.admin_clientes"))
                
    except Exception as e:
        logging.error(f"Error en edición de cliente: {str(e)}", exc_info=True)
        flash("Error al procesar la solicitud", "danger")
        return redirect(url_for("admin.admin_clientes"))
    
    return redirect(url_for("admin.admin_clientes"))

@admin_bp.route('/admin/catalog/client/eliminar-cliente/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-ELIMINAR")
def admin_eliminar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente pertenece a la empresa actual y está activo
            cursor.execute(
                """SELECT c.* 
                FROM clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s 
                AND c.Estado = 'ACTIVO' AND e.Estado = 'Activo'""",
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin.admin_clientes"))
            
            # Eliminar (cambiar estado a INACTIVO)
            cursor.execute(
                "UPDATE clientes SET Estado = 'INACTIVO' WHERE ID_Cliente = %s AND ID_Empresa = %s",
                (id, id_empresa)
            )
            
            flash("Cliente eliminado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al eliminar cliente: {str(e)}")
        flash("Error al eliminar el cliente", "danger")
    
    return redirect(url_for("admin.admin_clientes"))

# SUCURSALES DE CLIENTES
@admin_bp.route('/admin/catalog/client/sucursales')
@admin_required
@bitacora_decorator("SUCURSALES_CLIENTES")
def admin_sucursales_clientes():
    try:
        with get_db_cursor() as cursor:
            # Obtener todas las sucursales activas con información de clientes
            cursor.execute("""
                SELECT s.ID_Sucursal, s.Nombre_Sucursal, s.Direccion, s.Telefono, 
                       s.Encargado, s.Estado, s.Fecha_Creacion,
                       s.ID_Cliente, c.Nombre as Nombre_Cliente
                FROM sucursales s
                INNER JOIN clientes c ON s.ID_Cliente = c.ID_Cliente
                WHERE s.Estado = 'ACTIVO'
                ORDER BY c.Nombre, s.Nombre_Sucursal
            """)
            sucursales = cursor.fetchall()
            
            # Obtener lista de clientes activos para el formulario
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA, Direccion 
                FROM clientes 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            clientes = cursor.fetchall()
            
            return render_template("admin/catalog/client/sucursales_clientes.html", 
                                 sucursales=sucursales, 
                                 clientes=clientes)
    except Exception as e:
        logging.error(f"Error al cargar sucursales de clientes: {str(e)}")
        flash("Error al cargar las sucursales de clientes", "danger")
        return render_template("admin/catalog/client/sucursales_clientes.html", 
                             sucursales=[], clientes=[])

@admin_bp.route('/admin/catalog/client/sucursales/create', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_SUCURSAL")
def admin_sucursales_create():
    try:
        # Obtener datos del formulario
        id_cliente = request.form.get('id_cliente')
        nombre_sucursal = request.form.get('nombre_sucursal', '').strip().upper()
        direccion = request.form.get('direccion', '').strip()
        telefono = request.form.get('telefono', '').strip()
        encargado = request.form.get('encargado', '').strip().upper()
        
        # Validaciones
        if not id_cliente:
            flash("Debe seleccionar un cliente", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        if not nombre_sucursal:
            flash("El nombre de la sucursal es obligatorio", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        if len(nombre_sucursal) < 3:
            flash("El nombre de la sucursal debe tener al menos 3 caracteres", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente existe y está activo
            cursor.execute("""
                SELECT ID_Cliente, Nombre FROM clientes 
                WHERE ID_Cliente = %s AND Estado = 'ACTIVO'
            """, (id_cliente,))
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("El cliente seleccionado no existe o está inactivo", "danger")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Verificar si ya existe una sucursal con el mismo nombre para ese cliente
            cursor.execute("""
                SELECT ID_Sucursal FROM sucursales 
                WHERE ID_Cliente = %s AND Nombre_Sucursal = %s AND Estado = 'ACTIVO'
            """, (id_cliente, nombre_sucursal))
            
            if cursor.fetchone():
                flash(f"Ya existe una sucursal activa con el nombre '{nombre_sucursal}' para el cliente {cliente['Nombre']}", "warning")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Insertar nueva sucursal
            cursor.execute("""
                INSERT INTO sucursales (ID_Cliente, Nombre_Sucursal, Direccion, Telefono, Encargado, Estado, Fecha_Creacion)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVO', %s)
            """, (id_cliente, nombre_sucursal, direccion, telefono, encargado, datetime.now()))
            
            flash(f"Sucursal '{nombre_sucursal}' creada exitosamente para el cliente {cliente['Nombre']}", "success")
            
    except Exception as e:
        logging.error(f"Error al crear sucursal: {str(e)}")
        flash("Error al crear la sucursal. Por favor, intente nuevamente", "danger")
    
    return redirect(url_for('admin.admin_sucursales_clientes'))

@admin_bp.route('/admin/catalog/client/sucursales/edit/<int:id_sucursal>', methods=['POST'])
@admin_required
@bitacora_decorator("EDITAR_SUCURSAL")
def admin_sucursales_edit(id_sucursal):
    try:
        # Obtener datos del formulario
        nombre_sucursal = request.form.get('nombre_sucursal', '').strip().upper()
        direccion = request.form.get('direccion', '').strip()
        telefono = request.form.get('telefono', '').strip()
        encargado = request.form.get('encargado', '').strip().upper()
        
        if not nombre_sucursal:
            flash("El nombre de la sucursal es obligatorio", "warning")
            return redirect(url_for('admin.admin_sucursales_clientes'))
        
        with get_db_cursor() as cursor:
            # Verificar que la sucursal existe
            cursor.execute("SELECT ID_Sucursal, ID_Cliente, Nombre_Sucursal FROM sucursales WHERE ID_Sucursal = %s", (id_sucursal,))
            sucursal = cursor.fetchone()
            
            if not sucursal:
                flash("La sucursal no existe", "danger")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Verificar si el nuevo nombre ya existe para el mismo cliente (excluyendo la sucursal actual)
            cursor.execute("""
                SELECT ID_Sucursal FROM sucursales 
                WHERE ID_Cliente = %s AND Nombre_Sucursal = %s AND ID_Sucursal != %s AND Estado = 'ACTIVO'
            """, (sucursal['ID_Cliente'], nombre_sucursal, id_sucursal))
            
            if cursor.fetchone():
                flash(f"Ya existe otra sucursal con el nombre '{nombre_sucursal}' para este cliente", "warning")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Actualizar sucursal
            cursor.execute("""
                UPDATE sucursales 
                SET Nombre_Sucursal = %s, Direccion = %s, Telefono = %s, Encargado = %s
                WHERE ID_Sucursal = %s
            """, (nombre_sucursal, direccion, telefono, encargado, id_sucursal))
            
            flash("Sucursal actualizada exitosamente", "success")
            
    except Exception as e:
        logging.error(f"Error al editar sucursal {id_sucursal}: {str(e)}")
        flash("Error al actualizar la sucursal", "danger")
    
    return redirect(url_for('admin.admin_sucursales_clientes'))

@admin_bp.route('/admin/catalog/client/sucursales/delete/<int:id_sucursal>')
@admin_required
@bitacora_decorator("ELIMINAR_SUCURSAL")
def admin_sucursales_delete(id_sucursal):
    try:
        with get_db_cursor() as cursor:
            # Obtener nombre de la sucursal antes de desactivar
            cursor.execute("SELECT Nombre_Sucursal FROM sucursales WHERE ID_Sucursal = %s", (id_sucursal,))
            sucursal = cursor.fetchone()
            
            if not sucursal:
                flash("La sucursal no existe", "danger")
                return redirect(url_for('admin.admin_sucursales_clientes'))
            
            # Desactivar la sucursal
            cursor.execute("""
                UPDATE sucursales 
                SET Estado = 'INACTIVO' 
                WHERE ID_Sucursal = %s
            """, (id_sucursal,))
            
            flash(f"Sucursal '{sucursal['Nombre_Sucursal']}' desactivada exitosamente", "success")
            
    except Exception as e:
        logging.error(f"Error al eliminar sucursal {id_sucursal}: {str(e)}")
        flash("Error al eliminar la sucursal", "danger")
    
    return redirect(url_for('admin.admin_sucursales_clientes'))

@admin_bp.route('/admin/catalog/client/sucursales/get/<int:id_sucursal>')
@admin_required
def admin_sucursales_get(id_sucursal):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Sucursal, ID_Cliente, Nombre_Sucursal, Direccion, 
                       Telefono, Encargado, Estado
                FROM sucursales 
                WHERE ID_Sucursal = %s
            """, (id_sucursal,))
            
            sucursal = cursor.fetchone()
            if sucursal:
                return jsonify({'success': True, 'data': sucursal})
            else:
                return jsonify({'success': False, 'error': 'Sucursal no encontrada'})
                
    except Exception as e:
        logging.error(f"Error al obtener sucursal {id_sucursal}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# CATALOGO PROVEEDORES
@admin_bp.route('/admin/catalog/proveedor/proveedores', methods=['GET'])
@admin_required
@bitacora_decorator("PROVEEDORES")
def admin_proveedores():
    # Valores por defecto
    proveedores = []
    page = 1
    per_page = 20
    total = 0
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            offset = (page - 1) * per_page
            
            # Consulta base
            base_query = """
                SELECT p.*, e.Nombre_Empresa
                FROM proveedores p
                INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total
            count_query = "SELECT COUNT(*) as total FROM proveedores p WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s"
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Obtener datos con paginación
            data_query = base_query + " ORDER BY p.Nombre LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(data_query, params)
            proveedores = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/proveedor/proveedores: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los proveedores. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/proveedor/proveedores.html", 
                        proveedores=proveedores, 
                        page=page,
                        per_page=per_page,
                        total=total,
                        search=search_query)
    
@admin_bp.route('/admin/catalog/proveedor/crear-proveedor', methods=['POST'])  
@admin_required
@bitacora_decorator("PROVEEDORES-CREAR")
def admin_crear_proveedor():
    try:
        nombre = request.form.get('nombre','').strip()
        telefono = request.form.get('telefono','').strip()
        direccion = request.form.get('direccion','').strip()
        ruc_cedula = request.form.get('ruc_cedula','').strip()
        id_usuario = session.get('id_usuario',1)
        id_empresa = session.get('id_empresa',1)
        
        if not nombre:
            flash("El nombre del proveedor es obligatorio","danger")
            return redirect(url_for('admin.admin_proveedores'))
        
        
        with get_db_cursor() as cursor:
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    "SELECT 1 FROM proveedores WHERE RUC_CEDULA = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un proveedor con este RUC/Cédula", "danger")
                    return redirect(url_for("admin.admin_proveedores"))

            # Insertar nuevo proveedor
            cursor.execute("""
                INSERT INTO Proveedores (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, id_usuario))
            
            flash("Proveedor agregado correctamente.", "success")
    except Exception as e:
        logging.error(f"Error al crear proveedor: {str(e)}")
        flash("Error al guardar el proveedor", "danger")
    return redirect(url_for('admin.admin_proveedores'))

@admin_bp.route('/admin/catalog/proveedor/editar-proveedor/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-EDITAR")
def admin_editar_proveedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                           SELECT p.* 
                           FROM proveedores p
                           INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND e.Estado = 'Activo'
                           """, (id, id_empresa))
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado.", "danger")
                return redirect(url_for("admin.admin_proveedores"))
            
            if request.method == 'GET':
                return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                       proveedor=proveedor)
                
            elif request.method == 'POST':
                nombre = request.form.get('nombre','').strip()
                telefono = request.form.get('telefono','').strip()
                direccion = request.form.get('direccion','').strip()
                ruc_cedula = request.form.get('ruc_cedula','').strip()
                estado = request.form.get('estado','ACTIVO').strip()
                
                if not nombre:
                    flash("El nombre del proveedor es obligatorio","danger")
                    return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                           proveedor=proveedor)
                
                # Verificar si el RUC/Cédula ya existe en otro proveedor activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        "SELECT 1 FROM proveedores WHERE RUC_CEDULA = %s AND ID_Proveedor != %s AND ID_Empresa = %s AND Estado = 'ACTIVO'",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro proveedor activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                               proveedor=proveedor)
                
                # Actualizar proveedor
                cursor.execute("""
                               UPDATE Proveedores 
                               SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s, Estado = %s
                               WHERE ID_Proveedor = %s AND ID_Empresa = %s
                               """, (nombre, telefono, direccion, ruc_cedula, estado, id, id_empresa))
                
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Proveedor {accion} correctamente.","success")
                
                return redirect(url_for("admin.admin_proveedores"))
            
    except Exception as e:
        logging.error(f"Error en edición de proveedor: {str(e)}")
        flash("Error al procesar la solicitud","danger")
        return redirect(url_for("admin.admin_proveedores"))

    return redirect(url_for("admin.admin_proveedores"))

@admin_bp.route('/admin/catalog/proveedor/eliminar-proveedor/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-ELIMINAR")
def admin_eliminar_probeedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            #verificar que el proveedor pertenece a la emprsa
            cursor.execute("""
                           SELECT p.*
                           FROM proveedores p
                           INNER JOIN empresa e On p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND p.Estado = 'ACTIVO' AND e.Estado = 'Activo'
                           """, (id, id_empresa)
                        )
            
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado","danger")
                return redirect(url_for("admin.admin_proveedores"))

            #Eliminar (cambiar estado a INACTIVO)
            cursor.execute("""
                           UPDATE Proveedores SET Estado = 'INACTIVO' 
                           WHERE ID_Proveedor = %s AND ID_Empresa = %s
                           """, (id, id_empresa)
                           )
            
            flash("Proveedor eliminado correctamente.","success")
    
    except Exception as e:
        logging.error(f"Error al eliminar proveedor: {str(e)}")
        flash("Error al eliminar el proveedor","danger")
    
    return redirect(url_for("admin.admin_proveedores"))

# CATALOGO MEDIDAS
@admin_bp.route('/admin/catalog/medidas/unidades-medidas', methods=['GET'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS")
def admin_unidades_medidas():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_Unidad, Descripcion, Abreviatura 
                FROM unidades_medida 
                ORDER BY Descripcion DESC
            """)
            unidades = cursor.fetchall()
            return render_template('admin/catalog/medidas/unidades_medidas.html', 
                                 unidades=unidades)
    except Exception as e:
        flash(f"Error al cargar unidades de medida: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/catalog/medidas/crear-unidad', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-CREAR")
def admin_crear_unidad_medida():

    if request.method == 'POST':
        descripcion = request.form.get('descripcion','').strip()
        abreviatura = request.form.get('abreviatura','').strip()

        if not descripcion or not abreviatura:
            flash("Descripción y abreviatura son obligatorias.", "danger")
            return redirect(url_for('admin.admin_unidades_medidas'))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO unidades_medida (Descripcion, Abreviatura)
                    VALUES (%s, %s)
                """, (descripcion, abreviatura))
                
                flash("Unidad de medida creada exitosamente.", "success")
                return redirect(url_for('admin.admin_unidades_medidas'))
            
        except Exception as e:
            flash(f"Error al crear unidad de medida: {e}", "danger")
            return redirect(url_for('admin.admin_unidades_medidas'))
    
    return render_template('admin/catalog/medidas/crear_unidad.html')

@admin_bp.route('/admin/catalog/medidas/editar-unidad/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-EDITAR")
def admin_editar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            
            if request.method == 'POST':

                descripcion = request.form.get('descripcion','').strip()
                abreviatura = request.form.get('abreviatura','').strip()

                if not descripcion or not abreviatura:
                    flash("Descripción y abreviatura son obligatorias.", "danger")
                    return redirect(url_for('admin.admin_unidades_medidas'))
                
                cursor.execute("""
                    UPDATE unidades_medida
                    SET Descripcion = %s, Abreviatura = %s
                    WHERE ID_Unidad = %s
                    """, (descripcion, abreviatura, id))
                
                flash("Unidad de medida actualizada exitosamente.", "success")
                return redirect(url_for('admin.admin_unidades_medidas'))
            
            else:

                #obtener datos actuales
                cursor.execute("""
                    SELECT ID_Unidad, Descripcion, Abreviatura
                    FROM unidades_medida
                    WHERE ID_Unidad = %s
                    """, (id,))
                
                unidad = cursor.fetchone()

                if not unidad:
                    flash("Unidad de medida no encontrada.", "danger")
                    return redirect(url_for('admin.admin_unidades_medidas'))
                
                return render_template('admin/catalog/medidas/editar_unidad_medida.html',
                                        unidad=unidad)
        
    except Exception as e:
        flash(f"Error al editar unidad de medida: {e}", "danger")
        return redirect(url_for('admin.admin_unidades_medidas'))

@admin_bp.route('/admin/catalog/medidas/unidades-medidas/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS-ELIMINAR")
def eliminar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la unidad existe
            cursor.execute("SELECT Descripcion FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            unidad = cursor.fetchone()
            
            if not unidad:
                flash("Unidad de medida no encontrada", "danger")
                return redirect(url_for('admin.admin_unidades_medidas'))
            
            cursor.execute("DELETE FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            
            flash(f"Unidad de medida '{unidad['Descripcion']}' eliminada exitosamente", "success")
            
    except Exception as e:
        flash(f"Error al eliminar unidad de medida: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_unidades_medidas'))

# CATALOGO CATEGORIAS
@admin_bp.route('/admin/catalog/categorias', methods=['GET'])
@admin_required
@bitacora_decorator("CATEGORIAS")
def admin_categorias():
    try:
        with get_db_cursor() as cursor: 
            cursor.execute("""
                SELECT ID_Categoria, Descripcion, Estado 
                FROM categorias_producto 
                ORDER BY ID_Categoria DESC
            """)
            categorias = cursor.fetchall()
            return render_template('admin/catalog/categorias/categorias.html', 
                                 categorias=categorias)
    except Exception as e:
        logger.error(f"Error al cargar categorías: {str(e)}", exc_info=True)
        flash("Error al cargar las categorías", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/catalog/categorias/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_CREAR")
def admin_categorias_crear():
    try:
        descripcion = request.form.get('descripcion', '').strip()
        estado = request.form.get('estado', 'Activo')  # Obtener estado del formulario
        
        if not descripcion:
            flash("La descripción es requerida", "danger")
            return redirect(url_for('admin.admin_categorias'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO categorias_producto (Descripcion, Estado) 
                VALUES (%s, %s)
            """, (descripcion, estado))
            
        flash("Categoría creada exitosamente", "success")
    except Exception as e:
        logger.error(f"Error al crear categoría: {str(e)}", exc_info=True)
        flash(f"Error al crear categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_categorias'))

@admin_bp.route('/admin/catalog/categorias/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_EDITAR")
def admin_categorias_editar(id):
    try:
        if request.method == 'GET':
            # Mostrar formulario con datos actuales
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT ID_Categoria, Descripcion, Estado 
                    FROM categorias_producto 
                    WHERE ID_Categoria = %s
                """, (id,))
                categoria = cursor.fetchone()
                
                if not categoria:
                    flash("Categoría no encontrada", "danger")
                    return redirect(url_for('admin.admin_categorias'))
                
                return render_template('admin/catalog/categorias/editar_categoria.html', 
                                     categoria=categoria)
        
        else:  # POST - procesar edición
            descripcion = request.form.get('descripcion', '').strip()
            estado = request.form.get('estado', 'Activo')  # Obtener estado del formulario
            
            if not descripcion:
                flash("La descripción es requerida", "danger")
                return redirect(url_for('admin.admin_categorias_editar', id=id))
            
            # Verificar que la categoría existe
            with get_db_cursor(commit=True) as cursor:
                # Primero verificar existencia
                cursor.execute("""
                    SELECT ID_Categoria 
                    FROM categorias_producto 
                    WHERE ID_Categoria = %s
                """, (id,))
                
                if not cursor.fetchone():
                    flash("Categoría no encontrada", "danger")
                    return redirect(url_for('admin.admin_categorias'))
                
                # Actualizar categoría incluyendo el estado
                cursor.execute("""
                    UPDATE categorias_producto 
                    SET Descripcion = %s, Estado = %s 
                    WHERE ID_Categoria = %s
                """, (descripcion, estado, id))
            
            flash("Categoría actualizada exitosamente", "success")
            return redirect(url_for('admin.admin_categorias'))
            
    except Exception as e:
        logger.error(f"Error al editar categoría {id}: {str(e)}", exc_info=True)
        flash(f"Error al editar categoría: {str(e)}", "danger")
        return redirect(url_for('admin.admin_categorias'))

@admin_bp.route('/admin/catalog/categorias/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_ELIMINAR")
def admin_categorias_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la categoría existe
            cursor.execute("""
                SELECT ID_Categoria, Estado FROM categorias_producto 
                WHERE ID_Categoria = %s
            """, (id,))
            
            categoria = cursor.fetchone()
            if not categoria:
                flash("Categoría no encontrada", "warning")
                return redirect(url_for('admin.admin_categorias'))
            
            cursor.execute("""
                UPDATE categorias_producto 
                SET Estado = 'Inactivo' 
                WHERE ID_Categoria = %s
            """, (id,))
            
            affected_rows = cursor.rowcount
            
        if affected_rows > 0:
            flash("Categoría desactivada exitosamente", "success")
        else:
            flash("No se pudo desactivar la categoría", "warning")
            
    except Exception as e:
        logger.error(f"Error al eliminar categoría ID {id}: {str(e)}", exc_info=True)
        
        # Verificar si es error de integridad referencial
        if "foreign key constraint" in str(e).lower() or "1451" in str(e):
            flash("No se puede eliminar la categoría porque tiene productos asociados", "danger")
        else:
            flash(f"Error al eliminar categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_categorias'))

@admin_bp.route('/admin/catalog/categorias/toggle-estado/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_TOGGLE_ESTADO")
def admin_categorias_toggle_estado(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Obtener estado actual
            cursor.execute("""
                SELECT Estado FROM categorias_producto 
                WHERE ID_Categoria = %s
            """, (id,))
            
            categoria = cursor.fetchone()
            if not categoria:
                flash("Categoría no encontrada", "warning")
                return redirect(url_for('admin.admin_categorias'))
            
            # Cambiar estado
            nuevo_estado = 'Inactivo' if categoria['Estado'] == 'Activo' else 'Activo'
            cursor.execute("""
                UPDATE categorias_producto 
                SET Estado = %s 
                WHERE ID_Categoria = %s
            """, (nuevo_estado, id))
            
        flash(f"Categoría {nuevo_estado.lower()} exitosamente", "success")
        
    except Exception as e:
        logger.error(f"Error al cambiar estado de categoría {id}: {str(e)}", exc_info=True)
        flash(f"Error al cambiar estado: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_categorias'))

# CATALOGO METODOS DE PAGO
@admin_bp.route('/admin/catalog/metodospagos/metodo-pagos', methods=['GET'])
@admin_required
@bitacora_decorator("METODOS-PAGO")
def admin_metodos_pago():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM Metodos_Pago 
                ORDER BY ID_MetodoPago DESC
            """)
            metodos = cursor.fetchall()
            return render_template('admin/catalog/metodospagos/metodo_pagos.html', 
                                 metodos=metodos)
    except Exception as e:
        flash(f"Error al cargar métodos de pago: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/catalog/metodospagos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-CREAR")
def admin_metodos_pago_crear():
    try:
        nombre = request.form.get('nombre', '').strip()

        if not nombre:
            flash("El nombre del método de pago es requerido", "danger")
            return redirect(url_for('admin.admin_metodos_pago'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Metodos_Pago (Nombre) 
                VALUES (%s)
            """, (nombre,))

        flash("Método de pago creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear método de pago: {str(e)}", "danger")
    return redirect(url_for('admin.admin_metodos_pago'))

@admin_bp.route('/admin/catalog/metodospagos/editar/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-EDITAR")
def admin_metodos_pago_editar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # GET
            if request.method == 'GET':
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM Metodos_Pago
                    WHERE ID_MetodoPago = %s 
                               """,(id,))
                
                metodo = cursor.fetchone()

                if not metodo:
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                return render_template('admin/catalog/metodospagos/editar_metodo_pago.html',
                                       metodo=metodo)
            
            #POST
            elif request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()

                if not nombre:
                    flash("El nombre del método de pago es requerido", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                cursor.execute("""
                        SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s   
                        """, (id,))
                
                if not cursor.fetchone():
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                cursor.execute("""
                    UPDATE Metodos_Pago
                    SET Nombre = %s
                    WHERE ID_MetodoPago = %s
                    """, (nombre, id))
                
                flash("Metodo d epago actualizado exitosamente", "success")
                return redirect(url_for('admin.admin_metodos_pago'))

    except Exception as e:
        flash(f"Error al editar método de pago: {str(e)}", "danger")
        return redirect(url_for('admin.admin_metodos_pago'))

@admin_bp.route('/admin/catalog/metodospagos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-ELIMINAR")
def admin_metodos_pago_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s
            """, (id,))

            if not cursor.fetchone():
                flash("Método de pago no encontrado.", "danger")
                return redirect(url_for('admin.admin_metodos_pago'))
            
            cursor.execute("""
                DELETE FROM Metodos_Pago
                WHERE ID_MetodoPago = %s
            """, (id,))

        flash("Metodos de pago eliminado exitosamente", "success")
            
    except Exception as e:
        #Manejar error de integridad referencial
        if "foreing key constraint" in str(e).lower():
            flash("No se puede eliminar el método de pago porque está asociado a otros registros.", "danger")
        else:
            flash(f"Error al eliminar método de pago: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_metodos_pago'))

#CATALOGO MOVIMINETOS DE INVENTARIO
@admin_bp.route('/admin/catalog/movimientos/movimientos-inventario', methods=['GET'])
@admin_required
@bitacora_decorator("MOVIMIENTOS-INVENTARIO")
def admin_movimientos_inventario():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT * FROM catalogo_movimientos ORDER BY ID_TipoMovimiento""")
            movimientos = cursor.fetchall()
            return render_template('admin/catalog/movimientos/movimientos_inventario.html', 
                                 movimientos=movimientos)
    except Exception as e:
        flash(f"Error al cargar movimientos de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))
    
@admin_bp.route('/admin/catalog/movimientos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR-MOVIMIENTO-INVENTARIO")
def admin_crear_movimiento():
    try:
        descripcion = request.form.get('descripcion')
        adicion = request.form.get('adicion')
        letra = request.form.get('letra')
        
        if not descripcion or not letra:
            flash("Descripción y Letra son campos obligatorios", "warning")
            return redirect(url_for('admin.admin_movimientos_inventario'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO catalogo_movimientos (Descripcion, Adicion, Letra) VALUES (%s, %s, %s)",
                (descripcion, adicion, letra)
            )
            
        flash("Movimiento de inventario creado exitosamente", "success")
        return redirect(url_for('admin.admin_movimientos_inventario'))
        
    except Exception as e:
        flash(f"Error al crear movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin.admin_movimientos_inventario'))
            
@admin_bp.route('/admin/catalog/movimientos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR-MOVIMIENTO-INVENTARIO")
def admin_editar_movimiento(id):
    try:
        if request.method == 'POST':
            descripcion = request.form.get('descripcion')
            adicion = request.form.get('adicion')
            letra = request.form.get('letra')
            
            if not descripcion or not letra:
                flash("Descripción y Letra son campos obligatorios", "warning")
                return redirect(url_for('admin.admin_editar_movimiento', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE catalogo_movimientos SET Descripcion = %s, Adicion = %s, Letra = %s WHERE ID_TipoMovimiento = %s",
                    (descripcion, adicion, letra, id)
                )
                
            flash("Movimiento de inventario actualizado exitosamente", "success")
            return redirect(url_for('admin.admin_movimientos_inventario'))
        
        # GET - Cargar datos del movimiento
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM catalogo_movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin.admin_movimientos_inventario'))
                
        return render_template('admin/catalog/movimientos/editar_movimiento.html', movimiento=movimiento)
        
    except Exception as e:
        flash(f"Error al editar movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin.admin_movimientos_inventario'))

@admin_bp.route('/admin/catalog/movimientos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR-MOVIMIENTO-INVENTARIO")
def admin_eliminar_movimiento(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si el movimiento existe
            cursor.execute("SELECT * FROM catalogo_movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin.admin_movimientos_inventario'))
            
            # Eliminar el movimiento
            cursor.execute("DELETE FROM catalogo_movimientos WHERE ID_TipoMovimiento = %s", (id,))
            
        flash("Movimiento de inventario eliminado exitosamente", "success")
        
    except Exception as e:
        flash(f"Error al eliminar movimiento de inventario: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_movimientos_inventario'))

# CATALOGO TIPOS DE GASTOS
# ========== GESTIÓN DE TIPOS DE GASTO ==========

@admin_bp.route('/admin/gastos/tipos', methods=['GET'])
@admin_required
@bitacora_decorator("VER_TIPOS_GASTO")
def admin_tipos_gasto():
    """Listar todos los tipos de gasto"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre, Descripcion, Origen, 
                       ID_Categoria_Inventario, Estado
                FROM tipos_gasto 
                WHERE ID_Empresa = %s
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
        return render_template(
            'admin/catalog/gastos/tipos_gasto.html',
            tipos_gasto=tipos_gasto,
            titulo="Tipos de Gastos"
        )
        
    except Exception as e:
        logger.error(f"Error al listar tipos de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

@admin_bp.route('/admin/gastos/tipos/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CREAR_TIPO_GASTO")
def crear_tipo_gasto():
    """Crear nuevo tipo de gasto"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener categorías de inventario para el select
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                WHERE Estado = 'Activo'
                ORDER BY Descripcion
            """)
            categorias_inventario = cursor.fetchall()
            
            if request.method == 'POST':
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                origen = request.form.get('origen')
                id_categoria_inventario = request.form.get('id_categoria_inventario') or None
                estado = request.form.get('estado', 'Activo')
                
                if not nombre:
                    flash('El nombre del tipo de gasto es requerido', 'error')
                    return redirect(url_for('admin.crear_tipo_gasto'))
                
                if origen == 'INVENTARIO' and not id_categoria_inventario:
                    flash('Debe seleccionar una categoría de inventario', 'error')
                    return redirect(url_for('admin.crear_tipo_gasto'))
                
                # Verificar si ya existe
                cursor.execute("""
                    SELECT ID_Tipo_Gasto FROM tipos_gasto 
                    WHERE Nombre = %s AND ID_Empresa = %s
                """, [nombre, id_empresa])
                existe = cursor.fetchone()
                
                if existe:
                    flash('Ya existe un tipo de gasto con ese nombre', 'error')
                    return redirect(url_for('admin.crear_tipo_gasto'))
                
                cursor.execute("""
                    INSERT INTO tipos_gasto (Nombre, Descripcion, Origen, ID_Categoria_Inventario, Estado, ID_Empresa)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, [nombre, descripcion, origen, id_categoria_inventario, estado, id_empresa])
                
                flash(f'Tipo de gasto "{nombre}" creado exitosamente', 'success')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            return render_template(
                'admin/catalog/gastos/tipo_gasto_form.html',
                tipo=None,
                categorias_inventario=categorias_inventario,
                titulo="Crear Tipo de Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al crear tipo de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_tipos_gasto'))


@admin_bp.route('/admin/gastos/tipos/editar/<int:id_tipo>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_TIPO_GASTO")
def editar_tipo_gasto(id_tipo):
    """Editar tipo de gasto existente"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre, Descripcion, Origen, 
                       ID_Categoria_Inventario, Estado
                FROM tipos_gasto 
                WHERE ID_Tipo_Gasto = %s AND ID_Empresa = %s
            """, [id_tipo, id_empresa])
            tipo = cursor.fetchone()
            
            if not tipo:
                flash('Tipo de gasto no encontrado', 'error')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            # Obtener categorías de inventario
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                WHERE Estado = 'Activo'
                ORDER BY Descripcion
            """)
            categorias_inventario = cursor.fetchall()
            
            if request.method == 'POST':
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                origen = request.form.get('origen')
                id_categoria_inventario = request.form.get('id_categoria_inventario') or None
                estado = request.form.get('estado')
                
                if not nombre:
                    flash('El nombre del tipo de gasto es requerido', 'error')
                    return redirect(url_for('admin.editar_tipo_gasto', id_tipo=id_tipo))
                
                if origen == 'INVENTARIO' and not id_categoria_inventario:
                    flash('Debe seleccionar una categoría de inventario', 'error')
                    return redirect(url_for('admin.editar_tipo_gasto', id_tipo=id_tipo))
                
                cursor.execute("""
                    UPDATE tipos_gasto 
                    SET Nombre = %s, Descripcion = %s, Origen = %s, 
                        ID_Categoria_Inventario = %s, Estado = %s
                    WHERE ID_Tipo_Gasto = %s AND ID_Empresa = %s
                """, [nombre, descripcion, origen, id_categoria_inventario, estado, id_tipo, id_empresa])
                
                flash(f'Tipo de gasto "{nombre}" actualizado exitosamente', 'success')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            return render_template(
                'admin/catalog/gastos/tipo_gasto_form.html',
                tipo=tipo,
                categorias_inventario=categorias_inventario,
                titulo="Editar Tipo de Gasto"
            )
            
    except Exception as e:
        logger.error(f"Error al editar tipo de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_tipos_gasto'))


@admin_bp.route('/admin/gastos/tipos/eliminar/<int:id_tipo>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR_TIPO_GASTO")
def eliminar_tipo_gasto(id_tipo):
    """Eliminar (desactivar) tipo de gasto"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Verificar si tiene subcategorías asociadas
            cursor.execute("""
                SELECT COUNT(*) as total FROM subcategorias_gasto 
                WHERE ID_Tipo_Gasto = %s
            """, [id_tipo])
            subcategorias = cursor.fetchone()
            
            if subcategorias['total'] > 0:
                flash(f'No se puede eliminar: tiene {subcategorias["total"]} subcategorías asociadas', 'error')
                return redirect(url_for('admin.admin_tipos_gasto'))
            
            # Desactivar en lugar de eliminar
            cursor.execute("""
                UPDATE tipos_gasto 
                SET Estado = 'Inactivo'
                WHERE ID_Tipo_Gasto = %s AND ID_Empresa = %s
            """, [id_tipo, id_empresa])
            
            flash('Tipo de gasto desactivado exitosamente', 'success')
            
    except Exception as e:
        logger.error(f"Error al eliminar tipo de gasto: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_tipos_gasto'))

# ========== GESTIÓN DE SUBCATEGORÍAS ==========

@admin_bp.route('/admin/gastos/subcategorias', methods=['GET'])
@admin_required
@bitacora_decorator("VER_SUBCATEGORIAS")
def admin_subcategorias():
    """Listar todas las subcategorías"""
    try:
        id_empresa = session.get('id_empresa', 1)
        tipo_filtro = request.args.get('tipo', '')
        
        with get_db_cursor(True) as cursor:
            query = """
                SELECT sg.ID_Subcategoria, sg.Nombre, sg.Descripcion, sg.Estado,
                       tg.Nombre as tipo_gasto_nombre, tg.ID_Tipo_Gasto
                FROM subcategorias_gasto sg
                INNER JOIN tipos_gasto tg ON sg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE tg.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if tipo_filtro:
                query += " AND tg.ID_Tipo_Gasto = %s"
                params.append(tipo_filtro)
            
            query += " ORDER BY tg.Nombre, sg.Nombre"
            
            cursor.execute(query, params)
            subcategorias = cursor.fetchall()
            
            # Obtener tipos de gasto para el filtro
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE ID_Empresa = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
        return render_template(
            'admin/catalog/gastos/subcategorias.html',
            subcategorias=subcategorias,
            tipos_gasto=tipos_gasto,
            tipo_filtro=tipo_filtro,
            titulo="Subcategorías de Gastos"
        )
        
    except Exception as e:
        logger.error(f"Error al listar subcategorías: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))


@admin_bp.route('/admin/gastos/subcategorias/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CREAR_SUBCATEGORIA")
def crear_subcategoria():
    """Crear nueva subcategoría"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE ID_Empresa = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                estado = request.form.get('estado', 'Activo')
                
                if not id_tipo_gasto:
                    flash('Debe seleccionar un tipo de gasto', 'error')
                    return redirect(url_for('admin.crear_subcategoria'))
                
                if not nombre:
                    flash('El nombre de la subcategoría es requerido', 'error')
                    return redirect(url_for('admin.crear_subcategoria'))
                
                # Verificar si ya existe
                cursor.execute("""
                    SELECT ID_Subcategoria FROM subcategorias_gasto 
                    WHERE ID_Tipo_Gasto = %s AND Nombre = %s
                """, [id_tipo_gasto, nombre])
                existe = cursor.fetchone()
                
                if existe:
                    flash('Ya existe una subcategoría con ese nombre para este tipo de gasto', 'error')
                    return redirect(url_for('admin.crear_subcategoria'))
                
                cursor.execute("""
                    INSERT INTO subcategorias_gasto (ID_Tipo_Gasto, Nombre, Descripcion, Estado)
                    VALUES (%s, %s, %s, %s)
                """, [id_tipo_gasto, nombre, descripcion, estado])
                
                flash(f'Subcategoría "{nombre}" creada exitosamente', 'success')
                return redirect(url_for('admin.admin_subcategorias'))
            
            return render_template(
                'admin/catalog/gastos/subcategoria_form.html',
                subcategoria=None,
                tipos_gasto=tipos_gasto,
                titulo="Crear Subcategoría"
            )
            
    except Exception as e:
        logger.error(f"Error al crear subcategoría: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_subcategorias'))


@admin_bp.route('/admin/gastos/subcategorias/editar/<int:id_sub>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_SUBCATEGORIA")
def editar_subcategoria(id_sub):
    """Editar subcategoría existente"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT sg.*, tg.ID_Tipo_Gasto, tg.Nombre as tipo_nombre
                FROM subcategorias_gasto sg
                INNER JOIN tipos_gasto tg ON sg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE sg.ID_Subcategoria = %s AND tg.ID_Empresa = %s
            """, [id_sub, id_empresa])
            subcategoria = cursor.fetchone()
            
            if not subcategoria:
                flash('Subcategoría no encontrada', 'error')
                return redirect(url_for('admin.admin_subcategorias'))
            
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE ID_Empresa = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                nombre = request.form.get('nombre')
                descripcion = request.form.get('descripcion')
                estado = request.form.get('estado')
                
                if not nombre:
                    flash('El nombre de la subcategoría es requerido', 'error')
                    return redirect(url_for('admin.editar_subcategoria', id_sub=id_sub))
                
                cursor.execute("""
                    UPDATE subcategorias_gasto 
                    SET ID_Tipo_Gasto = %s, Nombre = %s, Descripcion = %s, Estado = %s
                    WHERE ID_Subcategoria = %s
                """, [id_tipo_gasto, nombre, descripcion, estado, id_sub])
                
                flash(f'Subcategoría "{nombre}" actualizada exitosamente', 'success')
                return redirect(url_for('admin.admin_subcategorias'))
            
            return render_template(
                'admin/catalog/gastos/subcategoria_form.html',
                subcategoria=subcategoria,
                tipos_gasto=tipos_gasto,
                titulo="Editar Subcategoría"
            )
            
    except Exception as e:
        logger.error(f"Error al editar subcategoría: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.admin_subcategorias'))


@admin_bp.route('/admin/gastos/subcategorias/eliminar/<int:id_sub>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR_SUBCATEGORIA")
def eliminar_subcategoria(id_sub):
    """Eliminar (desactivar) subcategoría"""
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Verificar si tiene gastos asociados
            cursor.execute("""
                SELECT COUNT(*) as total FROM gastos_generales 
                WHERE ID_Subcategoria = %s AND ID_Empresa = %s
            """, [id_sub, id_empresa])
            gastos = cursor.fetchone()
            
            if gastos['total'] > 0:
                flash(f'No se puede eliminar: tiene {gastos["total"]} gastos asociados', 'error')
                return redirect(url_for('admin.admin_subcategorias'))
            
            # Desactivar en lugar de eliminar
            cursor.execute("""
                UPDATE subcategorias_gasto 
                SET Estado = 'Inactivo'
                WHERE ID_Subcategoria = %s
            """, [id_sub])
            
            flash('Subcategoría desactivada exitosamente', 'success')
            
    except Exception as e:
        logger.error(f"Error al eliminar subcategoría: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_subcategorias'))

#### RUTAS #####
@admin_bp.route('/admin/rutas', methods=['GET'])
@admin_required
@bitacora_decorator("RUTAS")
def admin_rutas():
    try:
        with get_db_cursor() as cursor:
            # Obtener rutas - ACTUALIZADO para nueva estructura
            cursor.execute("""
                SELECT 
                    r.ID_Ruta,
                    r.Nombre_Ruta,
                    r.Descripcion,
                    r.ID_Empresa,
                    r.Estado,
                    DATE_FORMAT(r.Fecha_Creacion, '%d/%m/%Y %H:%i:%s') as Fecha_Creacion,
                    e.Nombre_Empresa as Nombre_Empresa 
                FROM rutas r 
                LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                ORDER BY r.ID_Ruta DESC
            """)
            
            rutas = cursor.fetchall()
            
            # Obtener empresas activas para los select
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
        return render_template('admin/catalog/rutas/rutas.html', rutas=rutas, empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar rutas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/rutas/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR-RUTA")
def crear_ruta():
    try:
        # Obtener datos del formulario - ACTUALIZADO (sin hora_inicio y hora_fin)
        nombre_ruta = request.form.get('nombre_ruta', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        id_empresa = request.form.get('id_empresa')
        
        print(f"DEBUG: Creando ruta - Nombre: '{nombre_ruta}', Empresa: '{id_empresa}'")
        
        # Validaciones básicas
        if not nombre_ruta:
            flash("El nombre de la ruta es obligatorio", "danger")
            return redirect(url_for('admin.admin_rutas'))
        
        if not id_empresa:
            flash("Debe seleccionar una empresa", "danger")
            return redirect(url_for('admin.admin_rutas'))
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar si ya existe una ruta con el mismo nombre
            cursor.execute("SELECT ID_Ruta FROM rutas WHERE Nombre_Ruta = %s", (nombre_ruta,))
            if cursor.fetchone():
                flash("Ya existe una ruta con ese nombre. Por favor, use un nombre diferente.", "warning")
                return redirect(url_for('admin.admin_rutas'))
            
            # Verificar que la empresa existe
            cursor.execute("SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", (id_empresa,))
            if not cursor.fetchone():
                flash("La empresa seleccionada no existe o no está activa", "danger")
                return redirect(url_for('admin.admin_rutas'))
            
            # Insertar nueva ruta - ACTUALIZADO: Solo Nombre_Ruta, Descripcion, ID_Empresa, Estado
            cursor.execute("""
                INSERT INTO rutas (Nombre_Ruta, Descripcion, ID_Empresa, Estado)
                VALUES (%s, %s, %s, 'Activa')
            """, (nombre_ruta, descripcion or None, id_empresa))
            
            nuevo_id = cursor.lastrowid
            print(f"DEBUG: Ruta creada con ID: {nuevo_id}")
        
        flash("✅ Ruta creada exitosamente", "success")
        return redirect(url_for('admin.admin_rutas'))
        
    except Exception as e:
        print(f"ERROR en crear_ruta: {str(e)}")
        flash(f"Error al crear ruta: {str(e)}", "danger")
        return redirect(url_for('admin.admin_rutas'))

@admin_bp.route('/admin/rutas/editar/<int:id_ruta>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR-RUTA")
def admin_editar_ruta(id_ruta):
    """Maneja tanto la visualización como el procesamiento del formulario de edición"""
    
    try:
        with get_db_cursor() as cursor:
            # Obtener empresas activas (se usa en ambos métodos)
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            # ========== MÉTODO GET: Mostrar formulario ==========
            if request.method == 'GET':
                # Obtener los datos de la ruta específica - ACTUALIZADO para nueva estructura
                cursor.execute("""
                    SELECT 
                        r.ID_Ruta,
                        r.Nombre_Ruta,
                        r.Descripcion,
                        r.Estado,
                        r.ID_Empresa,
                        r.Fecha_Creacion,
                        e.Nombre_Empresa
                    FROM rutas r 
                    LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                    WHERE r.ID_Ruta = %s
                """, (id_ruta,))
                ruta = cursor.fetchone()
                
                if not ruta:
                    flash("❌ La ruta no existe", "danger")
                    return redirect(url_for('admin.admin_rutas'))
                
                print(f"DEBUG: Mostrando formulario para editar ruta ID: {id_ruta}")
                print(f"DEBUG: Datos de la ruta: {dict(ruta)}")
                
                return render_template('admin/catalog/rutas/editar_ruta.html', 
                                     ruta=ruta, 
                                     empresas=empresas)
            
            # ========== MÉTODO POST: Procesar formulario ==========
            elif request.method == 'POST':
                # Obtener datos del formulario - ACTUALIZADO (sin hora_inicio y hora_fin)
                nombre_ruta = request.form.get('nombre_ruta', '').strip()
                descripcion = request.form.get('descripcion', '').strip()
                id_empresa = request.form.get('id_empresa')
                
                print(f"DEBUG: Procesando edición de ruta {id_ruta}")
                print(f"DEBUG: Datos recibidos - Nombre: '{nombre_ruta}', Empresa: '{id_empresa}'")
                
                # Validaciones
                errores = []
                
                if not nombre_ruta:
                    errores.append("El nombre de la ruta es obligatorio")
                
                if not id_empresa:
                    errores.append("Debe seleccionar una empresa")
                else:
                    # Validar que el ID de empresa es numérico
                    try:
                        id_empresa = int(id_empresa)
                    except ValueError:
                        errores.append("El ID de empresa no es válido")
                
                if errores:
                    for error in errores:
                        flash(f"❌ {error}", "danger")
                    
                    # Obtener datos actuales para mostrar el formulario con errores
                    cursor.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor.fetchone()
                    
                    return render_template('admin/catalog/rutas/editar_ruta.html', 
                                         ruta=ruta, 
                                         empresas=empresas)
                
                # Verificar si la ruta existe - ACTUALIZADO (sin hora_inicio y hora_fin)
                cursor.execute("""
                    SELECT ID_Ruta, Nombre_Ruta, Descripcion, ID_Empresa 
                    FROM rutas 
                    WHERE ID_Ruta = %s
                """, (id_ruta,))
                ruta_existente = cursor.fetchone()
                
                if not ruta_existente:
                    flash("❌ La ruta no existe", "danger")
                    return redirect(url_for('admin.admin_rutas'))
                
                # Verificar si ya existe otra ruta con el mismo nombre
                cursor.execute("""
                    SELECT ID_Ruta 
                    FROM rutas 
                    WHERE Nombre_Ruta = %s AND ID_Ruta != %s
                """, (nombre_ruta, id_ruta))
                
                if cursor.fetchone():
                    flash("⚠️ Ya existe otra ruta con ese nombre. Por favor, use un nombre diferente.", "warning")
                    
                    # Recargar datos para mostrar el formulario con el error
                    cursor.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor.fetchone()
                    
                    return render_template('admin/catalog/rutas/editar_ruta.html', 
                                         ruta=ruta, 
                                         empresas=empresas)
                
                # Verificar que la empresa existe y está activa
                cursor.execute("""
                    SELECT ID_Empresa, Nombre_Empresa 
                    FROM empresa 
                    WHERE ID_Empresa = %s AND Estado = 'Activo'
                """, (id_empresa,))
                
                empresa_valida = cursor.fetchone()
                if not empresa_valida:
                    flash("❌ La empresa seleccionada no existe o no está activa", "danger")
                    
                    # Recargar datos para mostrar el formulario con el error
                    cursor.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor.fetchone()
                    
                    return render_template('admin/catalog/rutas/editar_ruta.html', 
                                         ruta=ruta, 
                                         empresas=empresas)
                
                # Comparar datos actuales con nuevos para ver si hubo cambios
                hubo_cambios = False
                cambios_detalle = []
                
                # Comparar nombre
                if ruta_existente['Nombre_Ruta'] != nombre_ruta:
                    hubo_cambios = True
                    cambios_detalle.append(f"Nombre: '{ruta_existente['Nombre_Ruta']}' → '{nombre_ruta}'")
                
                # Comparar descripción (manejar valores None)
                desc_actual = ruta_existente['Descripcion'] or ''
                desc_nueva = descripcion or ''
                if desc_actual != desc_nueva:
                    hubo_cambios = True
                    cambios_detalle.append(f"Descripción actualizada")
                
                # Comparar empresa
                if ruta_existente['ID_Empresa'] != id_empresa:
                    hubo_cambios = True
                    cambios_detalle.append(f"Empresa: ID {ruta_existente['ID_Empresa']} → ID {id_empresa}")
                
                if not hubo_cambios:
                    flash("ℹ No se realizaron cambios en la ruta", "info")
                    return redirect(url_for('admin.admin_rutas'))
                
                # Actualizar ruta en la base de datos - ACTUALIZADO (sin hora_inicio y hora_fin)
                cursor.execute("""
                    UPDATE rutas 
                    SET 
                        Nombre_Ruta = %s,
                        Descripcion = %s,
                        ID_Empresa = %s
                    WHERE ID_Ruta = %s
                """, (nombre_ruta, descripcion or None, id_empresa, id_ruta))
                
                print(f"DEBUG: Ruta {id_ruta} actualizada exitosamente")
                print(f"DEBUG: Cambios realizados: {cambios_detalle}")
                
                # Registrar en bitácora
                if cambios_detalle:
                    cambios_texto = " | ".join(cambios_detalle)
                    print(f"BITACORA: Ruta {id_ruta} modificada - {cambios_texto}")
                
                flash("✅ Ruta actualizada exitosamente", "success")
                return redirect(url_for('admin.admin_rutas'))
    
    except Exception as e:
        print(f"ERROR en editar_ruta (ID: {id_ruta}): {str(e)}")
        
        flash(f"❌ Error al procesar la ruta: {str(e)}", "danger")
        
        # Si es POST, intentar redirigir de nuevo al formulario con datos básicos
        if request.method == 'POST':
            try:
                # Intentar obtener datos básicos para mostrar el formulario
                with get_db_cursor() as cursor2:
                    cursor2.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
                    empresas = cursor2.fetchall()
                    
                    cursor2.execute("""
                        SELECT 
                            r.ID_Ruta,
                            r.Nombre_Ruta,
                            r.Descripcion,
                            r.Estado,
                            r.ID_Empresa,
                            e.Nombre_Empresa
                        FROM rutas r 
                        LEFT JOIN empresa e ON r.ID_Empresa = e.ID_Empresa
                        WHERE r.ID_Ruta = %s
                    """, (id_ruta,))
                    ruta = cursor2.fetchone()
                    
                    if ruta:
                        return render_template('admin/catalog/rutas/editar_ruta.html', 
                                             ruta=ruta, 
                                             empresas=empresas)
            except Exception as e2:
                print(f"ERROR secundario al recuperar datos: {str(e2)}")
        
        return redirect(url_for('admin.admin_rutas'))

@admin_bp.route('/admin/rutas/cambiar-estado/<int:id_ruta>', methods=['POST'])
@admin_required
@bitacora_decorator("CAMBIAR-ESTADO-RUTA")
def cambiar_estado_ruta(id_ruta):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Obtener estado actual
            cursor.execute("SELECT Estado, Nombre_Ruta FROM rutas WHERE ID_Ruta = %s", (id_ruta,))
            resultado = cursor.fetchone()
            
            if not resultado:
                flash("La ruta no existe", "danger")
                return redirect(url_for('admin.admin_rutas'))
            
            estado_actual = resultado['Estado']
            nombre_ruta = resultado['Nombre_Ruta']
            nuevo_estado = 'Inactiva' if estado_actual == 'Activa' else 'Activa'
            
            # Actualizar estado
            cursor.execute("""
                UPDATE rutas 
                SET Estado = %s
                WHERE ID_Ruta = %s
            """, (nuevo_estado, id_ruta))
            
            print(f"DEBUG: Ruta {id_ruta} '{nombre_ruta}' cambiada de '{estado_actual}' a '{nuevo_estado}'")
        
        estado_texto = "desactivada" if nuevo_estado == 'Inactiva' else "activada"
        flash(f"✅ Ruta '{nombre_ruta}' {estado_texto} exitosamente", "success")
        return redirect(url_for('admin.admin_rutas'))
        
    except Exception as e:
        print(f"ERROR en cambiar_estado_ruta: {str(e)}")
        flash(f"Error al cambiar estado de ruta: {str(e)}", "danger")
        return redirect(url_for('admin.admin_rutas'))

@admin_bp.route('/admin/rutas/eliminar', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR-RUTA")
def eliminar_ruta(): 
    try:
        # Obtener ID del formulario
        id_ruta = request.form.get('id_ruta')
        
        # Validar que se recibió el ID
        if not id_ruta:
            flash("ID de ruta no especificado", "danger")
            return redirect(url_for('admin.admin_rutas'))
        
        # Convertir a entero
        id_ruta = int(id_ruta)
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la ruta existe
            cursor.execute("SELECT Nombre_Ruta FROM rutas WHERE ID_Ruta = %s", (id_ruta,))
            ruta = cursor.fetchone()
            
            if not ruta:
                flash("La ruta no existe", "danger")
                return redirect(url_for('admin.admin_rutas'))
            
            nombre_ruta = ruta['Nombre_Ruta']
            
            # Eliminar ruta
            cursor.execute("DELETE FROM rutas WHERE ID_Ruta = %s", (id_ruta,))
            
            print(f"DEBUG: Ruta {id_ruta} '{nombre_ruta}' eliminada")
        
        flash(f"✅ Ruta '{nombre_ruta}' eliminada exitosamente", "success")
        return redirect(url_for('admin.admin_rutas'))
        
    except Exception as e:
        print(f"ERROR en eliminar_ruta: {str(e)}")
        flash(f"Error al eliminar ruta: {str(e)}", "danger")
        return redirect(url_for('admin.admin_rutas')) 

@admin_bp.route('/admin/bodega', methods=['GET'])
@admin_required
@bitacora_decorator("BODEGA")
def admin_bodega():
    try:
        with get_db_cursor() as cursor:
            # Obtener bodegas con información de empresa
            cursor.execute("""
                SELECT b.*, e.Nombre_Empresa 
                FROM bodegas b
                INNER JOIN Empresa e ON b.ID_Empresa = e.ID_Empresa
                ORDER BY b.ID_Bodega DESC
            """)
            bodegas = cursor.fetchall()
            
            # Obtener lista de empresas para el modal de creación
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/bodega.html', 
                                 bodegas=bodegas,
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodegas: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/bodega/crear', methods=['POST'])
@admin_required
@bitacora_decorator("BODEGA-CREAR")
def admin_bodega_crear():
    try:
        nombre = request.form.get('nombre', '').strip()
        ubicacion = request.form.get('ubicacion', '').strip()
        id_empresa = request.form.get('id_empresa')

        if not nombre:
            flash("El nombre de la bodega es requerido", "danger")
            return redirect(url_for('admin.admin_bodega'))
        
        if not id_empresa:
            flash("La empresa es requerida", "danger")
            return redirect(url_for('admin.admin_bodega'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO bodegas (Nombre, Ubicacion, ID_Empresa) 
                VALUES (%s, %s, %s)
            """, (nombre, ubicacion, id_empresa))

        flash("Bodega creada exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear bodega: {str(e)}", "danger")
    return redirect(url_for('admin.admin_bodega'))

@admin_bp.route('/admin/bodega/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("BODEGA_EDITAR")
def admin_editar_bodega(id):
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        ubicacion = request.form.get('ubicacion')
        id_empresa = request.form.get('id_empresa')
        estado = request.form.get('estado', 'activa')
        
        if not nombre:
            flash("El nombre de la bodega es obligatorio", "danger")
            return redirect(url_for('admin.admin_editar_bodega', id=id))
        
        if not id_empresa:
            flash("La empresa es obligatoria", "danger")
            return redirect(url_for('admin.admin_editar_bodega', id=id))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE bodegas SET Nombre = %s, Ubicacion = %s, Estado = %s, ID_Empresa = %s WHERE ID_Bodega = %s",
                    (nombre, ubicacion, estado, id_empresa, id)
                )
                flash("Bodega actualizada exitosamente", "success")
                return redirect(url_for('admin.admin.admin_bodega'))
        except Exception as e:
            flash(f"Error al actualizar bodega: {str(e)}", "danger")
            return redirect(url_for('admin.admin_editar_bodega', id=id))
    
    # GET - Cargar datos de la bodega y empresas
    try:
        with get_db_cursor() as cursor:
            # Obtener datos de la bodega
            cursor.execute("SELECT * FROM bodegas WHERE ID_Bodega = %s", (id,))
            bodega = cursor.fetchone()
            
            if not bodega:
                flash("Bodega no encontrada", "danger")
                return redirect(url_for('admin.admin_bodega'))
            
            # Obtener lista de empresas para el dropdown
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/editar_bodega.html', 
                                 bodega=bodega, 
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodega: {str(e)}", "danger")
        return redirect(url_for('admin.admin_bodega'))

#CATALOGO PRODUCTOS - BODEGA
@admin_bp.route('/admin/bodega/productos', methods=['GET'])
@admin_required
@bitacora_decorator("PRODUCTOS")
def admin_productos():
    try:
        # Obtener el parámetro de filtro de categoría de la URL
        categoria_filtro = request.args.get('categoria', 'todos')
        
        with get_db_cursor() as cursor:
            # Consulta base para productos con filtro opcional por categoría
            query = """
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    p.Unidad_Medida,
                    um.Descripcion as Nombre_Unidad,
                    um.Abreviatura,
                    COALESCE(SUM(ib.Existencias), 0) as Existencias,
                    p.Estado,
                    p.ID_Categoria,
                    cp.Descripcion as Nombre_Categoria,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    p.Precio_Ruta,
                    p.ID_Empresa,
                    e.Nombre_Empresa,
                    p.Fecha_Creacion,
                    p.Usuario_Creador,
                    u.NombreUsuario as Usuario_Creador_Nombre,
                    p.Stock_Minimo,
                    (SELECT COUNT(*) FROM inventario_bodega ib2 WHERE ib2.ID_Producto = p.ID_Producto) as bodegas_Con_Stock
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE p.Estado = 'activo'
            """
            
            # Parámetros para la consulta
            params = []
            
            # Agregar filtro por categoría si no es 'todos'
            if categoria_filtro != 'todos':
                query += " AND p.ID_Categoria = %s"
                params.append(categoria_filtro)
            
            query += """
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, p.Unidad_Medida, 
                         um.Descripcion, um.Abreviatura, p.Estado, p.ID_Categoria,
                         cp.Descripcion, p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,
                         p.ID_Empresa, e.Nombre_Empresa, p.Fecha_Creacion, p.Usuario_Creador, 
                         u.NombreUsuario, p.Stock_Minimo
                ORDER BY p.ID_Producto DESC
            """
            
            cursor.execute(query, params)
            productos = cursor.fetchall()
            
            # Convertir productos a diccionario si es necesario
            productos_list = []
            for producto in productos:
                if isinstance(producto, dict):
                    productos_list.append(producto)
                else:
                    productos_list.append({
                        'ID_Producto': producto[0],
                        'COD_Producto': producto[1],
                        'Descripcion': producto[2],
                        'Unidad_Medida': producto[3],
                        'Nombre_Unidad': producto[4],
                        'Abreviatura': producto[5],
                        'Existencias': producto[6],
                        'Estado': producto[7],
                        'ID_Categoria': producto[8],
                        'Nombre_Categoria': producto[9],
                        'Precio_Mercado': producto[10],
                        'Precio_Mayorista': producto[11],
                        'Precio_Ruta': producto[12],
                        'ID_Empresa': producto[13],
                        'Nombre_Empresa': producto[14],
                        'Fecha_Creacion': producto[15],
                        'Usuario_Creador': producto[16],
                        'Usuario_Creador_Nombre': producto[17],
                        'Stock_Minimo': producto[18],
                        'bodegas_Con_Stock': producto[19]
                    })
            
            # Obtener todas las categorías para el filtro
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
            categorias = cursor.fetchall()
            
            # Resto de las consultas...
            cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM unidades_medida")
            unidades = cursor.fetchall()
            
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
            cursor.execute("""
                SELECT b.ID_Bodega, b.Nombre, b.ID_Empresa, e.Nombre_Empresa 
                FROM bodegas b 
                JOIN empresa e ON b.ID_Empresa = e.ID_Empresa 
                WHERE b.Estado = 'activa'
                ORDER BY e.Nombre_Empresa, b.Nombre
            """)
            bodegas = cursor.fetchall()
            
            return render_template('admin/bodega/producto/productos.html', 
                                 productos=productos_list,
                                 categorias=categorias,
                                 categorias_filtro=categorias,  # Para el filtro
                                 categoria_seleccionada=categoria_filtro,
                                 unidades=unidades,
                                 empresas=empresas,
                                 bodegas=bodegas)
    except Exception as e:
        flash(f'Error al cargar productos: {str(e)}', 'error')
        return render_template('admin/bodega/producto/productos.html',
                                productos=[], 
                                categorias=[], 
                                categorias_filtro=[],
                                categoria_seleccionada='todos',
                                unidades=[], 
                                empresas=[],
                                bodegas=[])

@admin_bp.route('/admin/bodega/productos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PRODUCTO")
def admin_crear_producto():
    try:
        # Obtener datos del formulario - Actualizado con nuevos precios
        cod_producto = request.form.get('COD_Producto')
        descripcion = request.form.get('Descripcion')
        id_unidad_medida = request.form.get('Unidad_Medida')
        id_categoria = request.form.get('ID_Categoria')
        precio_mercado = request.form.get('Precio_Mercado', 0)      # Nuevo
        precio_mayorista = request.form.get('Precio_Mayorista', 0)  # Nuevo
        precio_ruta = request.form.get('Precio_Ruta', 0)            # Nuevo
        id_empresa = request.form.get('ID_Empresa', 1)
        stock_minimo = request.form.get('Stock_Minimo', 5)
        cantidad_inicial = request.form.get('Cantidad_Inicial')
        id_bodega = request.form.get('ID_Bodega')
        estado = request.form.get('Estado', 'activo')
        usuario_creador = session.get('id_usuario', 1)

        print(f"DEBUG: Datos recibidos - Descripcion: {descripcion}, Bodega: {id_bodega}, Empresa: {id_empresa}")

        # Validaciones básicas
        if not all([descripcion, id_unidad_medida, id_categoria]):
            flash('Descripción, unidad de medida y categoría son campos obligatorios', 'error')
            return redirect(url_for('admin.admin_productos'))

        if not id_bodega:
            flash('Debe seleccionar una bodega para el inventario inicial', 'error')
            return redirect(url_for('admin.admin_productos'))

        # Validar y convertir valores
        try:
            cantidad_inicial = float(cantidad_inicial) if cantidad_inicial else 0
        except (ValueError, TypeError):
            cantidad_inicial = 0
            
        # Convertir precios
        try:
            precio_mercado = float(precio_mercado) if precio_mercado else 0.0
        except (ValueError, TypeError):
            precio_mercado = 0.0
            
        try:
            precio_mayorista = float(precio_mayorista) if precio_mayorista else 0.0
        except (ValueError, TypeError):
            precio_mayorista = 0.0
            
        try:
            precio_ruta = float(precio_ruta) if precio_ruta else 0.0
        except (ValueError, TypeError):
            precio_ruta = 0.0
            
        try:
            stock_minimo = float(stock_minimo) if stock_minimo else 5.0
        except (ValueError, TypeError):
            stock_minimo = 5.0

        try:
            id_unidad_medida = int(id_unidad_medida)
        except (ValueError, TypeError):
            flash('Unidad de medida no válida', 'error')
            return redirect(url_for('admin.admin_productos'))
            
        try:
            id_categoria = int(id_categoria)
        except (ValueError, TypeError):
            flash('Categoría no válida', 'error')
            return redirect(url_for('admin.admin_productos'))
            
        try:
            id_empresa = int(id_empresa)
        except (ValueError, TypeError):
            id_empresa = 1
            
        try:
            id_bodega = int(id_bodega)
        except (ValueError, TypeError):
            flash('Bodega no válida', 'error')
            return redirect(url_for('admin.admin_productos'))

        with get_db_cursor(commit=True) as cursor:
            print(f"DEBUG: Verificando bodega ID: {id_bodega}")
            
            # Verificar que la bodega existe y está activa
            cursor.execute("""
                SELECT ID_Bodega, ID_Empresa FROM bodegas 
                WHERE ID_Bodega = %s AND Estado = 'activa'
            """, (id_bodega,))
            
            bodega_data = cursor.fetchone()
            print(f"DEBUG: Datos bodega obtenidos: {bodega_data}")
            
            if not bodega_data:
                flash('La bodega seleccionada no es válida', 'error')
                return redirect(url_for('admin.admin_productos'))
            
            # Manejar tanto diccionarios como tuplas
            if isinstance(bodega_data, dict):
                bodega_id = bodega_data.get('ID_Bodega')
                bodega_empresa_id = bodega_data.get('ID_Empresa')
            else:
                bodega_id = bodega_data[0]
                bodega_empresa_id = bodega_data[1]
            
            print(f"DEBUG: Bodega ID: {bodega_id}, Empresa Bodega: {bodega_empresa_id}, Empresa Form: {id_empresa}")
            
            # Verificar que la bodega pertenece a la empresa del producto
            if bodega_empresa_id != id_empresa:
                flash('La bodega seleccionada no pertenece a la empresa del producto', 'error')
                return redirect(url_for('admin.admin_productos'))

            # Verificar si el código de producto ya existe
            if cod_producto:
                cursor.execute("SELECT ID_Producto FROM productos WHERE COD_Producto = %s", (cod_producto,))
                if cursor.fetchone():
                    flash('El código de producto ya existe', 'error')
                    return redirect(url_for('admin.admin_productos'))
            else:
                # Generar código automático si no se proporciona
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(COD_Producto AS UNSIGNED)), 0) + 1 
                    FROM productos 
                    WHERE COD_Producto REGEXP '^[0-9]+$'
                """)
                result = cursor.fetchone()
                
                if isinstance(result, dict):
                    max_cod = result.get(list(result.keys())[0])
                else:
                    max_cod = result[0] if result else 0
                    
                cod_producto = str(max_cod + 1) if max_cod else "1"
                print(f"DEBUG: Código generado: {cod_producto}")

            # Insertar nuevo producto - Actualizado con los nuevos campos de precio
            print(f"DEBUG: Insertando producto...")
            cursor.execute("""
                INSERT INTO Productos (
                    COD_Producto, Descripcion, Unidad_Medida, Estado,
                    ID_Categoria, Precio_Mercado, Precio_Mayorista, Precio_Ruta, 
                    ID_Empresa, Usuario_Creador, Stock_Minimo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cod_producto, descripcion, id_unidad_medida, estado,
                id_categoria, precio_mercado, precio_mayorista, precio_ruta, 
                id_empresa, usuario_creador, stock_minimo
            ))

            producto_id = cursor.lastrowid
            print(f"DEBUG: Producto creado con ID: {producto_id}")

            # Insertar en inventario_bodega con la cantidad inicial
            cursor.execute("""
                INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            """, (id_bodega, producto_id, cantidad_inicial))

        flash(f'Producto "{descripcion}" creado exitosamente con {cantidad_inicial} unidades en la bodega seleccionada', 'success')
        
    except Exception as e:
        print(f"ERROR DETALLADO: {str(e)}")
        print(traceback.format_exc())
        flash(f'Error al crear producto: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_productos'))

@admin_bp.route('/admin/bodegas/por-empresa/<int:id_empresa>')
@admin_required
def obtener_bodegas_por_empresa(id_empresa):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 'activa'
                ORDER BY Nombre
            """, (id_empresa,))
            bodegas = cursor.fetchall()
        
        return jsonify({
            'bodegas': bodegas
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/bodega/productos/editar/<int:id_producto>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_PRODUCTO")
def admin_editar_producto(id_producto):
    try:
        if request.method == 'POST':
            # ========== PROCESAR FORMULARIO POST ==========
            # Obtener datos del formulario - Actualizado con nuevos precios
            cod_producto = request.form.get('COD_Producto', '').strip()
            descripcion = request.form.get('Descripcion', '').strip()
            unidad_medida = request.form.get('Unidad_Medida')
            id_categoria = request.form.get('ID_Categoria')
            precio_mercado = request.form.get('Precio_Mercado', 0)      # Nuevo
            precio_mayorista = request.form.get('Precio_Mayorista', 0)  # Nuevo
            precio_ruta = request.form.get('Precio_Ruta', 0)            # Nuevo
            id_empresa = request.form.get('ID_Empresa')
            stock_minimo = request.form.get('Stock_Minimo', 5)
            estado = request.form.get('Estado', 'activo')

            # Validaciones
            if not descripcion:
                flash('La descripción es obligatoria', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            if not unidad_medida or not id_categoria or not id_empresa:
                flash('Unidad de medida, categoría y empresa son campos obligatorios', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            # Validar estado
            if estado not in ['activo', 'inactivo']:
                estado = 'activo'

            # Convertir valores numéricos
            try:
                precio_mercado = float(precio_mercado) if precio_mercado else 0
                precio_mayorista = float(precio_mayorista) if precio_mayorista else 0
                precio_ruta = float(precio_ruta) if precio_ruta else 0
                stock_minimo = float(stock_minimo) if stock_minimo else 5
                
                # Validar valores positivos
                if precio_mercado < 0 or precio_mayorista < 0 or precio_ruta < 0:
                    flash('Los precios no pueden ser negativos', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                    
                if stock_minimo < 0:
                    flash('El stock mínimo no puede ser negativo', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))
                    
            except (ValueError, TypeError):
                flash('Error en los valores numéricos', 'error')
                return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            with get_db_cursor(commit=True) as cursor:
                # Verificar si el código de producto ya existe en otro producto
                if cod_producto:
                    cursor.execute("""
                        SELECT ID_Producto FROM productos 
                        WHERE COD_Producto = %s AND ID_Producto != %s
                    """, (cod_producto, id_producto))
                    if cursor.fetchone():
                        flash('El código de producto ya existe en otro producto', 'error')
                        return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                # Verificar que las referencias existan
                cursor.execute("SELECT ID_Unidad FROM unidades_medida WHERE ID_Unidad = %s", (unidad_medida,))
                if not cursor.fetchone():
                    flash('La unidad de medida seleccionada no existe', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Categoria FROM categorias_producto WHERE ID_Categoria = %s", (id_categoria,))
                if not cursor.fetchone():
                    flash('La categoría seleccionada no existe', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", (id_empresa,))
                if not cursor.fetchone():
                    flash('La empresa seleccionada no existe o está inactiva', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

                # Actualizar producto - Actualizado con nuevos precios
                cursor.execute("""
                    UPDATE productos SET
                        COD_Producto = %s,
                        Descripcion = %s,
                        Unidad_Medida = %s,
                        ID_Categoria = %s,
                        Precio_Mercado = %s,      -- Nuevo
                        Precio_Mayorista = %s,    -- Nuevo
                        Precio_Ruta = %s,          -- Nuevo
                        ID_Empresa = %s,
                        Stock_Minimo = %s,
                        Estado = %s
                    WHERE ID_Producto = %s
                """, (
                    cod_producto or None,
                    descripcion, 
                    unidad_medida, 
                    id_categoria,
                    precio_mercado, 
                    precio_mayorista,
                    precio_ruta,
                    id_empresa, 
                    stock_minimo, 
                    estado,
                    id_producto
                ))

                # Verificar si se actualizó algún registro
                if cursor.rowcount == 0:
                    flash('No se pudo actualizar el producto. Puede que no exista.', 'error')
                    return redirect(url_for('admin.admin_editar_producto', id_producto=id_producto))

            flash('Producto actualizado exitosamente', 'success')
            return redirect(url_for('admin.admin_productos'))

        else:
            # ========== CARGAR FORMULARIO GET ==========
            with get_db_cursor() as cursor:
                # Obtener el producto específico - Actualizado con nuevos precios
                cursor.execute("""
                    SELECT 
                        p.ID_Producto,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida,
                        um.Descripcion as Nombre_Unidad,
                        um.Abreviatura,
                        p.Estado,
                        p.ID_Categoria,
                        cp.Descripcion as Nombre_Categoria,
                        p.Precio_Mercado,      -- Nuevo
                        p.Precio_Mayorista,    -- Nuevo
                        p.Precio_Ruta,          -- Nuevo
                        p.ID_Empresa,
                        e.Nombre_Empresa,
                        p.Fecha_Creacion,
                        p.Usuario_Creador,
                        u.NombreUsuario as Usuario_Creador_Nombre,
                        p.Stock_Minimo,
                        COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales
                    FROM productos p
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                    LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                    LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                    WHERE p.ID_Producto = %s
                    GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, p.Unidad_Medida,
                             um.Descripcion, um.Abreviatura, p.Estado, p.ID_Categoria,
                             cp.Descripcion, p.Precio_Mercado, p.Precio_Mayorista, p.Precio_Ruta,  -- Actualizado
                             p.ID_Empresa, e.Nombre_Empresa, p.Fecha_Creacion, p.Usuario_Creador, 
                             u.NombreUsuario, p.Stock_Minimo
                """, (id_producto,))
                producto = cursor.fetchone()
                
                if not producto:
                    flash('Producto no encontrado', 'error')
                    return redirect(url_for('admin.admin_productos'))
                
                # Convertir a diccionario si es necesario
                if isinstance(producto, dict):
                    producto_data = producto
                else:
                    # Si es tupla, convertir a diccionario - Actualizado
                    producto_data = {
                        'ID_Producto': producto[0],
                        'COD_Producto': producto[1],
                        'Descripcion': producto[2],
                        'Unidad_Medida': producto[3],
                        'Nombre_Unidad': producto[4],
                        'Abreviatura': producto[5],
                        'Estado': producto[6],
                        'ID_Categoria': producto[7],
                        'Nombre_Categoria': producto[8],
                        'Precio_Mercado': producto[9],
                        'Precio_Mayorista': producto[10],
                        'Precio_Ruta': producto[11],
                        'ID_Empresa': producto[12],
                        'Nombre_Empresa': producto[13],
                        'Fecha_Creacion': producto[14],
                        'Usuario_Creador': producto[15],
                        'Usuario_Creador_Nombre': producto[16],
                        'Stock_Minimo': producto[17],
                        'Existencias_Totales': producto[18] or 0
                    }
                
                print(f"DEBUG - Estado del producto: {producto_data.get('Estado')}")
                print(f"DEBUG - Precios: Mercado={producto_data.get('Precio_Mercado')}, Mayorista={producto_data.get('Precio_Mayorista')}, Ruta={producto_data.get('Precio_Ruta')}")
                
                # Obtener datos para los dropdowns
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto")
                categorias = cursor.fetchall()
                
                cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM unidades_medida")
                unidades = cursor.fetchall()
                
                cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
                empresas = cursor.fetchall()
                
                # CONSULTA PARA INVENTARIO POR BODEGA
                cursor.execute("""
                    SELECT 
                        b.ID_Bodega, 
                        b.Nombre as Nombre_Bodega,
                        e.Nombre_Empresa,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM bodegas b
                    JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                    LEFT JOIN inventario_bodega ib ON b.ID_Bodega = ib.ID_Bodega AND ib.ID_Producto = %s
                    WHERE b.Estado = 'activa'
                    ORDER BY e.Nombre_Empresa, b.Nombre
                """, (id_producto,))
                inventario_bodegas = cursor.fetchall()
                
                fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
                
                return render_template('admin/bodega/producto/editar_producto.html', 
                                     producto=producto_data,
                                     categorias=categorias,
                                     unidades=unidades,
                                     empresas=empresas,
                                     inventario_bodegas=inventario_bodegas,
                                     fecha_actual=fecha_actual)
                
    except Exception as e:
        flash(f'Error al procesar producto: {str(e)}', 'error')
        traceback.print_exc()
        return redirect(url_for('admin.admin_productos'))
    
@admin_bp.route('/admin/bodega/productos/activar/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("ACTIVAR_PRODUCTO")
def admin_activar_producto(id_producto):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE Productos 
                SET Estado = 'activo'
                WHERE ID_Producto = %s
            """, (id_producto,))
            
            if cursor.rowcount > 0:
                flash('Producto activado exitosamente', 'success')
            else:
                flash('Producto no encontrado', 'error')
                
    except Exception as e:
        flash(f'Error al activar producto: {str(e)}', 'error')
        
    return redirect(url_for('admin.admin_productos'))

@admin_bp.route('/admin/bodega/productos/desactivar/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("DESACTIVAR_PRODUCTO")
def admin_desactivar_producto(id_producto):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE Productos 
                SET Estado = 'inactivo'
                WHERE ID_Producto = %s
            """, (id_producto,))
            
            if cursor.rowcount > 0:
                flash('Producto desactivado exitosamente', 'success')
            else:
                flash('Producto no encontrado', 'error')
                
    except Exception as e:
        flash(f'Error al desactivar producto: {str(e)}', 'error')
        
    return redirect(url_for('admin.admin_productos'))


@admin_bp.route('/admin/reportes')
@admin_required
def reportes():
    """Panel principal de reportes ejecutivos"""
    return render_template('admin/reportes/reportes.html',
                            now=datetime.now())

@admin_bp.route('/admin/reporte/ventas')
@admin_required
def reporte_ventas():
    """Reporte de ventas con filtros (incluye facturación normal y de ruta)"""
    try:
        fecha_inicio = request.args.get('fecha_inicio', datetime.now().strftime('%Y-%m-01'))
        fecha_fin = request.args.get('fecha_fin', datetime.now().strftime('%Y-%m-%d'))
        tipo_venta = request.args.get('tipo_venta', 'todos')
        vendedor_id = request.args.get('vendedor_id', '')
        formato = request.args.get('formato', 'html')
        
        with get_db_cursor() as cursor:
            # Query principal de ventas (UNION de facturación normal + facturación ruta)
            query = """
                SELECT 
                    Fecha,
                    Tipo_Venta,
                    Vendedor,
                    Cliente,
                    Factura_Numero,
                    Items,
                    Cantidad_Total,
                    Total_Venta,
                    Origen
                FROM (
                    -- FACTURACIÓN NORMAL
                    SELECT 
                        DATE(fac.Fecha_Creacion) AS Fecha,
                        CASE 
                            WHEN fac.Credito_Contado = 0 THEN 'CONTADO' 
                            WHEN fac.Credito_Contado = 1 THEN 'CREDITO'
                            ELSE 'NO DEFINIDO'
                        END AS Tipo_Venta,
                        u.NombreUsuario AS Vendedor,
                        c.Nombre AS Cliente,
                        CAST(fac.ID_Factura AS CHAR) AS Factura_Numero,
                        COUNT(df.ID_Detalle) AS Items,
                        SUM(df.Cantidad) AS Cantidad_Total,
                        SUM(df.Total) AS Total_Venta,
                        'NORMAL' AS Origen
                    FROM facturacion fac
                    INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                    INNER JOIN clientes c ON fac.IDCliente = c.ID_Cliente
                    INNER JOIN usuarios u ON fac.ID_Usuario_Creacion = u.ID_Usuario
                    WHERE DATE(fac.Fecha_Creacion) BETWEEN %s AND %s
                      AND fac.Estado = 'Activa'
                    GROUP BY fac.ID_Factura, fac.Fecha_Creacion, fac.Credito_Contado, u.NombreUsuario, c.Nombre
                    
                    UNION ALL
                    
                    -- FACTURACIÓN DE RUTA
                    SELECT 
                        DATE(fr.Fecha_Creacion) AS Fecha,
                        CASE 
                            WHEN fr.Credito_Contado = 1 THEN 'CONTADO' 
                            WHEN fr.Credito_Contado = 2 THEN 'CREDITO'
                            ELSE 'NO DEFINIDO'
                        END AS Tipo_Venta,
                        u.NombreUsuario AS Vendedor,
                        c.Nombre AS Cliente,
                        CONCAT('R-', fr.ID_FacturaRuta) AS Factura_Numero,
                        COUNT(dfr.ID_DetalleRuta) AS Items,
                        SUM(dfr.Cantidad) AS Cantidad_Total,
                        SUM(dfr.Total) AS Total_Venta,
                        'RUTA' AS Origen
                    FROM facturacion_ruta fr
                    INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
                      AND fr.Estado = 'Activa'
                    GROUP BY fr.ID_FacturaRuta, fr.Fecha_Creacion, fr.Credito_Contado, u.NombreUsuario, c.Nombre
                ) AS todas_ventas
                WHERE 1=1
            """
            
            params = [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin]
            
            # Filtro por tipo de venta
            if tipo_venta != 'todos':
                query += " AND Tipo_Venta = %s"
                params.append(tipo_venta.upper())
            
            # Filtro por vendedor
            if vendedor_id:
                query += " AND Vendedor IN (SELECT NombreUsuario FROM usuarios WHERE ID_Usuario = %s)"
                params.append(vendedor_id)
            
            query += " ORDER BY Fecha DESC, Origen"
            
            cursor.execute(query, params)
            ventas = cursor.fetchall()
            
            # Resumen general (incluye ambas fuentes)
            cursor.execute("""
                SELECT 
                    COUNT(*) AS Total_Facturas,
                    COUNT(DISTINCT Cliente) AS Clientes_Atendidos,
                    COALESCE(SUM(Total_Venta), 0) AS Monto_Total,
                    COALESCE(AVG(Total_Venta), 0) AS Ticket_Promedio
                FROM (
                    -- Facturación normal
                    SELECT 
                        c.Nombre AS Cliente,
                        SUM(df.Total) AS Total_Venta
                    FROM facturacion fac
                    INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                    INNER JOIN clientes c ON fac.IDCliente = c.ID_Cliente
                    WHERE DATE(fac.Fecha_Creacion) BETWEEN %s AND %s
                      AND fac.Estado = 'Activa'
                    GROUP BY fac.ID_Factura, c.Nombre
                    
                    UNION ALL
                    
                    -- Facturación de ruta
                    SELECT 
                        c.Nombre AS Cliente,
                        SUM(dfr.Total) AS Total_Venta
                    FROM facturacion_ruta fr
                    INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    WHERE DATE(fr.Fecha_Creacion) BETWEEN %s AND %s
                      AND fr.Estado = 'Activa'
                    GROUP BY fr.ID_FacturaRuta, c.Nombre
                ) AS resumen
            """, [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin])
            resumen = cursor.fetchone()
            
            # Resumen por tipo de origen (normal vs ruta)
            cursor.execute("""
                SELECT 
                    Origen,
                    COUNT(*) AS Cantidad,
                    COALESCE(SUM(Total_Venta), 0) AS Total
                FROM (
                    SELECT 'NORMAL' AS Origen, SUM(df.Total) AS Total_Venta
                    FROM facturacion fac
                    INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                    WHERE DATE(fac.Fecha_Creacion) BETWEEN %s AND %s 
                      AND fac.Estado = 'Activa'
                    GROUP BY fac.ID_Factura
                    
                    UNION ALL
                    
                    SELECT 'RUTA' AS Origen, SUM(dfr.Total) AS Total_Venta
                    FROM facturacion_ruta fr
                    INNER JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE DATE(fr.Fecha_Creacion) BETWEEN %s AND %s 
                      AND fr.Estado = 'Activa'
                    GROUP BY fr.ID_FacturaRuta
                ) AS origen_ventas
                GROUP BY Origen
            """, [fecha_inicio, fecha_fin, fecha_inicio, fecha_fin])
            resumen_origen = cursor.fetchall()
            
            # Vendedores para filtro (de ambas fuentes)
            cursor.execute("""
                SELECT DISTINCT u.ID_Usuario, u.NombreUsuario
                FROM usuarios u
                WHERE u.Estado = 'ACTIVO'
                  AND (
                      u.ID_Usuario IN (SELECT ID_Usuario_Creacion FROM facturacion)
                      OR u.ID_Usuario IN (SELECT ID_Usuario FROM asignacion_vendedores)
                  )
                ORDER BY u.NombreUsuario
            """)
            vendedores = cursor.fetchall()
            
            if formato == 'csv':
                return exportar_csv(ventas, 'reporte_ventas')
            elif formato == 'json':
                return exportar_json(ventas, 'reporte_ventas')
            
            return render_template('admin/reportes/reporte_ventas.html',
                                 ventas=ventas,
                                 resumen=resumen,
                                 resumen_origen=resumen_origen,
                                 vendedores=vendedores,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 tipo_venta=tipo_venta,
                                 vendedor_id=vendedor_id,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/admin/reporte/cartera')
@admin_required
def reporte_cartera():
    """Reporte de cartera y cuentas por cobrar"""
    try:
        fecha_corte = request.args.get('fecha_corte', datetime.now().strftime('%Y-%m-%d'))
        estado = request.args.get('estado', 'todos')
        formato = request.args.get('formato', 'html')
        
        with get_db_cursor() as cursor:
            query = """
                SELECT 
                    c.Nombre AS Cliente,
                    c.Telefono,
                    cxc.Num_Documento,
                    cxc.Fecha,
                    cxc.Fecha_Vencimiento,
                    DATEDIFF(%s, cxc.Fecha_Vencimiento) AS Dias_Vencido,
                    cxc.Monto_Movimiento AS Monto_Original,
                    cxc.Saldo_Pendiente,
                    cxc.Estado AS Estado_Actual,
                    CASE 
                        WHEN cxc.Estado = 'Pagada' THEN 'PAGADA'
                        WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) > 0 THEN 'VENCIDA'
                        ELSE 'PENDIENTE'
                    END AS Estado_Calculado,
                    CASE 
                        WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 0 THEN 'AL DIA'
                        WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 30 THEN '1-30 días'
                        WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 60 THEN '31-60 días'
                        WHEN DATEDIFF(%s, cxc.Fecha_Vencimiento) <= 90 THEN '61-90 días'
                        ELSE '90+ días'
                    END AS Rango_Mora
                FROM cuentas_por_cobrar cxc
                INNER JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
                WHERE cxc.Fecha <= %s
                  AND cxc.Saldo_Pendiente > 0
            """
            params = [fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte]
            
            if estado != 'todos':
                if estado == 'vencida':
                    query += " AND (cxc.Estado = 'Vencida' OR DATEDIFF(%s, cxc.Fecha_Vencimiento) > 0)"
                    params.append(fecha_corte)
                else:
                    query += " AND cxc.Estado = %s"
                    params.append(estado.capitalize())
            
            query += " ORDER BY Dias_Vencido DESC"
            
            cursor.execute(query, params)
            cartera = cursor.fetchall()
            
            # Resumen de cartera
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Dias_Vencido <= 0 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_Al_Dia,
                    COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 1 AND 30 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_30_Dias,
                    COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 31 AND 60 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_60_Dias,
                    COALESCE(SUM(CASE WHEN Dias_Vencido BETWEEN 61 AND 90 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_90_Dias,
                    COALESCE(SUM(CASE WHEN Dias_Vencido > 90 THEN Saldo_Pendiente ELSE 0 END), 0) AS Cartera_90_Mas,
                    COALESCE(SUM(Saldo_Pendiente), 0) AS Total_Cartera
                FROM (
                    SELECT 
                        cxc.Saldo_Pendiente,
                        DATEDIFF(%s, cxc.Fecha_Vencimiento) AS Dias_Vencido
                    FROM cuentas_por_cobrar cxc
                    WHERE cxc.Estado IN ('Pendiente', 'Vencida')
                      AND cxc.Fecha <= %s
                      AND cxc.Saldo_Pendiente > 0
                ) AS calculo
            """, [fecha_corte, fecha_corte])
            resumen = cursor.fetchone()
            
            if formato == 'csv':
                return exportar_csv(cartera, 'reporte_cartera')
            elif formato == 'json':
                return exportar_json(cartera, 'reporte_cartera')
            
            return render_template('admin/reportes/reporte_cartera.html',
                                 cartera=cartera,
                                 resumen=resumen,
                                 fecha_corte=fecha_corte,
                                 estado=estado,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/admin/reporte/inventario')
@admin_required
def reporte_inventario():
    """Reporte de inventario y productos"""
    try:
        categoria_id = request.args.get('categoria_id', '')
        stock_status = request.args.get('stock_status', 'todos')
        formato = request.args.get('formato', 'html')
        
        with get_db_cursor() as cursor:
            query = """
                SELECT 
                    p.COD_Producto AS Codigo,
                    p.Descripcion AS Producto,
                    cp.Descripcion AS Categoria,
                    COALESCE(ib.Existencias, 0) AS Stock_Actual,
                    p.Stock_Minimo,
                    CASE 
                        WHEN COALESCE(ib.Existencias, 0) <= p.Stock_Minimo THEN 'STOCK BAJO'
                        WHEN COALESCE(ib.Existencias, 0) <= p.Stock_Minimo * 2 THEN 'STOCK MINIMO'
                        ELSE 'NORMAL'
                    END AS Estado_Stock,
                    p.Precio_Mercado,
                    p.Precio_Mayorista,
                    COALESCE(SUM(df.Cantidad), 0) AS Vendido_Ultimo_Mes,
                    COALESCE(ib.Existencias, 0) * COALESCE(p.Precio_Mercado, 0) AS Valor_Inventario
                FROM productos p
                INNER JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                LEFT JOIN detalle_facturacion df ON p.ID_Producto = df.ID_Producto
                LEFT JOIN facturacion fac ON df.ID_Factura = fac.ID_Factura 
                    AND fac.Fecha_Creacion >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                    AND fac.Estado = 'Activa'
                WHERE p.Estado = 'activo'
            """
            params = []
            
            if categoria_id:
                query += " AND p.ID_Categoria = %s"
                params.append(categoria_id)
            
            query += " GROUP BY p.ID_Producto, ib.Existencias"
            
            if stock_status == 'critico':
                query += " HAVING Stock_Actual <= Stock_Minimo"
            elif stock_status == 'minimo':
                query += " HAVING Stock_Actual <= Stock_Minimo * 2 AND Stock_Actual > Stock_Minimo"
            elif stock_status == 'normal':
                query += " HAVING Stock_Actual > Stock_Minimo * 2"
            
            query += " ORDER BY Estado_Stock, Stock_Actual ASC"
            
            cursor.execute(query, params)
            inventario = cursor.fetchall()
            
            # Categorías para filtro
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto WHERE Estado = 'Activo'")
            categorias = cursor.fetchall()
            
            # Resumen
            cursor.execute("""
                SELECT 
                    COUNT(*) AS Total_Productos,
                    SUM(CASE WHEN Stock_Actual <= Stock_Minimo THEN 1 ELSE 0 END) AS Stock_Critico,
                    SUM(CASE WHEN Stock_Actual <= 0 THEN 1 ELSE 0 END) AS Stock_Cero,
                    SUM(Stock_Actual * COALESCE(Precio_Mercado, 0)) AS Valor_Inventario
                FROM (
                    SELECT 
                        p.ID_Producto,
                        p.Stock_Minimo,
                        COALESCE(ib.Existencias, 0) AS Stock_Actual,
                        p.Precio_Mercado
                    FROM productos p
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                    WHERE p.Estado = 'activo'
                ) AS calculo
            """)
            resumen = cursor.fetchone()
            
            if formato == 'csv':
                return exportar_csv(inventario, 'reporte_inventario')
            elif formato == 'json':
                return exportar_json(inventario, 'reporte_inventario')
            
            return render_template('admin/reportes/reporte_inventario.html',
                                 inventario=inventario,
                                 resumen=resumen,
                                 categorias=categorias,
                                 categoria_id=categoria_id,
                                 stock_status=stock_status,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/admin/reporte/estado_resultados')
@admin_required
def reporte_estado_resultados():
    """Estado de resultados financiero"""
    try:
        mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        formato = request.args.get('formato', 'html')
        
        año = int(mes.split('-')[0])
        mes_num = int(mes.split('-')[1])
        
        with get_db_cursor() as cursor:
            # Ingresos por ventas (solo contado)
            cursor.execute("""
                SELECT 
                    'INGRESOS' AS Tipo,
                    'Ventas de Contado' AS Concepto,
                    COALESCE(SUM(df.Total), 0) AS Monto
                FROM facturacion fac
                INNER JOIN detalle_facturacion df ON fac.ID_Factura = df.ID_Factura
                WHERE MONTH(fac.Fecha_Creacion) = %s 
                  AND YEAR(fac.Fecha_Creacion) = %s
                  AND fac.Estado = 'Activa'
                  AND fac.Credito_Contado = 1
            """, [mes_num, año])
            ingresos_ventas = cursor.fetchall()
            
            # Ingresos por cobros de cartera
            cursor.execute("""
                SELECT 
                    'INGRESOS' AS Tipo,
                    'Cobros de Cartera' AS Concepto,
                    COALESCE(SUM(ad.Monto_Aplicado), 0) AS Monto
                FROM abonos_detalle ad
                WHERE MONTH(ad.Fecha) = %s AND YEAR(ad.Fecha) = %s
            """, [mes_num, año])
            ingresos_abonos = cursor.fetchall()
            
            # Gastos generales
            cursor.execute("""
                SELECT 
                    'GASTOS' AS Tipo,
                    tg.Nombre AS Concepto,
                    COALESCE(SUM(gg.Monto), 0) AS Monto
                FROM gastos_generales gg
                INNER JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                WHERE MONTH(gg.Fecha) = %s AND YEAR(gg.Fecha) = %s
                  AND gg.Estado = 'Activo'
                GROUP BY tg.ID_Tipo_Gasto
                ORDER BY Monto DESC
            """, [mes_num, año])
            gastos = cursor.fetchall()
            
            # Consolidar resultados
            resultados = []
            total_ingresos = 0
            total_gastos = 0
            
            for ingreso in ingresos_ventas:
                resultados.append(ingreso)
                total_ingresos += float(ingreso['Monto'])
            
            for ingreso in ingresos_abonos:
                resultados.append(ingreso)
                total_ingresos += float(ingreso['Monto'])
            
            for gasto in gastos:
                resultados.append(gasto)
                total_gastos += float(gasto['Monto'])
            
            utilidad = total_ingresos - total_gastos
            margen = (utilidad / total_ingresos * 100) if total_ingresos > 0 else 0
            
            # ============================================
            # MESES DISPONIBLES - VERSIÓN CORREGIDA
            # ============================================
            cursor.execute("""
                SELECT DISTINCT 
                    CONCAT(YEAR(f.Fecha_Creacion), '-', LPAD(MONTH(f.Fecha_Creacion), 2, '0')) AS mes
                FROM facturacion f
                WHERE f.Estado = 'Activa'
                ORDER BY CONCAT(YEAR(f.Fecha_Creacion), '-', LPAD(MONTH(f.Fecha_Creacion), 2, '0')) DESC
                LIMIT 12
            """)
            meses_disponibles = cursor.fetchall()
            
            if formato == 'csv':
                return exportar_csv(resultados, 'estado_resultados')
            elif formato == 'json':
                return exportar_json(resultados, 'estado_resultados')
            
            return render_template('admin/reportes/reporte_estado_resultados.html',
                                 resultados=resultados,
                                 total_ingresos=total_ingresos,
                                 total_gastos=total_gastos,
                                 utilidad=utilidad,
                                 margen=margen,
                                 mes_actual=mes,
                                 meses_disponibles=meses_disponibles,
                                 now=datetime.now())
    except Exception as e:
        flash(f"Error al generar reporte: {e}", "danger")
        return redirect(url_for('admin.reportes'))
