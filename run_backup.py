"""
Script ejecutor de respaldos para Railway Cron o tareas programadas externas.
Uso en Railway Cron: python run_backup.py
"""
import os
import sys

# Asegurar que el directorio raíz del proyecto esté en el path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from helpers.backup_service import ejecutar_backup_servidor

if __name__ == '__main__':
    print("Iniciando respaldo de FERDEL FARM...")
    res = ejecutar_backup_servidor(es_automatico=True)
    if res.get('success'):
        print(f"✅ Respaldo exitoso: {res.get('filename')} ({res.get('size_mb')} MB)")
        sys.exit(0)
    else:
        print(f"⚠️ Nota de respaldo: {res.get('message', 'No ejecutado')}")
        sys.exit(0)

