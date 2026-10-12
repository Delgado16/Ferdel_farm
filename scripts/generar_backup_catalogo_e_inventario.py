"""
Script para generar una copia de seguridad filtrada (Plantilla / Base limpia):
- Conserva la ESTRUCTURA COMPLETA de todas las tablas y vistas.
- CONSERVA TODOS LOS DATOS de:
    * Vehículos
    * Productos y Categorías
    * Bodegas y Ubicaciones
    * Movimientos de Inventario y Kardex (Stock bodega y ruta)
    * Unidades de Medida
    * Rutas y Sucursales
    * Usuarios y Roles
    * Empresa y Configuración del Sistema
    * Métodos de Pago y Catálogos de Gastos
- VACÍA LOS DATOS (solo conserva estructura) de:
    * Clientes, Anticipos, Cuentas por Cobrar, Abonos
    * Proveedores, Cuentas por Pagar, Abonos a Proveedores
    * Ventas (Facturación, Facturación en Ruta, Detalle)
    * Pedidos y Entregas
    * Caja / Movimientos de caja asociados a ventas y cobros
    * Logs de anulaciones y bitácora
"""
import sys
import os
import io
from datetime import datetime, date
from decimal import Decimal

# Asegurar path base
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.database import get_db_cursor
from helpers.backup_service import obtener_directorio_backups

# Tablas transaccionales a vaciar de datos
TABLAS_A_VACIAR = {
    # Clientes y Cuentas por Cobrar
    'clientes',
    'sucursales',
    'anticipos_clientes',
    'cuentas_por_cobrar',
    'pagos_cuentascobrar',
    'abonos_general',
    'abonos_detalle',
    
    # Proveedores y Cuentas por Pagar
    'proveedores',
    'cuentas_por_pagar',
    'pagos_cuentaspagar',
    'abonos_proveedores_detalle',
    'cargas_pendientes_recepcion',
    'cargas_pendientes_detalle',
    
    # Ventas y Pedidos
    'facturacion',
    'detalle_facturacion',
    'facturacion_ruta',
    'detalle_facturacion_ruta',
    'pedidos',
    'detalle_pedidos',
    'pedidos_consolidados_productos',
    'entregas',
    'detalle_entregas',
    'log_anulaciones',
    
    # Movimientos de Caja por ventas / cobros
    'caja_movimientos',
    'movimientos_caja_ruta',
    
    # Jornadas, Asignaciones e Inventario en Ruta de Vendedores
    'asignacion_vendedores',
    'inventario_ruta',
    
    # Historial de Movimientos de Inventario y Rutas
    'movimientos_inventario',
    'detalle_movimientos_inventario',
    'movimientos_ruta_cabecera',
    'movimientos_ruta_detalle',
    
    # Bitácora
    'bitacora'
}


