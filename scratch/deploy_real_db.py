import os
import mysql.connector
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Configuración origen (base de datos de pruebas)
DB_SOURCE = os.environ.get('DB_NAME', 'db_ferdel')

# Configuración destino (base de datos real)
DB_TARGET = 'db_ferdel_real'

# Credenciales de conexión
conn_config = {
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'admin'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 3306))
}

# Definiciones reales de las vistas
VIEWS_DEFINITIONS = {
    'vista_gastos_unificados': """
        CREATE VIEW `vista_gastos_unificados` AS 
        select 'INVENTARIO' AS `origen`,`cp`.`ID_Categoria` AS `id_tipo`,`cp`.`Descripcion` AS `tipo_gasto`,NULL AS `subcategoria`,`mi`.`Fecha` AS `Fecha`,coalesce(sum((`dmi`.`Cantidad` * `dmi`.`Costo_Unitario`)),0) AS `monto`,`mi`.`N_Factura_Externa` AS `factura`,`pr`.`Nombre` AS `proveedor`,`pr`.`ID_Proveedor` AS `id_proveedor`,NULL AS `vehiculo`,`mi`.`ID_Empresa` AS `ID_Empresa`,`mi`.`Estado` AS `Estado`,`mi`.`ID_Movimiento` AS `id_gasto`,NULL AS `id_categoria_inv` 
        from ((((`movimientos_inventario` `mi` 
            join `detalle_movimientos_inventario` `dmi` on((`mi`.`ID_Movimiento` = `dmi`.`ID_Movimiento`))) 
            join `productos` `p` on((`dmi`.`ID_Producto` = `p`.`ID_Producto`))) 
            join `categorias_producto` `cp` on((`p`.`ID_Categoria` = `cp`.`ID_Categoria`))) 
            left join `proveedores` `pr` on((`mi`.`ID_Proveedor` = `pr`.`ID_Proveedor`))) 
        where ((`mi`.`ID_TipoMovimiento` = 1) and (`mi`.`Estado` = 'Activa')) 
        group by `cp`.`ID_Categoria`,`cp`.`Descripcion`,`mi`.`Fecha`,`mi`.`N_Factura_Externa`,`pr`.`Nombre`,`pr`.`ID_Proveedor`,`mi`.`ID_Empresa`,`mi`.`Estado`,`mi`.`ID_Movimiento` 
        union all 
        select 'GASTO_DIRECTO' AS `origen`,`tg`.`ID_Tipo_Gasto` AS `id_tipo`,`tg`.`Nombre` AS `tipo_gasto`,`sg`.`Nombre` AS `subcategoria`,`gg`.`Fecha` AS `Fecha`,coalesce(`gg`.`Monto`,0) AS `monto`,`gg`.`N_Factura` AS `factura`,`pr`.`Nombre` AS `proveedor`,`pr`.`ID_Proveedor` AS `id_proveedor`,`v`.`Placa` AS `vehiculo`,`gg`.`ID_Empresa` AS `ID_Empresa`,`gg`.`Estado` AS `Estado`,`gg`.`ID_Gasto` AS `id_gasto`,NULL AS `id_categoria_inv` 
        from ((((`gastos_generales` `gg` 
            join `tipos_gasto` `tg` on((`gg`.`ID_Tipo_Gasto` = `tg`.`ID_Tipo_Gasto`))) 
            left join `subcategorias_gasto` `sg` on((`gg`.`ID_Subcategoria` = `sg`.`ID_Subcategoria`))) 
            left join `proveedores` `pr` on((`gg`.`ID_Proveedor` = `pr`.`ID_Proveedor`))) 
            left join `vehiculos` `v` on((`gg`.`ID_Vehiculo` = `v`.`ID_Vehiculo`))) 
        where (`gg`.`Estado` = 'Activo')
    """,
    'vista_kardex_productos': """
        CREATE VIEW `vista_kardex_productos` AS 
        select `p`.`ID_Producto` AS `ID_Producto`,`p`.`COD_Producto` AS `COD_Producto`,`p`.`Descripcion` AS `Producto`,`cp`.`Descripcion` AS `Categoria`,`um`.`Descripcion` AS `Unidad_Medida`,`um`.`Abreviatura` AS `Abreviatura`,`b`.`Nombre` AS `Bodega`,`ib`.`Existencias` AS `Stock_Actual`,`p`.`Stock_Minimo` AS `Stock_Minimo`,
        (select sum(`dmi2`.`Cantidad`) 
         from ((`detalle_movimientos_inventario` `dmi2` 
            join `movimientos_inventario` `mi2` on((`dmi2`.`ID_Movimiento` = `mi2`.`ID_Movimiento`))) 
            join `catalogo_movimientos` `cm2` on((`mi2`.`ID_TipoMovimiento` = `cm2`.`ID_TipoMovimiento`))) 
         where ((`dmi2`.`ID_Producto` = `p`.`ID_Producto`) and (`mi2`.`Estado` = 'Activa') and (`mi2`.`ID_Bodega` = `b`.`ID_Bodega`) and ((`cm2`.`Adicion` = 'RESTA') or (`cm2`.`Letra` = 'S')) and (month(`mi2`.`Fecha`) = month(curdate())) and (year(`mi2`.`Fecha`) = year(curdate())))) AS `Salidas_Mes`,
        (select sum(`dmi2`.`Cantidad`) 
         from ((`detalle_movimientos_inventario` `dmi2` 
            join `movimientos_inventario` `mi2` on((`dmi2`.`ID_Movimiento` = `mi2`.`ID_Movimiento`))) 
            join `catalogo_movimientos` `cm2` on((`mi2`.`ID_TipoMovimiento` = `cm2`.`ID_TipoMovimiento`))) 
         where ((`dmi2`.`ID_Producto` = `p`.`ID_Producto`) and (`mi2`.`Estado` = 'Activa') and (`mi2`.`ID_Bodega` = `b`.`ID_Bodega`) and (`cm2`.`Letra` = 'E') and (month(`mi2`.`Fecha`) = month(curdate())) and (year(`mi2`.`Fecha`) = year(curdate())))) AS `Entradas_Mes` 
        from ((((`productos` `p` 
            join `categorias_producto` `cp` on((`p`.`ID_Categoria` = `cp`.`ID_Categoria`))) 
            join `unidades_medida` `um` on((`p`.`Unidad_Medida` = `um`.`ID_Unidad`))) 
            join `inventario_bodega` `ib` on((`p`.`ID_Producto` = `ib`.`ID_Producto`))) 
            join `bodegas` `b` on((`ib`.`ID_Bodega` = `b`.`ID_Bodega`))) 
        where (`p`.`Estado` = 'activo') 
        order by `p`.`Descripcion`,`b`.`Nombre`
    """,
    'vw_entradas_inventario': """
        CREATE VIEW `vw_entradas_inventario` AS 
        select `mi`.`ID_Movimiento` AS `ID_Movimiento`,`mi`.`Fecha` AS `Fecha`,`cm`.`ID_TipoMovimiento` AS `ID_TipoMovimiento`,`cm`.`Descripcion` AS `Tipo_Movimiento`,`cm`.`Letra` AS `Letra`,`mi`.`N_Factura_Externa` AS `N_Factura_Externa`,`mi`.`ID_Proveedor` AS `ID_Proveedor`,`p`.`Nombre` AS `Proveedor`,`mi`.`Tipo_Compra` AS `Tipo_Compra`,`mi`.`ID_Bodega` AS `ID_Bodega`,`b`.`Nombre` AS `Bodega`,`dmi`.`ID_Producto` AS `ID_Producto`,`pr`.`COD_Producto` AS `Codigo_Producto`,`pr`.`Descripcion` AS `Producto`,`dmi`.`Cantidad` AS `Cantidad`,`dmi`.`Costo_Unitario` AS `Costo_Unitario`,`dmi`.`Precio_Unitario` AS `Precio_Unitario`,`dmi`.`Subtotal` AS `Subtotal`,`mi`.`Estado` AS `Estado` 
        from (((((`movimientos_inventario` `mi` 
            join `catalogo_movimientos` `cm` on((`mi`.`ID_TipoMovimiento` = `cm`.`ID_TipoMovimiento`))) 
            join `detalle_movimientos_inventario` `dmi` on((`mi`.`ID_Movimiento` = `dmi`.`ID_Movimiento`))) 
            join `productos` `pr` on((`dmi`.`ID_Producto` = `pr`.`ID_Producto`))) 
            join `bodegas` `b` on((`mi`.`ID_Bodega` = `b`.`ID_Bodega`))) 
            left join `proveedores` `p` on((`mi`.`ID_Proveedor` = `p`.`ID_Proveedor`))) 
        where ((`mi`.`ID_Empresa` = 1) and (`mi`.`Estado` = 'Activa') and (`cm`.`ID_TipoMovimiento` in (1,3)))
    """
}

