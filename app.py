"""
Archivo principal de la aplicación Flask
Inicializa la app, configura middleware, y registra blueprints
"""
from flask import Flask
from flask_cors import CORS
from flask_session import Session
import secrets

# Importar configuraciones
from config.settings import SECRET_KEY, SESSION_CONFIG, CORS_CONFIG, RENDER_ENV, print_db_config
from config.database import init_pool, close_db

# Importar autenticación
from auth import setup_login_manager

# Importar helpers
from helpers.formatters import apply_filters

# Importar blueprints
from routes import auth_bp, main_bp, admin_bp, vendedor_bp, bodega_bp



def create_app():
    """Factory function para crear la aplicación Flask"""
    
    # ===== INICIALIZAR APLICACIÓN =====
    app = Flask(__name__)
    
    # ===== CONFIGURACIÓN FLASK =====
    app.secret_key = SECRET_KEY
    app.config['CORS_HEADERS'] = CORS_CONFIG['CORS_HEADERS']
    app.config['TEMPLATES_AUTO_RELOAD'] = SESSION_CONFIG['TEMPLATES_AUTO_RELOAD']
    app.config['SESSION_PERMANENT'] = SESSION_CONFIG['PERMANENT']
    app.config['SESSION_TYPE'] = SESSION_CONFIG['TYPE']
    app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_CONFIG['PERMANENT_LIFETIME']
    
    # ===== EXTENSIONES =====
    CORS(app)
    Session(app)
    
    # ===== AUTENTICACIÓN =====
    setup_login_manager(app)
    
    # ===== FILTROS JINJA2 =====
    apply_filters(app)
    
    # ===== BASE DE DATOS =====
    # Inicializar pool de conexiones
    init_pool()
    print_db_config()
    
    # Cerrar conexión al terminar cada request
    app.teardown_appcontext(close_db)
    
    # ===== REGISTRAR BLUEPRINTS =====
    app.register_blueprint(auth_bp)      # /auth
    app.register_blueprint(main_bp)      # /
    app.register_blueprint(admin_bp)     # /admin
    app.register_blueprint(vendedor_bp)  # /vendedor
    app.register_blueprint(bodega_bp)    # /bodega
    
    # ===== MENSAJES DE INICIALIZACIÓN =====
    print("📋 Configuración de aplicación:")
    print(f"   Secret Key: {'✅ Configurado' if SECRET_KEY else '❌ No configurado'}")
    print(f"   CORS: ✅ Habilitado")
    print(f"   Autenticación: ✅ Flask-Login configurado")
    print(f"   Ambiente: {'🏭 Render' if RENDER_ENV else '💻 Desarrollo'}")
    print("✅ Aplicación inicializada correctamente")
    
    return app

# ===== PUNTO DE ENTRADA =====
if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, host='0.0.0.0', port=5000)