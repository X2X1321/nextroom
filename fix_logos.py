import re

with open('chat/models_catalog.py', 'r') as f:
    content = f.read()

# Replace lobehub logos with simpleicons in white
replacements = {
    'deepseek.svg': 'https://cdn.simpleicons.org/deepseek/white',
    'qwen.svg': 'https://cdn.simpleicons.org/qwen/white',
    'openai.svg': 'https://cdn.simpleicons.org/openai/white',
    'meta.svg': 'https://cdn.simpleicons.org/meta/white',
    'google.svg': 'https://cdn.simpleicons.org/google/white',
    'gemini.svg': 'https://cdn.simpleicons.org/google/white',
    'openrouter.svg': 'https://cdn.simpleicons.org/openrouter/white',
    'groq.svg': 'https://cdn.simpleicons.org/groq/white'
}

for old_file, new_url in replacements.items():
    pattern = r"'https://cdn\.jsdelivr\.net/npm/@lobehub/icons-static-svg@latest/icons/" + old_file + r"'"
    content = re.sub(pattern, f"'{new_url}'", content)

with open('chat/models_catalog.py', 'w') as f:
    f.write(content)

print("Logos updated in models_catalog.py")
