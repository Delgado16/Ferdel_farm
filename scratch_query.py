from app import app
from config.database import get_db_cursor

with app.app_context():
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM catalogo_movimientos WHERE Descripcion LIKE '%Ajuste%' OR ID_TipoMovimiento = 5")
        for row in cursor.fetchall():
            print(row)
