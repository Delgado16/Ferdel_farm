import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

import mysql.connector
from config.settings import DB_CONFIG

config_simple = {k: v for k, v in DB_CONFIG.items() 
                 if k not in ['pool_name', 'pool_size', 'pool_reset_session']}
conn = mysql.connector.connect(**config_simple)
cursor = conn.cursor()

try:
    print("Agregando columna Cliente_Nombre_Temporal a facturacion_ruta...")
    cursor.execute("""
        ALTER TABLE facturacion_ruta 
        ADD COLUMN Cliente_Nombre_Temporal VARCHAR(255) DEFAULT NULL
    """)
    conn.commit()
    print("Columna agregada exitosamente a facturacion_ruta.")
except Exception as e:
    print(f"Error en facturacion_ruta: {e}")

try:
    print("Agregando columna Cliente_Nombre_Temporal a facturacion...")
    cursor.execute("""
        ALTER TABLE facturacion 
        ADD COLUMN Cliente_Nombre_Temporal VARCHAR(255) DEFAULT NULL
    """)
    conn.commit()
    print("Columna agregada exitosamente a facturacion.")
except Exception as e:
    print(f"Error en facturacion: {e}")

cursor.close()
conn.close()
print("Migración finalizada.")
