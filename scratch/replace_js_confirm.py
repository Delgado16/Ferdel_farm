import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # Busca bloques de la forma:
    # if (confirm('Mensaje')) {
    #     ... codigo ...
    # }
    # y los convierte en:
    # Swal.fire({title: 'Mensaje', icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí', cancelButtonText: 'No'}).then((result) => {
    #     if (result.isConfirmed) {
    #         ... codigo ...
    #     }
    # });
    
    # Solo reemplazamos if(confirm(...)) { ...
    def repl_confirm(match):
        msg = match.group(1)
        return f"Swal.fire({{title: {msg}, icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí', cancelButtonText: 'No'}}).then((result) => {{\n        if (result.isConfirmed) {{"

    # The regex looks for `if (confirm('msg')) {`
    # We replace only the header. But we need to add the closing `});` 
    # This is risky without proper parsing.
    
    return False

# Since it's risky, let's just do it manually for `detalle_venta.html`.
