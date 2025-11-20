from flask import Flask, flash, render_template, redirect, url_for, abort, request, session, Response, jsonify, current_app, g
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from weasyprint import HTML
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from mysql.connector import Error, pooling
import mysql.connector
import functools
from functools import wraps
from datetime import datetime
import time
import threading
import traceback
import json
import logging
import os
import secrets
from dotenv import load_dotenv
import contextlib

load_dotenv()
app = Flask(__name__)
# Configuración de la base de datos
DB_CONFIG = {
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'admin'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'database': os.environ.get('DB_NAME', 'db_ferdel'),
    'pool_name': 'ferdel_pool',
    'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
    'pool_reset_session': True,
    'autocommit': True,
    'connect_timeout': 30
}

# Inicializar connection_pool
connection_pool = None
pool_lock = threading.Lock()

def init_pool():
    """Inicializar el pool con reintentos automaticos"""
    global connection_pool
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            with pool_lock:
                connection_pool = mysql.connector.pooling.MySQLConnectionPool(**DB_CONFIG)
            print("Conexión a la base de datos establecida correctamente.")
            return True
        except Error as e:
            print(f"Intentos {attempt + 1} fallados: {e}")
            if attempt < max_retries - 1:
                time.sleep(2*(attempt + 1))  # Espera exponencial
    return False

#inicializar al inicio
init_pool()

def get_db():
    """Obtener conexión de la base de datos con manejo de errores"""
    if 'db' not in g:
        try:
            if connection_pool:
                g.db = connection_pool.get_connection()
            else:
                # Fallback a conexión simple si el pool falla
                config_simple = {k: v for k, v in DB_CONFIG.items() 
                               if k not in ['pool_name', 'pool_size','pool_reset_session']}
                g.db = mysql.connector.connect(**config_simple)
            print("Conexión a BD establecida")
            
        except pooling.PoolError as e:
            print(f"Pool agotado, usando conexion directa: {e}")
            try:
                config_simple = {k: v for k, v in DB_CONFIG.items()
                                if k not in ['pool_name','pool_size','pool_reset_session']}
                g.db = mysql.connector.connect(**config_simple)
            except Error as fallback_error:
                print(f"Fallback tambien fallo: {fallback_error}")
                g.db = None
        except Error as e:
            print(f"Error al conectar a la BD: {e}")
            g.db = None
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Cerrar conexión al final de cada request"""
    db = g.pop('db', None)
    if db is not None:
        try:
            if db.is_connected():
                db.close()
                print("Conexión a BD cerrada")
            else:
                print("Conexion ya estaba cerrada")
        except Error as e:
            print(f"Error al cerrar conexión: {e}")

@contextlib.contextmanager
def get_db_cursor(commit=False):
    """Context manager para manejar cursor automáticamente"""
    db = get_db()
    if db is None:
        raise Exception("No se pudo conectar a la base de datos")
    
    cursor = None
    try:
        if not db.is_connected():
            print("Reconectando...")
            db.reconnect(attempts=1, delay=0)
    
        cursor = db.cursor(dictionary=True)
        yield cursor
        
        if commit:
            db.commit()
            print("Cambios confirmados en la BD")

    except Exception as e:
        print(f"Error en operacion de BD: {e}")
        if commit:
            try:
                db.rollback()
                print("Rollback realizado en la BD")
            except:
                print("Error al hacer rollback")
        raise e

    finally:
        if cursor:
            try:
                cursor.close()
                print("Cursor cerrado")
            except:
                pass

def test_connection():
    """Probar la conexión a la base de datos"""
    try:
        conn = get_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            print("✅ Conexión a BD exitosa")
            return True
        else:
            print("❌ No se pudo establecer conexión a la BD")
            return False
    except Error as e:
        print(f"❌ Error al probar conexión a la BD: {e}")
        return False

def diagnose_db():
    """Diagnóstico completo de la base de datos"""
    print("\n=== DIAGNÓSTICO DE BASE DE DATOS ===")
    
    # Verificar variables de entorno
    print(f"📋 Variables de entorno:")
    print(f"   DB_USER: {os.environ.get('DB_USER')}")
    print(f"   DB_NAME: {os.environ.get('DB_NAME')}")
    print(f"   DB_HOST: {os.environ.get('DB_HOST')}")
    
    # 1. Verificar conexión
    conn = get_db()
    if not conn:
        print("❌ No se pudo conectar a la BD")
        return False
    
    try:
        # Crear cursor con dictionary=True para obtener resultados como diccionarios
        cursor = conn.cursor(buffered=True, dictionary=True)
        
        # 2. Verificar base de datos
        cursor.execute("SELECT DATABASE() as current_db")
        current_db = cursor.fetchone()['current_db']
        print(f"📊 Base de datos actual: {current_db}")
        
        # 3. Verificar tablas
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables] if tables else []
        print(f"📊 Tablas encontradas: {table_names}")
        
        # 4. Verificar tabla usuarios específicamente
        if 'usuarios' in table_names:
            cursor.execute("DESCRIBE usuarios")
            columns = cursor.fetchall()
            print("📋 Estructura de tabla usuarios:")
            for col in columns:
                print(f"   - {col['Field']}: {col['Type']}")
                
            # 5. Verificar datos en usuarios
            cursor.execute("SELECT COUNT(*) as count FROM usuarios")
            count_result = cursor.fetchone()
            user_count = count_result['count'] if count_result else 0
            print(f"👥 Usuarios en sistema: {user_count}")
            
            # 6. Mostrar algunos usuarios de ejemplo
            if user_count > 0:
                cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado, Contraseña FROM usuarios LIMIT 5")
                sample_users = cursor.fetchall()
                print("👤 Ejemplo de usuarios:")
                for user in sample_users:
                    print(f"   - {user['ID_Usuario']}: {user['NombreUsuario']} ({user['Estado']})")
                    print(f"     Contraseña: {user['Contraseña']}")
        
        # 7. Verificar tabla Roles
        if 'Roles' in table_names:
            cursor.execute("SELECT * FROM Roles")
            roles = cursor.fetchall()
            print("🎭 Roles disponibles:")
            for role in roles:
                print(f"   - {role['ID_Rol']}: {role['Nombre_Rol']}")
        
        else:
            print("❌ Tabla 'usuarios' no encontrada")
            
        cursor.close()
        return True
        
    except Error as e:
        print(f"❌ Error en diagnóstico: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verify_credentials_debug(username, password):
    """Función de debug para verificar credenciales con logs detallados"""
    print(f"\n🔍 DEBUG: Verificando credenciales para usuario: '{username}'")
    
    try:
        with get_db_cursor() as cursor:
            # Consulta case-insensitive para estado
            query = """
                SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol, u.Estado
                FROM Usuarios u 
                JOIN Roles r ON u.ID_Rol = r.ID_Rol 
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
                print(f"   Hash contraseña: {user_data['Contraseña']}")
                
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
                    print("⚠️  ADVERTENCIA: Contraseña en texto plano - debe ser hasheada")
                
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

def registrar_bitacora(id_usuario=None, modulo=None, accion=None, ip_acceso=None):
    """
    Función principal para registrar en la bitácora
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            # Si no se proporciona IP, obtenerla del request
            if ip_acceso is None and request:
                ip_acceso = request.remote_addr
            
            # Si no se proporciona usuario, usar el current_user
            if id_usuario is None and current_user.is_authenticated:
                id_usuario = current_user.id
            
            cursor.execute("""
                INSERT INTO bitacora (ID_Usuario, Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, modulo, accion, ip_acceso))
            
            print(f"Bitácora registrada: {modulo} - {accion} - Usuario: {id_usuario}")
            return True
            
    except Exception as e:
        print(f"Error al registrar en bitácora: {e}")
        return False

def bitacora_decorator(modulo):
    """
    Decorador para automatizar el registro en bitácora
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Ejecutar la función primero
            result = func(*args, **kwargs)
            
            # Registrar en bitácora después de la ejecución exitosa
            try:
                if current_user.is_authenticated:
                    registrar_bitacora(
                        modulo=modulo,
                        accion=func.__name__,
                        ip_acceso=request.remote_addr
                    )
            except Exception as e:
                print(f"Error en decorador bitácora: {e}")
            
            return result
        return wrapper
    return decorator

def registrar_login_exitoso(username, id_usuario):
    """Registrar login exitoso en bitácora"""
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH",
        accion="LOGIN_EXITOSO",
        ip_acceso=request.remote_addr
    )
    
def registrar_login_fallido(username, razon):
    """Registrar intento fallido de login"""
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO bitacora (Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s)
            """, ("AUTH", f"LOGIN_FALLIDO: {razon} - Usuario: {username}", request.remote_addr))
    except Exception as e:
        print(f"Error al registrar login fallido: {e}")

def registrar_logout(id_usuario):
    """Registrar logout en bitácora"""
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH", 
        accion="LOGOUT",
        ip_acceso=request.remote_addr
    )

# Configuración de Flask (FUERA del bloque try-except)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(24))
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
Session(app)

# Configuración de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Inicia sesión para acceder a esta página"
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, id, username, rol):
        self.id = str(id)
        self.username = username
        self.rol = rol

