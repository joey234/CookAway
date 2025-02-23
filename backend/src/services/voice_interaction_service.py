import logging
import re
from typing import Dict, Tuple, Optional
from models.schemas import ConversationState
from services.tts_service import TTSService
from services.recipe_service import RecipeService
from services.substitution_service import SubstitutionService
from services.parallel_task_service import ParallelTaskService

logger = logging.getLogger(__name__)

class VoiceInteractionService:
    def __init__(self, tts_service: TTSService, recipe_service: RecipeService, substitution_service: SubstitutionService, parallel_task_service: ParallelTaskService):
        self.tts_service = tts_service
        self.recipe_service = recipe_service
        self.substitution_service = substitution_service
        self.parallel_task_service = parallel_task_service

    def process_servings_request(self, transcript: str, recipe_dict: Dict) -> Tuple[bytes, str, ConversationState, Dict]:
        """Process a request to change the number of servings."""
        numbers = re.findall(r'\d+', transcript)
        logger.info(f"Processing servings request. Found numbers: {numbers}")
        
        if numbers:
            new_servings = int(numbers[0])
            next_state = ConversationState.ASKING_SUBSTITUTION
            
            # Adjust servings and create new recipe
            adjusted_recipe = self.tts_service.adjust_recipe_servings(recipe_dict, new_servings)
            adjusted_recipe["metadata"]["current_state"] = next_state
            
            # Preserve the recipe ID if it exists
            recipe_id = recipe_dict.get('id')
            if recipe_id:
                adjusted_recipe["id"] = recipe_id
            
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
        has_made_substitutions = recipe_dict.get("metadata", {}).get("has_made_substitutions", False)
        
        # Check for "no" to further substitutions
        if any(word in transcript_lower for word in ["no", "nope", "nah", "good", "fine"]) and not pending:
            recipe_dict["metadata"]["current_state"] = ConversationState.READY_TO_COOK
            
            # Only show final ingredients if substitutions were made
            if has_made_substitutions:
                response_text = "Great! Here's your final list of ingredients with the substitutions:\n"
                for ingredient in recipe_dict["ingredients"]:
                    if formatted := self.tts_service._format_ingredient(ingredient):
                        response_text += f"- {formatted}\n"
                response_text += "\nNow, here's the equipment you'll need:\n"
            else:
                response_text = "Great! Here's the equipment you'll need:\n"
            
            # Add equipment list
            response_text += "\n".join(f"- {item}" for item in recipe_dict["equipment"])
            response_text += "\nDo you have all the equipment ready? Say 'ready' when you want to start cooking."
            
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.READY_TO_COOK)
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
                    
                    # Mark that substitutions have been made
                    updated_recipe["metadata"]["has_made_substitutions"] = True
                    
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
        """Process cooking steps and handle timers with parallel tasks."""
        transcript_lower = transcript.lower()
        current_step = recipe_dict.get("metadata", {}).get("current_step", 0)
        timer_running = recipe_dict.get("metadata", {}).get("timer_running", False)
        steps = recipe_dict.get("steps", [])
        
        # Get current step data early
        current_step_data = steps[current_step - 1] if current_step > 0 and current_step <= len(steps) else None

        # Initialize parallel tasks if not already done or if explicitly requested
        if not hasattr(self.parallel_task_service, 'parallel_tasks') or not self.parallel_task_service.parallel_tasks or transcript_lower == "initialize parallel tasks":
            logger.info("Initializing parallel tasks for recipe")
            self.parallel_task_service.analyze_recipe_for_parallel_tasks(steps)
            if transcript_lower == "initialize parallel tasks":
                audio_data, response_text = self.tts_service.generate_voice_response(
                    "Parallel tasks initialized. Say 'start' to begin cooking.",
                    ConversationState.COOKING
                )
                available_tasks = self.parallel_task_service.get_available_parallel_tasks(1, float('inf'))
                logger.info(f"Available parallel tasks after initialization: {available_tasks}")
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                    "hasTimer": False,
                    "parallelTasks": available_tasks if available_tasks else None
                }

        # Handle timer completion
        if "timer finished" in transcript_lower or "timer done" in transcript_lower:
            recipe_dict["metadata"]["timer_running"] = False
            timer_end_data = self.parallel_task_service.end_timer_period()
            logger.info(f"Timer ended with data: {timer_end_data}")
            
            response_text = "Timer finished. "
            if timer_end_data.get("completed_parallel_tasks"):
                completed_steps = timer_end_data["completed_parallel_tasks"]
                response_text += f"You've completed step{'s' if len(completed_steps) > 1 else ''} {', '.join(map(str, completed_steps))}. "
            
            if timer_end_data.get("next_main_step"):
                next_step = steps[timer_end_data["next_main_step"] - 1]
                response_text += f"\nLet's move on to step {timer_end_data['next_main_step']}: {next_step['instruction']}"
                recipe_dict["metadata"]["current_step"] = timer_end_data["next_main_step"]
            
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
            return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                "duration": 0,
                "type": "stop",
                "step": current_step,
                "warning_time": 0,
                "available_next_steps": timer_end_data.get("available_next_steps")
            }

        # Handle clarifying questions and issues first
        if any(word in transcript_lower for word in ["help", "what", "how", "why", "can", "should", "could", "problem", "wrong", "issue", "too much", "not enough"]):
            # Extract the current step data if we're in a step
            context = {
                "recipe_title": recipe_dict.get("title", ""),
                "current_step": current_step,
                "total_steps": len(steps),
                "current_step_data": current_step_data,
                "all_steps": steps,
                "ingredients": recipe_dict.get("ingredients", []),
                "equipment": recipe_dict.get("equipment", []),
                "question": transcript,
            }
            
            # Get LLM response through TTS service
            response_text = self.tts_service.get_llm_cooking_guidance(context)
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
            return audio_data, response_text, ConversationState.COOKING, recipe_dict, None

        # Handle start command
        if any(word in transcript_lower for word in ["start", "begin", "first"]):
            current_step = 1
            recipe_dict["metadata"]["current_step"] = current_step
            first_step = steps[current_step - 1]
            response_text = self._build_step_guidance(first_step, current_step)
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
            return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
        
        # Handle timer-related commands
        if timer_running:
            # Handle timer stop
            if "stop timer" in transcript_lower or "cancel timer" in transcript_lower:
                recipe_dict["metadata"]["timer_running"] = False
                timer_end_data = self.parallel_task_service.end_timer_period()
                
                response_text = "Timer stopped. "
                if timer_end_data["completed_parallel_tasks"]:
                    completed_steps = timer_end_data["completed_parallel_tasks"]
                    response_text += f"You've completed step{'s' if len(completed_steps) > 1 else ''} {', '.join(map(str, completed_steps))} during this time. "
                response_text += "Would you like me to repeat the current step?"
                
                audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                    "duration": 0,
                    "type": "stop",
                    "step": current_step,
                    "warning_time": 0
                }
            
            # Handle parallel task selection
            if transcript_lower.isdigit():
                step_number = int(transcript_lower)
                available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                    current_step,
                    current_step_data["timer"]["duration"]
                )
                
                if any(task["step_number"] == step_number for task in available_tasks):
                    task = next(task for task in available_tasks if task["step_number"] == step_number)
                    response_text = f"Okay, let's work on step {step_number}: {task['instruction']}\n"
                    response_text += f"Let me know when you've completed this task by saying 'done with step {step_number}'."
                    
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
            
            # Handle parallel task completion
            if "done with step" in transcript_lower:
                try:
                    step_number = int(re.search(r"step (\d+)", transcript_lower).group(1))
                    self.parallel_task_service.mark_step_completed(step_number)
                    
                    # Get next available tasks and find the next main step
                    timer_end_data = self.parallel_task_service.end_timer_period()
                    next_main_step = timer_end_data.get("next_main_step")
                    
                    response_text = f"Great! Step {step_number} is completed. "
                    
                    if next_main_step:
                        next_step = steps[next_main_step - 1]
                        response_text += f"\nLet's move on to step {next_main_step}: {next_step['instruction']}"
                        recipe_dict["metadata"]["current_step"] = next_main_step
                    else:
                        # Get available tasks for the current timer period
                        available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                            current_step,
                            current_step_data["timer"]["duration"] if current_step_data and current_step_data.get("timer") else float('inf')
                        )
                        
                        if available_tasks:
                            response_text += "You can work on these tasks next:\n"
                            for task in available_tasks:
                                est_time = task["estimated_time"]
                                est_minutes = est_time // 60
                                est_seconds = est_time % 60
                                est_time_str = f"{est_minutes}m {est_seconds}s" if est_minutes > 0 else f"{est_seconds}s"
                                response_text += f"• Step {task['step_number']}: {task['instruction']} (estimated time: {est_time_str})\n"
                            response_text += "Which task would you like to work on? Just say the step number."
                        else:
                            response_text += "Let's focus on completing the current step."
                    
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
                except (AttributeError, ValueError):
                    pass

        # Handle timer start request
        if any(word in transcript_lower for word in ["start timer", "yes", "start the timer"]) and current_step_data and current_step_data.get("timer"):
            timer_data = current_step_data["timer"]
            recipe_dict["metadata"]["timer_running"] = True
            
            # Start timer period and get available parallel tasks
            self.parallel_task_service.start_timer_period(current_step)
            available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                current_step,
                timer_data["duration"]
            )
            
            duration = int(timer_data["duration"])
            minutes = duration // 60
            seconds = duration % 60
            time_str = f"{minutes} minutes and {seconds} seconds" if minutes > 0 else f"{seconds} seconds"
            
            # Build response with parallel task suggestions
            response_text = f"Starting timer for {time_str}. I'll remind you when there are 20 seconds left and when the timer is done."
            
            if available_tasks:
                # Select the first available task as the recommended one
                recommended_task = available_tasks[0]
                est_time = recommended_task["estimated_time"]
                est_minutes = est_time // 60
                est_seconds = est_time % 60
                est_time_str = f"{est_minutes}m {est_seconds}s" if est_minutes > 0 else f"{est_seconds}s"
                
                response_text += f"\n\nWhile we wait, let's work on step {recommended_task['step_number']}: {recommended_task['instruction']}. This will take about {est_time_str}."
                response_text += f"\nLet me know when you've completed this task by saying 'done with step {recommended_task['step_number']}'."
            
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
            
            return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                "duration": duration,
                "type": timer_data["type"],
                "step": current_step,
                "warning_time": 20,
                "parallel_tasks": available_tasks
            }
        
        # Handle step navigation
        if current_step > 0 and current_step <= len(steps):
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
        """Build natural, conversational guidance for a cooking step."""
        # Start with the main instruction
        response = f"Step {step_number}: {step_data['instruction']}"
        
        # Add visual cues and tips in a natural way
        if step_data.get("checkpoints"):
            response += f" You'll know you're on track when {' and '.join(step_data['checkpoints']).lower()}."
        
        # Add warnings if any, phrased naturally
        if step_data.get("warnings"):
            response += f" Just be careful not to {' or '.join(warning.lower() for warning in step_data['warnings'])}."
        
        # Add helpful tips in a conversational way
        if step_data.get("notes"):
            response += f" Here's a helpful tip: {step_data['notes'][0].lower()}"
            if len(step_data['notes']) > 1:
                response += f", and remember to {' and '.join(note.lower() for note in step_data['notes'][1:])}."
            else:
                response += "."
        
        # Add timer information in a natural way
        if step_data.get("timer"):
            duration = step_data["timer"]["duration"]
            minutes = duration // 60
            seconds = duration % 60
            time_str = f"{minutes} minutes" if minutes > 0 else f"{seconds} seconds"
            response += f" This will take about {time_str}. Would you like me to set a timer?"
        
        return response 