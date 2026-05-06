"""
Utilidades de autenticación
"""
from werkzeug.security import check_password_hash
from flask_login import LoginManager
from config.database import get_db_cursor
from .models import User


def verify_credentials_debug(username, password):
    """
    Función de debug para verificar credenciales con logs detallados
    
    Args:
        username (str): Nombre de usuario
        password (str): Contraseña
    
    Returns:
        bool: True si las credenciales son válidas, False en caso contrario
    """
    print(f"\n🔍 DEBUG: Verificando credenciales para usuario: '{username}'")
    
    try:
        with get_db_cursor() as cursor:
            # Consulta case-insensitive para estado
            query = """
                SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol, u.Estado
                FROM usuarios u 
                JOIN roles r ON u.ID_Rol = r.ID_Rol 
                WHERE u.NombreUsuario = %s AND UPPER(u.Estado) = 'ACTIVO'
            """
            print(f"📝 Ejecutando query: {query}")
            print(f"📝 Parámetros: ({username},)")
            
            cursor.execute(query, (username,))
            user_data = cursor.fetchone()
            
            if user_data:
                print(f"✅ Usuario encontrado en BD:")
                print(f"   ID: {user_data['ID_Usuario']}")
                print(f"   Nombre: {user_data['NombreUsuario']}")
                print(f"   Rol: {user_data['Nombre_Rol']}")
                print(f"   Estado: {user_data['Estado']}")
                print(f"   Hash contraseña: {user_data['Contraseña'][:20]}...")
                
                # Verificar si la contraseña está hasheada
                is_hashed = user_data['Contraseña'].startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))
                print(f"   ¿Contraseña hasheada?: {is_hashed}")
                
                if is_hashed:
                    # Verificar contraseña hasheada
                    password_match = check_password_hash(user_data['Contraseña'], password)
                    print(f"🔐 Contraseña coincide (hash): {password_match}")
                else:
                    # Verificar contraseña en texto plano (temporal)
                    password_match = (user_data['Contraseña'] == password)
                    print(f"🔐 Contraseña coincide (texto plano): {password_match}")
                    print("⚠️ ADVERTENCIA: Contraseña en texto plano - debe ser hasheada")
                
                if password_match:
                    print("✅ Credenciales válidas")
                    return True
                else:
                    print("❌ Contraseña incorrecta")
                    return False
            else:
                print("❌ Usuario no encontrado en la base de datos")
                return False
                
    except Exception as e:
        print(f"❌ Error en verify_credentials_debug: {e}")
        return False


def load_user(user_id):
    """
    Cargar un usuario de la BD para Flask-Login
    
    Args:
        user_id (str): ID del usuario
    
    Returns:
        User: Objeto User si existe, None en caso contrario
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(""" 
                SELECT u.ID_Usuario, u.NombreUsuario, r.Nombre_Rol
                FROM usuarios u
                JOIN roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Usuario = %s AND UPPER(u.Estado) = 'ACTIVO'
            """, (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                return User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
            return None
    except Exception as e:
        print(f"Error en load_user: {e}")
        return None


def setup_login_manager(app):
    """
    Configurar Flask-Login para la aplicación
    
    Args:
        app (Flask): Instancia de la aplicación Flask
    
    Returns:
        LoginManager: Instancia configurada de LoginManager
    """
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Inicia sesión para acceder a esta página"
    login_manager.login_message_category = "info"
    
    @login_manager.user_loader
    def user_loader(user_id):
        return load_user(user_id)
    
    return login_manager