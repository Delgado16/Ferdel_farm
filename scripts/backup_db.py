"""
Script de ejecución manual o programada (CLI / Cron / Tareas de Windows)
Genera una copia de seguridad completa de la base de datos de Ferdel.
Uso:
    python scripts/backup_db.py
"""
import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.database import init_pool
from helpers.backup_service import ejecutar_backup_servidor

def main():
    print("=" * 60)
    print("  FERDEL - GENERADOR DE COPIA DE SEGURIDAD (BACKUP)")
    print("=" * 60)
    
    print("🔌 Conectando a la base de datos...")
    if not init_pool():
        print("❌ Error: No se pudo conectar a la base de datos.")
        sys.exit(1)
        
    print("💾 Generando respaldo SQL y guardando en servidor...")
    try:
        resultado = ejecutar_backup_servidor(es_automatico=True)
        print(f"✅ ¡Respaldo completado exitosamente!")
        print(f"   Archivo: {resultado['filename']}")
        print(f"   Ruta:    {resultado['filepath']}")
        print(f"   Tamaño:  {resultado['size_mb']} MB")
        print(f"   Fecha:   {resultado['fecha'].strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"❌ Error al generar el respaldo: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
