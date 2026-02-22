from fastapi import FastAPI, HTTPException
from bs4 import BeautifulSoup
import json
from typing import Optional, Dict
from enum import Enum
from serpapi import GoogleSearch
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import google.generativeai as genai
import traceback
import asyncio
import httpx


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

class SortBy(str, Enum):
    ingredients = "ingredients"
    time = "time"
    rating = "rating"


async def extract_json_ld(client: httpx.AsyncClient, url: str):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }
        response = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        response.raise_for_status()  # Raise an exception for bad status codes
    except httpx.HTTPError as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")

    # find all script tags with type application/ld+json
    jsonld_scripts = soup.find_all('script', type="application/ld+json")

    for script in jsonld_scripts:
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    graph = data
                elif isinstance(data, dict):
                    graph = data.get('@graph', [data])
                else:
                    continue

                for item in graph:
                    if isinstance(item, dict) and item.get('@type') == 'Recipe':
                        return item # Return the first recipe found
            except json.JSONDecodeError:
                continue # Ignore scripts that are not valid JSON
    return None


def get_sorting_prompt(recipes_json_str: str, sort_by: str) -> str:
    """Creates the prompt for the Gemini API to sort recipes."""
    criteria_definitions = {
        "ingredients": "Sort by the recipe that has the most ingredients in common with all other recipes. The recipe with the highest 'commonality' score should come first. This recipe can be considered the most 'average' or representative of the search results.",
        "time": "Sort by the total time to prepare and cook the dish (totalTime, or prepTime + cookTime). Shorter total times should come first. You will need to parse ISO 8601 duration strings (e.g., 'PT1H30M').",
        "rating": "Sort by the 'ratingValue' found within 'aggregateRating'. Higher ratings should come first. Handle cases where rating is a string or number, and where it might be missing."
    }

    return f"""
    You are a recipe analysis and sorting expert.
    Your task is to sort a given list of recipes based on a specific criterion.

    Here is the JSON data containing the recipes, identified by keys like "recipe_1", "recipe_2", etc.:
    {recipes_json_str}

    The criterion for sorting is: '{sort_by}'.

    Here is the definition of the sorting criterion:
    {criteria_definitions[sort_by]}

    Your response MUST be a valid JSON array of strings, where each string is a recipe key from the input data, ordered according to the criterion. Do not include any other text, explanations, or markdown formatting around the JSON array.

    Example of a valid response format:
    ["recipe_3", "recipe_1", "recipe_2"]
    """

async def sort_recipes_with_gemini(recipes: Dict, sort_by: SortBy) -> Dict:
    """Sorts recipes using the Gemini API."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Warning: GEMINI_API_KEY is not set. Skipping sorting.")
        return recipes

    genai.configure(api_key=gemini_api_key)

    model = genai.GenerativeModel('gemini-3-flash-preview')

    recipes_json_str = json.dumps(recipes, indent=2)
    prompt = get_sorting_prompt(recipes_json_str, sort_by.value)

    try:
        response = await model.generate_content_async(prompt)
        # Clean up the response to ensure it's valid JSON
        cleaned_response_text = response.text.strip().replace("`", "").replace("json\n", "")

        sorted_keys = json.loads(cleaned_response_text)

        sorted_recipes = {key: recipes[key] for key in sorted_keys if key in recipes}
        return sorted_recipes
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error sorting recipes with Gemini: {e}. Returning unsorted.")
        return recipes


async def normalize_ingredients(recipes: Dict) -> Dict:
    """Normalizes ingredients using Gemini to standard format."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Skipping normalization: GEMINI_API_KEY not found.")
        return recipes

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')

    # Extract ingredients to minimize token usage
    ingredients_payload = {
        k: v.get("recipeIngredient", [])
        for k, v in recipes.items()
        if "recipeIngredient" in v
    }

    if not ingredients_payload:
        return recipes

    prompt = f"""
    You are a culinary data expert.
    Convert these recipe ingredients into a clean JSON list of 'ingredient_name' and 'quantity'.
    Map 'cloves of garlic' to 'garlic' and 'EVOO' to 'olive oil'.
    Standardize units and names.

    Input JSON:
    {json.dumps(ingredients_payload, indent=2)}

    Output MUST be a valid JSON object where keys are the recipe IDs (e.g., "recipe_1") and values are lists of objects with 'ingredient_name' and 'quantity'.
    Example:
    {{
      "recipe_1": [
        {{"ingredient_name": "flour", "quantity": "2 cups"}}
      ]
    }}
    Do not include markdown formatting.
    """

    try:
        response = await model.generate_content_async(prompt)
        text = response.text
        # Robust JSON extraction: find the first '{' and the last '}'
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx : end_idx + 1]
            normalized_data = json.loads(json_str)

            for key, normalized_ingredients in normalized_data.items():
                if key in recipes:
                    recipes[key]["recipeIngredient"] = normalized_ingredients
        else:
            print(f"Error normalizing ingredients: No JSON found in response.\nResponse: {text}")

    except Exception as e:
        print(f"Error normalizing ingredients: {e}")

    return recipes


