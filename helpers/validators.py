"""
Validadores de datos y entrada
"""


def validate_username(username):
    """
    Validar que el nombre de usuario sea válido
    
    Args:
        username (str): Nombre de usuario a validar
    
    Returns:
        tuple: (bool, str) - (es_válido, mensaje_error)
    """
    if not username or not username.strip():
        return False, "El nombre de usuario es requerido"
    
    if len(username) < 3:
        return False, "El nombre de usuario debe tener al menos 3 caracteres"
    
    if len(username) > 50:
        return False, "El nombre de usuario no puede exceder 50 caracteres"
    
    return True, ""


def validate_password(password):
    """
    Validar que la contraseña sea válida
    
    Args:
        password (str): Contraseña a validar
    
    Returns:
        tuple: (bool, str) - (es_válida, mensaje_error)
    """
    if not password:
        return False, "La contraseña es requerida"
    
    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres"
    
    if len(password) > 100:
        return False, "La contraseña no puede exceder 100 caracteres"
    
    return True, ""


def validate_email(email):
    """
    Validar que el email sea válido
    
    Args:
        email (str): Email a validar
    
    Returns:
        tuple: (bool, str) - (es_válido, mensaje_error)
    """
    import re
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not email or not email.strip():
        return False, "El email es requerido"
    
    if not re.match(email_pattern, email):
        return False, "El email no es válido"
    
    return True, ""


