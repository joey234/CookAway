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

    def get_llm_cooking_guidance(self, context: Dict) -> str:
        """Get cooking guidance from Mistral based on context."""
        try:
            # Format the current step data nicely
            current_step_info = ""
            if context['current_step_data']:
                current_step_info = f"""Current instruction: {context['current_step_data'].get('instruction', '')}

Visual checkpoints to look for:
{self._format_list(context['current_step_data'].get('checkpoints', []))}

Common mistakes to watch out for:
{self._format_list(context['current_step_data'].get('warnings', []))}

Helpful tips:
{self._format_list(context['current_step_data'].get('notes', []))}

Timer information:
{self._format_timer(context['current_step_data'].get('timer', {}))}"""

            # Format available parallel tasks
            parallel_tasks_info = ""
            if context['available_tasks']:
                parallel_tasks_info = "\nAvailable parallel tasks:\n" + "\n".join(
                    f"• Step {task['step_number']}: {task['instruction']} "
                    f"(estimated time: {task['estimated_time'] // 60}m {task['estimated_time'] % 60}s)"
                    for task in context['available_tasks']
                )

            # Format completed steps with their status
            completed_steps_info = "\nCompleted steps: " + (
                ", ".join(f"Step {step}" for step in context['completed_steps'])
                if context['completed_steps'] else "None"
            )

            # Special handling for timer start requests
            user_input_lower = context['user_input'].lower()
            if user_input_lower in ['yes', 'yeah', 'sure', 'okay', 'ok'] and context['current_step_data'] and context['current_step_data'].get('timer'):
                duration = context['current_step_data']['timer']['duration']
                minutes = duration // 60
                seconds = duration % 60
                time_str = []
                if minutes:
                    time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds:
                    time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
                response = f"Starting a timer for {' and '.join(time_str)}."
                if context['available_tasks']:
                    response += " While we wait, you can:\n"
                    for task in context['available_tasks']:
                        response += f"• Step {task['step_number']}: {task['instruction']} "
                        response += f"(estimated time: {task['estimated_time'] // 60}m {task['estimated_time'] % 60}s)\n"
                return f"{response}\nSYSTEM_ACTION: START_TIMER:{context['current_step']}"

            # Construct a detailed prompt for Mistral that includes action instructions
            prompt = f"""CURRENT COOKING CONTEXT:
Step {context['current_step']} of {context['total_steps']}
{current_step_info}

RECIPE STATE:
- Timer running: {context['timer_running']}
{completed_steps_info}
{parallel_tasks_info}

RECIPE RESOURCES:
Available ingredients:
{self._format_ingredients_list(context['ingredients'])}

Equipment being used:
{', '.join(context['equipment'])}

Previous steps (for context):
{self._format_previous_steps(context['all_steps'], context['current_step'])}

USER'S INPUT:
{context['user_input']}

As a cooking assistant, guide the user through the recipe. For each response:
1. If the user says "start" and no step is active:
   - Provide the first step's instructions
   - Include SYSTEM_ACTION: START_COOKING

2. If the user asks a question:
   - Provide a clear, helpful answer
   - No system action needed unless explicitly requested

3. If the user indicates completion ("done", "finished", etc.):
   - Confirm completion
   - Include SYSTEM_ACTION: MARK_COMPLETED:X (where X is the step number)
   - List any newly available tasks
   - Suggest the next step

4. If the user wants to start a timer:
   - Confirm timer start
   - Include SYSTEM_ACTION: START_TIMER:X (where X is the step number)
   - Suggest parallel tasks if available

5. If a timer is running and the user asks what to do:
   - List available parallel tasks
   - Provide guidance on current step progress

6. If all steps are completed:
   - Congratulate the user
   - Include SYSTEM_ACTION: FINISH_COOKING

Format your response as:
[Conversational response to user]
SYSTEM_ACTION: [ACTION_TYPE:step_number] (if needed)"""

            # Use Mistral to get the response
            from services.mistral_service import get_mistral_response
            logger.info("Sending prompt to Mistral:\n%s", prompt)
            response = get_mistral_response(prompt, context)
            logger.info("Raw response from Mistral:\n%s", response)
            
            # Validate response format
            if "SYSTEM_ACTION:" not in response and context['user_input'].lower() == "start":
                # If user says "start" and we don't get a proper response, force the START_COOKING action
                return (
                    "Let's begin cooking! I'll guide you through each step.\n\n"
                    f"Step 1: {context['all_steps'][0]['instruction']}\n"
                    "Would you like me to start a timer for this step?\n"
                    "SYSTEM_ACTION: START_COOKING"
                )
            
            return response

        except Exception as e:
            logger.error(f"Error getting Mistral response: {e}")
            # Return a properly formatted error response
            return (
                "I apologize, but I'm having trouble processing your request right now. "
                "Let me repeat the current step for you.\n"
                "SYSTEM_ACTION: NEXT_STEP"
            )

    def _format_list(self, items: List[str]) -> str:
        """Format a list of items with bullet points."""
        if not items:
            return "None provided"
        return "\n".join(f"• {item}" for item in items)

    def _format_timer(self, timer: Dict) -> str:
        """Format timer information."""
        if not timer or 'duration' not in timer:
            return "No timer for this step"
        
        duration = timer['duration']
        minutes = duration // 60
        seconds = duration % 60
        time_str = []
        if minutes:
            time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds:
            time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        return f"This step takes {' and '.join(time_str)}"

    def _format_ingredients_list(self, ingredients: List[Dict]) -> str:
        """Format ingredients list for the prompt."""
        return "\n".join(
            f"- {ingredient.get('amount', '')} {ingredient.get('unit', '')} {ingredient['item']}"
            for ingredient in ingredients
        )

    def _format_previous_steps(self, steps: List[Dict], current_step: int) -> str:
        """Format relevant previous steps for context."""
        if current_step <= 1:
            return "No previous steps."
        
        # Include up to 2 previous steps for context
        start_step = max(0, current_step - 3)
        relevant_steps = steps[start_step:current_step-1]
        
        return "\n".join(
            f"Step {i+start_step+1}: {step['instruction']}"
            for i, step in enumerate(relevant_steps)
        ) 