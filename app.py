"""
Archivo principal de la aplicación Flask
Inicializa la app, configura middleware, y registra blueprints
"""
import sys

# Configurar encoding a UTF-8 para evitar errores de codificación con emojis en Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from flask import Flask, jsonify, request, render_template, g
from flask_cors import CORS
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import logging
from logging.handlers import RotatingFileHandler

# Importar configuraciones
from config.settings import SECRET_KEY, SESSION_CONFIG, CORS_CONFIG, RENDER_ENV, RAILWAY_ENV, print_db_config
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
    
    # Resolver la IP real del cliente detrás de proxies inversos (como Railway/Render)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    
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
    
    # ===== CONFIGURAR LOGGING ROTATIVO =====
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240000, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    logging.getLogger('werkzeug').addHandler(file_handler)
    app.logger.info('Ferdel Startup')

    # ===== CONTROL DE ERRORES GLOBAL =====
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning(f"404 No Encontrado: {request.path}")
        accept = request.headers.get('Accept', '')
        if request.path.startswith('/api/') or \
           request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           ('application/json' in accept and 'text/html' not in accept):
            return jsonify({'status': 'error', 'message': 'Recurso no encontrado'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 Error Interno del Servidor: {error}", exc_info=True)
        db = getattr(g, 'db', None)
        if db is not None:
            try:
                db.rollback()
            except Exception as rollback_err:
                app.logger.error(f"Error al hacer rollback tras error 500: {rollback_err}")
                
        accept = request.headers.get('Accept', '')
        if request.path.startswith('/api/') or \
           request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           ('application/json' in accept and 'text/html' not in accept):
            return jsonify({'status': 'error', 'message': 'Error interno del servidor'}), 500
        return render_template('errors/500.html'), 500
    
    # ===== MENSAJES DE INICIALIZACIÓN =====
    print("📋 Configuración de aplicación:")
    print(f"   Secret Key: {'✅ Configurado' if SECRET_KEY else '❌ No configurado'}")
    print(f"   CORS: ✅ Habilitado")
    print(f"   Autenticación: ✅ Flask-Login configurado")
    print(f"   Ambiente: {'🏭 Render' if RENDER_ENV else ('🚂 Railway' if RAILWAY_ENV else '💻 Desarrollo')}")
    print("✅ Aplicación inicializada correctamente")
    
    return app

# ===== INSTANCIA GLOBAL PARA GUNICORN (PRODUCCIÓN) =====
app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)