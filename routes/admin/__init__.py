from flask import Blueprint

admin_bp = Blueprint('admin',__name__, url_prefix='/admin')

#importar los modulos
from . import dashboard
from . import caja
from . import ventas
from . import compras
from . import catalogos
from . import productos
from . import bodega
from . import herramientas
from . import reportes


__all__ = ['admin_bp']