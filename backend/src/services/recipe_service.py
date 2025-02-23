import os
import httpx
import json
from typing import Dict, Optional, List
import uuid
import logging
from dotenv import load_dotenv
from services.recipe_parser_service import RecipeParserService
from pydantic import BaseModel, Field
from firecrawl import FirecrawlApp

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not FIRECRAWL_API_KEY:
    logger.warning("FIRECRAWL_API_KEY not found in environment variables")
else:
    logger.info("FIRECRAWL_API_KEY loaded successfully")

# Initialize FirecrawlApp
firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY) if FIRECRAWL_API_KEY else None

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"

class RecipeTimer(BaseModel):
    duration: int = Field(description="Duration in seconds")
    type: str = Field(description="Type of timer (prep or cooking)")

class RecipeStep(BaseModel):
    step: int = Field(description="Step number")
    instruction: str = Field(description="Step instruction")
    timer: Optional[RecipeTimer] = Field(None, description="Timer information if needed")
    checkpoints: Optional[List[str]] = Field(None, description="Visual/sensory checkpoints")
    warnings: Optional[List[str]] = Field(None, description="Common mistakes to avoid")
    notes: Optional[List[str]] = Field(None, description="Helpful tips and techniques")
    parallel_with: Optional[List[int]] = Field([], description="Step numbers that can be done in parallel with this step")
    estimated_time: Optional[int] = Field(None, description="Estimated time in seconds this step will take")

class RecipeIngredient(BaseModel):
    item: str = Field(description="Ingredient name")
    amount: float = Field(description="Quantity of ingredient")
    unit: str = Field(description="Unit of measurement")
    notes: Optional[str] = Field(None, description="Additional notes about the ingredient")

class RecipeMetadata(BaseModel):
    servings: int = Field(description="Number of servings")
    prepTime: str = Field(description="Preparation time")
    cookTime: str = Field(description="Cooking time")
    difficulty: str = Field(description="Recipe difficulty (easy, medium, hard)")

class RecipeSchema(BaseModel):
    title: str = Field(description="Recipe title")
    metadata: RecipeMetadata
    ingredients: List[RecipeIngredient]
    steps: List[RecipeStep]
    equipment: List[str] = Field(description="Required kitchen equipment")