# Tablas catálogo cuyos datos copiaremos completos
CATALOG_TABLES = [
    'empresa',
    'roles',
    'metodos_pago',
    'unidades_medida',
    'catalogo_movimientos',
    'bodegas',
    'rutas'
]

def main():
    print(f"[INFO] Iniciando creacion de la base de datos real: '{DB_TARGET}'")
    print(f"[INFO] Servidor MySQL: {conn_config['host']}:{conn_config['port']}")
    
    # 1. Conectar al servidor MySQL (sin DB específica)
    try:
        conn = mysql.connector.connect(**conn_config)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Error al conectar al servidor MySQL: {e}")
        return

    # 2. Crear base de datos destino si no existe (la volvemos a crear para limpiar intentos fallidos previos)
    try:
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_TARGET};")
        cursor.execute(f"CREATE DATABASE {DB_TARGET} CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
        print(f"[SUCCESS] Base de datos '{DB_TARGET}' recreada e inicializada limpia.")
    except Exception as e:
        print(f"[ERROR] Error al crear la base de datos destino: {e}")
        cursor.close()
        conn.close()
        return

    cursor.close()
    conn.close()

    # 3. Conectarse a la nueva base de datos para correr el export.sql
    try:
        conn_target = mysql.connector.connect(database=DB_TARGET, **conn_config)
        cursor_target = conn_target.cursor()
    except Exception as e:
        print(f"[ERROR] Error al conectar a '{DB_TARGET}': {e}")
        return

    # Desactivar revisión de llaves foráneas para poder crear las tablas en cualquier orden
    cursor_target.execute("SET FOREIGN_KEY_CHECKS = 0;")

    # Leer export.sql
    export_path = os.path.join('querys', 'export.sql')
    if not os.path.exists(export_path):
        print(f"[ERROR] No se encontro el archivo de esquema en: {export_path}")
        cursor_target.close()
        conn_target.close()
        return

    print(f"[INFO] Leyendo esquema desde {export_path}...")
    with open(export_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Dividir el archivo SQL en sentencias individuales
    statements = sql_content.split(';')
    
    print("[INFO] Creando tablas con FOREIGN_KEY_CHECKS deshabilitado...")
    created_tables_count = 0
    for stmt in statements:
        stmt_strip = stmt.strip()
        if not stmt_strip:
            continue
            
        # Saltamos cualquier declaración de vista placeholder al final del archivo
        if 'DROP TABLE IF EXISTS `vista_' in stmt_strip or 'DROP VIEW IF EXISTS `vista_' in stmt_strip:
            continue
        if 'DROP TABLE IF EXISTS `vw_' in stmt_strip or 'DROP VIEW IF EXISTS `vw_' in stmt_strip:
            continue
        if 'CREATE VIEW `vista_' in stmt_strip or 'CREATE VIEW `vw_' in stmt_strip:
            continue
        if 'character_set_client' in stmt_strip: # Saltamos configuraciones temporales de vistas
            continue
            
        try:
            cursor_target.execute(stmt_strip)
            if 'CREATE TABLE' in stmt_strip.upper():
                created_tables_count += 1
        except Exception as e:
            if "CREATE TABLE" in stmt_strip.upper():
                print(f"[WARNING] Error al ejecutar sentencia: {e}\nSentencia: {stmt_strip[:100]}...")

    print(f"[SUCCESS] Se crearon {created_tables_count} tablas en '{DB_TARGET}'.")

    # 4. Crear las vistas con sus definiciones reales completas
    print("[INFO] Creando vistas del sistema...")
    for view_name, view_sql in VIEWS_DEFINITIONS.items():
        try:
            cursor_target.execute(f"DROP VIEW IF EXISTS {view_name};")
            cursor_target.execute(view_sql)
            print(f"   [SUCCESS] Vista '{view_name}' creada exitosamente.")
        except Exception as e:
            print(f"   [ERROR] Error al crear vista '{view_name}': {e}")

    # Reactivar llaves foráneas para la estructura básica
    cursor_target.execute("SET FOREIGN_KEY_CHECKS = 1;")

    cursor_target.close()
    conn_target.close()

    # 5. Copiar datos de catálogo y el usuario Admin desde db_ferdel
    try:
        conn_source = mysql.connector.connect(database=DB_SOURCE, **conn_config)
        cursor_source = conn_source.cursor(dictionary=True)
        
        conn_target = mysql.connector.connect(database=DB_TARGET, **conn_config)
        cursor_target = conn_target.cursor()
    except Exception as e:
        print(f"[ERROR] Error al conectar a las bases de datos para migracion de datos: {e}")
        return

    print("[INFO] Migrando datos de catalogo desde la base de datos de pruebas...")

    # Desactivar temporalmente revisión de llaves foráneas para evitar problemas de orden en inserción
    cursor_target.execute("SET FOREIGN_KEY_CHECKS = 0;")

    for table in CATALOG_TABLES:
        try:
            # Leer origen
            cursor_source.execute(f"SELECT * FROM {table}")
            rows = cursor_source.fetchall()
            
            if not rows:
                print(f"   [WARNING] La tabla '{table}' esta vacia en el origen.")
                continue
                
            # Limpiar destino por si acaso
            cursor_target.execute(f"TRUNCATE TABLE {table}")
            
            # Preparar insert dinámico
            columns = list(rows[0].keys())
            placeholders = ", ".join(["%s"] * len(columns))
            insert_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Ejecutar inserts
            data_to_insert = [tuple(row[col] for col in columns) for row in rows]
            cursor_target.executemany(insert_query, data_to_insert)
            conn_target.commit()
            print(f"   [SUCCESS] Migrada tabla '{table}' ({len(rows)} registros).")
        except Exception as e:
            print(f"   [ERROR] Error al migrar tabla '{table}': {e}")

    # 6. Copiar usuario Administrador 'Admin'
    try:
        cursor_source.execute("SELECT * FROM usuarios WHERE NombreUsuario = 'Admin' OR ID_Usuario = 1 LIMIT 1")
        admin_user = cursor_source.fetchone()
        
        if admin_user:
            cursor_target.execute("TRUNCATE TABLE usuarios")
            columns = list(admin_user.keys())
            placeholders = ", ".join(["%s"] * len(columns))
            insert_query = f"INSERT INTO usuarios ({', '.join(columns)}) VALUES ({placeholders})"
            
            val = tuple(admin_user[col] for col in columns)
            cursor_target.execute(insert_query, val)
            conn_target.commit()
            print(f"   [SUCCESS] Usuario '{admin_user['NombreUsuario']}' migrado exitosamente con su contrasena encriptada.")
        else:
            print("   [WARNING] No se encontro al usuario 'Admin' o con ID 1 en la base de datos origen.")
    except Exception as e:
        print(f"   [ERROR] Error al migrar usuario Administrador: {e}")

    # Reactivar llaves foráneas
    cursor_target.execute("SET FOREIGN_KEY_CHECKS = 1;")

    cursor_source.close()
    conn_source.close()
    cursor_target.close()
    conn_target.close()

    print("\n[SUCCESS] Proceso finalizado con exito! ")
    print(f"La base de datos '{DB_TARGET}' ha sido inicializada y poblada con los datos esenciales.")
    print("Siguientes pasos:")
    print(f"1. Abre tu archivo .env y actualiza la variable DB_NAME a: DB_NAME={DB_TARGET}")
    print("2. Reinicia tu servidor Flask.")
    print("3. Inicia sesion con tus credenciales de Administrador habituales (el usuario Admin ya fue migrado).")

if __name__ == '__main__':
    main()
