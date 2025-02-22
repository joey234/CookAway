import requests
import os
from typing import Optional, List, Dict, Any
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ConversationState(str, Enum):
    INITIAL_SUMMARY = "initial_summary"
    ASKING_SERVINGS = "asking_servings"
    ASKING_SUBSTITUTION = "asking_substitution"
    READY_TO_COOK = "ready_to_cook"
    COOKING = "cooking"

class TTSService:
    def __init__(self):
        self.api_key = os.getenv("ELEVEN_LABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVEN_LABS_API_KEY environment variable is not set")
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }

    def _generate_audio(self, text: str) -> bytes:
        """Generate audio from text using ElevenLabs API."""
        try:
            logger.info("Generating audio")
            
            # Use the Bella voice ID
            voice_id = "EXAVITQu4vr4xnSDxMaL"
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            
            payload = {
                "text": text,
                "model_id": "eleven_flash_v2_5",
                "voice_settings": {
                    "stability": 0.75,
                    "similarity_boost": 0.75
                }
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise

    def generate_recipe_summary(self, recipe_data: dict, state: ConversationState = ConversationState.INITIAL_SUMMARY) -> tuple[bytes, str]:
        """Generate audio summary of the recipe."""
        try:
            summary_text = self._create_summary_text(recipe_data, state)
            audio_data = self._generate_audio(summary_text)
            return audio_data, summary_text
        except Exception as e:
            logger.error(f"Error generating recipe summary: {e}")
            raise

    def generate_voice_response(self, message: str, state: ConversationState) -> tuple[bytes, str]:
        """Generate a voice response for the current conversation state."""
        try:
            audio_data = self._generate_audio(message)
            return audio_data, message
        except Exception as e:
            logger.error(f"Error generating voice response: {e}")
            raise

    def generate_substitution_response(
        self, 
        recipe_id: str, 
        original_ingredient: str, 
        updated_recipe: dict,
        suggestion: Optional[str] = None
    ) -> tuple[bytes, str]:
        """Generate a response explaining the substitution and listing equipment."""
        try:
            response_text = ""
            
            # Add Mistral's suggestion if provided
            if suggestion:
                response_text = f"{suggestion}\n\n"
            
            # Find the substituted ingredient
            substituted_ingredient = next(
                (ing for ing in updated_recipe["ingredients"] 
                 if "substitute for" in (ing.get("notes") or "").lower()),
                None
            )

            if substituted_ingredient:
                formatted_ingredient = self._format_ingredient(substituted_ingredient)
                if formatted_ingredient:
                    response_text += f"I've updated the recipe with this substitution. "
            
            response_text += "Here's your complete ingredient list:\n"
            valid_ingredients = [
                formatted for ing in updated_recipe["ingredients"] 
                if (formatted := self._format_ingredient(ing))
            ]
            
            if valid_ingredients:
                for ingredient in valid_ingredients:
                    response_text += f"- {ingredient}\n"
            
            # Add equipment list
            response_text += "\nNow, here's the equipment you'll need:\n"
            for item in updated_recipe.get("equipment", []):
                response_text += f"- {item}\n"
            
            response_text += "\nDo you have all the equipment ready? Say 'ready' when you want to start cooking."

            audio_data = self._generate_audio(response_text)
            return audio_data, response_text
        except Exception as e:
            logger.error(f"Error generating substitution response: {e}")
            raise

    def _format_ingredient(self, ing: Dict) -> Optional[str]:
        """Format a single ingredient in a natural way."""
        if not ing or not ing.get("item"):
            return None

        amount = ing.get("amount")
        unit = (ing.get("unit") or "").lower()
        item = (ing.get("item") or "").lower()
        
        # Handle special cases
        if "to taste" in unit:
            return f"{item} to taste"
        if "for garnish" in unit:
            return f"{item} for garnish"

        parts = []
        
        # Format the amount if present
        if amount:
            # Convert float to ASCII fraction representation
            if isinstance(amount, float):
                if amount.is_integer():
                    amount = int(amount)
                elif amount == 0.5:
                    amount = "1/2"
                elif amount == 0.25:
                    amount = "1/4"
                elif amount == 0.75:
                    amount = "3/4"
                elif amount == 0.33:
                    amount = "1/3"
                elif amount == 0.67:
                    amount = "2/3"
                elif amount == 0.125:
                    amount = "1/8"
                else:
                    # For other decimal values, round to 2 decimal places
                    amount = round(amount, 2)
            
            # Handle size descriptors
            if unit in ["small", "medium", "large"]:
                parts.append(f"{amount} {unit}" if amount > 1 else unit)
            else:
                parts.append(str(amount))
                if unit and unit not in ["whole", "piece", "pieces"]:
                    parts.append(unit)

        # Add the item name
        if amount and unit in ["whole", "piece", "pieces"]:
            # Make item plural if needed
            if amount > 1:
                if item.endswith('ch') or item.endswith('sh') or item.endswith('ss'):
                    item += 'es'
                elif not item.endswith('s'):
                    item += 's'
            parts.append(item)
        else:
            parts.append(item)

        return " ".join(parts)

    def _format_step(self, step: Dict) -> str:
        """Format a single step with its timer information."""
        instruction = step["instruction"]
        timer = step.get("timer")
        checkpoints = step.get("checkpoints")

        if timer and timer.get("duration"):
            duration = timer["duration"]
            minutes = duration // 60
            seconds = duration % 60
            
            time_str = ""
            if minutes > 0:
                time_str += f"{minutes} minute{'s' if minutes != 1 else ''}"
            if seconds > 0:
                if time_str:
                    time_str += " and "
                time_str += f"{seconds} second{'s' if seconds != 1 else ''}"
            
            instruction += f" This step takes {time_str}."

        if checkpoints and isinstance(checkpoints, list) and checkpoints:
            checkpoint_str = ", ".join(checkpoints[:-1])
            if len(checkpoints) > 1:
                checkpoint_str += f", and {checkpoints[-1]}"
            else:
                checkpoint_str = checkpoints[0]
            instruction += f" Look for these signs: {checkpoint_str}."

        return instruction

    def _adjust_amount(self, original_amount: float, original_servings: int, new_servings: int) -> float:
        """Adjust ingredient amount based on new serving size."""
        return (original_amount * new_servings) / original_servings

    def adjust_recipe_servings(self, recipe: dict, new_servings: int) -> dict:
        """Create a new recipe with adjusted serving size and scaled ingredients."""
        original_servings = recipe["metadata"]["servings"]
        logger.info(f"Adjusting servings from {original_servings} to {new_servings}")
        
        # Create a copy of the recipe
        adjusted_recipe = {
            "title": recipe["title"],
            "metadata": recipe["metadata"].copy(),  # Make a copy of metadata to preserve all fields
            "ingredients": [
                {
                    **ingredient,
                    "amount": self._adjust_amount(
                        ingredient["amount"],
                        original_servings,
                        new_servings
                    )
                }
                for ingredient in recipe["ingredients"]
            ],
            "steps": recipe["steps"],
            "equipment": recipe["equipment"]
        }
        
        # Update only the servings count in metadata
        adjusted_recipe["metadata"]["servings"] = new_servings
        logger.info(f"Adjusted recipe metadata: {adjusted_recipe['metadata']}")
        
        return adjusted_recipe

    def generate_servings_response(self, recipe: dict, new_servings: int) -> tuple[bytes, str]:
        """Generate a response for serving size adjustment."""
        try:
            response_text = f"I've adjusted the recipe for {new_servings} servings. Here are the ingredients you'll need:\n\n"
            
            # Add adjusted ingredients to the response
            valid_ingredients = [
                formatted for ing in recipe["ingredients"] 
                if (formatted := self._format_ingredient(ing))
            ]
            
            if valid_ingredients:
                for ingredient in valid_ingredients:
                    # Ensure each ingredient line is ASCII-compatible
                    ingredient = ingredient.encode('ascii', 'replace').decode('ascii')
                    response_text += f"- {ingredient}\n"
            
            response_text += "\nDo you need to substitute any of these ingredients?"
            
            # Generate audio from ASCII-compatible text
            audio_data = self._generate_audio(response_text)
            return audio_data, response_text
        except Exception as e:
            logger.error(f"Error generating servings response: {e}")
            raise

    def _create_summary_text(self, recipe_data: Dict[str, Any], state: ConversationState) -> str:
        title = recipe_data.get('title', '')
        metadata = recipe_data.get('metadata', {})
        ingredients = recipe_data.get('ingredients', [])
        equipment = recipe_data.get('equipment', [])
        
        if state == ConversationState.INITIAL_SUMMARY:
            # Start with recipe name and directly ask for servings
            summary = f"{title}! "
            summary += "How many servings would you like to make?"
            
        elif state == ConversationState.ASKING_SUBSTITUTION:
            # List ingredients and ask about substitutions
            summary = "Here are all the ingredients you'll need:\n"
            for ingredient in ingredients:
                if formatted := self._format_ingredient(ingredient):
                    summary += f"- {formatted}\n"
            summary += "\nDo you need to substitute any of these ingredients?"
            
        elif state == ConversationState.READY_TO_COOK:
            # Confirm ingredients and list equipment
            summary = "Great! Now that we have all the ingredients ready, "
            summary += "here's the equipment you'll need:\n"
            for item in equipment:
                summary += f"- {item}\n"
            summary += "\nDo you have all the equipment ready? Say 'ready' when you want to start cooking."
            
        else:
            summary = "I'm ready to guide you through the cooking steps. Let me know when you want to begin."
            
        return summary 