"""
Script para probar y diagnosticar la conexión a la Base de Datos MySQL
Uso: python test_conexion_bd.py
"""

import sys
import os

# Forzar UTF-8 en terminales de Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Cargar configuración del proyecto
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    print("Aviso: python-dotenv no encontrado, leyendo variables del entorno actual.")

import mysql.connector
from mysql.connector import Error

def probar_conexion():
    print("=" * 60)
    print("DIAGNOSTICO DE CONEXION A BASE DE DATOS")
    print("=" * 60)

    db_user = os.environ.get('DB_USER', 'root')
    db_password = os.environ.get('DB_PASSWORD', '')
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = int(os.environ.get('DB_PORT', 3306))
    db_name = os.environ.get('DB_NAME', 'db_ferdel_real')

    print(f"Parametros detectados:")
    print(f"   • Host:     {db_host}")
    print(f"   • Puerto:   {db_port}")
    print(f"   • Usuario:  {db_user}")
    print(f"   • Base:     {db_name}")
    print(f"   • Password: {'*' * len(db_password)} ({len(db_password)} caracteres)")
    print("-" * 60)

    # 1. Probar conexión al servidor MySQL (sin seleccionar BD)
    print("1. Probando conexion al servidor MySQL...")
    try:
        conn = mysql.connector.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            use_pure=True,
            connect_timeout=10
        )
        print("   [OK] Conexion al servidor MySQL exitosa.")
        
        # Listar bases de datos disponibles
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES;")
        databases = [row[0] for row in cursor.fetchall()]
        print(f"   [BDs disponibles]: {', '.join(databases)}")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"   [ERROR] Error de autenticacion al servidor: {e}")
        print("\nSugerencia: Revisa que el usuario y la contrasena en tu archivo .env sean los correctos.")
        return False

    # 2. Probar conexión a la base de datos específica
    print(f"\n2. Probando conexion a la base de datos '{db_name}'...")
    try:
        conn = mysql.connector.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            use_pure=True,
            charset='utf8mb4',
            collation='utf8mb4_general_ci',
            connect_timeout=10
        )
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   [OK] Conexion exitosa a '{db_name}'.")
        print(f"   [Tablas encontradas ({len(tables)})]: {', '.join(tables[:10])}{'...' if len(tables) > 10 else ''}")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"   [ERROR] Error al conectar a la base de datos '{db_name}': {e}")
        return False

    # 3. Probar Pool de conexiones de la aplicación
    print(f"\n3. Probando el Pool de conexiones (configuracion de app.py)...")
    try:
        from config.database import init_pool
        exito = init_pool()
        if exito:
            print("   [OK] Pool de conexiones inicializado exitosamente.")
        else:
            print("   [ERROR] Fallo la inicializacion del pool.")
            return False
    except Exception as e:
        print(f"   [ERROR] Error al inicializar pool: {e}")
        return False

    print("\n" + "=" * 60)
    print("TODO FUNCIONA CORRECTAMENTE. Ya puedes iniciar Flask.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    probar_conexion()
