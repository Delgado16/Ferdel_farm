from app import app
from config.database import get_db_cursor

with app.app_context():
    with get_db_cursor() as cursor:
        cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago WHERE LOWER(Nombre) LIKE '%cruce%' OR LOWER(Nombre) LIKE '%compensac%'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO metodos_pago (Nombre) VALUES ('Cruce de Cuentas')")
            print("Metodo 'Cruce de Cuentas' insertado.")
        else:
            print(f"Metodo ya existe: {row}")

        cursor.execute("DESCRIBE clientes")
        cols_c = [c['Field'] for c in cursor.fetchall()]
        print("Columnas clientes:", 'ID_Proveedor_Vinculado' in cols_c)

        cursor.execute("DESCRIBE proveedores")
        cols_p = [c['Field'] for c in cursor.fetchall()]
        print("Columnas proveedores:", 'ID_Cliente_Vinculado' in cols_p)
