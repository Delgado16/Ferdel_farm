import os

count = 0
for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            target = "window.location.href = this.href || this.closest('a').href;"
            if target in content:
                new_logic = "if (this.tagName === 'BUTTON' || this.tagName === 'INPUT') { const form = this.closest('form'); if (form) { form.submit(); } } else { window.location.href = this.href || this.closest('a').href; }"
                new_content = content.replace(target, new_logic)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                count += 1

print(f"Fixed {count} files with onclick bug.")
