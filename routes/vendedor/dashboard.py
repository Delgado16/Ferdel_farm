# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date, time
import traceback
from flask import json, jsonify, render_template, flash, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required
from . import vendedor_bp
from .utils import convertir_hora_db, procesar_asignacion, procesar_lista_asignaciones

@vendedor_bp.route('/vendedor/dashboard')
@login_required
def vendedor_dashboard():
    # Obtener el ID del usuario logueado (asumiendo que está en session)
    user_id = current_user.id
    empresa_id = session.get('empresa_id', 1)
    
    if not user_id:
        flash('Usuario no autenticado', 'danger')
        return redirect(url_for('auth.login'))
    
    with get_db_cursor() as cursor:
        # 1. Obtener asignaciones activas del vendedor
        cursor.execute("""
            SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta, av.Fecha_Asignacion,
                   av.Estado, av.Hora_Inicio, av.Hora_Fin
            FROM asignacion_vendedores av
            JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
            WHERE av.ID_Usuario = %s 
              AND av.Estado = 'Activa'
            ORDER BY av.Fecha_Asignacion DESC
            LIMIT 1
        """, (user_id,))
        asignacion_activa = cursor.fetchone()
        
        # ID de asignación actual (si existe)
        asignacion_id = asignacion_activa['ID_Asignacion'] if asignacion_activa else None
        
        # 2. Tarjeta: Ventas de Contado (Hoy) - EFECTIVO QUE ENTRA
        cursor.execute("""
            SELECT COALESCE(SUM(dfr.Total), 0) AS Total_Ventas_Contado_Hoy
            FROM facturacion_ruta fr
            JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND DATE(fr.Fecha) = CURDATE()
              AND fr.Estado = 'Activa'
              AND fr.Credito_Contado = 1
        """, (user_id,))
        result = cursor.fetchone()
        total_ventas_contado_hoy = result['Total_Ventas_Contado_Hoy'] if result else 0
        
        # 3. Tarjeta: Ventas a Crédito (Hoy) - FIADO
        cursor.execute("""
            SELECT COALESCE(SUM(dfr.Total), 0) AS Total_Ventas_Credito_Hoy
            FROM facturacion_ruta fr
            JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND DATE(fr.Fecha) = CURDATE()
              AND fr.Estado = 'Activa'
              AND fr.Credito_Contado = 2
        """, (user_id,))
        result = cursor.fetchone()
        total_ventas_credito_hoy = result['Total_Ventas_Credito_Hoy'] if result else 0
        
        # 4. Tarjeta: Total Ventas (Contado + Crédito)
        total_ventas_hoy = total_ventas_contado_hoy + total_ventas_credito_hoy
        
        # 5. Tarjeta: Cobros Realizados (Hoy) - ABONOS A CRÉDITO
        cursor.execute("""
            SELECT COALESCE(SUM(ad.Monto_Aplicado), 0) AS Total_Cobrado_Hoy
            FROM abonos_detalle ad
            WHERE ad.ID_Usuario = %s
              AND DATE(ad.Fecha) = CURDATE()
        """, (user_id,))
        result = cursor.fetchone()
        total_cobrado_hoy = result['Total_Cobrado_Hoy'] if result else 0
        
        # 6. Tarjeta: Saldo de Caja (Actual)
        saldo_caja = 0
        if asignacion_id:
            cursor.execute("""
                SELECT Saldo_Acumulado
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s
                  AND ID_Asignacion = %s
                  AND Estado = 'ACTIVO'
                ORDER BY Fecha DESC, ID_Movimiento DESC
                LIMIT 1
            """, (user_id, asignacion_id))
            resultado_saldo = cursor.fetchone()
            if resultado_saldo:
                saldo_caja = resultado_saldo['Saldo_Acumulado']
        
        # 7. Tarjeta: Cobros por Vencer (Próximos 7 días)
        cursor.execute("""
            SELECT COUNT(*) AS Cobros_Proximos,
                   COALESCE(SUM(cxc.Saldo_Pendiente), 0) AS Monto_Proximo
            FROM cuentas_por_cobrar cxc
            JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE c.ID_Ruta IN (
                SELECT ID_Ruta FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            )
              AND cxc.Estado = 'Pendiente'
              AND cxc.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """, (user_id,))
        result = cursor.fetchone()
        cobros_proximos = result['Cobros_Proximos'] if result else 0
        monto_proximo = result['Monto_Proximo'] if result else 0
        
        # 8. Gráfico: Ventas Diarias (Últimos 30 días)
        cursor.execute("""
            SELECT 
                DATE(fr.Fecha) as Dia,
                COALESCE(SUM(CASE WHEN fr.Credito_Contado = 1 THEN dfr.Total ELSE 0 END), 0) as Ventas_Contado,
                COALESCE(SUM(CASE WHEN fr.Credito_Contado = 2 THEN dfr.Total ELSE 0 END), 0) as Ventas_Credito,
                COALESCE(SUM(dfr.Total), 0) as Total_Ventas
            FROM facturacion_ruta fr
            LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND fr.Fecha BETWEEN DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND CURDATE()
              AND fr.Estado = 'Activa'
            GROUP BY DATE(fr.Fecha)
            ORDER BY Dia
        """, (user_id,))
        ventas_diarias = cursor.fetchall()
        
        # Preparar datos para gráfico
        ventas_fechas = [v['Dia'].strftime('%Y-%m-%d') for v in ventas_diarias] if ventas_diarias else []
        ventas_contado = [float(v['Ventas_Contado']) for v in ventas_diarias] if ventas_diarias else []
        ventas_credito = [float(v['Ventas_Credito']) for v in ventas_diarias] if ventas_diarias else []
        
        # 9. Gráfico: Top 5 Productos Más Vendidos
        cursor.execute("""
            SELECT p.Descripcion as Producto, SUM(dfr.Cantidad) as Cantidad_Total,
                   SUM(dfr.Total) as Total_Vendido
            FROM detalle_facturacion_ruta dfr
            JOIN facturacion_ruta fr ON dfr.ID_FacturaRuta = fr.ID_FacturaRuta
            JOIN productos p ON dfr.ID_Producto = p.ID_Producto
            WHERE fr.ID_Usuario_Creacion = %s
              AND fr.Fecha BETWEEN DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND CURDATE()
              AND fr.Estado = 'Activa'
            GROUP BY p.Descripcion
            ORDER BY Cantidad_Total DESC
            LIMIT 5
        """, (user_id,))
        top_productos = cursor.fetchall()
        
        productos_nombres = [p['Producto'] for p in top_productos] if top_productos else []
        productos_cantidades = [float(p['Cantidad_Total']) for p in top_productos] if top_productos else []
        productos_totales = [float(p['Total_Vendido']) for p in top_productos] if top_productos else []
        
        # 10. Tabla: clientes con Cartera Vencida
        cursor.execute("""
            SELECT c.ID_Cliente, c.Nombre, c.Telefono, cxc.Num_Documento, 
                   cxc.Saldo_Pendiente, cxc.Fecha_Vencimiento,
                   DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as Dias_Vencido
            FROM cuentas_por_cobrar cxc
            JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE c.ID_Ruta IN (
                SELECT ID_Ruta FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            )
              AND cxc.Estado = 'Pendiente'
              AND cxc.Fecha_Vencimiento < CURDATE()
            ORDER BY cxc.Fecha_Vencimiento ASC
            LIMIT 10
        """, (user_id,))
        clientes_vencidos = cursor.fetchall()
        
        # 11. Tabla: Movimientos Recientes de Caja
        movimientos_caja = []
        if asignacion_id:
            cursor.execute("""
                SELECT ID_Movimiento, Fecha, Tipo, Concepto, Monto, Saldo_Acumulado
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s
                  AND ID_Asignacion = %s
                  AND Estado = 'ACTIVO'
                ORDER BY Fecha DESC
                LIMIT 10
            """, (user_id, asignacion_id))
            movimientos_caja = cursor.fetchall()
        
        # 12. Tabla: Ventas Recientes
        cursor.execute("""
            SELECT fr.ID_FacturaRuta, fr.Fecha, c.Nombre as Cliente, 
                   fr.Credito_Contado,
                   COALESCE(SUM(dfr.Total), 0) as Total_Venta,
                   COUNT(dfr.ID_DetalleRuta) as Num_Productos
            FROM facturacion_ruta fr
            JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
            LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND fr.Estado = 'Activa'
            GROUP BY fr.ID_FacturaRuta, fr.Fecha, c.Nombre, fr.Credito_Contado
            ORDER BY fr.Fecha_Creacion DESC
            LIMIT 10
        """, (user_id,))
        ventas_recientes = cursor.fetchall()
        
        # 13. Resumen de Inventario en Ruta
        inventario_ruta = []
        if asignacion_id:
            cursor.execute("""
                SELECT p.ID_Producto, p.Descripcion, p.COD_Producto, 
                       ir.Cantidad, p.Stock_Minimo,
                       CASE 
                           WHEN ir.Cantidad <= p.Stock_Minimo THEN 'critico'
                           WHEN ir.Cantidad <= p.Stock_Minimo * 2 THEN 'bajo'
                           ELSE 'ok' 
                       END as Nivel_Stock
                FROM inventario_ruta ir
                JOIN productos p ON ir.ID_Producto = p.ID_Producto
                WHERE ir.ID_Asignacion = %s
                ORDER BY Nivel_Stock ASC, p.Descripcion ASC
                LIMIT 20
            """, (asignacion_id,))
            inventario_ruta = cursor.fetchall()
        
        # 14. Resumen de Cartera por Cobrar Total
        cursor.execute("""
            SELECT 
                COUNT(*) as Total_Creditos,
                COALESCE(SUM(Saldo_Pendiente), 0) as Total_Cartera,
                COALESCE(AVG(Saldo_Pendiente), 0) as Promedio_Credito
            FROM cuentas_por_cobrar cxc
            JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE c.ID_Ruta IN (
                SELECT ID_Ruta FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            )
              AND cxc.Estado = 'Pendiente'
        """, (user_id,))
        resumen_cartera = cursor.fetchone()


        
    return render_template('vendedor/dashboard.html',
                         asignacion_activa=asignacion_activa,
                         asignacion_id=asignacion_id,
                         total_ventas_hoy=total_ventas_hoy,
                         total_ventas_contado_hoy=total_ventas_contado_hoy,
                         total_ventas_credito_hoy=total_ventas_credito_hoy,
                         total_cobrado_hoy=total_cobrado_hoy,
                         saldo_caja=saldo_caja,
                         cobros_proximos=cobros_proximos,
                         monto_proximo=monto_proximo,
                         ventas_fechas=ventas_fechas,
                         ventas_contado=ventas_contado,
                         ventas_credito=ventas_credito,
                         productos_nombres=productos_nombres,
                         productos_cantidades=productos_cantidades,
                         productos_totales=productos_totales,
                         clientes_vencidos=clientes_vencidos,
                         movimientos_caja=movimientos_caja,
                         ventas_recientes=ventas_recientes,
                         inventario_ruta=inventario_ruta,
                         resumen_cartera=resumen_cartera)

