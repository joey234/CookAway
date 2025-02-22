from typing import Dict, Optional, List
import uuid
from services.recipe_parser_service import RecipeParserService

class Recipe:
    def __init__(self, title: str, metadata: dict, ingredients: list, steps: list, equipment: list):
        self.id = str(uuid.uuid4())
        self.title = title
        self.metadata = metadata
        self.ingredients = ingredients
        self.steps = steps
        self.equipment = equipment

class RecipeService:
    def __init__(self, recipe_parser: RecipeParserService):
        self._recipes: Dict[str, Recipe] = {}
        self.recipe_parser = recipe_parser
        self._test_recipe_id = None
        # Add a test recipe for debugging
        self._add_test_recipe()

    def get_test_recipe_id(self) -> str:
        """Get the ID of the test recipe."""
        return self._test_recipe_id

    def _add_test_recipe(self):
        """Add a test recipe for debugging purposes."""
        test_recipe = Recipe(
            title="Test Pasta with Garlic and Olive Oil",
            metadata={
                "servings": 2,
                "prepTime": "5 minutes",
                "cookTime": "15 minutes",
                "difficulty": "easy",
                "current_step": 1,  # Start at step 1 for testing
                "current_state": "cooking"  # Set state directly to cooking
            },
            ingredients=[
                {"item": "spaghetti", "amount": 200.0, "unit": "grams", "notes": None},
                {"item": "olive oil", "amount": 3.0, "unit": "tablespoons", "notes": "extra virgin"},
                {"item": "garlic", "amount": 4.0, "unit": "cloves", "notes": "thinly sliced"},
                {"item": "red pepper flakes", "amount": 0.5, "unit": "teaspoon", "notes": "optional"},
                {"item": "parsley", "amount": 2.0, "unit": "tablespoons", "notes": "freshly chopped"},
                {"item": "salt", "amount": 1.0, "unit": "teaspoon", "notes": "for pasta water"}
            ],
            steps=[
                {
                    "step": 1,
                    "instruction": "Bring a large pot of water to a boil. Add salt.",
                    "timer": {"duration": 300, "type": "prep"},  # 5 minutes
                    "checkpoints": ["Water should be rolling with big bubbles", "Water should taste like the sea"]
                },
                {
                    "step": 2,
                    "instruction": "Add pasta to the boiling water and cook until al dente.",
                    "timer": {"duration": 480, "type": "cooking"},  # 8 minutes
                    "checkpoints": [
                        "Stir immediately after adding to prevent sticking",
                        "Test pasta 1 minute before timer ends",
                        "Pasta should be firm but not hard when bitten"
                    ]
                },
                {
                    "step": 3,
                    "instruction": "While pasta cooks, heat olive oil in a large pan over medium heat. Add sliced garlic and red pepper flakes.",
                    "timer": {"duration": 120, "type": "cooking"},  # 2 minutes
                    "checkpoints": [
                        "Garlic should turn golden, not brown",
                        "If garlic browns, it will become bitter",
                        "Oil should be shimmering but not smoking"
                    ]
                },
                {
                    "step": 4,
                    "instruction": "Reserve 1 cup of pasta water, then drain pasta.",
                    "checkpoints": [
                        "Don't forget to save the pasta water",
                        "Pasta should still be very hot",
                        "Don't rinse the pasta"
                    ]
                },
                {
                    "step": 5,
                    "instruction": "Add pasta to the pan with garlic oil. Toss well. Add some pasta water if needed.",
                    "timer": {"duration": 60, "type": "cooking"},  # 1 minute
                    "checkpoints": [
                        "Pasta should be well coated with oil",
                        "Add pasta water gradually, 2-3 tablespoons at a time",
                        "Sauce should cling to pasta"
                    ]
                },
                {
                    "step": 6,
                    "instruction": "Finish with fresh parsley, toss once more, and serve immediately.",
                    "checkpoints": [
                        "Parsley should be fresh and bright green",
                        "Pasta should be glossy with oil",
                        "Serve while very hot"
                    ]
                }
            ],
            equipment=[
                "Large pot for pasta",
                "Large frying pan",
                "Colander",
                "Measuring cups and spoons",
                "Sharp knife",
                "Cutting board"
            ]
        )
        self._test_recipe_id = test_recipe.id  # Store the test recipe ID
        self._recipes[test_recipe.id] = test_recipe
        return test_recipe.id

    def import_recipe(self, content: str, content_type: str = "text") -> Recipe:
        """Import a recipe from text or URL."""
        recipe_data = self.recipe_parser.parse_recipe(content, content_type)
        return self.create_recipe(
            title=recipe_data["title"],
            metadata=recipe_data["metadata"],
            ingredients=recipe_data["ingredients"],
            steps=recipe_data["steps"],
            equipment=recipe_data["equipment"]
        )

    def create_recipe(self, title: str, metadata: dict, ingredients: list, steps: list, equipment: list) -> Recipe:
        recipe = Recipe(title, metadata, ingredients, steps, equipment)
        self._recipes[recipe.id] = recipe
        return recipe

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        return self._recipes.get(recipe_id)

    def list_recipes(self) -> List[Recipe]:
        return list(self._recipes.values())

    def delete_recipe(self, recipe_id: str) -> bool:
        if recipe_id in self._recipes:
            del self._recipes[recipe_id]
            return True
        return False 