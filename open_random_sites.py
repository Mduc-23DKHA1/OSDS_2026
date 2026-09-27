from playwright.sync_api import sync_playwright
import csv

URL = lambda key, id: f"https://tiki.vn/{key}/c{id}"
i = 283

with open("categories.csv", mode="r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    key = rows[i]["url_key"]
    id = rows[i]["id"]

print("key =", key)
print("id =", id)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL(key, id))
    page.wait_for_timeout(10000)
    browser.close()