@login_manager.user_loader
def load_user(user_id):
    try:
        with get_db_cursor() as cursor:
            cursor.execute(""" 
                SELECT u.ID_Usuario, u.NombreUsuario, r.Nombre_Rol
                FROM Usuarios u
                JOIN Roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Usuario = %s AND UPPER(u.Estado) = 'ACTIVO'
            """, (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                return User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
            return None
    except Exception as e:
        print(f"Error en load_user: {e}")
        return None

# Decorador Personalizado
def role_requerido(requested_role):
    def decorator(f):
        @login_required
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.rol != requested_role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return role_requerido('Administrador')(f)

# Rutas de autenticaciones y autorizaciones
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    session.clear()
    
    if request.method == 'POST':
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        print(f"\n Intento de login - Usuario: '{username}', Contraseña: '{password}'")
        
        if not username:
            flash("El nombre de usuario es requerido", "danger")
            registrar_login_fallido(username,"Usuario vacio")
            return render_template('login.html')
        
        if not password:
            flash("La contraseña es requerida", "danger")
            registrar_login_fallido(username, "Contraseña vacia")
            return render_template('login.html')
        
        if len(password) < 4:
            flash("La contraseña debe tener al menos 4 caracteres", "danger")
            return render_template('login.html')
        
        # Debug: verificar credenciales con logging detallado
        credentials_valid = verify_credentials_debug(username, password)
        
        try:
            with get_db_cursor() as cursor:
                # Consulta case-insensitive para estado
                cursor.execute("""
                    SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol 
                    FROM Usuarios u 
                    JOIN Roles r ON u.ID_Rol = r.ID_Rol 
                    WHERE u.NombreUsuario = %s AND UPPER(u.Estado) = 'ACTIVO'
                """, (username,))
                
                user_data = cursor.fetchone()
                
                if user_data:
                    # Verificar si la contraseña está hasheada
                    if user_data['Contraseña'].startswith(('scrypt:', 'pbkdf2:', 'bcrypt:')):
                        # Contraseña hasheada
                        if check_password_hash(user_data['Contraseña'], password):
                            user = User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
                            login_user(user)
                            registrar_login_exitoso(username, user_data['ID_Usuario'])
                            print(f"Usuario {username} ha iniciado sesión - Rol: {user_data['Nombre_Rol']}")
                            flash(f"¡Bienvenido {user.username}!", "success")
                            return redirect(url_for('dashboard'))
                        else:
                            print("Contraseña incorrecta (hash)")
                            registrar_login_fallido(username, "contraseña incorrecta")
                            flash("Credenciales incorrectas. Por favor verifique sus datos.", "danger")
                    else:
                        # Contraseña en texto plano (temporal)
                        if user_data['Contraseña'] == password:
                            user = User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
                            login_user(user)
                            registrar_login_exitoso(username, user_data['ID_Usuario'])
                            print(f"Usuario {username} ha iniciado sesión (texto plano) - Rol: {user_data['Nombre_Rol']}")
                            flash(f"¡Bienvenido {user.username}!", "success")
                            return redirect(url_for('dashboard'))
                        else:
                            print("Contraseña incorrecta (texto plano)")
                            registrar_login_fallido(username, "contraseña incorrecta")
                            flash("Credenciales incorrectas. Por favor verifique sus datos.", "danger")
                else:
                    print("Usuario no encontrado o inactivo")
                    registrar_login_fallido(username, "contraseña no encontrado o inactivo")
                    flash("Credenciales incorrectas o usuario inactivo.", "danger")
                
        except Exception as e:
            print(f"Error en login: {e}")
            registrar_login_fallido(username, f"Error del sistema: {e}")
            flash("Error interno del sistema. Intente más tarde.", "danger")
        
        return render_template('login.html')

    return render_template('login.html')

@app.route('/reset-admin')
def reset_admin():
    """Reset completo del usuario admin"""
    try:
        with get_db_cursor() as cursor:
            # Resetear a texto plano temporalmente
            cursor.execute("""
                UPDATE Usuarios 
                SET Estado = 'Activo', 
                    Contraseña = 'Admin123$'
                WHERE ID_Usuario = 2
            """)
            
            print("✅ Admin reseteado a texto plano")
            print("   Usuario: Admin")
            print("   Contraseña: Admin123$ (texto plano)")
            
        return """
        <h1>✅ Admin reseteado</h1>
        <p>Ahora prueba iniciar sesión con:</p>
        <ul>
            <li><strong>Usuario:</strong> Admin</li>
            <li><strong>Contraseña:</strong> Admin123$</li>
        </ul>
        <p><a href="/login">Ir al login</a></p>
        """
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

# RUTAS TEMPORALES PARA FIX - ELIMINAR DESPUÉS DE USAR
@app.route('/fix-admin')
def fix_admin():
    """Ruta temporal para corregir el usuario admin - ELIMINAR DESPUÉS"""
    try:
        with get_db_cursor() as cursor:
            # 1. Corregir estado (case-insensitive)
            cursor.execute("UPDATE Usuarios SET Estado = 'Activo' WHERE ID_Usuario = 2")
            
            # 2. Crear hash válido para la contraseña
            hashed_password = generate_password_hash('Admin123$')
            cursor.execute("UPDATE Usuarios SET Contraseña = %s WHERE ID_Usuario = 2", (hashed_password,))
            
            print("✅ Usuario admin corregido:")
            print(f"   - Estado: Activo")
            print(f"   - Contraseña hash: {hashed_password}")
            print("   - Credenciales: usuario='Admin', contraseña='Admin123$'")
            
        return """
        <h1>✅ Usuario admin corregido</h1>
        <p>Ahora puedes iniciar sesión con:</p>
        <ul>
            <li><strong>Usuario:</strong> Admin</li>
            <li><strong>Contraseña:</strong> Admin123$</li>
        </ul>
        <p><a href="/login">Ir al login</a></p>
        <p style='color: red; font-weight: bold;'>⚠️ RECUERDA ELIMINAR ESTA RUTA /fix-admin DESPUÉS DE USAR</p>
        """
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

@app.route('/check-users')
def check_users():
    """Ruta temporal para ver todos los usuarios - ELIMINAR DESPUÉS"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado, Contraseña FROM Usuarios")
            users = cursor.fetchall()
            
            result = "<h1>👥 Usuarios en el sistema</h1>"
            for user in users:
                result += f"""
                <div style='border: 1px solid #ccc; padding: 10px; margin: 10px;'>
                    <strong>ID:</strong> {user['ID_Usuario']}<br>
                    <strong>Usuario:</strong> {user['NombreUsuario']}<br>
                    <strong>Estado:</strong> {user['Estado']}<br>
                    <strong>Contraseña:</strong> {user['Contraseña']}<br>
                    <strong>¿Hasheada?:</strong> {user['Contraseña'].startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))}
                </div>
                """
            
            return result + "<p><a href='/login'>Ir al login</a></p>"
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

@app.route('/diagnostico', methods=["GET"])
def diagnostico():
    """Página de diagnóstico para verificar el estado de la BD"""
    result = diagnose_db()
    return f"""
    <h1>Diagnóstico de Base de Datos</h1>
    <p>Resultado: {'✅ Éxito' if result else '❌ Fallo'}</p>
    <p>Ver logs detallados en la consola del servidor.</p>
    <p><a href="/login">Ir al login</a> | <a href="/fix-admin">Corregir admin</a> | <a href="/check-users">Ver usuarios</a></p>
    """

@app.route('/logout')
@login_required
def logout():
    registrar_logout(current_user.id)
    logout_user()
    flash("Sesion cerrada exitosamente", "info")
    return redirect(url_for('login'))

# Rutas principales
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.rol == 'Administrador':
        return render_template('admin/dashboard.html')
    elif current_user.rol == 'Vendedor':
        return render_template('vendedor/dashboard.html')
    elif current_user.rol == 'Jefe Galera':
        return render_template('jefe_galera/dashboard.html')
    else:
        abort(403)

# Dashboard por roles
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM Usuarios WHERE UPPER(Estado) = 'ACTIVO'")
            usuarios_count = cursor.fetchone()['count']
            
            return render_template('admin/dashboard.html', usuarios_count=usuarios_count)
    except Exception as e:
        flash(f"Error al cargar dashboard: {e}", "danger")
        return redirect(url_for('dashboard'))

@app.route('/vendedor/dashboard')
@login_required
def vendedor_dashboard():
    return render_template('vendedor/dashboard.html')

@app.route('/jefe_galera/dashboard')
@login_required
def jefe_galera_dashboard():
    return render_template('jefe_galera/dashboard.html')

## MODULOS DEL ADMINISTRADOR
# CATALOGOS USUARIOS
@app.route('/admin/usuarios')
@admin_required
@bitacora_decorator("USUARIOS")
def admin_usuarios():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa FROM Usuarios u
                JOIN Roles r ON u.ID_Rol = r.ID_Rol
                JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
            """)
            usuarios = cursor.fetchall()
            
            cursor.execute("SELECT * FROM Roles")
            roles = cursor.fetchall()
            
            cursor.execute("SELECT * FROM Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/usuarios.html', usuarios=usuarios, roles=roles, empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar usuarios: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/crear-usuario', methods=['POST'])
@admin_required
@bitacora_decorator("USUARIOS")
def crear_usuario():
    username = request.form.get('username')
    password = request.form.get('password')
    rol_id = request.form.get('rol_id')
    empresa_id = request.form.get('empresa_id')

    if not all([username, password, rol_id, empresa_id]):
        flash("Todos los campos son requeridos", "danger")
        return redirect(url_for('admin_usuarios'))

    hashed_password = generate_password_hash(password)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO Usuarios (NombreUsuario, Contraseña, ID_Rol, ID_Empresa, Estado)
                VALUES (%s, %s, %s, %s, 'Activo')
            """, (username, hashed_password, rol_id, empresa_id))
            registrar_bitacora(modulo="USUARIOS", accion=f"CREAR_USUARUI: {username}")
            flash("Usuario creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear usuario: {e}", "danger")
    
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/catalog/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(user_id):
    try:
        with get_db_cursor() as cursor:
            if request.method == 'GET':
                # Obtener datos del usuario a editar
                cursor.execute("""
                    SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa 
                    FROM Usuarios u
                    JOIN Roles r ON u.ID_Rol = r.ID_Rol
                    JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
                    WHERE u.ID_Usuario = %s
                """, (user_id,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    flash("Usuario no encontrado", "danger")
                    return redirect(url_for('admin_usuarios'))
                
                # Obtener roles y empresas para el formulario
                cursor.execute("SELECT * FROM Roles")
                roles = cursor.fetchall()
                
                cursor.execute("SELECT * FROM Empresa")
                empresas = cursor.fetchall()
                
                return render_template('admin/catalog/editar_usuario.html', 
                                     usuario=usuario, 
                                     roles=roles, 
                                     empresas=empresas)
            
            elif request.method == 'POST':
                # Procesar el formulario de edición
                username = request.form.get('username')
                rol_id = request.form.get('rol_id')
                empresa_id = request.form.get('empresa_id')
                estado = request.form.get('estado')
                password = request.form.get('password')
                
                if not all([username, rol_id, empresa_id, estado]):
                    flash("Todos los campos son requeridos", "danger")
                    return redirect(url_for('editar_usuario', user_id=user_id))
                
                # Construir la consulta dinámicamente
                update_fields = []
                update_values = []
                
                update_fields.append("NombreUsuario = %s")
                update_values.append(username)
                
                update_fields.append("ID_Rol = %s")
                update_values.append(rol_id)
                
                update_fields.append("ID_Empresa = %s")
                update_values.append(empresa_id)
                
                update_fields.append("Estado = %s")
                update_values.append(estado)
                
                # Si se proporcionó una nueva contraseña, actualizarla
                if password:
                    hashed_password = generate_password_hash(password)
                    update_fields.append("Contraseña = %s")
                    update_values.append(hashed_password)
                
                # Agregar el ID al final de los valores
                update_values.append(user_id)
                
                # Ejecutar la actualización
                query = f"UPDATE Usuarios SET {', '.join(update_fields)} WHERE ID_Usuario = %s"
                cursor.execute(query, update_values)
                
                flash("Usuario actualizado exitosamente", "success")
                return redirect(url_for('admin_usuarios'))
                
    except Exception as e:
        flash(f"Error al editar usuario: {e}", "danger")
        return redirect(url_for('admin_usuarios'))

# CATALOGO BITACORA
@app.route('/admin/bitacora')
@admin_required
def admin_bitacora():
    """Vista principal de la bitácora del sistema"""
    try:
        modulo = request.args.get('modulo')
        fecha_desde = request.args.get('fecha_desde')
        fecha_hasta = request.args.get('fecha_hasta')
        
        with get_db_cursor() as cursor:
            # Construir query con filtros
            query = """
                SELECT b.*, u.NombreUsuario 
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                WHERE 1=1
            """
            params = []
            
            if modulo:
                query += " AND b.Modulo = %s"
                params.append(modulo)
                
            if fecha_desde:
                query += " AND DATE(b.Fecha) >= %s"
                params.append(fecha_desde)
                
            if fecha_hasta:
                query += " AND DATE(b.Fecha) <= %s"
                params.append(fecha_hasta)
            
            query += " ORDER BY b.Fecha DESC LIMIT 200"
            
            cursor.execute(query, params)
            registros = cursor.fetchall()
            
            # Obtener módulos únicos para el dropdown
            cursor.execute("SELECT DISTINCT Modulo FROM bitacora WHERE Modulo IS NOT NULL ORDER BY Modulo")
            modulos = cursor.fetchall()
            
            return render_template('admin/bitacora.html', 
                                 registros=registros, 
                                 modulos=modulos)
            
    except Exception as e:
        flash(f"Error al cargar bitácora: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/bitacora/limpiar', methods=['POST'])
@admin_required
def limpiar_bitacora():
    """Limpiar registros antiguos de la bitácora"""
    try:
        with get_db_cursor(commit=True) as cursor:
            # Mantener solo los últimos 1000 registros
            cursor.execute("""
                DELETE FROM bitacora 
                WHERE ID_Bitacora NOT IN (
                    SELECT ID_Bitacora FROM (
                        SELECT ID_Bitacora FROM bitacora 
                        ORDER BY Fecha DESC 
                        LIMIT 1000
                    ) AS temp
                )
            """)
            
            registros_eliminados = cursor.rowcount
            registrar_bitacora(modulo="BITACORA", accion=f"LIMPIAR_BITACORA: {registros_eliminados} registros eliminados")
            
            flash(f"Bitácora limpiada exitosamente. Se eliminaron {registros_eliminados} registros antiguos.", "success")
            
    except Exception as e:
        flash(f"Error al limpiar bitácora: {e}", "danger")
    
    return redirect(url_for('admin_bitacora'))

@app.route('/admin/bitacora/exportar')
@admin_required
def exportar_bitacora():
    """Exportar bitácora a CSV"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT b.Fecha, u.NombreUsuario, b.Modulo, b.Accion, b.IP_Acceso
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                ORDER BY b.Fecha DESC
            """)
            registros = cursor.fetchall()
            
            # Crear respuesta CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Fecha', 'Usuario', 'Módulo', 'Acción', 'IP'])
            
            for registro in registros:
                writer.writerow([
                    registro['Fecha'].strftime('%Y-%m-%d %H:%M:%S'),
                    registro['NombreUsuario'] or 'Sistema',
                    registro['Modulo'] or 'N/A',
                    registro['Accion'] or 'N/A',
                    registro['IP_Acceso'] or 'N/A'
                ])
            
            # Registrar exportación
            registrar_bitacora(modulo="BITACORA", accion="EXPORTAR_BITACORA_CSV")
            
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=bitacora_sistema.csv"
            response.headers["Content-type"] = "text/csv"
            return response
            
    except Exception as e:
        flash(f"Error al exportar bitácora: {e}", "danger")
        return redirect(url_for('admin_bitacora'))

# CATALOGO CLIENTES
@app.route('/admin/catalog/client/clientes', methods=['GET'])
@admin_required
@bitacora_decorator("CLIENTES")
def admin_clientes():
    # Valores por defecto
    clientes = []
    page = 1
    per_page = 20
    total = 0
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            offset = (page - 1) * per_page
            
            # Consulta base
            base_query = """
                SELECT c.*, e.Nombre_Empresa
                FROM Clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado = 'ACTIVO' AND c.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total
            count_query = "SELECT COUNT(*) as total FROM Clientes c WHERE c.Estado = 'ACTIVO' AND c.ID_Empresa = %s"
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Obtener datos con paginación
            data_query = base_query + " ORDER BY c.Nombre LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(data_query, params)
            clientes = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/client/clientes: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los clientes. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/client/clientes.html", 
                        clientes=clientes, 
                        page=page,
                        per_page=per_page,
                        total=total,
                        search=search_query)

