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

def restore_admin():
    app = create_app()
    with app.app_context():
        try:
            with get_db_cursor(commit=True) as cursor:
                # El hash original que registramos antes de modificarlo
                old_hash = "scrypt:32768:8:1$Kkxb8FtMXk7Tv6IG$b736f360f1fc619ecad7f01a4125e9245cf7c0bc39b478eb4d65c5ff859e595cc9d2f833da606862d2ec80aae17a8d78314ab1726a2f2097e477790cdbdc5935"
                cursor.execute("""
                    UPDATE usuarios 
                    SET Contraseña = %s 
                    WHERE ID_Usuario = 1
                """, (old_hash,))
                print("✅ Hash original del administrador restaurado correctamente.")
        except Exception as e:
            print("Error:", e)

if __name__ == '__main__':
    restore_admin()
