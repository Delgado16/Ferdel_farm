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
cursor = conn.cursor(dictionary=True)

# Consultar columnas de facturacion_ruta
cursor.execute("DESCRIBE facturacion_ruta")
print("--- facturacion_ruta ---")
for row in cursor.fetchall():
    print(f"{row['Field']}: {row['Type']}")

# Consultar columnas de facturacion
cursor.execute("DESCRIBE facturacion")
print("\n--- facturacion ---")
for row in cursor.fetchall():
    print(f"{row['Field']}: {row['Type']}")

cursor.close()
conn.close()