@app.route('/admin/catalog/client/crear-cliente', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-CREAR")
def admin_crear_cliente():
    try:
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        direccion = request.form.get("direccion", "").strip()
        ruc_cedula = request.form.get("ruc_cedula", "").strip()
        id_usuario = session.get('id_usuario',1)
        id_empresa = session.get('id_empresa', 1)

        if not nombre:
            flash("El nombre del cliente es obligatorio.", "danger")
            return redirect(url_for("admin_clientes"))
        
        if not id_usuario:
            flash("Error de autenticación. Por favor, inicie sesión nuevamente.", "danger")
            return redirect(url_for("admin_clientes"))
        
        with get_db_cursor() as cursor:
            # Verificar que la empresa existe y está activa
            cursor.execute(
                "SELECT 1 FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", 
                (id_empresa,)
            )
            empresa_activa = cursor.fetchone()
            
            if not empresa_activa:
                flash("Empresa no válida o inactiva.", "danger")
                return redirect(url_for("admin_clientes"))
            
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    "SELECT 1 FROM Clientes WHERE RUC_CEDULA = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un cliente con este RUC/Cédula", "danger")
                    return redirect(url_for("admin_clientes"))

            # Insertar nuevo cliente
            cursor.execute("""
                INSERT INTO Clientes (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, id_usuario))
            
            flash("Cliente agregado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al crear cliente: {str(e)}")
        flash("Error al guardar el cliente", "danger")
    
    return redirect(url_for("admin_clientes"))

@app.route('/admin/catalog/client/editar-cliente/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-EDITAR")
def admin_editar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente existe (sin filtrar por estado para poder reactivar)
            cursor.execute(
                """SELECT c.* 
                FROM Clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s AND e.Estado = 'Activo'""",
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin_clientes"))
            
            # MÉTODO GET - Mostrar formulario
            if request.method == 'GET':
                return render_template("admin/catalog/client/editar_clientes.html", cliente=cliente)
            
            # MÉTODO POST - Procesar formulario
            elif request.method == 'POST':
                nombre = request.form.get("nombre", "").strip()
                telefono = request.form.get("telefono", "").strip()
                direccion = request.form.get("direccion", "").strip()
                ruc_cedula = request.form.get("ruc_cedula", "").strip()
                estado = request.form.get("estado", "ACTIVO").strip()

                if not nombre:
                    flash("El nombre del cliente es obligatorio.", "danger")
                    # Redirigir de vuelta al formulario de edición
                    return render_template("admin/catalog/client/editar_clientes.html", cliente=cliente)

                # Verificar si el RUC/Cédula ya existe en otro cliente activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        "SELECT 1 FROM Clientes WHERE RUC_CEDULA = %s AND ID_Cliente != %s AND ID_Empresa = %s AND Estado = 'ACTIVO'",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro cliente activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", cliente=cliente)

                # Actualizar cliente
                cursor.execute("""
                    UPDATE Clientes 
                    SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s, Estado = %s
                    WHERE ID_Cliente = %s AND ID_Empresa = %s
                """, (nombre, telefono, direccion, ruc_cedula, estado, id, id_empresa))
                
                # Registrar en bitácora
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Cliente {accion} correctamente.", "success")
                
                return redirect(url_for("admin_clientes"))
                
    except Exception as e:
        logging.error(f"Error en edición de cliente: {str(e)}")
        flash("Error al procesar la solicitud", "danger")
        return redirect(url_for("admin_clientes"))
    
    # Fallback en caso de que no se cumpla ninguna condición anterior
    return redirect(url_for("admin_clientes"))

@app.route('/admin/catalog/client/eliminar-cliente/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-ELIMINAR")
def admin_eliminar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente pertenece a la empresa actual y está activo
            cursor.execute(
                """SELECT c.* 
                FROM Clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s AND c.Estado = 'ACTIVO' AND e.Estado = 'Activo'""",
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin_clientes"))
            
            # Eliminar (cambiar estado a INACTIVO)
            cursor.execute(
                "UPDATE Clientes SET Estado = 'INACTIVO' WHERE ID_Cliente = %s AND ID_Empresa = %s",
                (id, id_empresa)
            )
            
            flash("Cliente eliminado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al eliminar cliente: {str(e)}")
        flash("Error al eliminar el cliente", "danger")
    
    return redirect(url_for("admin_clientes"))

# CATALOGO PROVEEDORES
@app.route('/admin/catalog/proveedor/proveedores', methods=['GET'])
@admin_required
@bitacora_decorator("PROVEEDORES")
def admin_proveedores():
    # Valores por defecto
    proveedores = []
    page = 1
    per_page = 20
    total = 0
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            offset = (page - 1) * per_page
            
            # Consulta base
            base_query = """
                SELECT p.*, e.Nombre_Empresa
                FROM Proveedores p
                INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total
            count_query = "SELECT COUNT(*) as total FROM Proveedores p WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s"
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Obtener datos con paginación
            data_query = base_query + " ORDER BY p.Nombre LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(data_query, params)
            proveedores = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/proveedor/proveedores: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los proveedores. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/proveedor/proveedores.html", 
                        proveedores=proveedores, 
                        page=page,
                        per_page=per_page,
                        total=total,
                        search=search_query)
    
@app.route('/admin/catalog/proveedor/crear-proveedor', methods=['POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-CREAR")
def admin_crear_proveedor():
    try:
        nombre = request.form.get('nombre','').strip()
        telefono = request.form.get('telefono','').strip()
        direccion = request.form.get('direccion','').strip()
        ruc_cedula = request.form.get('ruc_cedula','').strip()
        id_usuario = session.get('id_usuario',1)
        id_empresa = session.get('id_empresa',1)
        
        if not nombre:
            flash("El nombre del proveedor es obligatorio","danger")
            return redirect(url_for('admin_proveedores'))
        
        
        with get_db_cursor() as cursor:
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    "SELECT 1 FROM Proveedores WHERE RUC_CEDULA = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un proveedor con este RUC/Cédula", "danger")
                    return redirect(url_for("admin_proveedores"))

            # Insertar nuevo proveedor
            cursor.execute("""
                INSERT INTO Proveedores (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, id_usuario))
            
            flash("Proveedor agregado correctamente.", "success")
    except Exception as e:
        logging.error(f"Error al crear proveedor: {str(e)}")
        flash("Error al guardar el proveedor", "danger")
    return redirect(url_for('admin_proveedores'))

@app.route('/admin/catalog/proveedor/editar-proveedor/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-EDITAR")
def admin_editar_proveedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                           SELECT p.* 
                           FROM Proveedores p
                           INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND e.Estado = 'Activo'
                           """, (id, id_empresa))
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado.", "danger")
                return redirect(url_for("admin_proveedores"))
            
            if request.method == 'GET':
                return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                       proveedor=proveedor)
                
            elif request.method == 'POST':
                nombre = request.form.get('nombre','').strip()
                telefono = request.form.get('telefono','').strip()
                direccion = request.form.get('direccion','').strip()
                ruc_cedula = request.form.get('ruc_cedula','').strip()
                estado = request.form.get('estado','ACTIVO').strip()
                
                if not nombre:
                    flash("El nombre del proveedor es obligatorio","danger")
                    return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                           proveedor=proveedor)
                
                # Verificar si el RUC/Cédula ya existe en otro proveedor activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        "SELECT 1 FROM Proveedores WHERE RUC_CEDULA = %s AND ID_Proveedor != %s AND ID_Empresa = %s AND Estado = 'ACTIVO'",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro proveedor activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                               proveedor=proveedor)
                
                # Actualizar proveedor
                cursor.execute("""
                               UPDATE Proveedores 
                               SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s, Estado = %s
                               WHERE ID_Proveedor = %s AND ID_Empresa = %s
                               """, (nombre, telefono, direccion, ruc_cedula, estado, id, id_empresa))
                
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Proveedor {accion} correctamente.","success")
                
                return redirect(url_for("admin_proveedores"))
            
    except Exception as e:
        logging.error(f"Error en edición de proveedor: {str(e)}")
        flash("Error al procesar la solicitud","danger")
        return redirect(url_for("admin_proveedores"))

    return redirect(url_for("admin_proveedores"))

