import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from config.database import get_db_cursor

app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['id_usuario'] = 1
        sess['id_empresa'] = 1
        sess['rol'] = 'ADMINISTRADOR'
        sess['usuario_rol'] = 'ADMINISTRADOR'
    
    test_endpoints = [
        '/admin/reporte/gastos_categorias',
        '/admin/reporte/gastos_categorias?periodo=dia',
        '/admin/reporte/gastos_categorias?periodo=ayer',
        '/admin/reporte/gastos_categorias?periodo=semana',
        '/admin/reporte/gastos_categorias?periodo=mes',
        '/admin/reporte/gastos_categorias?periodo=mes_anterior',
        '/admin/reporte/gastos_categorias?periodo=ano',
        '/admin/reporte/gastos_categorias?periodo=todo',
        '/admin/reporte/gastos_categorias?periodo=personalizado&fecha_inicio=2026-08-01&fecha_fin=2026-08-15',
        '/admin/reporte/gastos_categorias?fecha_inicio=2026-08-01&fecha_fin=2026-08-15',
        '/admin/reporte/categoria_ventas?periodo=ayer',
        '/admin/reporte/categoria_compras?periodo=ayer'
    ]
    
    for ep in test_endpoints:
        response = client.get(ep, follow_redirects=True)
        print(f"GET {ep} -> Status: {response.status_code}")
        if response.status_code != 200:
            print("Response text snippet:", response.data.decode('utf-8')[:300])
