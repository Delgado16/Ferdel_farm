"""
Script de migración para aplicar índices de rendimiento en la base de datos de FERDEL FARM.
Es completamente idempotente: comprueba si cada índice ya existe antes de crearlo.
No elimina tablas ni modifica tipos de datos.
"""
import os
import sys

# Agregar ruta base del proyecto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.database import get_db_cursor

INDICES_A_CREAR = [
    # (Tabla, Nombre_Indice, Columnas_SQL)
    ('facturacion', 'idx_facturacion_fecha', '(`Fecha`)'),
    ('facturacion', 'idx_facturacion_fecha_creacion', '(`Fecha_Creacion`)'),
    ('facturacion', 'idx_facturacion_estado_fecha', '(`Estado`, `Fecha`)'),
    ('facturacion', 'idx_facturacion_estado_creacion', '(`Estado`, `Fecha_Creacion`)'),

    ('facturacion_ruta', 'idx_facturacion_ruta_fecha', '(`Fecha`)'),
    ('facturacion_ruta', 'idx_facturacion_ruta_fecha_creacion', '(`Fecha_Creacion`)'),
    ('facturacion_ruta', 'idx_facturacion_ruta_asig_fecha', '(`ID_Asignacion`, `Fecha`)'),
    ('facturacion_ruta', 'idx_facturacion_ruta_estado_fecha', '(`Estado`, `Fecha`)'),
    ('facturacion_ruta', 'idx_facturacion_ruta_estado_creacion', '(`Estado`, `Fecha_Creacion`)'),

    ('cuentas_por_cobrar', 'idx_cxc_estado', '(`Estado`)'),
    ('cuentas_por_cobrar', 'idx_cxc_fecha', '(`Fecha`)'),
    ('cuentas_por_cobrar', 'idx_cxc_vencimiento', '(`Fecha_Vencimiento`)'),
    ('cuentas_por_cobrar', 'idx_cxc_num_doc', '(`Num_Documento`(50))'),
    ('cuentas_por_cobrar', 'idx_cxc_estado_vencimiento', '(`Estado`, `Fecha_Vencimiento`)'),
    ('cuentas_por_cobrar', 'idx_cxc_estado_saldo', '(`Estado`, `Saldo_Pendiente`)'),

    ('pagos_cuentascobrar', 'idx_pagos_cxc_fecha', '(`Fecha`)'),
    ('pagos_cuentascobrar', 'idx_pagos_cxc_metodo_fecha', '(`ID_MetodoPago`, `Fecha`)'),

    ('movimientos_caja_ruta', 'idx_mov_caja_ruta_fecha_estado', '(`Fecha`, `Estado`)'),
    ('movimientos_caja_ruta', 'idx_mov_caja_ruta_asig_fecha', '(`ID_Asignacion`, `Fecha`)'),

    ('gastos_generales', 'idx_gastos_fecha_estado', '(`Fecha`, `Estado`)'),
    ('gastos_generales', 'idx_gastos_tipo_fecha', '(`ID_Tipo_Gasto`, `Fecha`)'),

    ('bitacora', 'idx_bitacora_fecha', '(`Fecha`)'),
    ('bitacora', 'idx_bitacora_usuario_fecha', '(`ID_Usuario`, `Fecha`)'),
    ('bitacora', 'idx_bitacora_modulo', '(`Modulo`)'),

    ('usuarios', 'idx_usuarios_estado', '(`Estado`)'),

    ('vehiculos', 'idx_vehiculos_estado_seguro', '(`Estado`, `Fecha_Vencimiento_Seguro`)'),
]


def aplicar_indices():
    print("=" * 60)
    print("MIGRACIÓN DE ÍNDICES DE RENDIMIENTO — FERDEL FARM")
    print("=" * 60)
    
    with get_db_cursor(commit=True) as cursor:
        # Obtener índices existentes en el esquema actual
        cursor.execute("""
            SELECT TABLE_NAME, INDEX_NAME 
            FROM INFORMATION_SCHEMA.STATISTICS 
            WHERE TABLE_SCHEMA = DATABASE()
        """)
        existentes = set((r['TABLE_NAME'].lower(), r['INDEX_NAME'].lower()) for r in cursor.fetchall())
        
        creados = 0
        ya_existian = 0
        errores = 0

        for tabla, index_name, columnas in INDICES_A_CREAR:
            key = (tabla.lower(), index_name.lower())
            if key in existentes:
                print(f"  ⏭️  {tabla}.{index_name} ya existe. Omitiendo.")
                ya_existian += 1
                continue
                
            sql = f"CREATE INDEX `{index_name}` ON `{tabla}` {columnas};"
            try:
                cursor.execute(sql)
                print(f"  ✅ Creado: {tabla}.{index_name} -> {columnas}")
                creados += 1
            except Exception as e:
                print(f"  ❌ Error creando {tabla}.{index_name}: {e}")
                errores += 1

        print("-" * 60)
        print(f"Resultado: {creados} creados, {ya_existian} ya existían, {errores} errores.")
        print("=" * 60)
        return errores == 0


if __name__ == '__main__':
    aplicar_indices()