@vendedor_bp.route('/vendedor/mis-rutas')
@vendedor_required
def vendedor_mis_rutas():
    """Vista principal para que el vendedor vea y gestione sus rutas asignadas"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener las asignaciones del vendedor actual
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    r.Nombre_Ruta,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado,
                    a.Hora_Inicio,
                    a.Hora_Fin,
                    ua.NombreUsuario AS Asignado_Por
                FROM asignacion_vendedores a
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios ua ON a.ID_Usuario_Asigna = ua.ID_Usuario
                WHERE a.ID_Usuario = %s 
                AND a.ID_Empresa = %s
                AND a.Estado IN ('Activa', 'Finalizada', 'Suspendida')
                ORDER BY 
                    CASE 
                        WHEN a.Estado = 'Activa' THEN 1
                        WHEN a.Estado = 'Finalizada' THEN 2
                        WHEN a.Estado = 'Suspendida' THEN 3
                        ELSE 4
                    END,
                    a.Fecha_Asignacion DESC
            """, (usuario_id, empresa_id))
            asignaciones_raw = cursor.fetchall()
            
            # Procesar asignaciones para convertir horas
            asignaciones = procesar_lista_asignaciones(asignaciones_raw)
            
        return render_template(
            'vendedor/rutas/rutas.html',
            asignaciones=asignaciones,
            hoy=datetime.now().strftime('%Y-%m-%d'),
            hora_actual=datetime.now().strftime('%H:%M')
        )
        
    except Exception as e:
        flash(f'Error al cargar rutas: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))

@vendedor_bp.route('/vendedor/ruta/iniciar/<int:id>', methods=['POST'])
@vendedor_required
def vendedor_iniciar_ruta(id):
    """Permite al vendedor iniciar su ruta asignada"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        # Verificar que la asignación pertenezca al usuario actual
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT Estado, Hora_Inicio 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (id, usuario_id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o no pertenece a usted', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Estado'] != 'Activa':
                flash('Solo puede iniciar rutas en estado "Activa"', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Hora_Inicio']:
                flash('La ruta ya ha sido iniciada', 'warning')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
        
        # Obtener la hora de inicio del formulario o usar la actual
        hora_inicio = request.form.get('hora_inicio')
        if not hora_inicio:
            hora_inicio = datetime.now().strftime('%H:%M')
        
        # Actualizar la asignación (solo agregar hora inicio, mantener estado "Activa")
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Hora_Inicio = %s
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (hora_inicio, id, usuario_id, empresa_id))
            
        flash('Ruta iniciada exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al iniciar ruta: {str(e)}', 'error')
    
    return redirect(url_for('vendedor.vendedor_mis_rutas'))

@vendedor_bp.route('/vendedor/ruta/finalizar/<int:id>', methods=['POST'])
@vendedor_required
def vendedor_finalizar_ruta(id):
    """Permite al vendedor finalizar su ruta"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        # Verificar que la asignación pertenezca al usuario actual
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT Estado, Hora_Inicio, Hora_Fin, ID_Vehiculo
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (id, usuario_id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o no pertenece a usted', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Estado'] != 'Activa':
                flash('Solo puede finalizar rutas en estado "Activa"', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Hora_Fin']:
                flash('La ruta ya ha sido finalizada', 'warning')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
        
        # Obtener datos del formulario
        hora_fin = request.form.get('hora_fin')
        comentario = request.form.get('comentario', '')
        
        if not hora_fin:
            hora_fin = datetime.now().strftime('%H:%M')
        
        # Actualizar la asignación
        with get_db_cursor(commit=True) as cursor:
            # Actualizar hora de fin y estado
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Estado = 'Finalizada',
                    Hora_Fin = %s,
                    Fecha_Finalizacion = CURDATE()
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (hora_fin, id, usuario_id, empresa_id))
            
            # Liberar el vehículo si estaba asignado
            if asignacion['ID_Vehiculo']:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (asignacion['ID_Vehiculo'],))
            
        flash('Ruta finalizada exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al finalizar ruta: {str(e)}', 'error')
    
    return redirect(url_for('vendedor.vendedor_mis_rutas'))

