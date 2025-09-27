# list_models.py
import os, requests, json

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("GEMINI_API_KEY not set in env")
    raise SystemExit(1)

resp = requests.get("https://generativelanguage.googleapis.com/v1/models",
                    params={"key": API_KEY}, timeout=30)
print("Status:", resp.status_code)
data = resp.json()
if "models" in data:
    for m in data["models"]:
        name = m.get("name") or m.get("model") or m.get("id") or "<no-name>"
        methods = m.get("supported_methods") or m.get("capabilities") or {}
        print("MODEL:", name)
        print("  supported_methods:", methods)
        print("---")
else:
    print(json.dumps(data, indent=2)[:2000])
