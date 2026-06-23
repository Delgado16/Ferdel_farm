# -*- coding: utf-8 -*-
from flask import Blueprint

vendedor_bp = Blueprint('vendedor', __name__, url_prefix='/vendedor')

# Import modules to register routes:
from . import dashboard
from . import inventario
from . import movimientos
from . import ventas
from . import clientes
from . import caja

__all__ = ['vendedor_bp']
