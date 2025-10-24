with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    if 'url = "https://api.stability.ai/v2beta/stable-image/generate/core"' in lines[i]:
        # Replace this line with dynamic endpoint logic
        new_lines.append('        # Build the endpoint based on model\n')
        new_lines.append('        if \'ultra\' in model.lower():\n')
        new_lines.append('            endpoint_model = \'ultra\'\n')
        new_lines.append('        elif \'sd3\' in model.lower() or \'diffusion\' in model.lower():\n')
        new_lines.append('            endpoint_model = \'sd3\'\n')
        new_lines.append('        else:\n')
        new_lines.append('            endpoint_model = \'core\'\n')
        new_lines.append('        \n')
        new_lines.append('        url = f"https://api.stability.ai/v2beta/stable-image/generate/{endpoint_model}"\n')
        new_lines.append('        app.logger.info(f"Using Stability AI endpoint: {url}")\n')
        i += 1
    else:
        new_lines.append(lines[i])
        i += 1

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Fixed successfully')
