import os
import re

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # 1. Reemplazar onsubmit="return confirm('...')"
    def repl_onsubmit(match):
        msg = match.group(1)
        return f'onsubmit="event.preventDefault(); Swal.fire({{title: {msg}, icon: \'warning\', showCancelButton: true, confirmButtonText: \'Sí\', cancelButtonText: \'No\'}}).then((result) => {{ if (result.isConfirmed) {{ this.submit(); }} }});"'
    
    content = re.sub(r'onsubmit="return confirm\((.*?)\);?"', repl_onsubmit, content)
    
    # 2. Reemplazar onclick="return confirm('...')"
    def repl_onclick(match):
        msg = match.group(1)
        return f'onclick="event.preventDefault(); Swal.fire({{title: {msg}, icon: \'warning\', showCancelButton: true, confirmButtonText: \'Sí\', cancelButtonText: \'No\'}}).then((result) => {{ if (result.isConfirmed) {{ window.location.href = this.href || this.closest(\'a\').href; }} }});"'

    content = re.sub(r'onclick="return confirm\((.*?)\);?"', repl_onclick, content)

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