@app.route('/admin/catalog/proveedor/eliminar-proveedor/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-ELIMINAR")
def admin_eliminar_probeedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            #verificar que el proveedor pertenece a la emprsa
            cursor.execute("""
                           SELECT p.*
                           FROM Proveedores p
                           INNER JOIN empresa e On p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND p.Estado = 'ACTIVO' AND e.Estado = 'Activo'
                           """, (id, id_empresa)
                        )
            
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado","danger")
                return redirect(url_for("admin_proveedores"))

            #Eliminar (cambiar estado a INACTIVO)
            cursor.execute("""
                           UPDATE Proveedores SET Estado = 'INACTIVO' 
                           WHERE ID_Proveedor = %s AND ID_Empresa = %s
                           """, (id, id_empresa)
                           )
            
            flash("Proveedor eliminado correctamente.","success")
    
    except Exception as e:
        logging.error(f"Error al eliminar proveedor: {str(e)}")
        flash("Error al eliminar el proveedor","danger")
    
    return redirect(url_for("admin_proveedores"))

# CATALOGO MEDIDAS
@app.route('/admin/catalog/medidas/unidades-medidas', methods=['GET'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS")
def admin_unidades_medidas():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_Unidad, Descripcion, Abreviatura 
                FROM unidades_medida 
                ORDER BY Descripcion DESC
            """)
            unidades = cursor.fetchall()
            return render_template('admin/catalog/medidas/unidades_medidas.html', 
                                 unidades=unidades)
    except Exception as e:
        flash(f"Error al cargar unidades de medida: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/medidas/crear-unidad', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-CREAR")
def admin_crear_unidad_medida():

    if request.method == 'POST':
        descripcion = request.form.get('descripcion','').strip()
        abreviatura = request.form.get('abreviatura','').strip()

        if not descripcion or not abreviatura:
            flash("Descripción y abreviatura son obligatorias.", "danger")
            return redirect(url_for('admin_unidades_medidas'))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO Unidades_Medida (Nombre_Unidad, Abreviatura)
                    VALUES (%s, %s)
                """, (descripcion, abreviatura))
                
                flash("Unidad de medida creada exitosamente.", "success")
                return redirect(url_for('admin_unidades_medidas'))
            
        except Exception as e:
            flash(f"Error al crear unidad de medida: {e}", "danger")
            return redirect(url_for('admin_unidades_medidas'))
    
    return render_template('admin/catalog/medidas/crear_unidad.html')

@app.route('/admin/catalog/medidas/editar-unidad/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-EDITAR")
def admin_editar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            
            if request.method == 'POST':

                descripcion = request.form.get('descripcion','').strip()
                abreviatura = request.form.get('abreviatura','').strip()

                if not descripcion or not abreviatura:
                    flash("Descripción y abreviatura son obligatorias.", "danger")
                    return redirect(url_for('admin_unidades_medidas'))
                
                cursor.execute("""
                    UPDATE Unidades_Medida
                    SET Descripcion = %s, Abreviatura = %s
                    WHERE ID_Unidad = %s
                    """, (descripcion, abreviatura, id))
                
                flash("Unidad de medida actualizada exitosamente.", "success")
                return redirect(url_for('admin_unidades_medidas'))
            
            else:

                #obtener datos actuales
                cursor.execute("""
                    SELECT ID_Unidad, Descripcion, Abreviatura
                    FROM Unidades_Medida
                    WHERE ID_Unidad = %s
                    """, (id,))
                
                unidad = cursor.fetchone()

                if not unidad:
                    flash("Unidad de medida no encontrada.", "danger")
                    return redirect(url_for('admin_unidades_medidas'))
                
                return render_template('admin/catalog/medidas/editar_unidad_medida.html',
                                        unidad=unidad)
        
    except Exception as e:
        flash(f"Error al editar unidad de medida: {e}", "danger")
        return redirect(url_for('admin_unidades_medidas'))

@app.route('/admin/catalog/medidas/unidades-medidas/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS-ELIMINAR")
def eliminar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la unidad existe
            cursor.execute("SELECT Descripcion FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            unidad = cursor.fetchone()
            
            if not unidad:
                flash("Unidad de medida no encontrada", "danger")
                return redirect(url_for('admin_unidades_medidas'))
            
            cursor.execute("DELETE FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            
            flash(f"Unidad de medida '{unidad['Descripcion']}' eliminada exitosamente", "success")
            
    except Exception as e:
        flash(f"Error al eliminar unidad de medida: {str(e)}", "danger")
    
    return redirect(url_for('admin_unidades_medidas'))

# CATALOGO CATEGORIAS
@app.route('/admin/catalog/categorias/categorias', methods=['GET'])
@admin_required
@bitacora_decorator("CATEGORIAS")
def admin_categorias():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY ID_Categoria DESC
            """)
            categorias = cursor.fetchall()
            return render_template('admin/catalog/categorias/categorias.html', 
                                 categorias=categorias)
    except Exception as e:
        flash(f"Error al cargar categorías: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/categorias/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_CREAR")
def admin_categorias_crear():
    try:
        descripcion = request.form.get('descripcion')
        
        if not descripcion:
            flash("La descripción es requerida", "danger")
            return redirect(url_for('admin_categorias'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO categorias_producto (Descripcion) 
                VALUES (%s)
            """, (descripcion,))
            
        flash("Categoría creada exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin_categorias'))

@app.route('/admin/catalog/categorias/editar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_EDITAR")
def admin_categorias_editar(id):
    try:
        descripcion = request.form.get('descripcion')
        
        if not descripcion:
            flash("La descripción es requerida", "danger")
            return redirect(url_for('admin_categorias'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE categorias_producto 
                SET Descripcion = %s 
                WHERE ID_Categoria = %s
            """, (descripcion, id))
            
        flash("Categoría actualizada exitosamente", "success")
    except Exception as e:
        flash(f"Error al actualizar categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin_categorias'))

@app.route('/admin/catalog/categorias/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_ELIMINAR")
def admin_categorias_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                DELETE FROM categorias_producto 
                WHERE ID_Categoria = %s
            """, (id,))
            
        flash("Categoría eliminada exitosamente", "success")
    except Exception as e:
        flash(f"Error al eliminar categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin_categorias'))

# CATALOGO METODOS DE PAGO
@app.route('/admin/catalog/metodospagos/metodo-pagos', methods=['GET'])
@admin_required
@bitacora_decorator("METODOS-PAGO")
def admin_metodos_pago():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM Metodos_Pago 
                ORDER BY ID_MetodoPago DESC
            """)
            metodos = cursor.fetchall()
            return render_template('admin/catalog/metodospagos/metodo_pagos.html', 
                                 metodos=metodos)
    except Exception as e:
        flash(f"Error al cargar métodos de pago: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/metodospagos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-CREAR")
def admin_metodos_pago_crear():
    try:
        nombre = request.form.get('nombre', '').strip()

        if not nombre:
            flash("El nombre del método de pago es requerido", "danger")
            return redirect(url_for('admin_metodos_pago'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Metodos_Pago (Nombre) 
                VALUES (%s)
            """, (nombre,))

        flash("Método de pago creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear método de pago: {str(e)}", "danger")
    return redirect(url_for('admin_metodos_pago'))

@app.route('/admin/catalog/metodospagos/editar/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-EDITAR")
def admin_metodos_pago_editar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # GET
            if request.method == 'GET':
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM Metodos_Pago
                    WHERE ID_MetodoPago = %s 
                               """,(id,))
                
                metodo = cursor.fetchone()

                if not metodo:
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin_metodos_pago'))
                
                return render_template('admin/catalog/metodospagos/editar_metodo_pago.html',
                                       metodo=metodo)
            
            #POST
            elif request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()

                if not nombre:
                    flash("El nombre del método de pago es requerido", "danger")
                    return redirect(url_for('admin_metodos_pago'))
                
                cursor.execute("""
                        SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s   
                        """, (id,))
                
                if not cursor.fetchone():
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin_metodos_pago'))
                
                cursor.execute("""
                    UPDATE Metodos_Pago
                    SET Nombre = %s
                    WHERE ID_MetodoPago = %s
                    """, (nombre, id))
                
                flash("Metodo d epago actualizado exitosamente", "success")
                return redirect(url_for('admin_metodos_pago'))

    except Exception as e:
        flash(f"Error al editar método de pago: {str(e)}", "danger")
        return redirect(url_for('admin_metodos_pago'))

@app.route('/admin/catalog/metodospagos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-ELIMINAR")
def admin_metodos_pago_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s
            """, (id,))

            if not cursor.fetchone():
                flash("Método de pago no encontrado.", "danger")
                return redirect(url_for('admin_metodos_pago'))
            
            cursor.execute("""
                DELETE FROM Metodos_Pago
                WHERE ID_MetodoPago = %s
            """, (id,))

        flash("Metodos de pago eliminado exitosamente", "success")
            
    except Exception as e:
        #Manejar error de integridad referencial
        if "foreing key constraint" in str(e).lower():
            flash("No se puede eliminar el método de pago porque está asociado a otros registros.", "danger")
        else:
            flash(f"Error al eliminar método de pago: {str(e)}", "danger")
    
    return redirect(url_for('admin_metodos_pago'))

#CATALOGO MOVIMINETOS DE INVENTARIO
@app.route('/admin/catalog/movimientos/movimientos-inventario', methods=['GET'])
@admin_required
@bitacora_decorator("MOVIMIENTOS-INVENTARIO")
def admin_movimientos_inventario():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT * FROM Catalogo_Movimientos ORDER BY ID_TipoMovimiento""")
            movimientos = cursor.fetchall()
            return render_template('admin/catalog/movimientos/movimientos_inventario.html', 
                                 movimientos=movimientos)
    except Exception as e:
        flash(f"Error al cargar movimientos de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/catalog/movimientos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR-MOVIMIENTO-INVENTARIO")
def admin_crear_movimiento():
    try:
        descripcion = request.form.get('descripcion')
        adicion = request.form.get('adicion')
        letra = request.form.get('letra')
        
        if not descripcion or not letra:
            flash("Descripción y Letra son campos obligatorios", "warning")
            return redirect(url_for('admin_movimientos_inventario'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO Catalogo_Movimientos (Descripcion, Adicion, Letra) VALUES (%s, %s, %s)",
                (descripcion, adicion, letra)
            )
            
        flash("Movimiento de inventario creado exitosamente", "success")
        return redirect(url_for('admin_movimientos_inventario'))
        
    except Exception as e:
        flash(f"Error al crear movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_movimientos_inventario'))
            
@app.route('/admin/catalog/movimientos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR-MOVIMIENTO-INVENTARIO")
def admin_editar_movimiento(id):
    try:
        if request.method == 'POST':
            descripcion = request.form.get('descripcion')
            adicion = request.form.get('adicion')
            letra = request.form.get('letra')
            
            if not descripcion or not letra:
                flash("Descripción y Letra son campos obligatorios", "warning")
                return redirect(url_for('admin_editar_movimiento', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE Catalogo_Movimientos SET Descripcion = %s, Adicion = %s, Letra = %s WHERE ID_TipoMovimiento = %s",
                    (descripcion, adicion, letra, id)
                )
                
            flash("Movimiento de inventario actualizado exitosamente", "success")
            return redirect(url_for('admin_movimientos_inventario'))
        
        # GET - Cargar datos del movimiento
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin_movimientos_inventario'))
                
        return render_template('admin/catalog/movimientos/editar_movimiento.html', movimiento=movimiento)
        
    except Exception as e:
        flash(f"Error al editar movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_movimientos_inventario'))

@app.route('/admin/catalog/movimientos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR-MOVIMIENTO-INVENTARIO")
def admin_eliminar_movimiento(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si el movimiento existe
            cursor.execute("SELECT * FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin_movimientos_inventario'))
            
            # Eliminar el movimiento
            cursor.execute("DELETE FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (id,))
            
        flash("Movimiento de inventario eliminado exitosamente", "success")
        
    except Exception as e:
        flash(f"Error al eliminar movimiento de inventario: {str(e)}", "danger")
    
    return redirect(url_for('admin_movimientos_inventario'))

# MODULO BODEGA
@app.route('/admin/bodega', methods=['GET'])
@admin_required
@bitacora_decorator("BODEGA")
def admin_bodega():
    try:
        with get_db_cursor() as cursor:
            # Obtener bodegas con información de empresa
            cursor.execute("""
                SELECT b.*, e.Nombre_Empresa 
                FROM Bodegas b
                INNER JOIN Empresa e ON b.ID_Empresa = e.ID_Empresa
                ORDER BY b.ID_Bodega DESC
            """)
            bodegas = cursor.fetchall()
            
            # Obtener lista de empresas para el modal de creación
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM Empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/bodega.html', 
                                 bodegas=bodegas,
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodegas: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/bodega/crear', methods=['POST'])
@admin_required
@bitacora_decorator("BODEGA-CREAR")
def admin_bodega_crear():
    try:
        nombre = request.form.get('nombre', '').strip()
        ubicacion = request.form.get('ubicacion', '').strip()
        id_empresa = request.form.get('id_empresa')

        if not nombre:
            flash("El nombre de la bodega es requerido", "danger")
            return redirect(url_for('admin_bodega'))
        
        if not id_empresa:
            flash("La empresa es requerida", "danger")
            return redirect(url_for('admin_bodega'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Bodegas (Nombre, Ubicacion, ID_Empresa) 
                VALUES (%s, %s, %s)
            """, (nombre, ubicacion, id_empresa))

        flash("Bodega creada exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear bodega: {str(e)}", "danger")
    return redirect(url_for('admin_bodega'))

@app.route('/admin/bodega/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("BODEGA_EDITAR")
def admin_editar_bodega(id):
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        ubicacion = request.form.get('ubicacion')
        id_empresa = request.form.get('id_empresa')
        estado = request.form.get('estado', 'activa')
        
        if not nombre:
            flash("El nombre de la bodega es obligatorio", "danger")
            return redirect(url_for('admin_editar_bodega', id=id))
        
        if not id_empresa:
            flash("La empresa es obligatoria", "danger")
            return redirect(url_for('admin_editar_bodega', id=id))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE Bodegas SET Nombre = %s, Ubicacion = %s, Estado = %s, ID_Empresa = %s WHERE ID_Bodega = %s",
                    (nombre, ubicacion, estado, id_empresa, id)
                )
                flash("Bodega actualizada exitosamente", "success")
                return redirect(url_for('admin_bodega'))
        except Exception as e:
            flash(f"Error al actualizar bodega: {str(e)}", "danger")
            return redirect(url_for('admin_editar_bodega', id=id))
    
    # GET - Cargar datos de la bodega y empresas
    try:
        with get_db_cursor() as cursor:
            # Obtener datos de la bodega
            cursor.execute("SELECT * FROM Bodegas WHERE ID_Bodega = %s", (id,))
            bodega = cursor.fetchone()
            
            if not bodega:
                flash("Bodega no encontrada", "danger")
                return redirect(url_for('admin_bodega'))
            
            # Obtener lista de empresas para el dropdown
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM Empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/editar_bodega.html', 
                                 bodega=bodega, 
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodega: {str(e)}", "danger")
        return redirect(url_for('admin_bodega'))

#CATALOGO PRODUCTOS - BODEGA
@app.route('/admin/bodega/productos', methods=['GET'])
@admin_required
@bitacora_decorator("PRODUCTOS")
def admin_productos():
    try:
        with get_db_cursor() as cursor:
            # Consulta de productos CORREGIDA - Usando las existencias de la tabla Productos
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    p.Unidad_Medida,
                    um.Descripcion as Nombre_Unidad,
                    um.Abreviatura,
                    p.Existencias as Existencias,  -- ← USAR EXISTENCIAS DIRECTAMENTE DE PRODUCTOS
                    p.Estado,
                    p.ID_Categoria,
                    cp.Descripcion as Nombre_Categoria,
                    p.Precio_Venta,
                    p.ID_Empresa,
                    e.Nombre_Empresa,
                    p.Fecha_Creacion,
                    p.Usuario_Creador,
                    u.NombreUsuario as Usuario_Creador_Nombre,
                    p.Stock_Minimo,
                    -- Información adicional de bodegas (opcional)
                    (SELECT COUNT(*) FROM Inventario_Bodega ib WHERE ib.ID_Producto = p.ID_Producto) as Bodegas_Con_Stock
                FROM Productos p
                LEFT JOIN Unidades_Medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                -- ELIMINAMOS el LEFT JOIN con Inventario_Bodega para evitar problemas
                WHERE p.Estado = 1  -- Solo productos activos
                ORDER BY p.ID_Producto DESC
            """)
            productos = cursor.fetchall()
            
            # Resto de tu código para obtener categorías, unidades, etc...
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto")
            categorias = cursor.fetchall()
            
            cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM Unidades_Medida")
            unidades = cursor.fetchall()
            
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
            cursor.execute("""
                SELECT b.ID_Bodega, b.Nombre, b.ID_Empresa, e.Nombre_Empresa 
                FROM Bodegas b 
                JOIN empresa e ON b.ID_Empresa = e.ID_Empresa 
                WHERE b.Estado = 'activa'
                ORDER BY e.Nombre_Empresa, b.Nombre
            """)
            bodegas = cursor.fetchall()
            
            return render_template('admin/bodega/producto/productos.html', 
                                 productos=productos,
                                 categorias=categorias,
                                 unidades=unidades,
                                 empresas=empresas,
                                 bodegas=bodegas)
    except Exception as e:
        flash(f'Error al cargar productos: {str(e)}', 'error')
        return render_template('admin/bodega/producto/productos.html',
                                productos=[], 
                                categorias=[], 
                                unidades=[], 
                                empresas=[],
                                bodegas=[])
        
@app.route('/admin/bodega/productos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PRODUCTO")
def admin_crear_producto():
    try:
        # Obtener datos del formulario
        cod_producto = request.form.get('COD_Producto')
        descripcion = request.form.get('Descripcion')
        unidad_medida = request.form.get('Unidad_Medida')
        id_categoria = request.form.get('ID_Categoria')
        precio_venta = request.form.get('Precio_Venta')
        id_empresa = request.form.get('ID_Empresa', 1)
        stock_minimo = request.form.get('Stock_Minimo', 5)
        cantidad_inicial = request.form.get('Cantidad_Inicial')
        id_bodega = request.form.get('ID_Bodega')
        usuario_creador = session.get('id_usuario', 1)

        # Validaciones básicas
        if not descripcion or not unidad_medida or not id_categoria:
            flash('Descripción, unidad de medida y categoría son campos obligatorios', 'error')
            return redirect(url_for('admin_productos'))

        # Validar que se especifique bodega
        if not id_bodega:
            flash('Debe seleccionar una bodega para el inventario inicial', 'error')
            return redirect(url_for('admin_productos'))

        # Validar cantidad inicial
        try:
            cantidad_inicial = float(cantidad_inicial) if cantidad_inicial else 0
            if cantidad_inicial < 0:
                flash('La cantidad inicial no puede ser negativa', 'error')
                return redirect(url_for('admin_productos'))
        except (ValueError, TypeError):
            cantidad_inicial = 0

        with get_db_cursor(commit=True) as cursor:
            # Verificar si el código de producto ya existe (solo si se proporciona código)
            if cod_producto:
                cursor.execute("SELECT ID_Producto FROM Productos WHERE COD_Producto = %s", (cod_producto,))
                if cursor.fetchone():
                    flash('El código de producto ya existe', 'error')
                    return redirect(url_for('admin_productos'))

            # Verificar que la bodega existe y está activa
            cursor.execute("""
                SELECT ID_Bodega FROM Bodegas 
                WHERE ID_Bodega = %s AND Estado = 'activa'
            """, (id_bodega,))
            if not cursor.fetchone():
                flash('La bodega seleccionada no es válida', 'error')
                return redirect(url_for('admin_productos'))

            # Insertar nuevo producto - CORREGIDO según tu estructura
            cursor.execute("""
                INSERT INTO Productos (
                    COD_Producto, Descripcion, Unidad_Medida, ID_Categoria, 
                    Precio_Venta, ID_Empresa, Stock_Minimo, Usuario_Creador, Estado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cod_producto, descripcion, unidad_medida, id_categoria,
                precio_venta, id_empresa, stock_minimo, usuario_creador, 1  # Estado = 1 (activo)
            ))

            # Obtener el ID del producto recién creado
            producto_id = cursor.lastrowid

            # Insertar en Inventario_Bodega con la cantidad inicial
            cursor.execute("""
                INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
            """, (id_bodega, producto_id, cantidad_inicial))

        flash(f'Producto creado exitosamente con {cantidad_inicial} unidades en inventario', 'success')
        
    except Exception as e:
        flash(f'Error al crear producto: {str(e)}', 'error')
    
    return redirect(url_for('admin_productos'))

@app.route('/admin/bodegas/por-empresa/<int:id_empresa>')
@admin_required
def obtener_bodegas_por_empresa(id_empresa):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 'activa'
                ORDER BY Nombre
            """, (id_empresa,))
            bodegas = cursor.fetchall()
        
        return jsonify({
            'bodegas': bodegas
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/bodega/productos/editar/<int:id_producto>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_PRODUCTO")
def admin_editar_producto(id_producto):
    try:
        if request.method == 'POST':
            # ========== PROCESAR FORMULARIO POST ==========
            # Obtener datos del formulario
            cod_producto = request.form.get('COD_Producto', '').strip()
            descripcion = request.form.get('Descripcion', '').strip()
            unidad_medida = request.form.get('Unidad_Medida')
            id_categoria = request.form.get('ID_Categoria')
            precio_venta = request.form.get('Precio_Venta', 0)
            id_empresa = request.form.get('ID_Empresa')
            stock_minimo = request.form.get('Stock_Minimo', 5)
            estado = request.form.get('Estado', 1)

            # Validaciones
            if not descripcion:
                flash('La descripción es obligatoria', 'error')
                return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            if not unidad_medida or not id_categoria or not id_empresa:
                flash('Unidad de medida, categoría y empresa son campos obligatorios', 'error')
                return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            # Convertir valores numéricos
            try:
                precio_venta = float(precio_venta) if precio_venta else 0
                stock_minimo = float(stock_minimo) if stock_minimo else 5
                estado = int(estado) if estado else 1
                
                # Validar valores positivos
                if precio_venta < 0:
                    flash('El precio de venta no puede ser negativo', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))
                    
                if stock_minimo < 0:
                    flash('El stock mínimo no puede ser negativo', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))
                    
            except (ValueError, TypeError):
                flash('Error en los valores numéricos', 'error')
                return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            with get_db_cursor(commit=True) as cursor:
                # Verificar si el código de producto ya existe en otro producto
                if cod_producto:
                    cursor.execute("""
                        SELECT ID_Producto FROM Productos 
                        WHERE COD_Producto = %s AND ID_Producto != %s
                    """, (cod_producto, id_producto))
                    if cursor.fetchone():
                        flash('El código de producto ya existe en otro producto', 'error')
                        return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                # Verificar que las referencias existan
                cursor.execute("SELECT ID_Unidad FROM Unidades_Medida WHERE ID_Unidad = %s", (unidad_medida,))
                if not cursor.fetchone():
                    flash('La unidad de medida seleccionada no existe', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Categoria FROM categorias_producto WHERE ID_Categoria = %s", (id_categoria,))
                if not cursor.fetchone():
                    flash('La categoría seleccionada no existe', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", (id_empresa,))
                if not cursor.fetchone():
                    flash('La empresa seleccionada no existe o está inactiva', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                # Actualizar producto
                cursor.execute("""
                    UPDATE Productos SET
                        COD_Producto = %s,
                        Descripcion = %s,
                        Unidad_Medida = %s,
                        ID_Categoria = %s,
                        Precio_Venta = %s,
                        ID_Empresa = %s,
                        Stock_Minimo = %s,
                        Estado = %s
                    WHERE ID_Producto = %s
                """, (
                    cod_producto or None,  # Guardar como NULL si está vacío
                    descripcion, 
                    unidad_medida, 
                    id_categoria,
                    precio_venta, 
                    id_empresa, 
                    stock_minimo, 
                    estado, 
                    id_producto
                ))

                # Verificar si se actualizó algún registro
                if cursor.rowcount == 0:
                    flash('No se pudo actualizar el producto. Puede que no exista.', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            flash('Producto actualizado exitosamente', 'success')
            return redirect(url_for('admin_productos'))

        else:
            # ========== CARGAR FORMULARIO GET ==========
            with get_db_cursor() as cursor:
                # Obtener el producto específico
                cursor.execute("""
                    SELECT 
                        p.ID_Producto,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida,
                        um.Descripcion as Nombre_Unidad,
                        um.Abreviatura,
                        p.Existencias,  -- EXISTENCIAS GLOBALES
                        p.Estado,
                        p.ID_Categoria,
                        cp.Descripcion as Nombre_Categoria,
                        p.Precio_Venta,
                        p.ID_Empresa,
                        e.Nombre_Empresa,
                        p.Fecha_Creacion,
                        p.Usuario_Creador,
                        u.NombreUsuario as Usuario_Creador_Nombre,
                        p.Stock_Minimo
                    FROM Productos p
                    LEFT JOIN Unidades_Medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                    LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                    LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                    WHERE p.ID_Producto = %s
                """, (id_producto,))
                producto = cursor.fetchone()
                
                if not producto:
                    flash('Producto no encontrado', 'error')
                    return redirect(url_for('admin_productos'))
                
                # Obtener datos para los dropdowns
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto")
                categorias = cursor.fetchall()
                
                cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM Unidades_Medida")
                unidades = cursor.fetchall()
                
                cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
                empresas = cursor.fetchall()
                
                # CONSULTA PARA INVENTARIO POR BODEGA
                cursor.execute("""
                    SELECT 
                        b.ID_Bodega, 
                        b.Nombre as Nombre_Bodega,
                        e.Nombre_Empresa,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM Bodegas b
                    JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                    LEFT JOIN Inventario_Bodega ib ON b.ID_Bodega = ib.ID_Bodega AND ib.ID_Producto = %s
                    WHERE b.Estado = 'activa'
                    ORDER BY e.Nombre_Empresa, b.Nombre
                """, (id_producto,))
                inventario_bodegas = cursor.fetchall()
                
                from datetime import datetime
                fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
                
                # DEBUG: Verificar qué datos estamos enviando al template
                print("DEBUG - Producto:", producto)
                print("DEBUG - Existencias:", producto['Existencias'] if producto else 'No encontrado')
                
                return render_template('admin/bodega/producto/editar_producto.html', 
                                     producto=producto,
                                     categorias=categorias,
                                     unidades=unidades,
                                     empresas=empresas,
                                     inventario_bodegas=inventario_bodegas,
                                     fecha_actual=fecha_actual)
                
    except Exception as e:
        flash(f'Error al procesar producto: {str(e)}', 'error')
        return redirect(url_for('admin_productos'))
    
@app.route('/admin/productos/desactivar/<int:id_producto>', methods=['POST'])
def admin_desactivar_producto(id_producto):
    try:
        # Lógica para desactivar el producto
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE Productos SET Estado = 0 WHERE ID_Producto = %s", (id_producto,))
        flash('Producto desactivado correctamente', 'success')
    except Exception as e:
        flash(f'Error al desactivar producto: {str(e)}', 'error')
    return redirect(url_for('admin_productos'))

@app.route('/admin/productos/activar/<int:id_producto>', methods=['POST'])
def admin_activar_producto(id_producto):
    try:
        # Lógica para activar el producto
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE Productos SET Estado = 1 WHERE ID_Producto = %s", (id_producto,))
        flash('Producto activado correctamente', 'success')
    except Exception as e:
        flash(f'Error al activar producto: {str(e)}', 'error')
    return redirect(url_for('admin_productos'))

#MODULO PRODUCTOS - COMPRAS
@app.route('/admin/compras/compras-entradas', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS")
def admin_compras_entradas():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    p.Nombre as Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Fecha_Creacion,
                    mi.Estado,
                    (SELECT COUNT(*) FROM Detalle_Movimientos_Inventario dmi 
                     WHERE dmi.ID_Movimiento = mi.ID_Movimiento) as Total_Productos,
                    (SELECT SUM(Subtotal) FROM Detalle_Movimientos_Inventario dmi 
                     WHERE dmi.ID_Movimiento = mi.ID_Movimiento) as Total_Compra
                FROM Movimientos_Inventario mi
                LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE cm.Adicion = 'ENTRADA' OR cm.Letra = 'E'
                ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
            """)
            entradas = cursor.fetchall()
            return render_template('admin/compras/compras_entradas.html', 
                                 entradas=entradas)
    except Exception as e:
        flash(f'Error al cargar entradas de compras: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/compras/compras-entradas/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-CREAR")
def admin_crear_compra():
    try:
        if request.method == 'GET':
            with get_db_cursor(True) as cursor:
                # Obtener tipos de movimiento de entrada/compra
                cursor.execute("""
                SELECT *
                FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = 1
                """)
                tipos_movimiento = cursor.fetchall()
                
                # Obtener proveedores activos
                cursor.execute("SELECT ID_Proveedor, Nombre FROM Proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
                proveedores = cursor.fetchall()
                
                # Obtener bodegas activas
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                # Obtener categorías de productos
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                # Obtener productos activos CON PRECIO_VENTA (CORREGIDO)
                cursor.execute("""
                    SELECT p.ID_Producto, p.COD_Producto, p.Descripcion, p.Existencias, 
                           p.Precio_Venta, p.ID_Categoria, c.Descripcion as Categoria
                    FROM Productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE p.Estado = 1
                    ORDER BY c.Descripcion, p.Descripcion
                """)
                productos = cursor.fetchall()
                
                return render_template('admin/compras/crear_compra.html',
                                    tipos_movimiento=tipos_movimiento,
                                    proveedores=proveedores,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias)
        
        elif request.method == 'POST':
            # (MANTENER TU LÓGICA POST EXISTENTE)
            # Obtener datos del formulario
            id_tipo_movimiento = request.form.get('id_tipo_movimiento')
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            id_usuario_creacion = request.form.get('id_usuario_creacion')
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            costos_unitarios = request.form.getlist('costos_unitarios[]')
            precios_unitarios = request.form.getlist('precios_unitarios[]')
            lotes = request.form.getlist('lotes[]')
            fechas_vencimiento = request.form.getlist('fechas_vencimiento[]')
            
            print(f"Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_creacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin_crear_compra'))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin_crear_compra'))
            
            # Construir lista de productos
            for i in range(len(producto_ids)):
                if producto_ids[i] and cantidades[i] and costos_unitarios[i]:
                    cantidad = round(float(cantidades[i]), 2)
                    costo_unitario = round(float(costos_unitarios[i]), 2)
                    precio_unitario = round(float(precios_unitarios[i]) if precios_unitarios[i] and precios_unitarios[i] != '' else costo_unitario, 2)
                    
                    productos.append({
                        'id_producto': producto_ids[i],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'precio_unitario': precio_unitario,
                        'lote': lotes[i] if i < len(lotes) and lotes[i] != '' else None,
                        'fecha_vencimiento': fechas_vencimiento[i] if i < len(fechas_vencimiento) and fechas_vencimiento[i] != '' else None
                    })
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_creacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin_crear_compra'))
            
            with get_db_cursor() as cursor:
                # Calcular total de la compra
                total_compra = sum(
                    producto['cantidad'] * producto['costo_unitario'] 
                    for producto in productos
                )
                
                # Insertar movimiento principal
                cursor.execute("""
                    INSERT INTO Movimientos_Inventario (
                        ID_TipoMovimiento, N_Factura_Externa, Fecha, ID_Proveedor, 
                        Tipo_Compra, Observacion, ID_Empresa, ID_Bodega, 
                        ID_Usuario_Creacion, ID_Usuario_Modificacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_proveedor if id_proveedor else None,
                    tipo_compra,
                    observacion,
                    session.get('id_empresa', 1),
                    id_bodega,
                    id_usuario,
                    id_usuario
                ))
                
                id_movimiento = cursor.lastrowid
                print(f"Movimiento creado con ID: {id_movimiento}")
                
                # Insertar detalles del movimiento
                for producto in productos:
                    subtotal = round(producto['cantidad'] * producto['costo_unitario'], 2)
                    
                    cursor.execute("""
                        INSERT INTO Detalle_Movimientos_Inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                            Precio_Unitario, Subtotal, Lote, Fecha_Vencimiento, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['costo_unitario'],
                        producto['precio_unitario'],
                        subtotal,
                        producto['lote'],
                        producto['fecha_vencimiento'],
                        id_usuario
                    ))
                    
                    # Actualizar existencias del producto
                    cursor.execute("""
                        UPDATE Productos 
                        SET Existencias = Existencias + %s 
                        WHERE ID_Producto = %s
                    """, (producto['cantidad'], producto['id_producto']))
                
                # CREAR CUENTA POR PAGAR SI ES CRÉDITO
                if tipo_compra == 'CREDITO' and id_proveedor:
                    if not fecha_vencimiento:
                        from datetime import datetime, timedelta
                        fecha_compra = datetime.strptime(fecha, '%Y-%m-%d')
                        fecha_vencimiento = (fecha_compra + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    cursor.execute("""
                        INSERT INTO Cuentas_Por_Pagar (
                            ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                            Saldo_Pendiente, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        fecha,
                        id_proveedor,
                        n_factura_externa or '',
                        observacion or 'Compra a crédito',
                        fecha_vencimiento,
                        id_tipo_movimiento,
                        total_compra,
                        session.get('id_empresa', 1),
                        total_compra,
                        id_usuario
                    ))
                
                flash('Compra creada exitosamente', 'success')
                return redirect(url_for('admin_compras_entradas'))            
    except Exception as e:
        print(f"Error completo al crear compra: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Error al crear compra: {str(e)}', 'error')
        return redirect(url_for('admin_crear_compra'))

# RUTA AUXILIAR PARA PRODUCTOS POR CATEGORÍA (CORREGIDA PARA DICCIONARIOS)
@app.route('/admin/compras/productos-por-categoria/<int:id_categoria>')
@admin_required
def obtener_productos_por_categoria_compra(id_categoria):
    """
    Endpoint para obtener productos filtrados por categoría - CORREGIDO
    """
    try:
        with get_db_cursor(True) as cursor:
            if id_categoria == 0:  # Todas las categorías
                cursor.execute("""
                    SELECT ID_Producto, COD_Producto, Descripcion, Existencias,
                           Precio_Venta, ID_Categoria
                    FROM Productos 
                    WHERE Estado = 1
                    ORDER BY Descripcion
                """)
            else:
                cursor.execute("""
                    SELECT ID_Producto, COD_Producto, Descripcion, Existencias,
                           Precio_Venta, ID_Categoria
                    FROM Productos 
                    WHERE Estado = 1 AND ID_Categoria = %s
                    ORDER BY Descripcion
                """, (id_categoria,))
            
            productos = cursor.fetchall()
            print(f"✅ Productos encontrados: {len(productos)} para categoría {id_categoria}")
            
            productos_list = []
            for producto in productos:
                # USAR DICCIONARIOS (porque dictionary=True)
                productos_list.append({
                    'id': producto['ID_Producto'],
                    'codigo': producto['COD_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']) if producto['Existencias'] is not None else 0,
                    'precio_venta': float(producto['Precio_Venta']) if producto['Precio_Venta'] is not None else 0,
                    'id_categoria': producto['ID_Categoria']
                })
            
            print(f"📦 Productos procesados exitosamente: {len(productos_list)}")
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener productos por categoría: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# RUTA AUXILIAR PARA TODOS LOS PRODUCTOS (CORREGIDA PARA DICCIONARIOS)
@app.route('/admin/compras/todos-los-productos')
@admin_required
def obtener_todos_los_productos_compra():
    """
    Endpoint para obtener todos los productos - CORREGIDO
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Producto, COD_Producto, Descripcion, Existencias,
                       Precio_Venta, ID_Categoria
                FROM Productos 
                WHERE Estado = 1
                ORDER BY Descripcion
            """)
            
            productos = cursor.fetchall()
            print(f"✅ Todos los productos encontrados: {len(productos)}")
            
            productos_list = []
            for producto in productos:
                # USAR DICCIONARIOS (porque dictionary=True)
                productos_list.append({
                    'id': producto['ID_Producto'],
                    'codigo': producto['COD_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']) if producto['Existencias'] is not None else 0,
                    'precio_venta': float(producto['Precio_Venta']) if producto['Precio_Venta'] is not None else 0,
                    'id_categoria': producto['ID_Categoria']
                })
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener todos los productos: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# RUTA PARA CATEGORÍAS (CORREGIDA PARA DICCIONARIOS)
@app.route('/admin/compras/categorias-productos')
@admin_required
def obtener_categorias_productos_compra():
    """
    Endpoint para obtener todas las categorías
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
            categorias = cursor.fetchall()
            
            categorias_list = []
            for categoria in categorias:
                # USAR DICCIONARIOS (porque dictionary=True)
                categorias_list.append({
                    'id': categoria['ID_Categoria'],
                    'descripcion': categoria['Descripcion']
                })
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f"Error al obtener categorías: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/compras/compras-entradas/editar/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-EDITAR")
def admin_editar_compra(id_movimiento):
    try:
        if request.method == 'GET':
            with get_db_cursor(True) as cursor:
                # Obtener datos del movimiento principal
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.ID_TipoMovimiento,
                        mi.N_Factura_Externa,
                        mi.Fecha,
                        mi.ID_Proveedor,
                        mi.Tipo_Compra,
                        mi.Observacion,
                        mi.ID_Bodega,
                        mi.ID_Usuario_Creacion,
                        cm.Descripcion as Tipo_Movimiento_Desc,
                        (SELECT SUM(Subtotal) FROM Detalle_Movimientos_Inventario 
                         WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Compra,
                        mi.Estado
                    FROM Movimientos_Inventario mi
                    LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE mi.ID_Movimiento = %s AND mi.Estado = 1
                """, (id_movimiento,))
                
                movimiento = cursor.fetchone()
                
                if not movimiento:
                    flash('Compra no encontrada o ha sido anulada', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                # Obtener detalles del movimiento
                cursor.execute("""
                    SELECT 
                        dmi.ID_Detalle_Movimiento,
                        dmi.ID_Producto,
                        p.COD_Producto,
                        p.Descripcion as Producto_Desc,
                        p.Existencias,
                        dmi.Cantidad,
                        dmi.Costo_Unitario,
                        dmi.Precio_Unitario,
                        dmi.Subtotal,
                        dmi.Lote,
                        dmi.Fecha_Vencimiento
                    FROM Detalle_Movimientos_Inventario dmi
                    INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE dmi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                detalles = cursor.fetchall()
                
                # Obtener tipos de movimiento de entrada/compra
                cursor.execute("""
                    SELECT ID_TipoMovimiento, Descripcion, Letra, Adicion
                    FROM catalogo_movimientos 
                    WHERE Adicion = 'ENTRADA' OR Letra = 'E'
                    ORDER BY Descripcion
                """)
                tipos_movimiento = cursor.fetchall()
                
                # Obtener proveedores activos
                cursor.execute("SELECT ID_Proveedor, Nombre FROM Proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
                proveedores = cursor.fetchall()
                
                # Obtener bodegas activas
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                # Obtener categorías de productos (NUEVO - AGREGADO)
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                # Obtener productos activos CON PRECIO_VENTA (MODIFICADO)
                cursor.execute("""
                    SELECT p.ID_Producto, p.COD_Producto, p.Descripcion, p.Existencias,
                           p.Precio_Venta, p.ID_Categoria, c.Descripcion as Categoria
                    FROM Productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE p.Estado = 1
                    ORDER BY c.Descripcion, p.Descripcion
                """)
                productos = cursor.fetchall()
                
                # Verificar si existe cuenta por pagar
                cursor.execute("""
                    SELECT ID_Cuenta, Saldo_Pendiente, Monto_Movimiento
                    FROM Cuentas_Por_Pagar 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento,))
                cuenta_por_pagar = cursor.fetchone()
                
                return render_template('admin/compras/editar_compra.html',
                                    movimiento=movimiento,
                                    detalles=detalles,
                                    tipos_movimiento=tipos_movimiento,
                                    proveedores=proveedores,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias,  # NUEVO PARÁMETRO
                                    cuenta_por_pagar=cuenta_por_pagar)
        
        elif request.method == 'POST':
            # Obtener datos del formulario
            id_tipo_movimiento = request.form.get('id_tipo_movimiento')
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            id_usuario_modificacion = request.form.get('id_usuario_modificacion')
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            costos_unitarios = request.form.getlist('costos_unitarios[]')
            precios_unitarios = request.form.getlist('precios_unitarios[]')
            lotes = request.form.getlist('lotes[]')
            fechas_vencimiento = request.form.getlist('fechas_vencimiento[]')
            
            print(f"[EDIT] Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_modificacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))
            
            # Construir lista de productos
            for i in range(len(producto_ids)):
                if producto_ids[i] and cantidades[i] and costos_unitarios[i]:
                    cantidad = round(float(cantidades[i]), 2)
                    costo_unitario = round(float(costos_unitarios[i]), 2)
                    precio_unitario = round(float(precios_unitarios[i]) if precios_unitarios[i] and precios_unitarios[i] != '' else costo_unitario, 2)
                    
                    productos.append({
                        'id_producto': producto_ids[i],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'precio_unitario': precio_unitario,
                        'lote': lotes[i] if i < len(lotes) and lotes[i] != '' else None,
                        'fecha_vencimiento': fechas_vencimiento[i] if i < len(fechas_vencimiento) and fechas_vencimiento[i] != '' else None
                    })
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_modificacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"[EDIT] Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))
            
            with get_db_cursor() as cursor:
                # 1. Verificar que el movimiento existe y está activo
                cursor.execute("""
                    SELECT Estado, ID_Bodega, Tipo_Compra, ID_Proveedor 
                    FROM Movimientos_Inventario 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento,))
                movimiento_actual = cursor.fetchone()
                
                if not movimiento_actual:
                    flash('Movimiento no encontrado', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                if movimiento_actual['Estado'] != 1:
                    flash('No se puede editar un movimiento anulado', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                print(f"[EDIT] Reversando existencias de movimiento {id_movimiento}")
                
                # 2. Reversar existencias de productos anteriores
                cursor.execute("""
                    SELECT ID_Producto, Cantidad 
                    FROM Detalle_Movimientos_Inventario 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento,))
                
                detalles_anteriores = cursor.fetchall()
                
                for detalle in detalles_anteriores:
                    cursor.execute("""
                        UPDATE Productos 
                        SET Existencias = Existencias - %s 
                        WHERE ID_Producto = %s
                    """, (detalle['Cantidad'], detalle['ID_Producto']))
                    print(f"[EDIT] Reversado producto {detalle['ID_Producto']}: -{detalle['Cantidad']} unidades")
                
                # 3. Eliminar detalles anteriores
                cursor.execute("DELETE FROM Detalle_Movimientos_Inventario WHERE ID_Movimiento = %s", (id_movimiento,))
                print(f"[EDIT] Detalles anteriores eliminados")
                
                # 4. Actualizar movimiento principal
                cursor.execute("""
                    UPDATE Movimientos_Inventario 
                    SET ID_TipoMovimiento = %s,
                        N_Factura_Externa = %s,
                        Fecha = %s,
                        ID_Proveedor = %s,
                        Tipo_Compra = %s,
                        Observacion = %s,
                        ID_Bodega = %s,
                        ID_Usuario_Modificacion = %s,
                        Fecha_Modificacion = NOW()
                    WHERE ID_Movimiento = %s
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_proveedor if id_proveedor else None,
                    tipo_compra,
                    observacion,
                    id_bodega,
                    id_usuario,
                    id_movimiento
                ))
                print(f"[EDIT] Movimiento principal actualizado")
                
                # 5. Insertar nuevos detalles y actualizar existencias
                total_compra = 0
                for producto in productos:
                    cantidad = producto['cantidad']
                    costo_unitario = producto['costo_unitario']
                    subtotal = round(cantidad * costo_unitario, 2)
                    total_compra += subtotal
                    
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO Detalle_Movimientos_Inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                            Precio_Unitario, Subtotal, Lote, Fecha_Vencimiento, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        cantidad,
                        costo_unitario,
                        producto['precio_unitario'],
                        subtotal,
                        producto['lote'],
                        producto['fecha_vencimiento'],
                        id_usuario
                    ))
                    
                    # Actualizar existencias con los nuevos valores
                    cursor.execute("""
                        UPDATE Productos 
                        SET Existencias = Existencias + %s 
                        WHERE ID_Producto = %s
                    """, (cantidad, producto['id_producto']))
                    
                    print(f"[EDIT] Producto {producto['id_producto']} agregado: +{cantidad} unidades")
                
                print(f"[EDIT] Total compra actualizado: C$ {total_compra:.2f}")
                
                # 6. Manejar cuenta por pagar
                cursor.execute("SELECT ID_Cuenta FROM Cuentas_Por_Pagar WHERE ID_Movimiento = %s", (id_movimiento,))
                cuenta_existente = cursor.fetchone()
                
                # Si la compra es a crédito y hay proveedor
                if tipo_compra == 'CREDITO' and id_proveedor:
                    if not fecha_vencimiento:
                        from datetime import datetime, timedelta
                        fecha_compra = datetime.strptime(fecha, '%Y-%m-%d')
                        fecha_vencimiento = (fecha_compra + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    if cuenta_existente:
                        # Actualizar cuenta existente
                        cursor.execute("""
                            UPDATE Cuentas_Por_Pagar 
                            SET Fecha = %s,
                                ID_Proveedor = %s,
                                Num_Documento = %s,
                                Observacion = %s,
                                Fecha_Vencimiento = %s,
                                Tipo_Movimiento = %s,
                                Monto_Movimiento = %s,
                                Saldo_Pendiente = %s,
                                ID_Usuario_Creacion = %s
                            WHERE ID_Movimiento = %s
                        """, (
                            fecha,
                            id_proveedor,
                            n_factura_externa or '',
                            observacion or 'Compra a crédito editada',
                            fecha_vencimiento,
                            id_tipo_movimiento,
                            total_compra,
                            total_compra,
                            id_usuario,
                            id_movimiento
                        ))
                        print(f"[EDIT] Cuenta por pagar actualizada")
                    else:
                        # Crear nueva cuenta
                        cursor.execute("""
                            INSERT INTO Cuentas_Por_Pagar (
                                ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, Observacion,
                                Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                                Saldo_Pendiente, ID_Usuario_Creacion
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento,
                            fecha,
                            id_proveedor,
                            n_factura_externa or '',
                            observacion or 'Compra a crédito',
                            fecha_vencimiento,
                            id_tipo_movimiento,
                            total_compra,
                            session.get('id_empresa', 1),
                            total_compra,
                            id_usuario
                        ))
                        print(f"[EDIT] Nueva cuenta por pagar creada")
                elif cuenta_existente:
                    # Si antes era crédito y ahora es contado, eliminar la cuenta
                    cursor.execute("DELETE FROM Cuentas_Por_Pagar WHERE ID_Movimiento = %s", (id_movimiento,))
                    print(f"[EDIT] Cuenta por pagar eliminada (cambio a contado)")
                
                flash('Compra actualizada exitosamente', 'success')
                print(f"[EDIT] ✅ Compra {id_movimiento} actualizada exitosamente")
                return redirect(url_for('admin_compras_entradas'))
                
    except Exception as e:
        print(f"❌ Error editando compra: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if request.method == 'GET':
            flash(f'Error al cargar formulario de edición: {str(e)}', 'error')
            return redirect(url_for('admin_compras_entradas'))
        else:
            flash(f'Error al actualizar compra: {str(e)}', 'error')
            return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))

@app.route('/admin/compras/compras-entradas/anular/<int:id_movimiento>', methods=['POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-ANULAR")
def admin_anular_compra(id_movimiento):
    try:
        # Obtener datos del formulario
        id_usuario_anulacion = request.form.get('id_usuario_anulacion')
        motivo_anulacion = request.form.get('motivo_anulacion', '')
        
        # Validaciones
        with get_db_cursor() as cursor:
            # Verificar que existe y está activo
            cursor.execute("""
                SELECT Estado, Tipo_Compra FROM Movimientos_Inventario 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            if not movimiento:
                flash('Movimiento no encontrado', 'error')
                return redirect(url_for('admin_compras_entradas'))
            
            if movimiento['Estado'] != 1:
                flash('El movimiento ya está anulado', 'error')
                return redirect(url_for('admin_compras_entradas'))
            
            # Reversar existencias
            cursor.execute("""
                SELECT ID_Producto, Cantidad FROM Detalle_Movimientos_Inventario 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            for detalle in detalles:
                cursor.execute("""
                    UPDATE Productos 
                    SET Existencias = Existencias - %s 
                    WHERE ID_Producto = %s AND Existencias >= %s
                """, (detalle['Cantidad'], detalle['ID_Producto'], detalle['Cantidad']))
                
                # Verificar si la actualización fue exitosa
                if cursor.rowcount == 0:
                    flash(f'No hay suficientes existencias para reversar el producto ID: {detalle["ID_Producto"]}', 'error')
                    return redirect(url_for('admin_compras_entradas'))
            
            # Anular movimiento
            cursor.execute("""
                UPDATE Movimientos_Inventario 
                SET Estado = 0, 
                    ID_Usuario_Modificacion = %s,
                    Fecha_Modificacion = NOW(),
                    Observacion = CONCAT(COALESCE(Observacion, ''), ' ANULADO: ', %s)
                WHERE ID_Movimiento = %s
            """, (id_usuario_anulacion, motivo_anulacion, id_movimiento))
            
            # Anular cuenta por pagar si existe
            cursor.execute("""
                UPDATE Cuentas_Por_Pagar 
                SET Estado = 0 
                WHERE ID_Movimiento = %s AND Estado = 1
            """, (id_movimiento,))
            
            flash('Compra anulada exitosamente', 'success')
            return redirect(url_for('admin_compras_entradas'))
            
    except Exception as e:
        print(f"Error al anular compra: {str(e)}")
        flash(f'Error al anular compra: {str(e)}', 'error')
        return redirect(url_for('admin_compras_entradas'))

@app.route('/admin/compras/compras-entradas/detalle-completo/<int:id_movimiento>', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-DETALLE-COMPLETO")
def admin_detalle_compra_completo(id_movimiento):
    try:
        with get_db_cursor(True) as cursor:
            # CONSULTA PRINCIPAL CORREGIDA
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.ID_TipoMovimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    mi.ID_Proveedor,
                    p.Nombre as Proveedor,
                    p.RUC_CEDULA as RUC_Proveedor,
                    p.Direccion as Direccion_Proveedor,
                    p.Telefono as Telefono_Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    mi.ID_Bodega,
                    b.Nombre as Bodega,
                    b.Ubicacion as Direccion_Bodega,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Fecha_Creacion,
                    u_mod.NombreUsuario as Usuario_Modificacion,
                    mi.Fecha_Modificacion,
                    mi.Estado,
                    (SELECT SUM(Subtotal) FROM Detalle_Movimientos_Inventario 
                     WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Compra,
                    (SELECT COUNT(*) FROM Detalle_Movimientos_Inventario 
                     WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Productos
                FROM Movimientos_Inventario mi
                LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN Bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN usuarios u_mod ON mi.ID_Usuario_Modificacion = u_mod.ID_Usuario
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash('Compra no encontrada', 'error')
                return redirect(url_for('admin_compras_entradas'))
            
            # DETALLES CORREGIDOS
            cursor.execute("""
                SELECT 
                    dmi.ID_Detalle_Movimiento,
                    dmi.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto_Desc,
                    p.Existencias as Existencias_Actuales,
                    dmi.Cantidad,
                    dmi.Costo_Unitario,
                    dmi.Precio_Unitario,
                    dmi.Subtotal,
                    dmi.Lote,
                    dmi.Fecha_Vencimiento,
                    um.Descripcion as Unidad_Medida
                FROM Detalle_Movimientos_Inventario dmi
                INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN Unidades_Medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            
            # CUENTAS POR PAGAR CORREGIDA - SIN CAMPO ESTADO
            cursor.execute("""
                SELECT 
                    ID_Cuenta,
                    Fecha_Vencimiento,
                    Monto_Movimiento,
                    Saldo_Pendiente
                FROM Cuentas_Por_Pagar 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta_por_pagar = cursor.fetchone()
            
            # Calcular total de cantidad
            total_cantidad = sum([detalle['Cantidad'] for detalle in detalles]) if detalles else 0
            
            now = datetime.now().date()
            
            return render_template(
                'admin/compras/detalle_compra.html',
                movimiento=movimiento,
                detalles=detalles,
                cuenta_por_pagar=cuenta_por_pagar,
                total_cantidad=total_cantidad,
                now=now,
                title="Detalles de Compra"
            )
                                
    except Exception as e:
        print(f"Error al cargar detalle completo de compra: {str(e)}")
        flash(f'Error al cargar detalles: {str(e)}', 'error')
        return redirect(url_for('admin_compras_entradas'))

# CUENTAS POR PAGAR 
@app.route('/admin/compras/cxpagar/cuentas-por-pagar', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-CUENTAS-POR-PAGAR")
def admin_cuentas_por_pagar():
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    cpp.ID_Cuenta,
                    cpp.Fecha,
                    cpp.ID_Proveedor,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    cpp.Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    CASE 
                        WHEN cpp.Saldo_Pendiente > 0 THEN 'Pendiente'
                        ELSE 'Pagado'
                    END as Estado,
                    u.NombreUsuario as Usuario_Creacion,
                    DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) as dias_vencimiento
                FROM Cuentas_Por_Pagar cpp
                LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON cpp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE cpp.Saldo_Pendiente > 0
                ORDER BY cpp.Fecha_Vencimiento ASC
            """)
            
            cuentas = cursor.fetchall()
            
            # Calcular estadísticas
            total_pendiente = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas if cuenta['Saldo_Pendiente'])
            total_monto = sum(cuenta['Monto_Movimiento'] for cuenta in cuentas if cuenta['Monto_Movimiento'])
            cuentas_vencidas = sum(1 for cuenta in cuentas if cuenta['dias_vencimiento'] and cuenta['dias_vencimiento'] < 0)
            
            return render_template('admin/compras/cxpagar/cuentas_por_pagar.html', 
                                 cuentas=cuentas,
                                 total_pendiente=total_pendiente,
                                 total_monto=total_monto,
                                 total_saldo=total_pendiente,
                                 cuentas_vencidas=cuentas_vencidas,
                                 cuentas_mes=len(cuentas))
    except Exception as e:
        print(f"Error al cargar cuentas por pagar: {str(e)}")
        flash(f'Error al cargar cuentas por pagar: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/compras/cuentas-por-pagar/pagar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-REGISTRAR-PAGO")
def registrar_pago_cuenta():
    try:
        if request.method == 'GET':
            # Cargar métodos de pago para el formulario
            with get_db_cursor(True) as cursor:
                cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
                metodos_pago = cursor.fetchall()
                
                # Obtener información de la cuenta si se proporciona ID
                id_cuenta = request.args.get('id_cuenta')
                cuenta_info = None
                if id_cuenta:
                    cursor.execute("""
                        SELECT 
                            cpp.ID_Cuenta,
                            cpp.Saldo_Pendiente,
                            cpp.ID_Proveedor,
                            p.Nombre as Proveedor,
                            cpp.Num_Documento,
                            cpp.Monto_Movimiento
                        FROM Cuentas_Por_Pagar cpp
                        LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                        WHERE cpp.ID_Cuenta = %s
                    """, (id_cuenta,))
                    cuenta_info = cursor.fetchone()
                
                return render_template('admin/compras/cxpagar/registrar_pago.html',
                                     metodos_pago=metodos_pago,
                                     cuenta_info=cuenta_info)
        
        elif request.method == 'POST':
            # Procesar el pago
            id_cuenta = request.form['id_cuenta']
            monto_pago = float(request.form['monto_pago'])
            fecha_pago = request.form['fecha_pago']
            id_metodo_pago = request.form['id_metodo_pago']
            detalles_metodo = request.form.get('detalles_metodo', '')
            comentarios = request.form.get('comentarios_pago', '')
            
            with get_db_cursor() as cursor:
                # Obtener información de la cuenta
                cursor.execute("""
                    SELECT 
                        cpp.Saldo_Pendiente,
                        cpp.ID_Proveedor,
                        p.Nombre as Proveedor,
                        cpp.Num_Documento,
                        cpp.Monto_Movimiento
                    FROM Cuentas_Por_Pagar cpp
                    LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                    WHERE cpp.ID_Cuenta = %s
                """, (id_cuenta,))
                
                cuenta = cursor.fetchone()
                
                if not cuenta:
                    flash('Cuenta no encontrada', 'error')
                    return redirect(url_for('admin_cuentas_por_pagar'))
                
                saldo_actual = float(cuenta['Saldo_Pendiente'])
                proveedor = cuenta['Proveedor']
                num_documento = cuenta['Num_Documento']
                monto_total = float(cuenta['Monto_Movimiento'])
                
                # Validaciones
                if monto_pago <= 0:
                    flash('El monto a pagar debe ser mayor a cero', 'error')
                    return redirect(url_for('registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                if monto_pago > saldo_actual:
                    flash(f'El monto a pagar (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})', 'error')
                    return redirect(url_for('registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                # Calcular nuevo saldo
                nuevo_saldo = saldo_actual - monto_pago
                user = session.get('user_id', 1)
                
                # Registrar el pago en la tabla pagos_cuentaspagar
                cursor.execute("""
                    INSERT INTO pagos_cuentaspagar 
                    (ID_Cuenta, Fecha, Monto, ID_MetodoPago, Detalles_Metodo, Comentarios, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s )
                """, (id_cuenta, f"{fecha_pago} 00:00:00", monto_pago, id_metodo_pago, 
                      detalles_metodo, comentarios, user))
                
                # Actualizar saldo pendiente en la cuenta
                cursor.execute("""
                    UPDATE Cuentas_Por_Pagar 
                    SET Saldo_Pendiente = %s 
                    WHERE ID_Cuenta = %s
                """, (nuevo_saldo, id_cuenta))
                
                # Mensaje de éxito
                if nuevo_saldo == 0:
                    mensaje = f'¡Cuenta completamente pagada! Se registró pago de ${monto_pago:,.2f} para {proveedor}.'
                else:
                    mensaje = f'Pago de ${monto_pago:,.2f} registrado correctamente para {proveedor}. Saldo restante: ${nuevo_saldo:,.2f}'
                
                flash(mensaje, 'success')
                return redirect(url_for('admin_cuentas_por_pagar'))
                
    except Exception as e:
        print(f"Error al registrar pago: {str(e)}")
        flash(f'Error al registrar pago: {str(e)}', 'error')
        return redirect(url_for('admin_cuentas_por_pagar'))

# Ruta para ver historial de pagos de una cuenta
@app.route('/admin/compras/cuentas-por-pagar/<int:id_cuenta>/pagos', methods=['GET'])
@admin_required
def historial_pagos_cuenta(id_cuenta):
    try:
        with get_db_cursor(True) as cursor:
            # Obtener información de la cuenta
            cursor.execute("""
                SELECT 
                    cpp.ID_Cuenta,
                    cpp.Fecha,
                    cpp.ID_Proveedor,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    cpp.Fecha_Vencimiento,
                    cpp.Tipo_Movimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    u.NombreUsuario as Usuario_Creacion,
                    DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) as dias_vencimiento
                FROM Cuentas_Por_Pagar cpp
                LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON cpp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE cpp.ID_Cuenta = %s
            """, (id_cuenta,))
            
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash('Cuenta no encontrada', 'error')
                return redirect(url_for('admin_cuentas_por_pagar'))
            
            # Obtener historial de pagos
            cursor.execute("""
                SELECT 
                    pcp.ID_Pago,
                    pcp.Fecha,
                    pcp.Monto,
                    pcp.ID_MetodoPago,
                    mp.Nombre as Metodo_Pago,
                    pcp.Detalles_Metodo,
                    pcp.Comentarios,
                    pcp.ID_Usuario_Creacion,
                    u.NombreUsuario as Usuario_Pago
                FROM pagos_cuentaspagar pcp
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE pcp.ID_Cuenta = %s
                ORDER BY pcp.Fecha DESC
            """, (id_cuenta,))
            
            pagos = cursor.fetchall()
            
            # Convertir decimal.Decimal a float para cálculos
            monto_total = float(cuenta['Monto_Movimiento']) if cuenta['Monto_Movimiento'] else 0.0
            saldo_pendiente = float(cuenta['Saldo_Pendiente']) if cuenta['Saldo_Pendiente'] else 0.0
            
            # Calcular total pagado y porcentaje
            total_pagado = 0.0
            if pagos:
                for pago in pagos:
                    total_pagado += float(pago['Monto']) if pago['Monto'] else 0.0
            
            # Calcular porcentaje pagado
            if monto_total > 0:
                porcentaje_pagado = (total_pagado / monto_total) * 100
            else:
                porcentaje_pagado = 0.0
            
            # Determinar estado de la cuenta
            estado_cuenta = "Pagada" if saldo_pendiente == 0 else "Pendiente"
            
            return render_template('admin/compras/cxpagar/historial_pagos.html', 
                                 cuenta=cuenta,
                                 pagos=pagos,
                                 total_pagado=total_pagado,
                                 porcentaje_pagado=porcentaje_pagado,
                                 estado_cuenta=estado_cuenta)
            
    except Exception as e:
        print(f"Error al cargar historial de pagos: {str(e)}")
        flash(f'Error al cargar historial de pagos: {str(e)}', 'error')
        return redirect(url_for('admin_cuentas_por_pagar'))

#Modulo VENTAS
@app.route('/admin/ventas/ventas-salidas', methods=['GET'])
@admin_required
@bitacora_decorator("VENTAS-SALIDAS")
def admin_ventas_salidas():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    c.Nombre as Cliente,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Fecha_Creacion,
                    mi.Estado,
                    (SELECT COUNT(*) FROM Detalle_Movimientos_Inventario dmi 
                     WHERE dmi.ID_Movimiento = mi.ID_Movimiento) as Total_Productos,
                    (SELECT SUM(Subtotal) FROM Detalle_Movimientos_Inventario dmi 
                     WHERE dmi.ID_Movimiento = mi.ID_Movimiento) as Total_Venta,
                    mi.ID_Factura_Venta,
                    f.ID_Factura
                FROM Movimientos_Inventario mi
                LEFT JOIN Clientes c ON mi.ID_Cliente = c.ID_Cliente  -- Ahora usa ID_Cliente
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN Facturacion f ON mi.ID_Factura_Venta = f.ID_Factura
                WHERE cm.Adicion = 'SALIDA' OR cm.Letra = 'S'
                ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
            """)
            ventas = cursor.fetchall()
            return render_template('admin/ventas/ventas_salidas.html', 
                                 ventas=ventas)
    except Exception as e:
        flash(f'Error al cargar ventas: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/ventas/ventas-salidas/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("VENTAS-SALIDAS-CREAR")
def admin_crear_venta():
    try:
        if request.method == 'GET':
            with get_db_cursor(True) as cursor:
                # Obtener tipos de movimiento de salida/venta
                cursor.execute("""
                SELECT *
                FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = 2  -- Cambiar por el ID de ventas
                """)
                tipos_movimiento = cursor.fetchall()
                
                # Obtener clientes activos
                cursor.execute("""
                    SELECT ID_Cliente, Nombre, RUC_CEDULA 
                    FROM Clientes 
                    WHERE Estado = 'ACTIVO' 
                    ORDER BY Nombre
                """)
                clientes = cursor.fetchall()
                
                # Obtener bodegas activas
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                # Obtener categorías de productos
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                # Obtener productos activos con existencias
                cursor.execute("""
                    SELECT p.ID_Producto, p.COD_Producto, p.Descripcion, p.Existencias, 
                           p.Precio_Venta, p.ID_Categoria, c.Descripcion as Categoria
                    FROM Productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE p.Estado = 1 AND p.Existencias > 0
                    ORDER BY c.Descripcion, p.Descripcion
                """)
                productos = cursor.fetchall()
                
                return render_template('admin/ventas/crear_venta.html',
                                    tipos_movimiento=tipos_movimiento,
                                    clientes=clientes,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias)
        
        elif request.method == 'POST':
            # Obtener datos del formulario
            id_tipo_movimiento = request.form.get('id_tipo_movimiento')
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_cliente = request.form.get('id_cliente')
            tipo_venta = request.form.get('tipo_venta', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            id_usuario_creacion = request.form.get('id_usuario_creacion')
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            precios_unitarios = request.form.getlist('precios_unitarios[]')
            lotes = request.form.getlist('lotes[]')
            fechas_vencimiento = request.form.getlist('fechas_vencimiento[]')
            
            print(f"Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_creacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin_crear_venta'))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin_crear_venta'))
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_creacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin_crear_venta'))
            
            # Construir lista de productos y validar existencias
            with get_db_cursor(True) as cursor:
                for i in range(len(producto_ids)):
                    if producto_ids[i] and cantidades[i] and precios_unitarios[i]:
                        cantidad = round(float(cantidades[i]), 2)
                        precio_unitario = round(float(precios_unitarios[i]), 2)
                        
                        # Validar existencias
                        cursor.execute("SELECT Existencias FROM Productos WHERE ID_Producto = %s", (producto_ids[i],))
                        producto_info = cursor.fetchone()
                        if producto_info and producto_info['Existencias'] < cantidad:
                            flash(f'No hay suficientes existencias para el producto seleccionado. Disponible: {producto_info["Existencias"]}', 'error')
                            return redirect(url_for('admin_crear_venta'))
                        
                        productos.append({
                            'id_producto': producto_ids[i],
                            'cantidad': cantidad,
                            'precio_unitario': precio_unitario,
                            'lote': lotes[i] if i < len(lotes) and lotes[i] != '' else None,
                            'fecha_vencimiento': fechas_vencimiento[i] if i < len(fechas_vencimiento) and fechas_vencimiento[i] != '' else None
                        })
            
            with get_db_cursor() as cursor:
                # Calcular total de la venta
                total_venta = sum(
                    producto['cantidad'] * producto['precio_unitario'] 
                    for producto in productos
                )
                
                # Insertar movimiento principal
                cursor.execute("""
                    INSERT INTO Movimientos_Inventario (
                        ID_TipoMovimiento, N_Factura_Externa, Fecha, ID_Cliente,  -- Ahora usa ID_Cliente
                        Tipo_Compra, Observacion, ID_Empresa, ID_Bodega, 
                        ID_Usuario_Creacion, ID_Usuario_Modificacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_cliente if id_cliente else None,  # Se almacena en ID_Cliente
                    tipo_venta,
                    observacion,
                    session.get('id_empresa', 1),
                    id_bodega,
                    id_usuario,
                    id_usuario
                ))
                
                id_movimiento = cursor.lastrowid
                print(f"Movimiento de venta creado con ID: {id_movimiento}")
                
                # Insertar detalles del movimiento
                for producto in productos:
                    subtotal = round(producto['cantidad'] * producto['precio_unitario'], 2)
                    
                    cursor.execute("""
                        INSERT INTO Detalle_Movimientos_Inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, 
                            Subtotal, Lote, Fecha_Vencimiento, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['precio_unitario'],
                        subtotal,
                        producto['lote'],
                        producto['fecha_vencimiento'],
                        id_usuario
                    ))
                    
                    # Actualizar existencias del producto (RESTAR en ventas)
                    cursor.execute("""
                        UPDATE Productos 
                        SET Existencias = Existencias - %s 
                        WHERE ID_Producto = %s
                    """, (producto['cantidad'], producto['id_producto']))
                
                # CREAR FACTURA
                cursor.execute("""
                    INSERT INTO Facturacion (
                        Fecha, IDCliente, Tipo_Compra, Observacion, 
                        ID_Empresa, ID_Usuario_Creacion
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    fecha,
                    id_cliente if id_cliente else None,
                    tipo_venta,
                    observacion,
                    session.get('id_empresa', 1),
                    id_usuario
                ))
                
                id_factura = cursor.lastrowid
                
                # CREAR DETALLE DE FACTURACIÓN
                for producto in productos:
                    total_producto = round(producto['cantidad'] * producto['precio_unitario'], 2)
                    
                    cursor.execute("""
                        INSERT INTO Detalle_Facturacion (
                            ID_Factura, ID_Producto, Cantidad, Costo, Total
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_factura,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['precio_unitario'],  # En tu estructura se llama Costo pero es el precio de venta
                        total_producto
                    ))
                
                # CREAR CUENTA POR COBRAR SI ES CRÉDITO
                if tipo_venta == 'CREDITO' and id_cliente:
                    if not fecha_vencimiento:
                        from datetime import datetime, timedelta
                        fecha_venta = datetime.strptime(fecha, '%Y-%m-%d')
                        fecha_vencimiento = (fecha_venta + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    cursor.execute("""
                        INSERT INTO Cuentas_Por_Cobrar (
                            Fecha, ID_Cliente, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                            Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        fecha,
                        id_cliente,
                        n_factura_externa or f"VTA-{id_movimiento}",
                        observacion or 'Venta a crédito',
                        fecha_vencimiento,
                        id_tipo_movimiento,
                        total_venta,
                        session.get('id_empresa', 1),
                        total_venta,
                        id_factura,
                        id_usuario
                    ))
                
                flash('Venta creada exitosamente', 'success')
                return redirect(url_for('admin_ventas_salidas'))            
    except Exception as e:
        print(f"Error completo al crear venta: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Error al crear venta: {str(e)}', 'error')
        return redirect(url_for('admin_crear_venta'))
    
# RUTAS AUXILIARES PARA VENTAS - ADAPTADAS DE COMPRAS

# RUTA AUXILIAR PARA PRODUCTOS POR CATEGORÍA (PARA VENTAS)
@app.route('/admin/ventas/productos-por-categoria/<int:id_categoria>')
@admin_required
def obtener_productos_por_categoria_venta(id_categoria):
    """
    Endpoint para obtener productos filtrados por categoría - PARA VENTAS
    """
    try:
        with get_db_cursor(True) as cursor:
            if id_categoria == 0:  # Todas las categorías
                cursor.execute("""
                    SELECT ID_Producto, COD_Producto, Descripcion, Existencias,
                           Precio_Venta, ID_Categoria
                    FROM Productos 
                    WHERE Estado = 1 AND Existencias > 0
                    ORDER BY Descripcion
                """)
            else:
                cursor.execute("""
                    SELECT ID_Producto, COD_Producto, Descripcion, Existencias,
                           Precio_Venta, ID_Categoria
                    FROM Productos 
                    WHERE Estado = 1 AND Existencias > 0 AND ID_Categoria = %s
                    ORDER BY Descripcion
                """, (id_categoria,))
            
            productos = cursor.fetchall()
            print(f"✅ Productos encontrados para ventas: {len(productos)} para categoría {id_categoria}")
            
            productos_list = []
            for producto in productos:
                productos_list.append({
                    'id': producto['ID_Producto'],
                    'codigo': producto['COD_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']) if producto['Existencias'] is not None else 0,
                    'precio_venta': float(producto['Precio_Venta']) if producto['Precio_Venta'] is not None else 0,
                    'id_categoria': producto['ID_Categoria']
                })
            
            print(f"📦 Productos procesados exitosamente para ventas: {len(productos_list)}")
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener productos por categoría para ventas: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# RUTA AUXILIAR PARA TODOS LOS PRODUCTOS (PARA VENTAS)
@app.route('/admin/ventas/todos-los-productos')
@admin_required
def obtener_todos_los_productos_venta():
    """
    Endpoint para obtener todos los productos - PARA VENTAS
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Producto, COD_Producto, Descripcion, Existencias,
                       Precio_Venta, ID_Categoria
                FROM Productos 
                WHERE Estado = 1 AND Existencias > 0
                ORDER BY Descripcion
            """)
            
            productos = cursor.fetchall()
            print(f"✅ Todos los productos encontrados para ventas: {len(productos)}")
            
            productos_list = []
            for producto in productos:
                productos_list.append({
                    'id': producto['ID_Producto'],
                    'codigo': producto['COD_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']) if producto['Existencias'] is not None else 0,
                    'precio_venta': float(producto['Precio_Venta']) if producto['Precio_Venta'] is not None else 0,
                    'id_categoria': producto['ID_Categoria']
                })
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener todos los productos para ventas: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# RUTA PARA CATEGORÍAS (PARA VENTAS)
@app.route('/admin/ventas/categorias-productos')
@admin_required
def obtener_categorias_productos_venta():
    """
    Endpoint para obtener todas las categorías - PARA VENTAS
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
            categorias = cursor.fetchall()
            
            categorias_list = []
            for categoria in categorias:
                categorias_list.append({
                    'id': categoria['ID_Categoria'],
                    'descripcion': categoria['Descripcion']
                })
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f"Error al obtener categorías para ventas: {str(e)}")
        return jsonify({'error': str(e)}), 500


#Iniciar Aplicación
if __name__ == '__main__':
    
    os.makedirs('templates/admin', exist_ok=True)
    os.makedirs('templates/vendedor', exist_ok=True)
    os.makedirs('templates/jefe_galera', exist_ok=True)
    
    # Ejecutar diagnóstico al iniciar
    print("🚀 Iniciando aplicación...")
    test_connection()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
