import os
from app import app
from config.database import get_db_cursor
import mysql.connector

def aplicar_cambios():
    with app.app_context():
        print("Iniciando actualización de la base de datos...")
        with get_db_cursor(commit=True) as cursor:
            # 1. Agregar ID_Proveedor_Vinculado a la tabla clientes
            try:
                print("Intentando agregar ID_Proveedor_Vinculado a 'clientes'...")
                cursor.execute("""
                    ALTER TABLE clientes 
                    ADD COLUMN ID_Proveedor_Vinculado INT NULL;
                """)
                print("✅ Columna ID_Proveedor_Vinculado agregada a 'clientes'.")
            except mysql.connector.Error as err:
                if err.errno == 1060: # 1060 es el código de error para "Columna duplicada"
                    print("⚠️ La columna ID_Proveedor_Vinculado ya existe en 'clientes'.")
                else:
                    print(f"❌ Error al alterar 'clientes': {err}")

            # 2. Agregar llave foránea a clientes (Opcional, pero recomendado)
            try:
                print("Intentando agregar llave foránea a 'clientes'...")
                cursor.execute("""
                    ALTER TABLE clientes
                    ADD CONSTRAINT fk_cliente_proveedor
                    FOREIGN KEY (ID_Proveedor_Vinculado) REFERENCES proveedores(ID_Proveedor) ON DELETE SET NULL;
                """)
                print("✅ Llave foránea fk_cliente_proveedor agregada a 'clientes'.")
            except mysql.connector.Error as err:
                if err.errno in (1061, 1826, 1050): # Códigos comunes si la llave o constraint ya existe
                    print("⚠️ La llave foránea en 'clientes' ya existe.")
                else:
                    print(f"❌ Error al agregar llave foránea en 'clientes': {err}")

            # 3. Agregar ID_Cliente_Vinculado a la tabla proveedores
            try:
                print("Intentando agregar ID_Cliente_Vinculado a 'proveedores'...")
                cursor.execute("""
                    ALTER TABLE proveedores 
                    ADD COLUMN ID_Cliente_Vinculado INT NULL;
                """)
                print("✅ Columna ID_Cliente_Vinculado agregada a 'proveedores'.")
            except mysql.connector.Error as err:
                if err.errno == 1060:
                    print("⚠️ La columna ID_Cliente_Vinculado ya existe en 'proveedores'.")
                else:
                    print(f"❌ Error al alterar 'proveedores': {err}")

            # 4. Agregar llave foránea a proveedores (Opcional, pero recomendado)
            try:
                print("Intentando agregar llave foránea a 'proveedores'...")
                cursor.execute("""
                    ALTER TABLE proveedores
                    ADD CONSTRAINT fk_proveedor_cliente
                    FOREIGN KEY (ID_Cliente_Vinculado) REFERENCES clientes(ID_Cliente) ON DELETE SET NULL;
                """)
                print("✅ Llave foránea fk_proveedor_cliente agregada a 'proveedores'.")
            except mysql.connector.Error as err:
                if err.errno in (1061, 1826, 1050):
                    print("⚠️ La llave foránea en 'proveedores' ya existe.")
                else:
                    print(f"❌ Error al agregar llave foránea en 'proveedores': {err}")

        print("¡Actualización finalizada con éxito!")

if __name__ == '__main__':
    aplicar_cambios()
