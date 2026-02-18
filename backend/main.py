from fastapi import FastAPI, HTTPException
from bs4 import BeautifulSoup
import json
import requests
from serpapi import GoogleSearch
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Construct path to .env file relative to the main.py file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_json_ld(url):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")

    # find all script tags with type application/ld+json
    jsonld_scripts = soup.find_all('script', type="application/ld+json")

    for script in jsonld_scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                # Handle cases where data is a list (e.g., in a @graph)
                graph = data.get('@graph', [data])
                for item in graph:
                    if isinstance(item, dict) and item.get('@type') == 'Recipe':
                        return item # Return the first recipe found
            except json.JSONDecodeError:
                continue # Ignore scripts that are not valid JSON
    return None



@app.get("/")
def read_root():
    return {"Hello" : "World"}

@app.get("/searches")
def find_recipies(food: str, limit: int):
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="SERPAPI_API_KEY environment variable not set.")

    params = {
        "engine": "google",
        "q": f"{food} recipe",
        "google_domain": "google.com",
        "hl": "en",
        "gl": "us",
        "num": limit + 3, # The 'num' parameter specifies the number of results to return
        "api_key": api_key
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    if "error" in results:
        raise HTTPException(status_code=500, detail=results["error"])

    recipes = {}
    recipe_count = 0
    organic_results = results.get("organic_results", [])

    for result in organic_results:
        if recipe_count >= limit:
            break

        link = result.get("link")
        if link and "youtube.com" not in link:
            json_ld_data = extract_json_ld(link)
            if json_ld_data:
                recipe_count += 1
                recipes[f"recipe_{recipe_count}"] = json_ld_data

    return recipes
