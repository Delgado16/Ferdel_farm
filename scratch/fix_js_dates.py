import os
import re

TEMPLATES_DIR = r"c:\Users\ferza\OneDrive\Documents\ferdel\templates"

targets = [
    (r"\.toISOString\(\)\.split\('T'\)\[0\]", ".toLocaleDateString('sv-SE')"),
    (r"\.toISOString\(\)\.slice\(0,\s*10\)", ".toLocaleDateString('sv-SE')")
]

modified_files = []

for root, dirs, files in os.walk(TEMPLATES_DIR):
    for file in files:
        if file.endswith(".html"):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            new_content = content
            made_changes = False
            
            for pattern, replacement in targets:
                # We check if there's a match
                if re.search(pattern, new_content):
                    new_content = re.sub(pattern, replacement, new_content)
                    made_changes = True
            
            if made_changes:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                modified_files.append(filepath)

print(f"Total files modified: {len(modified_files)}")
for path in modified_files:
    print(f"- {os.path.relpath(path, TEMPLATES_DIR)}")
