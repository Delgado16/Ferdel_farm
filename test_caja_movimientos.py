from config.database import get_db_cursor
import app

def run_test():
    ctx = app.app.app_context()
    ctx.push()
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM caja_movimientos ORDER BY ID_Movimiento DESC LIMIT 5")
            print("=== Ultimos movimientos en caja_movimientos ===")
            for row in cursor.fetchall():
                print(f"ID: {row['ID_Movimiento']}, Descripcion: {row['Descripcion']}, Monto: {row['Monto']}, Ref: {row['Referencia_Documento']}")
    except Exception as e:
        print('ERROR:', e)
    finally:
        ctx.pop()

run_test()
