import json

def find_keys(data, keywords):
    results = []
    def recurse(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(kw in k.lower() for kw in keywords):
                    results.append((path + [k], v))
                recurse(v, path + [k])
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                recurse(item, path + [str(i)])
    recurse(data, [])
    return results

try:
    with open('xt_api.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        matches = find_keys(data, ['price', 'sum', 'amount', 'total'])
        for path, val in matches:
            if isinstance(val, (int, float, str)) and val:
                print(f"{' -> '.join(path)}: {val}")
except Exception as e:
    print(e)
