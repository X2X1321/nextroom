import re

filepath = 'templates/chat/image_generation_chat.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Show/hide plus button logic
script_start = content.find("document.getElementById('image-form').addEventListener('submit', async function(e) {")
if script_start != -1:
    krea_ui_logic = """
        let currentKreaB64 = null;
        
        const modelSelect = document.getElementById('image-model');
        const kreaUploadBtn = document.getElementById('krea-upload-btn');
        const kreaImageInput = document.getElementById('krea-image-input');
        const kreaUploadPreview = document.getElementById('krea-upload-preview');
        const kreaFileName = document.getElementById('krea-file-name');
        const kreaRemoveFile = document.getElementById('krea-remove-file');

        modelSelect.addEventListener('change', () => {
            if (modelSelect.value === 'krea-2-medium-turbo') {
                kreaUploadBtn.classList.remove('hidden');
            } else {
                kreaUploadBtn.classList.add('hidden');
                kreaImageInput.value = '';
                currentKreaB64 = null;
                kreaUploadPreview.classList.add('hidden');
            }
        });

        kreaImageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (evt) => {
                    currentKreaB64 = evt.target.result; // Data URI
                    kreaFileName.textContent = file.name;
                    kreaUploadPreview.classList.remove('hidden');
                };
                reader.readAsDataURL(file);
            }
        });

        kreaRemoveFile.addEventListener('click', () => {
            kreaImageInput.value = '';
            currentKreaB64 = null;
            kreaUploadPreview.classList.add('hidden');
        });

        """
    content = content[:script_start] + krea_ui_logic + content[script_start:]

# 2. Update form submit to send input_reference_b64
fetch_horde_start = content.find("} else if (model.startsWith('horde-')) {")
if fetch_horde_start != -1:
    fetch_krea_logic = """} else if (model === 'krea-2-medium-turbo') {
                const res = await fetch("{% url 'generate_image' %}", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ 
                        prompt: prompt, 
                        model: model,
                        aspect_ratio: ratio,
                        input_reference_b64: currentKreaB64
                    }),
                });
                const data = await res.json();
                
                if (!res.ok) {
                    throw new Error(data.error || 'Failed to generate image');
                }
                
                renderSuccess(data.image_url);
                saveStats('krea', prompt, Date.now() - startTime, data.image_url);
            """
    content = content[:fetch_horde_start] + fetch_krea_logic + content[fetch_horde_start:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("JS Updated")
