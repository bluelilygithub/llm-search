with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if '# Get AI response and usage info - use model_identifier for API call' in line:
        # Add validation before this line
        new_lines.append('        # Reject Stability AI image models in chat (they\'re for diagram generation only)\n')
        new_lines.append('        if model_identifier.startswith(\'stable-image\') or model_identifier.startswith(\'stable-audio\'):\n')
        new_lines.append('            app.logger.error(f"Attempted to use image generation model {model_identifier} for chat")\n')
        new_lines.append('            return jsonify({\'error\': f\'Model {model} is for image generation only. Use the Illustrate follow-up question for diagrams.\'}), 400\n')
        new_lines.append('\n')
    new_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Added Stability model validation')
