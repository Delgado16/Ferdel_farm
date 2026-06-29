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
from werkzeug.security import check_password_hash

def check_admin():
    app = create_app()
    with app.app_context():
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, u.Estado, r.Nombre_Rol 
                    FROM usuarios u
                    LEFT JOIN roles r ON u.ID_Rol = r.ID_Rol
                    WHERE u.ID_Usuario = 1
                """)
                user = cursor.fetchone()
                if user:
                    print(f"ID: {user['ID_Usuario']}")
                    print(f"Username: {user['NombreUsuario']}")
                    print(f"Role: {user['Nombre_Rol']}")
                    print(f"Hash in DB: {user['Contraseña']}")
                    
                    test_pass = "Admin123"
                    match = check_password_hash(user['Contraseña'], test_pass)
                    print(f"Check with '{test_pass}': {match}")
                else:
                    print("User 1 not found!")
        except Exception as e:
            print("Error:", e)

if __name__ == '__main__':
    check_admin()
