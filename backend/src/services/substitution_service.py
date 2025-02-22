import json
import logging
from typing import Dict, List, Optional
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from models.schemas import ConversationState

logger = logging.getLogger(__name__)

class SubstitutionService:
    def __init__(self, mistral_client: MistralClient):
        self.mistral_client = mistral_client

    def get_substitution_suggestions(self, ingredient: str, recipe_dict: Dict) -> Dict:
        """Get substitution suggestions for a specific ingredient."""
        suggestion_message = f"""You are a JSON-focused recipe substitution expert. Given this recipe ingredient that needs substitution: "{ingredient}"

        Current recipe context:
        {json.dumps(recipe_dict, indent=2)}

        Create a JSON object with MULTIPLE substitutions that consider:
        1. Common pantry ingredients
        2. Similar flavor profiles
        3. Similar texture properties
        4. Dietary considerations

        Your response must be ONLY a valid JSON object with EXACTLY 3 different substitution options in this format:
        {{
            "substitutions": [
                {{
                    "original": "{ingredient}",
                    "substitute": "option 1",
                    "amount": "amount1",
                    "unit": "unit1",
                    "notes": "brief explanation of why this is a good substitute",
                    "instructions": "any special notes about using this substitute"
                }},
                {{
                    "original": "{ingredient}",
                    "substitute": "option 2",
                    "amount": "amount2",
                    "unit": "unit2",
                    "notes": "brief explanation of why this is a good substitute",
                    "instructions": "any special notes about using this substitute"
                }},
                {{
                    "original": "{ingredient}",
                    "substitute": "option 3",
                    "amount": "amount3",
                    "unit": "unit3",
                    "notes": "brief explanation of why this is a good substitute",
                    "instructions": "any special notes about using this substitute"
                }}
            ],
            "updated_recipe": {{
                "title": "{recipe_dict['title']}",
                "metadata": {json.dumps(recipe_dict['metadata'])},
                "ingredients": [],
                "steps": {json.dumps(recipe_dict['steps'])},
                "equipment": {json.dumps(recipe_dict['equipment'])}
            }}
        }}"""

        try:
            response = self.mistral_client.chat(
                model="mistral-small-latest",
                messages=[
                    ChatMessage(role="system", content="You are a JSON generator that outputs only valid JSON objects with no additional text or comments."),
                    ChatMessage(role="user", content=suggestion_message)
                ],
                temperature=0.3,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()
            content = content.replace('```json\n', '').replace('\n```', '').strip()
            content = '\n'.join(line.strip() for line in content.split('\n'))
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error getting substitution suggestions: {e}")
            raise

    def apply_substitution(self, recipe_dict: Dict, chosen_option: Dict) -> Dict:
        """Apply a chosen substitution to the recipe."""
        try:
            # Find and replace the ingredient
            for i, ingredient in enumerate(recipe_dict["ingredients"]):
                if ingredient["item"].lower() == chosen_option["original"].lower():
                    recipe_dict["ingredients"][i] = {
                        "item": chosen_option["substitute"],
                        "amount": float(chosen_option["amount"]) if isinstance(chosen_option["amount"], (int, float)) 
                                else float(chosen_option["amount"].replace(',', '')),
                        "unit": chosen_option["unit"],
                        "notes": f"Substituted for {chosen_option['original']}: {chosen_option['notes']}"
                    }
                    break

            # Clear substitution-related metadata
            recipe_dict["metadata"].pop("pending_substitution", None)
            recipe_dict["metadata"].pop("substitution_options", None)

            return recipe_dict
        except Exception as e:
            logger.error(f"Error applying substitution: {e}")
            raise 