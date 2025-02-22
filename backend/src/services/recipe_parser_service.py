import json
import logging
from typing import Dict
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

logger = logging.getLogger(__name__)

class RecipeParserService:
    def __init__(self, mistral_client: MistralClient):
        self.mistral_client = mistral_client

    def parse_recipe(self, content: str, content_type: str = "text") -> Dict:
        """Parse recipe content into structured format using Mistral AI."""
        try:
            logger.info(f"Processing recipe parsing request. Type: {content_type}")
            
            if not content.strip():
                raise ValueError("Recipe content cannot be empty")

            # Prepare the system message for recipe parsing
            system_message = """You are a recipe parsing expert. Convert the given recipe text into a structured format with the following fields:
            {
                "title": "Recipe Name",
                "metadata": {
                    "servings": 4,
                    "prepTime": "30 minutes",
                    "cookTime": "1 hour",
                    "difficulty": "medium"
                },
                "ingredients": [
                    {
                        "item": "ingredient name",
                        "amount": 1.0,
                        "unit": "cup",
                        "notes": "optional notes"
                    }
                ],
                "steps": [
                    {
                        "step": 1,
                        "instruction": "step instruction",
                        "timer": {
                            "duration": 300,
                            "type": "cooking"
                        },
                        "checkpoints": ["check 1", "check 2"]
                    }
                ],
                "equipment": ["required equipment 1", "required equipment 2"]
            }
            
            Follow this exact JSON structure. All fields are required except 'notes' in ingredients and 'timer'/'checkpoints' in steps.
            For ingredients:
            - 'item' must be a string
            - 'amount' must be a number (float)
            - 'unit' must be a string and is required even if it's just 'piece' or 'whole'
            - 'notes' is optional
            
            For steps:
            - 'step' must be a number starting from 1
            - 'instruction' must be a string
            - 'timer' is optional and should only be included if there's a specific timing mentioned
            - 'checkpoints' is optional and should only be included if there are specific visual/tactile cues
            
            For metadata:
            - 'servings' must be a number
            - 'prepTime' must be a string in the format "X minutes" or "X hours Y minutes"
            - 'cookTime' must be a string in the format "X minutes" or "X hours Y minutes"
            - 'difficulty' must be one of: "easy", "medium", "hard"
            
            Ensure all measurements are standardized and instructions are clear.
            Your response must be a valid JSON object."""

            # Create the chat messages for Mistral
            messages = [
                ChatMessage(role="system", content=system_message),
                ChatMessage(role="user", content=content)
            ]

            logger.info("Sending request to Mistral API")
            
            # Get response from Mistral
            chat_response = self.mistral_client.chat(
                model="mistral-small-latest",
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
                random_seed=42
            )

            logger.info("Received response from Mistral API")
            
            # Parse the response into structured format
            content = chat_response.choices[0].message.content
            content = content.replace('```json\n', '').replace('\n```', '').strip()
            parsed_recipe = json.loads(content)

            # Validate the response has all required fields
            required_fields = {"title", "metadata", "ingredients", "steps", "equipment"}
            missing_fields = required_fields - set(parsed_recipe.keys())
            if missing_fields:
                logger.error(f"Missing fields in response: {missing_fields}")
                raise ValueError(f"Invalid recipe format: missing fields {missing_fields}")

            # Enhance recipe data
            enhanced_recipe = self._enhance_recipe(parsed_recipe)
            return enhanced_recipe

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            raise ValueError("Failed to parse recipe: Invalid JSON response from AI")
        except Exception as e:
            logger.error(f"Error parsing recipe: {e}")
            raise

    def _enhance_recipe(self, recipe: Dict) -> Dict:
        """Enhance recipe data with additional details and validations."""
        try:
            enhancement_message = """Please review and enhance this recipe data. For each section:

            1. For ingredients with missing or invalid units:
               - Add appropriate units (e.g., 'piece', 'whole', 'medium' for whole items)
               - Convert vague amounts to specific measurements
               - Add descriptive notes for preparation (e.g., "diced", "minced")

            2. For steps:
               - Add timer information where missing but implied
               - Add checkpoints for visual/tactile cues
               - Ensure instructions are clear and specific

            3. For metadata:
               - Validate and correct servings
               - Ensure prep/cook times are realistic
               - Set appropriate difficulty level

            Current recipe data:
            {recipe_json}

            Respond with only the enhanced JSON data maintaining the same structure."""

            # Ask Mistral to enhance the recipe
            enhancement_response = self.mistral_client.chat(
                model="mistral-small-latest",
                messages=[
                    ChatMessage(role="system", content=enhancement_message),
                    ChatMessage(role="user", content=json.dumps(recipe, indent=2))
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = enhancement_response.choices[0].message.content
            content = content.replace('```json\n', '').replace('\n```', '').strip()
            enhanced_recipe = json.loads(content)
            logger.info("Successfully enhanced recipe data")

            # Validate and transform ingredients
            for ingredient in enhanced_recipe["ingredients"]:
                if "unit" not in ingredient:
                    ingredient["unit"] = "piece"
                if "amount" not in ingredient:
                    ingredient["amount"] = 1.0
                if not isinstance(ingredient["amount"], (int, float)):
                    try:
                        ingredient["amount"] = float(ingredient["amount"])
                    except (ValueError, TypeError):
                        ingredient["amount"] = 1.0
                if "notes" not in ingredient:
                    ingredient["notes"] = None

            # Validate and transform steps
            for i, step in enumerate(enhanced_recipe["steps"], 1):
                step["step"] = i
                if "timer" not in step:
                    step["timer"] = None
                if "checkpoints" not in step:
                    step["checkpoints"] = None

            # Validate metadata
            metadata = enhanced_recipe["metadata"]
            if not isinstance(metadata["servings"], (int, float)):
                try:
                    metadata["servings"] = int(metadata["servings"])
                except (ValueError, TypeError):
                    metadata["servings"] = 4

            if metadata["difficulty"] not in ["easy", "medium", "hard"]:
                metadata["difficulty"] = "medium"

            return enhanced_recipe
        except Exception as e:
            logger.warning(f"Failed to enhance recipe data: {e}")
            return recipe 