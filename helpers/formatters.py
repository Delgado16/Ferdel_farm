# helpers/formatters.py

"""
Filtros y formateadores para templates Jinja2
"""
from markupsafe import Markup
from decimal import Decimal
from datetime import datetime


def format_currency(value):
    """
    Formatea un valor como moneda
    
    Args:
        value: Valor a formatear
    
    Returns:
        str: Valor formateado como moneda
    """
    try:
        if isinstance(value, Decimal):
            value = float(value)
        return f"C${value:,.2f}"
    except (ValueError, TypeError):
        return "C$0.00"


def format_date(value, format='%d/%m/%Y'):
    """
    Formatea una fecha
    
    Args:
        value: Fecha a formatear
        format: Formato de salida
    
    Returns:
        str: Fecha formateada
    """
    if value:
        try:
            return value.strftime(format)
        except AttributeError:
            return str(value)
    return ""


def format_hora(value):
    """
    Formatea una hora a formato 12 horas con AM/PM
    
    Args:
        value: Datetime, time o string de hora a formatear
    
    Returns:
        str: Hora formateada (ej: 2:30 PM)
    
    Examples:
        >>> format_hora("2024-01-15 14:30:00")
        "2:30 PM"
        >>> format_hora("09:15:00")
        "9:15 AM"
        >>> format_hora(datetime.now())
        "2:30 PM"
    """
    if not value:
        return ""
    
    try:
        # Función auxiliar para formatear sin cero inicial
        def _formatear(dt):
            # Obtener hora en formato 12h sin cero inicial
            hora_12 = dt.strftime('%I').lstrip('0')
            minutos = dt.strftime('%M')
            am_pm = dt.strftime('%p')
            return f"{hora_12}:{minutos} {am_pm}"
        
        # Si es string, intentar convertirlo a datetime
        if isinstance(value, str):
            # Limpiar microsegundos si existen
            if '.' in value:
                value = value.split('.')[0]
            
            # Formatos soportados
            formatos = [
                '%Y-%m-%d %H:%M:%S',  # 2024-01-15 14:30:00
                '%Y-%m-%d %H:%M',     # 2024-01-15 14:30
                '%H:%M:%S',           # 14:30:00
                '%H:%M',              # 14:30
                '%Y-%m-%dT%H:%M:%S',  # ISO format
                '%I:%M:%S %p',        # 02:30:00 PM
                '%I:%M %p'            # 02:30 PM
            ]
            
            for fmt in formatos:
                try:
                    fecha_dt = datetime.strptime(value, fmt)
                    return _formatear(fecha_dt)
                except ValueError:
                    continue
            
            # Si no se pudo parsear, devolver el valor original
            return value
        
        # Si es datetime, formatear directamente
        elif isinstance(value, datetime):
            return _formatear(value)
        
        # Si tiene método strftime (como time, date, etc.)
        elif hasattr(value, 'strftime'):
            try:
                return _formatear(value)
            except:
                pass
        
        return str(value)
    
    except Exception as e:
        print(f"Error en format_hora: {e}, valor: {value}")
        return str(value)


def format_datetime(value, format='%d/%m/%Y %I:%M %p'):
    """
    Formatea una fecha y hora completa
    
    Args:
        value: Datetime a formatear
        format: Formato de salida
    
    Returns:
        str: Fecha y hora formateada (ej: 15/01/2024 2:30 PM)
    """
    if not value:
        return ""
    
    try:
        if isinstance(value, str):
            # Intentar convertir string a datetime
            formatos = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
            for fmt in formatos:
                try:
                    value = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
        
        if isinstance(value, datetime):
            # Formatear sin cero inicial en la hora
            if '%I' in format:
                hora = value.strftime('%I').lstrip('0')
                format = format.replace('%I', hora)
            return value.strftime(format)
        
        return str(value)
    
    except Exception as e:
        print(f"Error en format_datetime: {e}")
        return str(value)


def format_status(status):
    """
    Formatea un estado con color y etiqueta
    
    Args:
        status (str): Estado a formatear
    
    Returns:
        Markup: HTML con etiqueta colored
    """
    status_map = {
        'Activo': '<span class="badge bg-success">Activo</span>',
        'Inactivo': '<span class="badge bg-danger">Inactivo</span>',
        'Pendiente': '<span class="badge bg-warning">Pendiente</span>',
        'ABIERTA': '<span class="badge bg-success">ABIERTA</span>',
        'CERRADA': '<span class="badge bg-danger">CERRADA</span>',
        'NO_APERTURADA': '<span class="badge bg-secondary">NO APERTURADA</span>',
    }
    
    return Markup(status_map.get(status, f'<span class="badge bg-secondary">{status}</span>'))


def truncate_text(text, length=50):
    """
    Trunca un texto a una longitud específica
    
    Args:
        text (str): Texto a truncar
        length (int): Longitud máxima
    
    Returns:
        str: Texto truncado
    """
    if text and len(text) > length:
        return text[:length] + "..."
    return text


def apply_filters(app):
    """
    Aplica todos los filtros personalizados a la aplicación Flask
    
    Args:
        app (Flask): Instancia de la aplicación Flask
    """
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['date'] = format_date
    app.jinja_env.filters['format_hora'] = format_hora  # ← NOMBRE CORRECTO para tu plantilla
    app.jinja_env.filters['hora'] = format_hora        # ← También como alias
    app.jinja_env.filters['datetime'] = format_datetime
    app.jinja_env.filters['status'] = format_status
    app.jinja_env.filters['truncate'] = truncate_text