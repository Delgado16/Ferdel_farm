from config.database import get_db_cursor
import app

def run_test():
    ctx = app.app.app_context()
    ctx.push()
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    ID_Asignacion, 
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        WHEN Tipo = 'CIERRE' THEN 0
                        ELSE Monto 
                    END), 0) as Saldo_Calculado,
                    COUNT(*) as Total_Registros
                FROM movimientos_caja_ruta
                GROUP BY ID_Asignacion
                ORDER BY ID_Asignacion DESC
                LIMIT 5
            """)
            print("=== Saldos Calculados por Asignación ===")
            for row in cursor.fetchall():
                print(row)
                
            print("\n=== Detalle última asignación ===")
            cursor.execute("SELECT ID_Asignacion FROM movimientos_caja_ruta ORDER BY ID_Asignacion DESC LIMIT 1")
            last_id = cursor.fetchone()['ID_Asignacion']
            
            cursor.execute("SELECT ID_Movimiento, Tipo, Monto, Tipo_Pago, Estado FROM movimientos_caja_ruta WHERE ID_Asignacion = %s", (last_id,))
            for row in cursor.fetchall():
                print(row)
                
    except Exception as e:
        print('ERROR:', e)
    finally:
        ctx.pop()

run_test()
