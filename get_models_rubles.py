import urllib.request, json, re

req = urllib.request.Request('https://routerai.ru/api/v1/models')
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        
        models = data.get('data', [])
        
        models = sorted(models, key=lambda x: x.get('pricing', {}).get('prompt', 0) if isinstance(x.get('pricing', {}), dict) else 0)[:50]
        
        results = []
        for m in models:
            pricing = m.get('pricing', {})
            
            p_prompt_raw = float(pricing.get('prompt', 0))
            p_comp_raw = float(pricing.get('completion', 0))
            
            # API is returning price per token in USD.
            # Convert to rubles per 1M tokens with 82.50 exchange rate and 1.2 markup (20%)
            # Price per 1M tokens = raw_price * 1_000_000 * 82.5 * 1.2
            
            p_prompt_rub = p_prompt_raw * 1_000_000 * 82.5 * 1.2
            p_comp_rub = p_comp_raw * 1_000_000 * 82.5 * 1.2
            
            # Remove brackets and anything inside them from name
            name = re.sub(r'\(.*?\)', '', m['name']).strip()
            
            provider = m['id'].split('/')[0].capitalize()
            if 'openai' in m['id']: provider = 'OpenAI'
            elif 'anthropic' in m['id']: provider = 'Anthropic'
            elif 'google' in m['id']: provider = 'Google'
            elif 'meta' in m['id']: provider = 'Meta'
            elif 'mistral' in m['id']: provider = 'Mistral'
            
            logo_url = ""
            if provider == 'OpenAI': logo_url = "https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg"
            elif provider == 'Anthropic': logo_url = "https://upload.wikimedia.org/wikipedia/commons/1/14/Anthropic.png"
            elif provider == 'Google': logo_url = "https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg"
            elif provider == 'Meta': logo_url = "https://upload.wikimedia.org/wikipedia/commons/7/7b/Meta_Platforms_Inc._logo.svg"
            elif provider == 'Mistral': logo_url = "https://upload.wikimedia.org/wikipedia/commons/e/e0/Mistral_AI_logo.svg"
            else: logo_url = "https://upload.wikimedia.org/wikipedia/commons/1/13/ChatGPT-Logo.png"

            results.append({
                'id': m['id'],
                'name': name,
                'provider': provider,
                'description': m.get('description', ''),
                'context_length': m.get('context_length', 0),
                'pricing': {
                    'prompt': p_prompt_rub, 
                    'completion': p_comp_rub,
                    'prompt_formatted': f"{p_prompt_rub:.2f}",
                    'completion_formatted': f"{p_comp_rub:.2f}"
                },
                'logo': logo_url
            })
            
        with open('chat/models_catalog.py', 'w') as f:
            f.write("MODELS_CATALOG = [\n")
            for r in results:
                f.write(f"    {repr(r)},\n")
            f.write("]\n")
            
        with open('chat/models_catalog.py', 'a') as f:
            f.write("\nAVAILABLE_PROVIDERS = [\n")
            for r in results:
                f.write(f"    ('{r['provider'].lower()}', '{r['provider']}', '{r['name']}'),\n")
            f.write("]\n")
            
        print("Generated chat/models_catalog.py")
except Exception as e:
    print('Error:', e)
