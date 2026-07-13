import os
import sys

# Add root directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from config.database import get_db

def run_test_query():
    app = create_app()
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Test 1: Date range for June
        query = """
            SELECT 
                cpr.ID_Carga,
                prov.Nombre AS Proveedor,
                cpr.Num_Factura AS Factura_N,
                cpr.Fecha_Carga AS Fecha_Envio,
                p.Descripcion AS Producto,
                cpd.Cantidad_Cargada AS Cantidad_Esperada,
                cpd.Cantidad_Recibida AS Cantidad_Recibida,
                (cpd.Cantidad_Cargada - cpd.Cantidad_Recibida) AS Diferencia_Cajas,
                cpd.Costo_Unitario AS Costo_Unitario,
                (cpd.Cantidad_Cargada * cpd.Costo_Unitario) AS Costo_Total_Esperado,
                (cpd.Cantidad_Recibida * cpd.Costo_Unitario) AS Costo_Total_Recibido,
                cpr.Estado AS Estado_Recepcion,
                cpr.Fecha_Recepcion AS Fecha_Recepcion,
                uc.NombreUsuario AS Usuario_Carga,
                ur.NombreUsuario AS Usuario_Recepcion
            FROM cargas_pendientes_recepcion cpr
            JOIN cargas_pendientes_detalle cpd ON cpr.ID_Carga = cpd.ID_Carga
            JOIN proveedores prov ON cpr.ID_Proveedor = prov.ID_Proveedor
            JOIN productos p ON cpd.ID_Producto = p.ID_Producto
            JOIN usuarios uc ON cpr.ID_Usuario_Carga = uc.ID_Usuario
            LEFT JOIN usuarios ur ON cpr.ID_Usuario_Recepcion = ur.ID_Usuario
            WHERE cpr.Fecha_Carga BETWEEN %s AND %s
        """
        # Testing with a broad date range to see if any data matches at all
        cursor.execute(query, ['2026-06-01', '2026-07-31'])
        res = cursor.fetchall()
        print(f"Results for June-July range: {len(res)} rows")
        for r in res[:3]:
            print(r)
            
        # Test 2: Let's see if we do LEFT JOINs instead of JOINs on uc (Usuario Carga) or others to be safe
        query_left = """
            SELECT 
                cpr.ID_Carga,
                prov.Nombre AS Proveedor,
                cpr.Num_Factura AS Factura_N,
                cpr.Fecha_Carga AS Fecha_Envio,
                p.Descripcion AS Producto,
                cpd.Cantidad_Cargada AS Cantidad_Esperada,
                cpd.Cantidad_Recibida AS Cantidad_Recibida,
                (cpd.Cantidad_Cargada - cpd.Cantidad_Recibida) AS Diferencia_Cajas,
                cpd.Costo_Unitario AS Costo_Unitario,
                (cpd.Cantidad_Cargada * cpd.Costo_Unitario) AS Costo_Total_Esperado,
                (cpd.Cantidad_Recibida * cpd.Costo_Unitario) AS Costo_Total_Recibido,
                cpr.Estado AS Estado_Recepcion,
                cpr.Fecha_Recepcion AS Fecha_Recepcion,
                uc.NombreUsuario AS Usuario_Carga,
                ur.NombreUsuario AS Usuario_Recepcion
            FROM cargas_pendientes_recepcion cpr
            LEFT JOIN cargas_pendientes_detalle cpd ON cpr.ID_Carga = cpd.ID_Carga
            LEFT JOIN proveedores prov ON cpr.ID_Proveedor = prov.ID_Proveedor
            LEFT JOIN productos p ON cpd.ID_Producto = p.ID_Producto
            LEFT JOIN usuarios uc ON cpr.ID_Usuario_Carga = uc.ID_Usuario
            LEFT JOIN usuarios ur ON cpr.ID_Usuario_Recepcion = ur.ID_Usuario
            WHERE cpr.Fecha_Carga BETWEEN %s AND %s
        """
        cursor.execute(query_left, ['2026-06-01', '2026-07-31'])
        res_left = cursor.fetchall()
        print(f"Results with LEFT JOINs: {len(res_left)} rows")

        cursor.close()

if __name__ == '__main__':
    run_test_query()
