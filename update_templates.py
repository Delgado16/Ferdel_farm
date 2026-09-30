import os
import re

def update_templates():
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    
    # regex para encontrar {{ "%.2f"|format(algo.Cantidad) }} o {{ "%.2f"|format(algo.Existencias) }}
    # group 1: lo que está dentro de format()
    pattern1 = re.compile(r'\{\{\s*"%\.?\d*[fF]"\s*\|\s*format\(\s*([^}]+?)\s*\)\s*\}\}')
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                # Replace pattern1
                def replacer1(match):
                    var = match.group(1).strip()
                    # Si var termina en |float o |abs, lo limpiamos para el filtro
                    # aunque el filtro cantidad ya maneja floats/strings
                    return f"{{{{ {var} | cantidad }}}}"
                    
                new_content = pattern1.sub(replacer1, new_content)
                
                # También buscar {{ algo.Cantidad }} sueltos sin format si existieran y cambiarlos
                # Pero es más riesgoso. Nos limitamos a los que usaban format.
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated {filepath}")

if __name__ == "__main__":
    update_templates()
