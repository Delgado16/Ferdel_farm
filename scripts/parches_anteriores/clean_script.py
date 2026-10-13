import re

with open('templates/admin/ventas/crear_venta.html', 'r', encoding='utf-8') as f:
    content = f.read()

# The sweetalert script tag is exactly: <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11">
# Currently, it has the pos_js inside it before the closing </script>
# We need to find: <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"> (anything) </script>
# But only the first occurrence! 
# Actually, replacing using regex:
pattern = re.compile(r'<script src="https://cdn\.jsdelivr\.net/npm/sweetalert2@11">.*?</script>', re.DOTALL)
content = pattern.sub('<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>', content)

# Now, we should check if there are any other unintended injections. 
# There's only one other </script> which is the main one at the bottom.
# So the one at the bottom has the pos_js correctly inside it. 
# Wait, did I inject pos_js v1 and then pos_js v2?
# In inject_pos_v2.py, I did:
# start_idx = html_content.find('// ============================================\n    // LÓGICA DE PUNTO DE VENTA (POS)')
# end_idx = html_content.find('</script>', start_idx)
# This removed the first occurrence (the one in sweetalert).
# So right now, the sweetalert might be clean from POS v1, but it got POS v2!
# Because after cleaning POS v1, I did:
# new_content = html_content.replace('</script>', pos_js + '\n</script>')
# which AGAIN injected POS v2 into BOTH </script> tags!

# So the regex replacement above will clean the sweetalert tag perfectly.

# Let's save it.
with open('templates/admin/ventas/crear_venta.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed sweetalert script tag.")
