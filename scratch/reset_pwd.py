import sys
import os

# Añadir directorio actual al path
sys.path.append(os.getcwd())

from app import create_app
from config.database import get_db_cursor
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            SELECT u.ID_Usuario, u.NombreUsuario, r.Nombre_Rol, u.Estado 
            FROM usuarios u
            JOIN roles r ON u.ID_Rol = r.ID_Rol
            WHERE r.Nombre_Rol = 'Administrador' AND u.Estado = 'ACTIVO'
        """)
        print("Active Administrators in the DB:")
        admins = cursor.fetchall()
        for a in admins:
            print(a)
            
        # Reset password of the first admin to 'admin123' so we can login with it
        if admins:
            admin_id = admins[0]['ID_Usuario']
            admin_name = admins[0]['NombreUsuario']
            new_hash = generate_password_hash("admin123")
            cursor.execute("UPDATE usuarios SET Contraseña = %s WHERE ID_Usuario = %s", (new_hash, admin_id))
            print(f"Password updated for admin '{admin_name}' (ID: {admin_id}) to: admin123")
        else:
            print("No active administrators found!")
