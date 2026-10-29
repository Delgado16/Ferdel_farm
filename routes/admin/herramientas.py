import csv
import io
import os
from flask import make_response, render_template, redirect, url_for, request, flash, jsonify, send_from_directory
from flask_login import current_user
from datetime import datetime, date
from decimal import Decimal
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator, registrar_bitacora
from helpers.backup_service import (
    generar_script_sql,
    ejecutar_backup_servidor,
    listar_backups_servidor,
    eliminar_backup_servidor,
    obtener_directorio_backups
)

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
    """Configurar visibilidad de categorías y bodegas"""
    
    if request.method == 'POST':
        try:
            with get_db_cursor(commit=True) as cursor:
                # 1. Procesar Categorías
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

                # 2. Procesar Bodegas
                cursor.execute("SELECT ID_Bodega FROM bodegas WHERE LOWER(Estado) = 'activa'")
                todas_bodegas = cursor.fetchall()
                
                for bodega in todas_bodegas:
                    bodega_id = bodega['ID_Bodega']
                    
                    # Para clientes Comunes
                    key_comun_bod = f"bod_{bodega_id}_Comun"
                    visible_comun_bod = 1 if key_comun_bod in request.form else 0
                    
                    cursor.execute("""
                        INSERT INTO config_visibilidad_bodegas 
                        (tipo_cliente, ID_Bodega, visible) 
                        VALUES ('Comun', %s, %s)
                        ON DUPLICATE KEY UPDATE visible = %s
                    """, (bodega_id, visible_comun_bod, visible_comun_bod))
                    
                    # Para clientes Especiales
                    key_especial_bod = f"bod_{bodega_id}_Especial"
                    visible_especial_bod = 1 if key_especial_bod in request.form else 0
                    
                    cursor.execute("""
                        INSERT INTO config_visibilidad_bodegas 
                        (tipo_cliente, ID_Bodega, visible) 
                        VALUES ('Especial', %s, %s)
                        ON DUPLICATE KEY UPDATE visible = %s
                    """, (bodega_id, visible_especial_bod, visible_especial_bod))
                
                flash('✅ Configuración guardada exitosamente', 'success')
                return redirect(url_for('admin.config_visibilidad'))
                
        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'danger')
    
    # GET: Mostrar formulario
    with get_db_cursor() as cursor:
        # Obtener Categorías
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

        # Obtener Bodegas
        cursor.execute("""
            SELECT 
                b.ID_Bodega,
                b.Nombre as nombre,
                COALESCE(cfg_comun.visible, 0) as comun_visible,
                COALESCE(cfg_especial.visible, 0) as especial_visible
            FROM bodegas b
            LEFT JOIN config_visibilidad_bodegas cfg_comun 
                ON b.ID_Bodega = cfg_comun.ID_Bodega 
                AND cfg_comun.tipo_cliente = 'Comun'
            LEFT JOIN config_visibilidad_bodegas cfg_especial 
                ON b.ID_Bodega = cfg_especial.ID_Bodega 
                AND cfg_especial.tipo_cliente = 'Especial'
            WHERE LOWER(b.Estado) = 'activa'
            ORDER BY b.Nombre
        """)
        bodegas = cursor.fetchall()
    
    return render_template('admin/config/visibilidad.html', categorias=categorias, bodegas=bodegas)


