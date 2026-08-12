import re

filepath = 'templates/chat/image_generation_chat.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the form HTML
form_pattern = re.compile(r'<form id="image-form" class="flex flex-col sm:flex-row gap-2 sm:gap-3">.*?</form>', re.DOTALL)
new_form = """<form id="image-form" class="flex flex-col sm:flex-row gap-2 sm:gap-3">
            {% csrf_token %}
            <input type="file" id="krea-image-input" class="hidden" accept="image/*">
            
            <!-- Desktop Upload Button -->
            <label for="krea-image-input" class="krea-upload-btn hidden sm:hidden cursor-pointer flex-none items-center justify-center w-11 h-11 rounded-xl bg-slate-800/80 border border-slate-700/50 text-indigo-400 hover:text-white hover:bg-indigo-900/40 transition duration-300" style="min-width: 44px; max-width: 44px;" title="Загрузить референс">
                <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            </label>

            <input type="text" id="image-prompt" placeholder="Например: Космонавт на марсе в стиле киберпанк" class="flex-1 rounded-xl bg-slate-900 border border-slate-800 px-3 py-2.5 sm:px-4 sm:py-3 text-xs sm:text-sm text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" required>
            
            <button type="submit" class="relative inline-flex items-center justify-center gap-2 px-4 py-2.5 sm:px-6 sm:py-3 text-xs sm:text-sm font-semibold text-slate-300 hover:text-white transition duration-300 group whitespace-nowrap">
                <span class="absolute inset-0 w-full h-full rounded-xl transition duration-300 ease-out transform translate-x-1 translate-y-1 bg-indigo-900/50 group-hover:-translate-x-0 group-hover:-translate-y-0"></span>
                <span class="absolute inset-0 w-full h-full rounded-xl bg-slate-800/80 border border-slate-700/50 group-hover:bg-indigo-900/40 transition duration-300"></span>
                <span class="relative z-10">Сгенерировать</span>
            </button>

            <!-- Mobile Upload Button -->
            <label for="krea-image-input" class="krea-upload-btn hidden sm:!hidden cursor-pointer w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700/50 text-indigo-400 hover:text-white hover:bg-indigo-900/40 transition duration-300" title="Загрузить референс">
                <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
                <span class="text-sm font-semibold">Загрузить изображение</span>
            </label>
        </form>"""
content = form_pattern.sub(new_form, content)

# Replace the JS logic
js_pattern = re.compile(r'const kreaUploadBtn = document\.getElementById\(\'krea-upload-btn\'\);(.*?)modelSelect\.addEventListener\(\'change\', \(\) => \{.*?\kreaUploadBtn\.classList\.add\(\'hidden\'\);\s+kreaImageInput\.value = \'\';\s+currentKreaB64 = null;\s+kreaUploadPreview\.classList\.add\(\'hidden\'\);\s+\}\s+\}\);', re.DOTALL)

new_js = """const kreaUploadBtns = document.querySelectorAll('.krea-upload-btn');
    const kreaImageInput = document.getElementById('krea-image-input');
    const kreaUploadPreview = document.getElementById('krea-upload-preview');
    const kreaFileName = document.getElementById('krea-file-name');
    const kreaRemoveFile = document.getElementById('krea-remove-file');

    modelSelect.addEventListener('change', () => {
        if (modelSelect.value === 'krea-2-medium-turbo' || modelSelect.value === 'riverflow-v2.5-fast') {
            kreaUploadBtns.forEach(btn => {
                if (btn.classList.contains('sm:hidden') && !btn.classList.contains('w-full')) {
                    // Desktop button
                    btn.classList.remove('hidden');
                    btn.classList.add('sm:inline-flex');
                } else if (btn.classList.contains('w-full')) {
                    // Mobile button
                    btn.classList.remove('hidden');
                }
            });
        } else {
            kreaUploadBtns.forEach(btn => {
                btn.classList.add('hidden');
                btn.classList.remove('sm:inline-flex');
            });
            kreaImageInput.value = '';
            currentKreaB64 = null;
            kreaUploadPreview.classList.add('hidden');
        }
    });"""

content = js_pattern.sub(new_js, content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("UI updated.")
