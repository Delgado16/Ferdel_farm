from config.database import get_db_cursor
import app

def run_test():
    ctx = app.app.app_context()
    ctx.push()
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO caja_movimientos 
                (Fecha, Tipo_Movimiento, Descripcion, Monto, Referencia_Documento, ID_Usuario, Estado)
                VALUES (NOW(), 'ENTRADA', 'Test', 100.0, 'RUTA-0', 1, 'ACTIVO')
            """)
        print('SUCCESS')
    except Exception as e:
        print('ERROR:', e)
    finally:
        ctx.pop()

run_test()
