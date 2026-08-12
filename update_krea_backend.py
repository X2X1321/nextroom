import re

filepath = 'chat/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

krea_logic = """
    # If explicitly requested Krea
    if model_param == 'krea-2-medium-turbo':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Login required for paid models'}, status=403)
        profile = request.user.profile
        if profile.balance < 3:
            return JsonResponse({'error': 'Недостаточно средств. Стоимость генерации 3 ₽.'}, status=402)
        
        import os, requests
        api_key = os.environ.get('ROUTER_AI_API_KEY')
        if not api_key:
            return JsonResponse({'error': 'RouterAI API Key not configured'}, status=500)
            
        input_ref = data.get('input_reference_b64')
        aspect_ratio = data.get('aspect_ratio', '1024x1024')
        # Translate the aspect_ratio from '1024x1024' format to '1:1', '16:9', '9:16'
        ratio_map = {'1024x1024': '1:1', '1024x576': '16:9', '576x1024': '9:16'}
        krea_ratio = ratio_map.get(aspect_ratio, '1:1')

        payload = {
            "model": "krea/krea-2-medium-turbo",
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": krea_ratio,
        }
        if input_ref:
            payload["input_references"] = [
                {"type": "image_url", "image_url": {"url": input_ref}}
            ]
            
        try:
            response = requests.post(
                "https://routerai.ru/api/v1/images",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            res_data = response.json()
            images = res_data.get('data', [])
            if not images or 'b64_json' not in images[0]:
                return JsonResponse({'error': 'Invalid response from RouterAI'}, status=500)
                
            img_b64 = images[0]['b64_json']
            
            # Deduct balance
            profile.balance -= 3
            profile.save()
            
            return JsonResponse({
                'status': 'success',
                'image_url': f"data:image/png;base64,{img_b64}",
                'model_used': 'krea-2-medium-turbo',
                'fallback_urls': []
            })
        except Exception as e:
            return JsonResponse({'error': f'Krea generation failed: {str(e)}'}, status=500)

"""

target_str = "    # If explicitly requested Horde"
content = content.replace(target_str, krea_logic + target_str)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Backend updated.")
