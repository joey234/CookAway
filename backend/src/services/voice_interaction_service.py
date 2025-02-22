import logging
import re
from typing import Dict, Tuple, Optional
from models.schemas import ConversationState
from services.tts_service import TTSService
from services.recipe_service import RecipeService
from services.substitution_service import SubstitutionService

logger = logging.getLogger(__name__)

class VoiceInteractionService:
    def __init__(self, tts_service: TTSService, recipe_service: RecipeService, substitution_service: SubstitutionService):
        self.tts_service = tts_service
        self.recipe_service = recipe_service
        self.substitution_service = substitution_service

    def process_servings_request(self, transcript: str, recipe_dict: Dict) -> Tuple[bytes, str, ConversationState, Dict]:
        """Process a request to change the number of servings."""
        number_mapping = {
            'one': '1', 'won': '1', 'juan': '1', 'a': '1',
            'two': '2', 'too': '2', 'to': '2',
            'three': '3', 'tree': '3',
            'four': '4', 'for': '4',
            'five': '5', 'fine': '5',
            'six': '6', 'sex': '6',
            'seven': '7',
            'eight': '8', 'ate': '8',
            'nine': '9',
            'ten': '10'
        }
        
        transcript_lower = transcript.lower()
        for word, digit in number_mapping.items():
            transcript_lower = transcript_lower.replace(word, digit)
        
        numbers = re.findall(r'\d+', transcript_lower)
        if numbers:
            new_servings = int(numbers[0])
            next_state = ConversationState.ASKING_SUBSTITUTION
            
            # Adjust servings and create new recipe
            adjusted_recipe = self.tts_service.adjust_recipe_servings(recipe_dict, new_servings)
            adjusted_recipe["metadata"]["current_state"] = next_state
            
            # Remove id field if present
            adjusted_recipe.pop('id', None)
            
            # Generate response and ensure it's ASCII-compatible
            audio_data, response_text = self.tts_service.generate_servings_response(adjusted_recipe, new_servings)
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            
            return audio_data, response_text, next_state, adjusted_recipe
        else:
            # Generate response and ensure it's ASCII-compatible
            audio_data, response_text = self.tts_service.generate_voice_response(
                "I need a specific number. Please tell me how many servings you'd like to make.",
                ConversationState.ASKING_SERVINGS
            )
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            
            return audio_data, response_text, ConversationState.ASKING_SERVINGS, recipe_dict

    def process_substitution_request(self, transcript: str, recipe_dict: Dict) -> Tuple[bytes, str, ConversationState, Dict, Optional[list]]:
        """Process a request for ingredient substitution."""
        transcript_lower = transcript.lower()
        pending = recipe_dict.get("metadata", {}).get("pending_substitution")
        
        # Check for "no" to further substitutions
        if any(word in transcript_lower for word in ["no", "nope", "nah", "good", "fine"]) and not pending:
            recipe_dict["metadata"]["current_state"] = ConversationState.READY_TO_COOK
            
            # First, summarize the final ingredients list
            ingredients_text = "Great! Here's your final list of ingredients:\n"
            for ingredient in recipe_dict["ingredients"]:
                if formatted := self.tts_service._format_ingredient(ingredient):
                    ingredients_text += f"- {formatted}\n"
            
            # Then add the equipment list
            equipment_text = ingredients_text + "\nNow, here's the equipment you'll need:\n" + \
                           "\n".join(f"- {item}" for item in recipe_dict["equipment"]) + \
                           "\nDo you have all the equipment ready? Say 'ready' when you want to start cooking."
            
            # Remove id field if present
            recipe_dict.pop('id', None)
            
            audio_data, response_text = self.tts_service.generate_voice_response(equipment_text, ConversationState.READY_TO_COOK)
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.READY_TO_COOK, recipe_dict, None
        
        # Check for specific ingredient mention
        if not pending:
            for ingredient in recipe_dict["ingredients"]:
                if ingredient["item"].lower() in transcript_lower:
                    substitution_data = self.substitution_service.get_substitution_suggestions(
                        ingredient["item"],
                        recipe_dict
                    )
                    
                    options_text = f"Here are some substitutions for {ingredient['item']}. "
                    for i, option in enumerate(substitution_data["substitutions"], 1):
                        options_text += f"Option {i}: {option['substitute']}. You'll need {option['amount']} {option['unit']}. {option['notes']}. "
                    options_text += "Which option would you like to use? Just say the number: 1, 2, or 3."
                    
                    recipe_dict["metadata"]["pending_substitution"] = {
                        "ingredient": ingredient["item"],
                        "options": substitution_data["substitutions"],
                        "awaiting_selection": True
                    }
                    
                    # Remove id field if present
                    recipe_dict.pop('id', None)
                    
                    audio_data, response_text = self.tts_service.generate_voice_response(options_text, ConversationState.ASKING_SUBSTITUTION)
                    response_text = response_text.encode('ascii', 'replace').decode('ascii')
                    return audio_data, response_text, ConversationState.ASKING_SUBSTITUTION, recipe_dict, substitution_data["substitutions"]
        
        # Handle pending substitution confirmation
        if pending and pending.get("ingredient"):
            if any(word in transcript_lower for word in ["yes", "yeah", "yep", "sure", "okay"]):
                substitution_data = self.substitution_service.get_substitution_suggestions(
                    pending["ingredient"],
                    recipe_dict
                )
                
                options_text = f"I found {len(substitution_data['substitutions'])} possible substitutions for {pending['ingredient']}. Let me read them to you. "
                for i, option in enumerate(substitution_data["substitutions"], 1):
                    options_text += f"Option {i}: {option['substitute']}. You'll need {option['amount']} {option['unit']}. {option['notes']}. "
                options_text += "Which option would you like to use? Just say the number: 1, 2, or 3."
                
                recipe_dict["metadata"]["pending_substitution"] = {
                    "ingredient": pending["ingredient"],
                    "options": substitution_data["substitutions"],
                    "awaiting_selection": True
                }
                
                # Remove id field if present
                recipe_dict.pop('id', None)
                
                audio_data, response_text = self.tts_service.generate_voice_response(options_text, ConversationState.ASKING_SUBSTITUTION)
                response_text = response_text.encode('ascii', 'replace').decode('ascii')
                return audio_data, response_text, ConversationState.ASKING_SUBSTITUTION, recipe_dict, substitution_data["substitutions"]
            
            elif pending.get("awaiting_selection") and any(num in transcript_lower for num in ["1", "2", "3", "one", "two", "three"]):
                number_map = {"one": "1", "two": "2", "three": "3"}
                for word, digit in number_map.items():
                    transcript_lower = transcript_lower.replace(word, digit)
                
                selection = next(num for num in ["1", "2", "3"] if num in transcript_lower)
                index = int(selection) - 1
                
                if "options" in pending and 0 <= index < len(pending["options"]):
                    chosen_option = pending["options"][index]
                    updated_recipe = self.substitution_service.apply_substitution(recipe_dict, chosen_option)
                    
                    # Remove id field if present
                    updated_recipe.pop('id', None)
                    
                    response_text = f"I've updated the recipe to use {chosen_option['substitute']}. Do you need to substitute any other ingredients?"
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.ASKING_SUBSTITUTION)
                    response_text = response_text.encode('ascii', 'replace').decode('ascii')
                    return audio_data, response_text, ConversationState.ASKING_SUBSTITUTION, updated_recipe, None
        
        # Default response for unclear input
        audio_data, response_text = self.tts_service.generate_voice_response(
            "If you need to substitute any ingredient, just say which ingredient you want to substitute.",
            ConversationState.ASKING_SUBSTITUTION
        )
        response_text = response_text.encode('ascii', 'replace').decode('ascii')
        
        # Remove id field if present
        recipe_dict.pop('id', None)
        
        return audio_data, response_text, ConversationState.ASKING_SUBSTITUTION, recipe_dict, None

    def process_ready_to_cook(self, transcript: str) -> Tuple[bytes, str, ConversationState]:
        """Process a request to start cooking."""
        transcript_lower = transcript.lower()
        if any(word in transcript_lower for word in ["yes", "yeah", "yep", "sure", "okay", "ready"]):
            audio_data, response_text = self.tts_service.generate_voice_response(
                "Great! Let's begin cooking. I'll guide you through each step. Say 'start' to begin with step 1.",
                ConversationState.COOKING
            )
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.COOKING
        elif any(word in transcript_lower for word in ["no", "nope", "nah", "wait", "not yet"]):
            audio_data, response_text = self.tts_service.generate_voice_response(
                "No problem. Take your time to prepare. Let me know when you're ready by saying 'ready'.",
                ConversationState.READY_TO_COOK
            )
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.READY_TO_COOK
        else:
            audio_data, response_text = self.tts_service.generate_voice_response(
                "I didn't understand. Are you ready to start cooking? Please say 'ready' when you want to begin.",
                ConversationState.READY_TO_COOK
            )
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.READY_TO_COOK

    def process_cooking_step(self, transcript: str, recipe_dict: Dict) -> Tuple[bytes, str, ConversationState, Dict, Optional[Dict]]:
        """Process cooking steps and handle timers."""
        transcript_lower = transcript.lower()
        current_step = recipe_dict.get("metadata", {}).get("current_step", 0)
        timer_running = recipe_dict.get("metadata", {}).get("timer_running", False)
        steps = recipe_dict.get("steps", [])
        
        # Initialize current step if not set
        if current_step == 0 and any(word in transcript_lower for word in ["start", "begin", "first"]):
            current_step = 1
            recipe_dict["metadata"]["current_step"] = current_step
        
        # Handle timer-related commands
        if timer_running:
            if "stop timer" in transcript_lower or "cancel timer" in transcript_lower:
                recipe_dict["metadata"]["timer_running"] = False
                audio_data, response_text = self.tts_service.generate_voice_response(
                    "Timer stopped. Would you like me to repeat the current step?",
                    ConversationState.COOKING
                )
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
        
        # Handle step navigation
        if current_step > 0 and current_step <= len(steps):
            current_step_data = steps[current_step - 1]
            
            # Handle "next" command
            if "next" in transcript_lower and current_step < len(steps):
                current_step += 1
                recipe_dict["metadata"]["current_step"] = current_step
                next_step = steps[current_step - 1]
                
                # Build comprehensive step guidance
                response_text = self._build_step_guidance(next_step, current_step)
                
                audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
            
            # Handle "repeat" command
            elif "repeat" in transcript_lower:
                response_text = self._build_step_guidance(current_step_data, current_step)
                
                audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
            
            # Handle timer start request
            elif any(word in transcript_lower for word in ["start timer", "yes", "start the timer"]) and current_step_data.get("timer"):
                timer_data = current_step_data["timer"]
                recipe_dict["metadata"]["timer_running"] = True
                
                duration = timer_data["duration"]
                minutes = duration // 60
                seconds = duration % 60
                time_str = f"{minutes} minutes and {seconds} seconds" if minutes > 0 else f"{seconds} seconds"
                
                response_text = f"Starting timer for {time_str}. I'll remind you when there are 20 seconds left and when the timer is done."
                audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                    "timer": {
                        "duration": timer_data["duration"],
                        "type": timer_data["type"],
                        "step": current_step,
                        "warning_time": 20  # 20 seconds before timer ends
                    }
                }
            
            # Handle completion
            elif current_step == len(steps) and "finish" in transcript_lower:
                audio_data, response_text = self.tts_service.generate_voice_response(
                    "Congratulations! You've completed all the steps. Your dish should be ready now. Enjoy!",
                    ConversationState.COOKING
                )
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
        
        # Default response for unclear input or initial state
        if current_step == 0:
            audio_data, response_text = self.tts_service.generate_voice_response(
                "Say 'start' to begin with the first step.",
                ConversationState.COOKING
            )
        else:
            audio_data, response_text = self.tts_service.generate_voice_response(
                "You can say 'next' for the next step, 'repeat' to hear the current step again, or 'finish' if you're done.",
                ConversationState.COOKING
            )
        
        return audio_data, response_text, ConversationState.COOKING, recipe_dict, None

    def _build_step_guidance(self, step_data: Dict, step_number: int) -> str:
        """Build comprehensive guidance for a cooking step."""
        response_parts = [f"Step {step_number}: {step_data['instruction']}"]
        
        # Add checkpoints/visual cues
        if step_data.get("checkpoints"):
            response_parts.append("\nWhat to look for:")
            for checkpoint in step_data["checkpoints"]:
                response_parts.append(f"• {checkpoint}")
        
        # Add common mistakes to avoid (if available)
        if step_data.get("warnings"):
            response_parts.append("\nCommon mistakes to avoid:")
            for warning in step_data["warnings"]:
                response_parts.append(f"• {warning}")
        
        # Add notes (if available)
        if step_data.get("notes"):
            response_parts.append("\nHelpful tips:")
            for note in step_data["notes"]:
                response_parts.append(f"• {note}")
        
        # Add timer information if available
        if step_data.get("timer"):
            duration = step_data["timer"]["duration"]
            minutes = duration // 60
            seconds = duration % 60
            time_str = f"{minutes} minutes" if minutes > 0 else f"{seconds} seconds"
            response_parts.append(f"\nThis step takes {time_str}. Would you like me to start a timer?")
        
        return "\n".join(response_parts) 