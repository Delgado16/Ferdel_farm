import os
import sys

# Agregar el directorio raíz del proyecto a sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(root_dir, '.env'))

from app import create_app
from config.database import get_db_cursor, init_pool
from werkzeug.security import generate_password_hash

def migrate_passwords():
    print("[INFO] Iniciando migracion de contrasenas...")
    
    app = create_app()
    with app.app_context():
        try:
            with get_db_cursor(commit=True) as cursor:
                # Obtener todos los usuarios
                cursor.execute("SELECT ID_Usuario, NombreUsuario, Contraseña FROM usuarios")
                users = cursor.fetchall()
                
                print(f"[INFO] Usuarios encontrados en total: {len(users)}")
                migrated_count = 0
                
                for user in users:
                    user_id = user['ID_Usuario']
                    username = user['NombreUsuario']
                    raw_password = user['Contraseña']
                    
                    # Verificar si ya está hasheada
                    is_hashed = raw_password.startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))
                    
                    if not is_hashed:
                        print(f"[ACTION] Hashing de contrasena para usuario: '{username}' (ID: {user_id})")
                        hashed = generate_password_hash(raw_password)
                        
                        cursor.execute("""
                            UPDATE usuarios 
                            SET Contraseña = %s 
                            WHERE ID_Usuario = %s
                        """, (hashed, user_id))
                        
                        migrated_count += 1
                    else:
                        print(f"[OK] Usuario '{username}' (ID: {user_id}) ya tiene contrasena encriptada.")
                        
                print(f"\n[SUCCESS] Migracion completada exitosamente. Se actualizaron {migrated_count} usuarios.")
                
        except Exception as e:
            print(f"[ERROR] Error durante la migracion: {e}")
        finally:
            print("[INFO] Finalizando ejecucion...")

if __name__ == '__main__':
    migrate_passwords()
