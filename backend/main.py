from fastapi import FastAPI
from bs4 import BeautifulSoup
import json
import requests

app = FastAPI()
def extract_json_ld(url):
    headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')

    # find all script tags with type application/ld+json
    jsonld_scripts = soup.find_all('script', type="application/ld+json")
    print(jsonld_scripts)
    for script in jsonld_scripts:
        # get string inside script tag
        json_data = script.string
        print("json_data:", json_data)
        if json_data:
            try:
                # parse json string into Python dict
                data = json.loads(json_data)
                data = data
                print(f"Extracted JSON-LD Data:")
                print(f"    Type: {data.get('@type')}")
                print(f"    Name: {data.get('name')}")
                print(f"    Rating: {data.get('aggregateRating').get('ratingValue')}")
                print(f"    Ingredients: {data.get('recipeIngredient')}")
                print(f"    Prep time: {data.get('prepTime')}")
                print(f"    Cook time: {data.get('cookTime')}")
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")

url = 'https://thewoksoflife.com/lu-rou-fan-taiwanese-braised-pork-rice-bowl/'


@app.get("/")
def read_root():
    return {"Hello" : "World"}


