from main import analyze_recipe_data
import json

def test_analysis():
    # 1. Create Mock Data
    # We create 4 recipes to easily test percentages (1/4 = 25%, 4/4 = 100%)
    mock_recipes = {
        "recipe_1": {
            "name": "Perfect Dish (High Rated)",
            "aggregateRating": {"ratingValue": "5.0"}, # High rating
            "recipeIngredient": [
                {"ingredient_name": "salt", "quantity": "1 tsp"},      # Common (100%)
                {"ingredient_name": "saffron", "quantity": "1 pinch"}, # Unique & High Rated (Secret)
                {"ingredient_name": "water", "quantity": "1 cup"}      # Common (50%)
            ]
        },
        "recipe_2": {
            "name": "Good Dish",
            "aggregateRating": {"ratingValue": "4.5"},
            "recipeIngredient": [
                {"ingredient_name": "salt", "quantity": "1 tsp"},
                {"ingredient_name": "pepper", "quantity": "1 tsp"},    # Variant (25%)
                {"ingredient_name": "water", "quantity": "1 cup"}
            ]
        },
        "recipe_3": {
            "name": "Okay Dish",
            "aggregateRating": {"ratingValue": "3.0"},
            "recipeIngredient": [
                {"ingredient_name": "salt", "quantity": "1 tsp"},
                {"ingredient_name": "dirt", "quantity": "1 cup"}       # Unique but Low Rated (Not Secret)
            ]
        },
        "recipe_4": {
            "name": "Another Dish",
            "aggregateRating": {"ratingValue": "4.0"},
            "recipeIngredient": [
                {"ingredient_name": "salt", "quantity": "1 tsp"}
            ]
        }
    }

    print("--- Debugging Analysis ---")
    # Replicating key logic from analyze_recipe_data for transparency
    num_recipes = len(mock_recipes)
    ingredient_counts = {}
    for recipe_key, recipe_data in mock_recipes.items():
        ingredients = recipe_data.get("recipeIngredient", [])
        ingredient_names_in_recipe = {
            ing.get("ingredient_name") for ing in ingredients if isinstance(ing, dict) and ing.get("ingredient_name")
        }
        for name in ingredient_names_in_recipe:
            ingredient_counts[name] = ingredient_counts.get(name, 0) + 1

    unique_ingredients = {name for name, count in ingredient_counts.items() if count == 1}
    print(f"\nTotal Recipes: {num_recipes}")
    print(f"\nIngredient Counts (name: count): {json.dumps(ingredient_counts, indent=2)}")
    print(f"\nUnique Ingredients (found in only 1 recipe): {unique_ingredients}")
    print("\n--- Running Full Analysis on Mock Data ---")

    # 2. Run the function
    analyzed_recipes = analyze_recipe_data(mock_recipes)

    # 3. Print Results
    for r_key, r_data in analyzed_recipes.items():
        print(f"\nRecipe: {r_data['name']} ({r_key})")
        for ing in r_data['recipeIngredient']:
            name = ing.get('ingredient_name')
            percent = ing.get('frequency_percent')
            consensus = ing.get('consensus_level', 'Normal')
            is_secret = ing.get('is_secret_ingredient', False)
            rating = r_data.get("aggregateRating", {}).get("ratingValue", "N/A")

            print(f"  - Ingredient: '{name}' | Freq: {percent}% | Consensus: {consensus}")
            if is_secret:
                print(f"    -> ✨ SECRET INGREDIENT DETECTED (Unique & Rating is {rating})")

if __name__ == "__main__":
    test_analysis()

"""
### How to Run the Test

1.  Open your terminal.
2.  Navigate to the `backend` directory:
    ```bash
    cd "backend"
    ```
3.  Run the test script:
    ```bash
    python test_analysis.py
    ```

### What to Look For
*   **Salt**: Should be **100%** and marked **Essential**.
*   **Pepper**: Should be **25%** and marked **Flavor Variant**.
*   **Saffron**: Should be marked as a **SECRET INGREDIENT** (because it's unique and in a 5.0-rated recipe).
*   **Dirt**: Should **NOT** be a secret ingredient (because the rating is only 3.0).

"""
