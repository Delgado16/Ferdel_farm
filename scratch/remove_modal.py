import sys

file_path = r'c:\Users\ferza\OneDrive\Documents\ferdel\templates\admin\ventas\cxcobrar\cuentas_cobrar.html'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_modal = False
skip_js = False

i = 0
while i < len(lines):
    line = lines[i]
    
    # Replace button
    if '<button type="button" class="btn btn-sm btn-success me-3" data-bs-toggle="modal" data-bs-target="#modalAbonoGlobal">' in line:
        new_lines.append('                    <a href="{{ url_for(\'admin.admin_crear_abono\') }}" class="btn btn-sm btn-success me-3">\n')
        new_lines.append('                        <i class="fas fa-money-check-alt me-1"></i> Abono Global\n')
        new_lines.append('                    </a>\n')
        i += 3  # skip the button lines
        continue

    # Remove modal HTML
    if '<!-- Modal Abono Global -->' in line:
        skip_modal = True
        
    if skip_modal and '<script>' in line:
        skip_modal = False
        new_lines.append(line)
        i += 1
        continue

    # Remove JS logic for modal
    if 'if(typeof jQuery !== \'undefined\') {' in line:
        skip_js = True
    
    if skip_js and '});' in line and i > 620:
        skip_js = False
        # wait, the file ends around 625, so we skip until the end of the script block
        pass

    if not skip_modal and not skip_js:
        new_lines.append(line)
        
    i += 1

# Manually remove the JS block (lines 534 to 623 approximately)
# Since the script logic was a bit messy, let's just use regular expressions
import re
text = "".join(new_lines)
# Remove the JS block from '// Inicializar Select2 en el modal' down to the end of '// AJAX para formulario'
text = re.sub(r'// Inicializar Select2 en el modal si está disponible.*?// AJAX para formulario', '// AJAX para formulario', text, flags=re.DOTALL)
text = re.sub(r'// AJAX para formulario.*?\}\);\n    \}\n', '', text, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("HTML modified successfully")