@vendedor_bp.route('/vendedor/ruta/detalle/<int:id>')
@vendedor_required
def vendedor_detalle_ruta(id):
    """Detalle de una ruta específica del vendedor"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    r.Nombre_Ruta,
                    r.Descripcion AS Descripcion_Ruta,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado,
                    a.Hora_Inicio,
                    a.Hora_Fin,
                    ua.NombreUsuario AS Asignado_Por,
                    a.Fecha_Creacion
                FROM asignacion_vendedores a
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios ua ON a.ID_Usuario_Asigna = ua.ID_Usuario
                WHERE a.ID_Asignacion = %s 
                AND a.ID_Usuario = %s 
                AND a.ID_Empresa = %s
            """, (id, usuario_id, empresa_id))
            
            asignacion_raw = cursor.fetchone()
            
            if not asignacion_raw:
                flash('Ruta no encontrada o no tiene acceso', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            # Procesar la asignación para convertir horas
            asignacion = procesar_asignacion(asignacion_raw)
            
        return render_template('vendedor/rutas/detalle_ruta.html', asignacion=asignacion)
        
    except Exception as e:
        flash(f'Error al cargar detalle: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_mis_rutas'))

@vendedor_bp.route('/api/vendedor/asignacion_actual', methods=['GET'])
@vendedor_required
def api_asignacion_actual():
    """Obtener la asignación actual del vendedor"""
    try:
        id_vendedor = int(current_user.id)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Empresa,
                       r.Nombre_Ruta
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s AND av.Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
                
            return jsonify({
                'success': True,
                'asignacion_id': asignacion['ID_Asignacion'],
                'ruta_id': asignacion['ID_Ruta'],
                'ruta_nombre': asignacion['Nombre_Ruta'],
                'empresa_id': asignacion['ID_Empresa']
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/vendedor/resumen/diario', methods=['GET'])
@vendedor_required
def resumen_diario_vendedor():
    """Resumen diario de actividades del vendedor"""
    try:
        id_vendedor = current_user.id
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    DATE(m.Fecha) as Dia,
                    r.Nombre_Ruta,
                    COUNT(DISTINCT CASE WHEN m.Tipo = 'VENTA' THEN m.ID_FacturaRuta END) as Total_Ventas,
                    SUM(CASE WHEN m.Tipo = 'VENTA' AND m.Tipo_Pago = 'CONTADO' THEN m.Monto ELSE 0 END) as Ventas_Contado,
                    SUM(CASE WHEN m.Tipo = 'VENTA' AND m.Tipo_Pago = 'CREDITO' THEN 1 ELSE 0 END) as Ventas_Credito,
                    COUNT(DISTINCT CASE WHEN m.Tipo = 'ABONO' THEN m.ID_Movimiento END) as Cantidad_Abonos,
                    SUM(CASE WHEN m.Tipo = 'ABONO' THEN m.Monto ELSE 0 END) as Total_Abonado,
                    COUNT(DISTINCT CASE WHEN m.Tipo = 'ABONO' THEN m.ID_Cliente END) as clientes_Abonaron,
                    SUM(CASE WHEN m.Tipo = 'GASTO' THEN m.Monto ELSE 0 END) as Total_Gastos
                FROM movimientos_caja_ruta m
                INNER JOIN asignacion_vendedores av ON m.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE m.ID_Usuario = %s
                AND m.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY DATE(m.Fecha), r.Nombre_Ruta
                ORDER BY Dia DESC
            """, (id_vendedor,))
            
            resumen = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'vendedor': current_user.NombreUsuario,
                'resumen': resumen
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