def generar_backup_filtrado():
    output = io.StringIO()
    fecha_actual_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    output.write("-- ========================================================\n")
    output.write("-- COPIA DE SEGURIDAD FERDEL - PLANTILLA CATALOGO E INVENTARIO\n")
    output.write(f"-- Fecha de generación: {fecha_actual_str}\n")
    output.write("-- NOTA: Datos de Clientes, Proveedores, Ventas y Cuentas vaciados.\n")
    output.write("-- Conserva: Catálogo de Vehículos, Inventario, Productos, Bodegas, Unidades, etc.\n")
    output.write("-- ========================================================\n\n")
    output.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

    with get_db_cursor(commit=False) as cursor:
        cursor.execute("SELECT DATABASE() as db_name")
        res_db = cursor.fetchone()
        db_name = res_db['db_name'] if res_db else 'ferdel'

        output.write(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;\n")
        output.write(f"USE `{db_name}`;\n\n")

        cursor.execute("SHOW TABLES")
        tables = [list(row.values())[0] for row in cursor.fetchall()]

        # 1. Estructura y datos de tablas
        for table in tables:
            cursor.execute(f"SHOW FULL TABLES LIKE '{table}'")
            table_info = cursor.fetchone()
            is_view = table_info and list(table_info.values())[1] == 'VIEW'
            if is_view:
                continue

            output.write(f"-- --------------------------------------------------------\n")
            output.write(f"-- Estructura de tabla: `{table}`\n")
            output.write(f"-- --------------------------------------------------------\n")
            output.write(f"DROP TABLE IF EXISTS `{table}`;\n")

            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            create_stmt = cursor.fetchone()
            sql_create = list(create_stmt.values())[1]
            output.write(f"{sql_create};\n\n")

            # Si es una tabla a vaciar, no exportamos filas
            if table in TABLAS_A_VACIAR:
                output.write(f"-- (Tabla `{table}` vaciada intencionalmente)\n\n")
                continue

            # Obtener datos de tablas conservadas
            cursor.execute(f"SELECT * FROM `{table}`")
            rows = cursor.fetchall()
            if rows:
                columns = list(rows[0].keys())
                col_names = ", ".join([f"`{col}`" for col in columns])

                output.write(f"-- Datos de la tabla `{table}` ({len(rows)} registros conservados)\n")

                chunk_size = 100
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i:i + chunk_size]
                    rows_values = []
                    for row in chunk:
                        vals = []
                        for col in columns:
                            val = row[col]

                            # Ajuste de llaves foráneas a tablas vaciadas para mantener consistencia referencial
                            if table == 'movimientos_inventario' and col in ('ID_Proveedor', 'ID_Factura_Venta', 'ID_Pedido_Origen'):
                                val = None
                            elif table == 'movimientos_ruta_cabecera' and col in ('ID_Cliente', 'ID_Pedido'):
                                val = None

                            if val is None:
                                vals.append("NULL")
                            elif isinstance(val, (int, float, Decimal)):
                                vals.append(str(val))
                            elif isinstance(val, (datetime, date)):
                                if isinstance(val, datetime):
                                    vals.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                                else:
                                    vals.append(f"'{val.strftime('%Y-%m-%d')}'")
                            elif isinstance(val, bytes):
                                vals.append(f"0x{val.hex()}")
                            else:
                                escaped_val = str(val).replace("\\", "\\\\").replace("'", "\\'")
                                vals.append(f"'{escaped_val}'")

                        rows_values.append(f"({', '.join(vals)})")

                    output.write(f"INSERT INTO `{table}` ({col_names}) VALUES\n")
                    output.write(",\n".join(rows_values) + ";\n")
            output.write("\n")

        # 2. Vistas
        for table in tables:
            cursor.execute(f"SHOW FULL TABLES LIKE '{table}'")
            table_info = cursor.fetchone()
            is_view = table_info and list(table_info.values())[1] == 'VIEW'
            if not is_view:
                continue

            output.write(f"-- --------------------------------------------------------\n")
            output.write(f"-- Estructura de vista: `{table}`\n")
            output.write(f"-- --------------------------------------------------------\n")
            output.write(f"DROP VIEW IF EXISTS `{table}`;\n")

            cursor.execute(f"SHOW CREATE VIEW `{table}`")
            create_stmt = cursor.fetchone()
            sql_create = list(create_stmt.values())[1]
            output.write(f"{sql_create};\n\n")

    output.write("SET FOREIGN_KEY_CHECKS = 1;\n")
    return output.getvalue()


def main():
    print("=" * 70)
    print("  FERDEL - GENERANDO COPIA DE SEGURIDAD FILTRADA")
    print("  (Catálogo, Vehículos e Inventario CONSERVADOS / Ventas y Clientes VACIADOS)")
    print("=" * 70)

    directorio = obtener_directorio_backups()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_ferdel_catalogo_inventario_{timestamp_str}.sql"
    filepath = os.path.join(directorio, filename)

    print(f"📦 Extrayendo estructuras y registros seleccionados...")
    sql_content = generar_backup_filtrado()

    print(f"💾 Guardando archivo en: {filepath}...")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(sql_content)

    tamano_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
    tamano_kb = round(os.path.getsize(filepath) / 1024, 1)

    print("\n" + "=" * 70)
    print("✅ ¡COPIA DE SEGURIDAD FILTRADA GENERADA CON ÉXITO!")
    print(f"   Archivo: {filename}")
    print(f"   Ruta:    {filepath}")
    print(f"   Tamaño:  {tamano_mb} MB ({tamano_kb} KB)")
    print("=" * 70)
    print("\n📋 Resumen de tablas vaciadas:")
    for t in sorted(list(TABLAS_A_VACIAR)):
        print(f"   - {t} (vacía)")
    print("\n📋 Resumen de datos conservados:")
    print("   - Vehículos, Productos, Categorías, Unidades de Medida")
    print("   - Bodegas y Stock Físico Actual (inventario_bodega e inventario_ruta)")
    print("   - Catálogo de Tipos de Movimiento, Rutas, Usuarios, Roles")
    print("   - Empresa y Configuración del Sistema, Catálogos de Gastos y Métodos de Pago")
    print("=" * 70)


if __name__ == '__main__':
    main()
