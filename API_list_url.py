import requests
import json

url = "https://tiki.vn/api/v2/categories"

params = {
    "include": "children",
    "parent_id": 316
}

response = requests.get(url, params=params)
response.raise_for_status()

data = response.json()

with open("categories_316.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)