#==================================
#=== MODULO CONFIGURACION GENERAL =
#==================================
@admin_bp.route('/admin/config/general', methods=['GET', 'POST'])
@admin_required
def config_general():
    """Vista y procesamiento de la configuración general del sistema"""
    if request.method == 'POST':
        try:
            llaves_config = [
                'empresa_nombre', 'empresa_ruc', 'empresa_direccion', 'empresa_telefono',
                'iva_porcentaje', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password'
            ]
            
            with get_db_cursor(commit=True) as cursor:
                for llave in llaves_config:
                    valor = request.form.get(llave, '').strip()
                    
                    # Validar porcentaje de IVA
                    if llave == 'iva_porcentaje':
                        try:
                            # Asegurar que sea decimal válido
                            float(valor)
                        except ValueError:
                            flash("❌ El porcentaje del IVA debe ser un número válido.", "danger")
                            return redirect(url_for('admin.config_general'))
                            
                    cursor.execute("""
                        INSERT INTO config_sistema (llave, valor) 
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE valor = %s
                    """, (llave, valor, valor))
            
            registrar_bitacora(modulo="CONFIGURACION", accion="ACTUALIZAR_CONFIGURACION_GENERAL")
            flash("✅ Configuración guardada exitosamente.", "success")
            return redirect(url_for('admin.config_general'))
            
        except Exception as e:
            flash(f"❌ Error al guardar la configuración: {e}", "danger")
            return redirect(url_for('admin.config_general'))
            
    # GET: Obtener configuraciones actuales
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT llave, valor FROM config_sistema")
            rows = cursor.fetchall()
            config = {row['llave']: row['valor'] for row in rows}
            
            # Asegurar que todas las llaves existan en el diccionario para evitar KeyError en plantilla
            llaves_esperadas = [
                'empresa_nombre', 'empresa_ruc', 'empresa_direccion', 'empresa_telefono',
                'iva_porcentaje', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password'
            ]
            for llave in llaves_esperadas:
                if llave not in config:
                    config[llave] = ""
                    
            return render_template('admin/config/general.html', config=config)
    except Exception as e:
        flash(f"❌ Error al cargar configuración: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


#==================================
#=== MODULO RESPALDOS DE BD =======
#==================================
@admin_bp.route('/backup')
@admin_bp.route('/admin/backup')
@admin_required
def admin_backup():
    """Vista principal de la gestión de respaldos con copias automáticas y manuales"""
    try:
        with get_db_cursor() as cursor:
            # Obtener el tamaño aproximado de la base de datos
            cursor.execute("SELECT DATABASE() as db_name")
            db_name_res = cursor.fetchone()
            db_name = db_name_res['db_name'] if db_name_res else 'ferdel'
            
            cursor.execute("""
                SELECT SUM(data_length + index_length) / 1024 / 1024 AS size_mb 
                FROM information_schema.TABLES 
                WHERE table_schema = %s
            """, (db_name,))
            res_size = cursor.fetchone()
            size_mb = res_size['size_mb'] if res_size and res_size['size_mb'] else 0.0
            
            cursor.execute("""
                SELECT TABLE_NAME AS table_name, 
                       COALESCE(TABLE_ROWS, 0) AS table_rows, 
                       COALESCE((DATA_LENGTH + INDEX_LENGTH) / 1024, 0.0) AS size_kb 
                FROM information_schema.TABLES 
                WHERE table_schema = %s
                ORDER BY TABLE_NAME
            """, (db_name,))
            tablas_raw = cursor.fetchall()
            tablas = []
            for row in tablas_raw:
                tablas.append({k.lower(): v for k, v in row.items()})

            # Obtener configuraciones de respaldo
            cursor.execute("""
                SELECT llave, valor FROM config_sistema 
                WHERE llave IN ('ultimo_backup_automatico', 'backup_auto_habilitado', 'backup_auto_dias_retencion')
            """)
            cfg_rows = cursor.fetchall()
            cfg = {r['llave']: r['valor'] for r in cfg_rows}
            
            config_respaldo = {
                'ultimo_backup': cfg.get('ultimo_backup_automatico', 'Ninguno registrado'),
                'habilitado': cfg.get('backup_auto_habilitado', '1') == '1',
                'dias_retencion': cfg.get('backup_auto_dias_retencion', '15')
            }
            
            # Obtener lista de respaldos existentes en el servidor
            backups_guardados = listar_backups_servidor()
            
            return render_template('admin/herramientas/backup.html', 
                                 db_name=db_name, 
                                 size_mb=round(float(size_mb), 2), 
                                 tablas=tablas,
                                 config_respaldo=config_respaldo,
                                 backups_guardados=backups_guardados)
    except Exception as e:
        flash(f"❌ Error al cargar información de respaldos: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/backup/generar')
@admin_bp.route('/admin/backup/generar')
@admin_required
def generar_backup():
    """Generar y descargar en el navegador un archivo .sql del respaldo de la base de datos"""
    try:
        sql_content = generar_script_sql()
        filename = f"backup_ferdel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        response = make_response(sql_content)
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-type"] = "application/sql"
        
        registrar_bitacora(modulo="RESPALDO", accion=f"GENERAR_BACKUP_DESCARGA: {filename}")
        return response
        
    except Exception as e:
        flash(f"❌ Error al generar respaldo: {e}", "danger")
        return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/backup/ejecutar-servidor', methods=['POST'])
@admin_bp.route('/admin/backup/ejecutar-servidor', methods=['POST'])
@admin_required
def backup_ejecutar_servidor():
    """Ejecutar respaldo inmediato y guardarlo en el servidor"""
    try:
        resultado = ejecutar_backup_servidor(es_automatico=False)
        flash(f"✅ Copia de seguridad guardada con éxito en el servidor: {resultado['filename']} ({resultado['size_mb']} MB)", "success")
    except Exception as e:
        flash(f"❌ Error al generar respaldo en el servidor: {e}", "danger")
    return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/backup/descargar/<filename>')
@admin_bp.route('/admin/backup/descargar/<filename>')
@admin_required
def descargar_backup_servidor(filename):
    """Descargar un archivo de respaldo específico almacenado en el servidor"""
    try:
        directorio = obtener_directorio_backups()
        return send_from_directory(directorio, filename, as_attachment=True)
    except Exception as e:
        flash(f"❌ No se pudo descargar el archivo: {e}", "danger")
        return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/backup/eliminar/<filename>', methods=['POST'])
@admin_bp.route('/admin/backup/eliminar/<filename>', methods=['POST'])
@admin_required
def eliminar_backup_archivo(filename):
    """Eliminar un archivo de respaldo guardado en el servidor"""
    try:
        if eliminar_backup_servidor(filename):
            flash(f"🗑️ Archivo de respaldo '{filename}' eliminado correctamente.", "success")
        else:
            flash(f"⚠️ El archivo '{filename}' no fue encontrado.", "warning")
    except Exception as e:
        flash(f"❌ Error al eliminar el respaldo: {e}", "danger")
    return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/backup/config', methods=['POST'])
@admin_bp.route('/admin/backup/config', methods=['POST'])
@admin_required
def guardar_config_backup():
    """Actualizar configuración de copias automáticas (habilitar/deshabilitar, días de retención)"""
    try:
        habilitado = '1' if 'backup_auto_habilitado' in request.form else '0'
        dias_retencion = request.form.get('backup_auto_dias_retencion', '15').strip()
        
        try:
            dias_val = int(dias_retencion)
            if dias_val < 1:
                dias_retencion = '15'
        except ValueError:
            dias_retencion = '15'

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO config_sistema (llave, valor)
                VALUES ('backup_auto_habilitado', %s)
                ON DUPLICATE KEY UPDATE valor = %s
            """, (habilitado, habilitado))

            cursor.execute("""
                INSERT INTO config_sistema (llave, valor)
                VALUES ('backup_auto_dias_retencion', %s)
                ON DUPLICATE KEY UPDATE valor = %s
            """, (dias_retencion, dias_retencion))

        registrar_bitacora(
            modulo="RESPALDO", 
            accion=f"ACTUALIZAR_CONFIG_BACKUP: habilitado={habilitado}, retencion={dias_retencion}d"
        )
        flash("✅ Configuración de respaldo automático actualizada.", "success")
    except Exception as e:
        flash(f"❌ Error al guardar configuración: {e}", "danger")
    return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/backup/restaurar-servidor/<filename>', methods=['POST'])
@admin_bp.route('/admin/backup/restaurar-servidor/<filename>', methods=['POST'])
@admin_required
def restaurar_backup_servidor(filename):
    """Restaurar la base de datos directamente desde un archivo guardado en el servidor"""
    try:
        directorio = obtener_directorio_backups()
        filepath = os.path.join(directorio, os.path.basename(filename))
        
        if not os.path.exists(filepath):
            flash("❌ Archivo de respaldo no encontrado en el servidor.", "danger")
            return redirect(url_for('admin.admin_backup'))
            
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()

        statements = []
        current_stmt = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
                continue
            current_stmt.append(line)
            if stripped.endswith(';'):
                statements.append(" ".join(current_stmt))
                current_stmt = []

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            exitosas = 0
            errores = 0
            for stmt in statements:
                stmt_strip = stmt.strip()
                if not stmt_strip:
                    continue
                try:
                    cursor.execute(stmt_strip)
                    exitosas += 1
                except Exception as stmt_err:
                    errores += 1
                    print(f"Error al ejecutar sentencia de backup: {stmt_err}\nSentencia: {stmt_strip[:150]}")
            
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            registrar_bitacora(modulo="RESPALDO", accion=f"RESTAURAR_BACKUP_SERVIDOR: {filename} ({exitosas} sentencias, {errores} errores)")

            if errores == 0:
                flash(f"✅ Base de datos restaurada con éxito desde '{filename}'. ({exitosas} sentencias ejecutadas)", "success")
            else:
                flash(f"⚠️ Base de datos restaurada con advertencias ({exitosas} exitosas, {errores} fallidas).", "warning")

    except Exception as e:
        flash(f"❌ Error al restaurar respaldo: {e}", "danger")

    return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/backup/restaurar', methods=['POST'])
@admin_bp.route('/admin/backup/restaurar', methods=['POST'])
@admin_required
def restaurar_backup():
    """Restaurar base de datos desde un archivo .sql subido"""
    try:
        file = request.files.get('backup_file')
        if not file or not file.filename.endswith('.sql'):
            flash("❌ Por favor seleccione un archivo .sql válido", "danger")
            return redirect(url_for('admin.admin_backup'))
            
        sql_content = file.read().decode('utf-8', errors='ignore')
        
        # Parseador simple de sentencias SQL separadas por punto y coma (;)
        statements = []
        current_stmt = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
                continue
            current_stmt.append(line)
            if stripped.endswith(';'):
                statements.append(" ".join(current_stmt))
                current_stmt = []
                
        with get_db_cursor(commit=True) as cursor:
            # Desactivar temporalmente revisión de llaves foráneas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            exitosas = 0
            errores = 0
            for stmt in statements:
                stmt_strip = stmt.strip()
                if not stmt_strip:
                    continue
                try:
                    cursor.execute(stmt_strip)
                    exitosas += 1
                except Exception as stmt_err:
                    errores += 1
                    print(f"Error al ejecutar sentencia de backup: {stmt_err}\nSentencia: {stmt_strip[:150]}")
            
            # Reactivar llaves foráneas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
            registrar_bitacora(modulo="RESPALDO", accion=f"RESTAURAR_BACKUP: {exitosas} sentencias ejecutadas, {errores} errores")
            
            if errores == 0:
                flash(f"✅ Base de datos restaurada con éxito. Se ejecutaron {exitosas} sentencias sin errores.", "success")
            else:
                flash(f"⚠️ Base de datos restaurada con advertencias. {exitosas} exitosas, {errores} fallidas. Revisa la consola para más detalles.", "warning")
                
    except Exception as e:
        flash(f"❌ Error al restaurar base de datos: {e}", "danger")
        
    return redirect(url_for('admin.admin_backup'))