class Recipe:
    def __init__(self, title: str, metadata: dict, ingredients: list, steps: list, equipment: list, id: str = None):
        self.id = id if id else str(uuid.uuid4())
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
                    "checkpoints": [
                        "Water should be rolling with big bubbles",
                        "Water should taste like the sea"
                    ],
                    "warnings": [
                        "Don't add salt before the water is boiling",
                        "Using too little water will make pasta stick together"
                    ],
                    "notes": [
                        "Use at least 4 quarts of water per pound of pasta",
                        "The water should taste like sea water"
                    ]
                },
                {
                    "step": 2,
                    "instruction": "While waiting for water to boil, chop garlic and parsley.",
                    "parallel_with": [1],  # Can be done during step 1's timer
                    "estimated_time": 120,  # 2 minutes
                    "checkpoints": [
                        "Garlic should be thinly sliced",
                        "Parsley should be finely chopped"
                    ],
                    "warnings": [
                        "Don't make garlic pieces too thick",
                        "Keep garlic slices even in size"
                    ],
                    "notes": [
                        "A sharp knife will make this easier",
                        "Stack parsley leaves before chopping"
                    ]
                },
                {
                    "step": 3,
                    "instruction": "Add pasta to the boiling water and cook until al dente.",
                    "timer": {"duration": 480, "type": "cooking"},  # 8 minutes
                    "checkpoints": [
                        "Stir immediately after adding to prevent sticking",
                        "Test pasta 1 minute before timer ends",
                        "Pasta should be firm but not hard when bitten"
                    ],
                    "warnings": [
                        "Don't break the pasta",
                        "Don't add oil to the water",
                        "Don't overcook"
                    ],
                    "notes": [
                        "Stir occasionally to prevent sticking",
                        "Test by biting a piece"
                    ]
                },
                {
                    "step": 4,
                    "instruction": "While pasta cooks, heat olive oil in a large pan over medium heat.",
                    "parallel_with": [3],  # Can be done during step 3's timer
                    "estimated_time": 60,  # 1 minute
                    "checkpoints": [
                        "Oil should be shimmering but not smoking"
                    ],
                    "warnings": [
                        "Don't let oil get too hot",
                        "Keep an eye on the heat level"
                    ],
                    "notes": [
                        "Use a wide pan to distribute heat evenly"
                    ]
                },
                {
                    "step": 5,
                    "instruction": "Add sliced garlic and red pepper flakes to the heated oil.",
                    "parallel_with": [3],  # Can also be done during step 3's timer
                    "estimated_time": 120,  # 2 minutes
                    "checkpoints": [
                        "Garlic should turn golden, not brown",
                        "Oil should be fragrant with garlic"
                    ],
                    "warnings": [
                        "Don't let garlic burn",
                        "Keep stirring gently"
                    ],
                    "notes": [
                        "Lower heat if garlic is browning too quickly",
                        "Add red pepper flakes to taste"
                    ]
                },
                {
                    "step": 6,
                    "instruction": "Reserve 1 cup of pasta water, then drain pasta.",
                    "checkpoints": [
                        "Save pasta water before draining",
                        "Pasta should still be very hot"
                    ],
                    "warnings": [
                        "Don't forget to reserve water",
                        "Don't rinse the pasta"
                    ],
                    "notes": [
                        "The starchy water helps create a silky sauce",
                        "Have your measuring cup ready"
                    ]
                },
                {
                    "step": 7,
                    "instruction": "Add pasta to the pan with garlic oil. Toss well, adding pasta water if needed.",
                    "timer": {"duration": 60, "type": "cooking"},  # 1 minute
                    "checkpoints": [
                        "Pasta should be well coated with oil",
                        "Sauce should cling to pasta"
                    ],
                    "warnings": [
                        "Don't add too much pasta water",
                        "Keep tossing to coat evenly"
                    ],
                    "notes": [
                        "Add water gradually, 2-3 tablespoons at a time",
                        "Keep heat on medium-low while tossing"
                    ]
                },
                {
                    "step": 8,
                    "instruction": "Add chopped parsley, toss once more, and serve immediately.",
                    "checkpoints": [
                        "Parsley should be evenly distributed",
                        "Pasta should be glossy with oil"
                    ],
                    "warnings": [
                        "Don't let the dish sit too long",
                        "Don't skip the final toss"
                    ],
                    "notes": [
                        "Reserve some parsley for garnish",
                        "Serve on warmed plates if possible"
                    ]
                }
            ],
            equipment=[
                "Large pot for pasta",
                "Large frying pan",
                "Colander",
                "Measuring cups and spoons",
                "Sharp knife",
                "Cutting board",
                "Tongs or pasta server"
            ]
        )
        self._test_recipe_id = test_recipe.id  # Store the test recipe ID
        self._recipes[test_recipe.id] = test_recipe
        return test_recipe.id

    async def import_recipe(self, content: str, content_type: str = "text") -> Recipe:
        """Import a recipe from text or URL."""
        if content_type == "url":
            recipe_data = await self._extract_recipe_from_url(content)
        else:
            recipe_data = self.recipe_parser.parse_recipe(content, content_type)
        
        return self.create_recipe(
            title=recipe_data["title"],
            metadata=recipe_data["metadata"],
            ingredients=recipe_data["ingredients"],
            steps=recipe_data["steps"],
            equipment=recipe_data["equipment"]
        )

    async def _extract_recipe_from_url(self, url: str) -> Dict:
        """Extract recipe data from a URL using Firecrawl."""
        if not firecrawl_app:
            logger.error("FIRECRAWL_API_KEY is not set in environment variables")
            raise ValueError(
                "FIRECRAWL_API_KEY environment variable is not set. "
                "Please make sure you have added your Firecrawl API key to the .env file"
            )
            
        logger.info(f"Attempting to extract recipe from URL: {url}")
        
        try:
            # Use FirecrawlApp to scrape the URL with our schema
            data = firecrawl_app.scrape_url(url, {
                'url': url,
                'formats': ['json'],
                'jsonOptions': {
                    'schema': RecipeSchema.model_json_schema()
                }
            })
            
            if not data or "json" not in data:
                logger.error("No JSON data in Firecrawl response")
                logger.debug(f"Response content: {data}")
                raise ValueError("No JSON data in Firecrawl response")
            
            raw_recipe = data["json"]
            logger.info("Successfully received recipe data")
            
            # Format the steps data
            for step in raw_recipe.get("steps", []):
                # Convert timer string to proper format if needed
                if isinstance(step.get("timer"), str):
                    try:
                        # Handle different time formats
                        time_str = step["timer"].lower()
                        minutes = 0
                        
                        # Handle ranges (e.g., "25-30 minutes")
                        if '-' in time_str:
                            times = time_str.split('-')
                            minutes = (float(times[0]) + float(times[1])) / 2
                        else:
                            # Extract the first number found
                            import re
                            numbers = re.findall(r'\d+', time_str)
                            if numbers:
                                minutes = float(numbers[0])
                        
                        if 'hour' in time_str:
                            minutes *= 60
                        
                        step["timer"] = {
                            "duration": int(minutes * 60),  # Convert to seconds
                            "type": "cooking"
                        }
                    except Exception as e:
                        logger.warning(f"Failed to parse timer '{step['timer']}': {e}")
                        step["timer"] = None
                
                # Convert checkpoints string to list if needed
                if isinstance(step.get("checkpoints"), str):
                    step["checkpoints"] = [step["checkpoints"]]
                elif not step.get("checkpoints"):
                    step["checkpoints"] = None
                
                # Ensure warnings and notes exist
                if not step.get("warnings"):
                    step["warnings"] = None
                if not step.get("notes"):
                    step["notes"] = None

                # Initialize parallel_with and estimated_time if not present
                if "parallel_with" not in step:
                    step["parallel_with"] = []
                elif isinstance(step["parallel_with"], str):
                    # Handle case where parallel_with might be a comma-separated string
                    try:
                        step["parallel_with"] = [int(x.strip()) for x in step["parallel_with"].split(",")]
                    except (ValueError, AttributeError):
                        step["parallel_with"] = []

                if "estimated_time" not in step:
                    # Default estimated time based on complexity
                    instruction = step["instruction"].lower()
                    if any(word in instruction for word in ["quick", "just", "simply"]):
                        step["estimated_time"] = 60  # 1 minute
                    elif any(word in instruction for word in ["carefully", "precisely"]):
                        step["estimated_time"] = 300  # 5 minutes
                    else:
                        step["estimated_time"] = 180  # 3 minutes default
                elif isinstance(step["estimated_time"], str):
                    # Handle case where estimated_time might be a string
                    try:
                        time_str = step["estimated_time"].lower()
                        minutes = 0
                        if "hour" in time_str:
                            hours = float(re.findall(r'\d+', time_str)[0])
                            minutes = hours * 60
                        else:
                            minutes = float(re.findall(r'\d+', time_str)[0])
                        step["estimated_time"] = int(minutes * 60)  # Convert to seconds
                    except (ValueError, IndexError, AttributeError):
                        step["estimated_time"] = 180  # 3 minutes default
            
            # Ensure metadata has all required fields
            if "metadata" not in raw_recipe:
                raw_recipe["metadata"] = {}
            
            metadata = raw_recipe["metadata"]
            if "servings" not in metadata or not isinstance(metadata["servings"], int):
                metadata["servings"] = 4  # Default serving size
            if "prepTime" not in metadata:
                metadata["prepTime"] = "30 minutes"  # Default prep time
            if "cookTime" not in metadata:
                metadata["cookTime"] = "1 hour"  # Default cook time
            if "difficulty" not in metadata:
                metadata["difficulty"] = "medium"  # Default difficulty
            
            return raw_recipe
                
        except Exception as e:
            logger.error(f"Error processing recipe from URL: {e}", exc_info=True)
            raise ValueError(f"Error processing recipe from URL: {str(e)}")

    def create_recipe(self, title: str, metadata: dict, ingredients: list, steps: list, equipment: list, id: str = None) -> Recipe:
        recipe = Recipe(title, metadata, ingredients, steps, equipment, id)
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