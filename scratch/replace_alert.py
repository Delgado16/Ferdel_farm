import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # 3. Reemplazar alert(...) en JS
    # Cuidado: no reemplazar SweetAlert2 o similar si tiene alert
    def repl_alert(match):
        msg = match.group(1)
        # Avoid replacing inside Swal, or if it's already an alert in a comment
        return f"Swal.fire({msg}, '', 'info')"
    
    # regex for alert( something ); where something does not contain unbalanced parens
    # Simple regex for alert('...') or alert("...") or alert(msg)
    content = re.sub(r'\balert\s*\(\s*(.*?)\s*\)', repl_alert, content)

    if content != original_content:
        print(f"Updated {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

updated_count = 0
for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            if process_file(os.path.join(root, file)):
                updated_count += 1

print(f"Total files updated: {updated_count}")
