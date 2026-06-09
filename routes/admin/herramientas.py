import csv
import io
from flask import make_response, render_template, redirect, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator, registrar_bitacora

#============================
#=== MODULO HERRAMIENTAS ====
#============================
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
