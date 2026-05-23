import os
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path

BASE = "https://www.simplyfitness.com"
INDEX = "https://www.simplyfitness.com/pages/workout-exercise-guides"
OUT_DIR = "gym"

os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def get_html(url):
    time.sleep(random.uniform(0.8, 2.0))

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)

        if r.status_code == 503:
            time.sleep(5)
            r = requests.get(url, headers=HEADERS, timeout=30)

        r.raise_for_status()
        return r.text

    except Exception as e:
        print("Request failed:", url, e)
        return None


def get_soup(url):
    html = get_html(url)
    if not html:
        return None
    return BeautifulSoup(html, "html.parser")


def safe_name(name):
    return "".join(c for c in name if c.isalnum() or c in " -_").strip()


def fix_url(url):
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    return url


def extract_thumbnail(section):
    img = section.select_one("img")
    if not img:
        return None
    return fix_url(img.get("src") or img.get("data-src"))


def extract_index():
    soup = get_soup(INDEX)
    if not soup:
        return []

    categories = []

    for section in soup.select("section.exo-item"):
        h2 = section.select_one("h2")
        if not h2:
            continue

        category = h2.get_text(strip=True)

        thumbnail_url = extract_thumbnail(section)

        exercises = []
        for a in section.select("ul li a"):
            exercises.append(
                {"name": a.get_text(strip=True), "url": urljoin(BASE, a["href"])}
            )

        categories.append(
            {
                "category": category,
                "thumbnail_url": thumbnail_url,
                "exercises": exercises,
            }
        )

    return categories


def extract_exercise_image(soup):
    if not soup:
        return None

    shopify_header = soup.select_one("#shopify-section-header")
    if shopify_header:
        shopify_header.decompose()

    header = soup.find("header")
    if not header:
        return None

    img = header.find("img")
    if not img:
        return None

    return fix_url(img.get("src") or img.get("data-src"))


def parse_exercise(url, category):
    soup = get_soup(url)
    if not soup:
        return None, None

    name_tag = soup.select_one("h1.exo-h1")
    if not name_tag:
        return None, None

    name = name_tag.get_text(strip=True)

    lead_tag = soup.select_one("p.lead")
    lead = lead_tag.get_text(strip=True) if lead_tag else ""

    img_url = extract_exercise_image(soup)

    sections = soup.select(".exo-info > div")

    data = {
        "name": name,
        "category": category,
        "url": url,
        "lead": lead,
        "instructions": {},
        "equipment": [],
        "main_muscles": [],
        "secondary_muscles": [],
    }

    if len(sections) > 0:
        for h3 in sections[0].select("h3"):
            key = h3.get_text(strip=True).lower()
            p = h3.find_next_sibling("p")
            if p:
                data["instructions"][key] = p.get_text(strip=True)

        tips = sections[0].select("ul li")
        if tips:
            data["instructions"]["tips"] = [t.get_text(strip=True) for t in tips]

    if len(sections) > 1:
        headers = sections[1].select("h3")
        spans = sections[1].select("span")

        for h3, span in zip(headers, spans):
            key = h3.get_text(strip=True).lower()
            items = [a.get_text(strip=True) for a in span.select("a")]

            if "equipment" in key:
                data["equipment"] = [x.strip() for x in span.get_text().split(",")]
            elif "main" in key:
                data["main_muscles"] = items
            elif "secondary" in key:
                data["secondary_muscles"] = items

    return data, img_url


def download_image(url, path):
    if not url:
        return

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "").lower()
        path = Path(path)

        if "svg" in content_type or url.endswith(".svg"):
            if path.suffix.lower() != ".svg":
                path = path.with_suffix(".svg")
            path.write_text(r.text, encoding="utf-8")
        else:
            path.write_bytes(r.content)

    except Exception as e:
        print("Image failed:", url, e)


def save_category_thumbnail(category_name, thumbnail_url):
    category_folder = os.path.join(OUT_DIR, safe_name(category_name))
    os.makedirs(category_folder, exist_ok=True)

    thumb_path = os.path.join(category_folder, "thumbnail.png")

    if not os.path.exists(thumb_path):
        download_image(thumbnail_url, thumb_path)


def save_exercise(data, img_url):
    category_folder = os.path.join(OUT_DIR, safe_name(data["category"]))
    os.makedirs(category_folder, exist_ok=True)

    base = safe_name(data["name"])

    json_path = os.path.join(category_folder, base + ".json")
    img_path = os.path.join(category_folder, base + ".png")

    if os.path.exists(json_path):
        return

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    download_image(img_url, img_path)


def main():
    categories = extract_index()

    for cat in categories:
        print(cat["category"])

        save_category_thumbnail(cat["category"], cat["thumbnail_url"])

        for ex in cat["exercises"]:
            print(" -", ex["name"])

            try:
                data, img_url = parse_exercise(ex["url"], cat["category"])

                if data:
                    save_exercise(data, img_url)

            except Exception as e:
                print("Failed:", ex["url"], e)


if __name__ == "__main__":
    main()
