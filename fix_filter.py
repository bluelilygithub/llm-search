with open('static/js/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "modelsByProvider[provider].forEach(model => { if (model.type === 'image') return;" in line:
        # Replace this line with proper formatting
        new_lines.append("                modelsByProvider[provider].forEach(model => {\n")
        new_lines.append("                    if (model.type === 'image') return;\n")
    else:
        new_lines.append(line)

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Fixed filter syntax')
