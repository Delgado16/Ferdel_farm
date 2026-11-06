from flask import Blueprint

admin_bp = Blueprint('admin',__name__, url_prefix='/admin')

#importar los modulos
from . import dashboard
from . import caja
from . import ventas
from . import compras
from . import cxpagar
from . import gastos
from . import catalogos
from . import productos
from . import bodega
from . import herramientas
from . import reportes
from . import cruce_cuentas


__all__ = ['admin_bp']