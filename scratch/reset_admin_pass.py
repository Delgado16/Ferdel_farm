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
from werkzeug.security import generate_password_hash

def reset_admin():
    app = create_app()
    with app.app_context():
        try:
            with get_db_cursor(commit=True) as cursor:
                new_pass = "admin"
                hashed = generate_password_hash(new_pass)
                cursor.execute("""
                    UPDATE usuarios 
                    SET Contraseña = %s 
                    WHERE ID_Usuario = 1
                """, (hashed,))
                print(f"✅ Contraseña del usuario 'Admin' restablecida correctamente a '{new_pass}'")
        except Exception as e:
            print("Error:", e)

if __name__ == '__main__':
    reset_admin()
