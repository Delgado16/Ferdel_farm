import os
import sys

# Agregar el directorio raíz del proyecto a sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(root_dir, '.env'))

from app import create_app
from config.database import get_db_cursor

def check_bitacora():
    app = create_app()
    with app.app_context():
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT * FROM bitacora ORDER BY 1 DESC LIMIT 5")
                rows = cursor.fetchall()
                print("\n=== ULTIMAS ENTRADAS DE BITACORA ===")
                for r in rows:
                    print(r)
        except Exception as e:
            print("Error:", e)

if __name__ == '__main__':
    check_bitacora()