def analyze_recipe_data(recipes: Dict) -> Dict:
    """
    Analyzes recipes to calculate ingredient frequency and identify "secret ingredients".
    """
    num_recipes = len(recipes)
    if num_recipes < 2:  # Analysis requires at least 2 recipes for comparison
        return recipes

    # 1. Build a frequency map of all ingredients
    ingredient_counts = {}
    for recipe_key, recipe_data in recipes.items():
        ingredients = recipe_data.get("recipeIngredient", [])
        if not isinstance(ingredients, list):
            continue

        if ingredients and isinstance(ingredients[0], str):
            print(f"Skipping analysis for {recipe_key}: Ingredients are strings (not normalized).")
            continue

        # Use a set to count each ingredient only once per recipe for frequency calculation
        ingredient_names_in_recipe = {
            ing.get("ingredient_name") for ing in ingredients if isinstance(ing, dict) and ing.get("ingredient_name")
        }

        for name in ingredient_names_in_recipe:
            ingredient_counts[name] = ingredient_counts.get(name, 0) + 1

    # 2. Identify unique ingredients (present in only one recipe)
    unique_ingredients = {name for name, count in ingredient_counts.items() if count == 1}

    # 3. Annotate each ingredient in each recipe
    for recipe_key, recipe_data in recipes.items():
        # Check for high rating for "secret ingredient" feature
        is_highly_rated = False
        rating_info = recipe_data.get("aggregateRating")
        if isinstance(rating_info, dict):
            try:
                rating_value = float(rating_info.get("ratingValue", 0))
                # Consider "highly-rated" if rating is 4.5 or higher
                if rating_value >= 4.5:
                    is_highly_rated = True
            except (ValueError, TypeError):
                pass  # Ignore if ratingValue is not a valid number

        ingredients = recipe_data.get("recipeIngredient", [])
        if not isinstance(ingredients, list):
            continue

        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                continue

            name = ingredient.get("ingredient_name")
            if not name:
                continue

            frequency = ingredient_counts.get(name, 0)
            percentage = (frequency / num_recipes) * 100
            ingredient["frequency_percent"] = round(percentage)

            if percentage >= 60:
                ingredient["consensus_level"] = "Essential"
            elif percentage < 40:
                ingredient["consensus_level"] = "Flavor Variant"

            ingredient["is_secret_ingredient"] = is_highly_rated and name in unique_ingredients

    return recipes


@app.get("/")
def read_root():
    return {"Hello" : "World"}

@app.get("/searches")
async def find_recipies(food: str, limit: int, sort_by: Optional[SortBy] = None):
    try:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            print("Error: SERPAPI_API_KEY not set.")
            raise HTTPException(status_code=500, detail="SERPAPI_API_KEY environment variable not set.")

        params = {
            "engine": "google",
            "q": f"{food} recipe",
            "google_domain": "google.com",
            "hl": "en",
            "gl": "us",
            "num": limit + 5, # The 'num' parameter specifies the number of results to return
            "api_key": api_key
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])

        recipes = {}
        recipe_count = 0
        organic_results = results.get("organic_results", [])

        valid_links = []
        for result in organic_results:
            link = result.get("link")
            if link and "youtube.com" not in link:
                valid_links.append(link)

        async with httpx.AsyncClient() as client:
            tasks = [extract_json_ld(client, url) for url in valid_links]
            extracted_data = await asyncio.gather(*tasks)

        for data in extracted_data:
            if data:
                recipe_count += 1
                recipes[f"recipe_{recipe_count}"] = data
                if recipe_count >= limit:
                    break

        if not recipes:
            return {}

        # Normalize ingredients using LLM
        recipes = await normalize_ingredients(recipes)

        # Analyze recipes for consensus and secret ingredients
        recipes = analyze_recipe_data(recipes)

        if sort_by:
            return await sort_recipes_with_gemini(recipes, sort_by)

        return recipes
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
