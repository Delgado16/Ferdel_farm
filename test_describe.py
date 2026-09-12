from app import create_app
from config.database import get_db_cursor

app = create_app()
with app.app_context():
    with get_db_cursor() as cursor:
        for t in ['gastos_vehiculo_detalle', 'gastos_generales', 'movimientos_caja_ruta', 'tipos_gasto', 'subcategorias_gasto', 'asignacion_vendedores', 'vehiculos']:
            print(f'=== TABLE: {t} ===')
            cursor.execute(f'DESCRIBE {t}')
            for row in cursor.fetchall():
                print(f"  {row['Field']:<25} {row['Type']:<25} {row['Null']:<6} {row['Key']:<6} {row['Default']}")
            print()
