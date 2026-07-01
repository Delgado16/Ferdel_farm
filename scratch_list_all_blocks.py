import os
import re

blocks_found = {}

for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            matches = re.findall(r'{%\s*block\s+(\w+)\s*%}', content)
            for m in matches:
                if m not in blocks_found:
                    blocks_found[m] = []
                blocks_found[m].append(filepath.replace('\\', '/'))

print("All blocks used in templates:")
for block, paths in sorted(blocks_found.items()):
    print(f"Block '{block}': used in {len(paths)} files")
    if len(paths) <= 5:
        print(f"  Files: {paths}")
