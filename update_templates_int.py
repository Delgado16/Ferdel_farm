import os
import re

def update_templates():
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    
    # regex para encontrar {{ algo.Cantidad|int }}
    pattern2 = re.compile(r'(\{\{\s*[^}]*Cantidad)\s*\|\s*int\s*(.*?\}\})')
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                
                # Replace pattern2
                def replacer2(match):
                    # match.group(1) is "{{ algo.Cantidad"
                    # match.group(2) is "if algo.Cantidad else 0 }}"
                    # we want "{{ algo.Cantidad | cantidad if algo.Cantidad else 0 }}"
                    return f"{match.group(1)} | cantidad {match.group(2)}"
                    
                new_content = pattern2.sub(replacer2, new_content)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated INT {filepath}")

if __name__ == "__main__":
    update_templates()
