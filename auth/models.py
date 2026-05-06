"""
Modelo de Usuario para Flask-Login
"""
from flask_login import UserMixin


class User(UserMixin):
    """Clase User para manejar la autenticación con Flask-Login"""
    
    def __init__(self, id, username, rol):
        self.id = str(id)
        self.username = username
        self.rol = rol
    
    def has_role(self, role):
        """Verificar si el usuario tiene un rol específico"""
        return self.rol == role
    
    def __repr__(self):
        return f'<User {self.username} ({self.rol})>'
