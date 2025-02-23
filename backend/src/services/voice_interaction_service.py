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

    def process_ready_to_cook(self, transcript: str, recipe_dict: Dict) -> Tuple[bytes, str, ConversationState, Dict]:
        """Process a request to start cooking."""
        transcript_lower = transcript.lower()
        if any(word in transcript_lower for word in ["yes", "yeah", "yep", "sure", "okay", "ready"]):
            # Add steps to recipe data when transitioning to cooking state
            recipe_dict["metadata"]["current_state"] = ConversationState.COOKING
            recipe_dict["metadata"]["current_step"] = 1
            recipe_dict["metadata"]["completed_steps"] = []
            recipe_dict["metadata"]["active_parallel_steps"] = []
            recipe_dict["metadata"]["active_step"] = 1
            
            # Initialize step statuses with first step as in_progress
            steps = recipe_dict.get("steps", [])
            step_statuses = {str(i+1): "not_started" for i in range(len(steps))}
            step_statuses["1"] = "in_progress"  # First step is now active
            recipe_dict["metadata"]["step_statuses"] = step_statuses
            
            # Get first step guidance
            first_step = steps[0]
            response_text = self._build_step_guidance(first_step, 1)
            
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.COOKING, recipe_dict
        elif any(word in transcript_lower for word in ["no", "nope", "nah", "wait", "not yet"]):
            # Remove steps from recipe data if present
            if "steps" in recipe_dict:
                del recipe_dict["steps"]
            recipe_dict["metadata"]["current_state"] = ConversationState.READY_TO_COOK
            audio_data, response_text = self.tts_service.generate_voice_response(
                "No problem. Take your time to prepare. Let me know when you're ready by saying 'ready'.",
                ConversationState.READY_TO_COOK
            )
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.READY_TO_COOK, recipe_dict
        else:
            # Remove steps from recipe data if present
            if "steps" in recipe_dict:
                del recipe_dict["steps"]
            recipe_dict["metadata"]["current_state"] = ConversationState.READY_TO_COOK
            audio_data, response_text = self.tts_service.generate_voice_response(
                "I didn't understand. Are you ready to start cooking? Please say 'ready' when you want to begin.",
                ConversationState.READY_TO_COOK
            )
            response_text = response_text.encode('ascii', 'replace').decode('ascii')
            return audio_data, response_text, ConversationState.READY_TO_COOK, recipe_dict

    def process_cooking_step(self, transcript: str, recipe_dict: Dict) -> Tuple[bytes, str, ConversationState, Dict, Optional[Dict]]:
        """Process cooking steps and handle timers with parallel tasks using Mistral LLM."""
        try:
            # Get current state
            current_step = recipe_dict.get("metadata", {}).get("current_step", 0)
            timer_running = recipe_dict.get("metadata", {}).get("timer_running", False)
            steps = recipe_dict.get("steps", [])
            current_step_data = steps[current_step - 1] if current_step > 0 and current_step <= len(steps) else None

            # Initialize parallel tasks if not already done
            if not hasattr(self.parallel_task_service, 'parallel_tasks') or not self.parallel_task_service.parallel_tasks:
                logger.info("Initializing parallel tasks for recipe")
                self.parallel_task_service.analyze_recipe_for_parallel_tasks(steps)

            # Build context for Mistral
            context = {
                "recipe_title": recipe_dict.get("title", ""),
                "current_step": current_step,
                "total_steps": len(steps),
                "current_step_data": current_step_data,
                "all_steps": steps,
                "ingredients": recipe_dict.get("ingredients", []),
                "equipment": recipe_dict.get("equipment", []),
                "timer_running": timer_running,
                "completed_steps": self.parallel_task_service.completed_steps,
                "available_tasks": self.parallel_task_service.get_available_parallel_tasks(
                    current_step,
                    current_step_data["timer"]["duration"] if current_step_data and current_step_data.get("timer") else float('inf')
                ) if current_step > 0 else [],
                "user_input": transcript
            }

            # Get Mistral's analysis and recommended action
            response = self.tts_service.get_llm_cooking_guidance(context)
            
            # Initialize response_text with Mistral's base response
            response_text = response.split("SYSTEM_ACTION:")[0].strip()
            
            # Check for step completion phrases
            completion_phrases = [
                "done", "finished", "ready", "complete", "completed",
                "water is boiled", "water is boiling", "water boiled",
                "timer finished", "timer done", "time is up"
            ]
            
            # Get the active timer step data if there is one
            active_timer_step = None
            active_step = recipe_dict.get("metadata", {}).get("active_step")
            if timer_running and active_step:
                active_timer_step = steps[active_step - 1]
            
            # Check if the user's input matches the context of the timer step
            is_water_boiling_step = False
            if active_timer_step:
                step_instruction = active_timer_step.get('instruction', '').lower()
                is_water_boiling_step = any(word in step_instruction for word in ['boil', 'water'])
            
            # Check for completion based on context
            should_complete_timer = False
            if timer_running and active_timer_step:
                if any(phrase in transcript.lower() for phrase in completion_phrases):
                    # General completion phrases always work
                    should_complete_timer = True
                elif is_water_boiling_step and any(phrase in transcript.lower() for phrase in ["water is boiled", "water is boiling", "water boiled"]):
                    # Water boiling phrases only work for water boiling steps
                    should_complete_timer = True
            
            if should_complete_timer:
                # Automatically stop the timer and mark step as completed
                recipe_dict["metadata"]["timer_running"] = False
                recipe_dict["metadata"]["active_step"] = None  # Clear active step
                
                # End timer period and get next step information
                timer_end_data = self.parallel_task_service.end_timer_period()
                recipe_dict["metadata"]["completed_steps"] = self.parallel_task_service.completed_steps
                recipe_dict["metadata"]["active_parallel_steps"] = []
                
                # Update step statuses
                step_statuses = recipe_dict.get("metadata", {}).get("step_statuses", {})
                step_statuses[str(active_step)] = "completed"
                recipe_dict["metadata"]["step_statuses"] = step_statuses
                
                # Get next main step from timer_end_data
                next_main_step = timer_end_data.get('next_main_step')
                if next_main_step:
                    # Update current step
                    recipe_dict["metadata"]["current_step"] = next_main_step
                    step_statuses[str(next_main_step)] = "in_progress"
                    
                    # Build response with next step guidance
                    next_step_data = steps[next_main_step - 1]
                    response_text = f"Great! The water is boiling and step {active_step} is completed. Let's move on to step {next_main_step}: {next_step_data['instruction']}"
                    
                    # Add timer prompt if next step has a timer
                    if next_step_data.get("timer"):
                        response_text += "\nWould you like me to start a timer for this step?"
                else:
                    response_text = f"Great! Step {active_step} is completed."
                    if len(recipe_dict["metadata"]["completed_steps"]) == len(steps):
                        response_text += "\nCongratulations! You've completed all the steps. Your dish should be ready now."
                
                audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                    "duration": 0,
                    "type": "stop",
                    "step": next_main_step or current_step,
                    "warning_time": 0,
                    "step_statuses": step_statuses
                }
            
            # Parse Mistral's response for actions
            if "SYSTEM_ACTION:" in response:
                action_part = response.split("SYSTEM_ACTION:")[1].strip()
                
                # Handle different actions
                if "MARK_COMPLETED:" in action_part:
                    step_number = int(action_part.split("MARK_COMPLETED:")[1].strip().split()[0])
                    
                    # Check if step can be completed
                    can_complete, reason = self._can_complete_step(recipe_dict, step_number)
                    if not can_complete:
                        response_text = f"Cannot complete this step yet. {reason}"
                        audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                        return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
                    
                    # Check if this is a timer step being completed
                    step_data = steps[step_number - 1]
                    is_timer_step = step_data.get("timer") is not None
                    timer_running = recipe_dict.get("metadata", {}).get("timer_running", False)
                    active_step = recipe_dict.get("metadata", {}).get("active_step")
                    
                    # Update completed steps and active parallel steps
                    available_tasks = self.parallel_task_service.mark_step_completed(step_number)
                    recipe_dict["metadata"]["completed_steps"] = self.parallel_task_service.completed_steps
                    
                    # Update step statuses
                    step_statuses = recipe_dict.get("metadata", {}).get("step_statuses", {})
                    step_statuses[str(step_number)] = "completed"
                    recipe_dict["metadata"]["step_statuses"] = step_statuses
                    
                    # Remove from active parallel steps if present
                    active_parallel_steps = recipe_dict.get("metadata", {}).get("active_parallel_steps", [])
                    if step_number in active_parallel_steps:
                        active_parallel_steps.remove(step_number)
                    recipe_dict["metadata"]["active_parallel_steps"] = active_parallel_steps
                    
                    # If this was a timer step, stop the timer only if there are no available parallel tasks
                    if is_timer_step and timer_running and active_step == step_number:
                        if not available_tasks:
                            recipe_dict["metadata"]["timer_running"] = False
                            recipe_dict["metadata"]["active_step"] = None
                            timer_end_data = self.parallel_task_service.end_timer_period()
                            recipe_dict["metadata"]["completed_steps"] = self.parallel_task_service.completed_steps
                            response_text = f"Great! Step {step_number} is completed and the timer has been stopped."
                        else:
                            response_text = f"Great! Step {step_number} is completed. The timer will continue running for remaining tasks."
                    else:
                        response_text = f"Great! Step {step_number} is completed."
                    
                    # Find the next main step
                    next_main_step = None
                    remaining_steps = []
                    for i, step in enumerate(steps, 1):
                        if i not in recipe_dict["metadata"]["completed_steps"] and i != step_number:
                            remaining_steps.append(i)
                            # If timer is running, only consider parallel tasks as next main step
                            if timer_running and active_step:
                                available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                                    active_step,
                                    steps[active_step - 1]["timer"]["duration"]
                                )
                                if any(task['step_number'] == i for task in available_tasks):
                                    next_main_step = i
                                    break
                            else:
                                next_main_step = i
                                break
                    
                    # Check available parallel tasks first
                    if available_tasks:
                        response_text += "\nWhile waiting, you can work on these tasks:\n"
                        for task in available_tasks:
                            est_time = task["estimated_time"]
                            est_minutes = est_time // 60
                            est_seconds = est_time % 60
                            est_time_str = f"{est_minutes}m {est_seconds}s" if est_minutes > 0 else f"{est_seconds}s"
                            response_text += f"• Step {task['step_number']}: {task['instruction']} (estimated time: {est_time_str})\n"
                            # Mark available tasks as ready
                            step_statuses[str(task['step_number'])] = "not_started"
                    
                    # Guide to the next main step if available
                    if remaining_steps:
                        if next_main_step:
                            next_step_data = steps[next_main_step - 1]
                            response_text += f"\nLet's move on to step {next_main_step}: {next_step_data['instruction']}"
                            if next_step_data.get("timer") and not timer_running:
                                response_text += "\nWould you like me to start a timer for this step?"
                            recipe_dict["metadata"]["current_step"] = next_main_step
                            step_statuses[str(next_main_step)] = "in_progress"
                        else:
                            response_text += f"\nThere are still {len(remaining_steps)} steps remaining. Please complete the current timer step first."
                    else:
                        response_text += "\nCongratulations! You've completed all the steps. Your dish should be ready now."
                    
                    # Keep timer step as in_progress if timer is still running
                    timer_running = recipe_dict.get("metadata", {}).get("timer_running", False)
                    active_step = recipe_dict.get("metadata", {}).get("active_step")
                    if timer_running and active_step:
                        step_statuses[str(active_step)] = "in_progress"
                        timer_step_data = steps[active_step - 1]["timer"]
                        available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                            active_step,
                            timer_step_data["duration"]
                        )
                        audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                        return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                            "duration": timer_step_data["duration"],
                            "type": timer_step_data["type"],
                            "step": active_step,
                            "warning_time": 20,
                            "parallel_tasks": available_tasks,
                            "step_statuses": step_statuses
                        }
                    
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                        "step_statuses": step_statuses,
                        "current_step": next_main_step
                    }
                
                elif "START_TIMER:" in action_part:
                    step_number = int(action_part.split("START_TIMER:")[1].strip().split()[0])
                    
                    # Try to start the timer
                    can_start, message, timer_data = self._handle_timer_start(recipe_dict, step_number)
                    if not can_start:
                        audio_data, response_text = self.tts_service.generate_voice_response(message, ConversationState.COOKING)
                        return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
                    
                    # Update recipe state
                    recipe_dict["metadata"]["timer_running"] = True
                    recipe_dict["metadata"]["active_step"] = step_number
                    
                    # Update step statuses
                    step_statuses = recipe_dict.get("metadata", {}).get("step_statuses", {})
                    step_statuses[str(step_number)] = "in_progress"  # Mark timer step as in progress
                    recipe_dict["metadata"]["step_statuses"] = step_statuses
                    
                    # Start timer and get available parallel tasks
                    self.parallel_task_service.start_timer_period(step_number)
                    
                    # Format response with timer and parallel tasks
                    minutes = timer_data["duration"] // 60
                    seconds = timer_data["duration"] % 60
                    time_str = []
                    if minutes:
                        time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                    if seconds:
                        time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                    
                    response_text = f"Starting a timer for {' and '.join(time_str)}. "
                    
                    # Sort available tasks by priority (prep tasks first, then by estimated time)
                    if timer_data.get("parallel_tasks"):
                        available_tasks = sorted(
                            timer_data["parallel_tasks"],
                            key=lambda x: (
                                0 if any(word in x['instruction'].lower() for word in ['chop', 'dice', 'slice', 'mince', 'prepare', 'cut']) else 1,
                                x['estimated_time']
                            )
                        )
                        # Automatically guide to the first available task
                        next_task = available_tasks[0]
                        est_time = next_task['estimated_time']
                        est_minutes = est_time // 60
                        est_seconds = est_time % 60
                        est_time_str = f"{est_minutes}m {est_seconds}s" if est_minutes > 0 else f"{est_seconds}s"
                        
                        response_text += f"While the timer is running, let's move on to step {next_task['step_number']}: {next_task['instruction']} (estimated time: {est_time_str})"
                        
                        # Update recipe state for the parallel task
                        recipe_dict["metadata"]["current_step"] = next_task['step_number']
                        active_parallel_steps = recipe_dict.get("metadata", {}).get("active_parallel_steps", [])
                        if next_task['step_number'] not in active_parallel_steps:
                            active_parallel_steps.append(next_task['step_number'])
                        recipe_dict["metadata"]["active_parallel_steps"] = active_parallel_steps
                        
                        # Update step statuses for parallel tasks
                        step_statuses[str(next_task['step_number'])] = "in_progress"  # Mark first parallel task as in progress
                        for task in available_tasks[1:]:
                            step_statuses[str(task['step_number'])] = "not_started"  # Mark other parallel tasks as not started
                    
                    # Add step statuses to timer data
                    timer_data["step_statuses"] = step_statuses
                    
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, timer_data
                
                elif "STOP_TIMER" in action_part:
                    recipe_dict["metadata"]["timer_running"] = False
                    active_step = recipe_dict["metadata"].get("active_step")  # Get active step before clearing it
                    recipe_dict["metadata"]["active_step"] = None  # Clear active step
                    
                    # End timer period and get next step information
                    timer_end_data = self.parallel_task_service.end_timer_period()
                    recipe_dict["metadata"]["completed_steps"] = self.parallel_task_service.completed_steps
                    recipe_dict["metadata"]["active_parallel_steps"] = []
                    
                    # Update step statuses
                    step_statuses = recipe_dict.get("metadata", {}).get("step_statuses", {})
                    if active_step:  # Use the active_step we got earlier
                        step_statuses[str(active_step)] = "completed"
                    recipe_dict["metadata"]["step_statuses"] = step_statuses
                    
                    # Get next main step from timer_end_data
                    next_main_step = timer_end_data.get('next_main_step')
                    if next_main_step:
                        # Update current step
                        recipe_dict["metadata"]["current_step"] = next_main_step
                        step_statuses[str(next_main_step)] = "in_progress"
                        
                        # Build response with next step guidance
                        next_step_data = steps[next_main_step - 1]
                        response_text = f"Timer completed! Step {active_step} is done. Let's move on to step {next_main_step}: {next_step_data['instruction']}"
                        
                        # Add timer prompt if next step has a timer
                        if next_step_data.get("timer"):
                            response_text += "\nWould you like me to start a timer for this step?"
                    else:
                        response_text = f"Timer completed! Step {active_step} is done."
                        if len(recipe_dict["metadata"]["completed_steps"]) == len(steps):
                            response_text += "\nCongratulations! You've completed all the steps. Your dish should be ready now."
                    
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                        "duration": 0,
                        "type": "stop",
                        "step": next_main_step or current_step,
                        "warning_time": 0,
                        "step_statuses": step_statuses
                    }
                
                elif "NEXT_STEP" in action_part:
                    if current_step < len(steps):
                        next_step = current_step + 1
                        # Validate the transition
                        is_valid, reason = self._validate_step_transition(recipe_dict, current_step, next_step)
                        if not is_valid:
                            response_text = f"We can't move to the next step yet. {reason}"
                            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                            return audio_data, response_text, ConversationState.COOKING, recipe_dict, None

                        # Update step statuses
                        step_statuses = recipe_dict.get("metadata", {}).get("step_statuses", {})
                        step_statuses[str(next_step)] = "in_progress"
                        recipe_dict["metadata"]["step_statuses"] = step_statuses
                        
                        # Keep timer step as in_progress if timer is running
                        current_timer_running = recipe_dict.get("metadata", {}).get("timer_running", False)
                        active_step = recipe_dict.get("metadata", {}).get("active_step")
                        if current_timer_running and active_step:
                            step_statuses[str(active_step)] = "in_progress"
                        
                        # Update current step
                        current_step = next_step
                        recipe_dict["metadata"]["current_step"] = current_step
                        
                        # If this is a parallel task, add to active parallel steps
                        if current_timer_running and active_step:
                            available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                                active_step,
                                steps[active_step - 1]["timer"]["duration"]
                            )
                            if any(task['step_number'] == current_step for task in available_tasks):
                                active_parallel_steps = recipe_dict.get("metadata", {}).get("active_parallel_steps", [])
                                if current_step not in active_parallel_steps:
                                    active_parallel_steps.append(current_step)
                                recipe_dict["metadata"]["active_parallel_steps"] = active_parallel_steps
                        
                        next_step_data = steps[current_step - 1]
                        response_text = self._build_step_guidance(next_step_data, current_step)
                        
                        # Always keep timer data if timer is running
                        timer_info = None
                        if current_timer_running and active_step:
                            timer_step_data = steps[active_step - 1]["timer"]
                            available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                                active_step,
                                timer_step_data["duration"]
                            )
                            timer_info = {
                                "duration": timer_step_data["duration"],
                                "type": timer_step_data["type"],
                                "step": active_step,
                                "warning_time": 20,
                                "parallel_tasks": available_tasks,
                                "step_statuses": step_statuses
                            }
                        
                        audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                        return audio_data, response_text, ConversationState.COOKING, recipe_dict, timer_info
                    else:
                        # Remind user to finish current timer step
                        response_text = f"Let's finish step {active_step} first. The timer is still running."
                        if available_tasks:
                            response_text += " While waiting, you can work on:\n"
                            for task in available_tasks:
                                est_time = task['estimated_time']
                                est_str = f"{est_time // 60}m {est_time % 60}s" if est_time >= 60 else f"{est_time}s"
                                response_text += f"\n• Step {task['step_number']}: {task['instruction']} (estimated time: {est_str})"
                        
                        audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                        return audio_data, response_text, ConversationState.COOKING, recipe_dict, None
                
                elif "START_COOKING" in action_part:
                    current_step = 1
                    recipe_dict["metadata"]["current_step"] = current_step
                    recipe_dict["metadata"]["completed_steps"] = []
                    recipe_dict["metadata"]["active_parallel_steps"] = []
                    recipe_dict["metadata"]["active_step"] = current_step
                    # Initialize step statuses with first step as in_progress
                    step_statuses = {str(i+1): "not_started" for i in range(len(steps))}
                    step_statuses["1"] = "in_progress"  # First step is now active
                    recipe_dict["metadata"]["step_statuses"] = step_statuses
                    first_step = steps[current_step - 1]
                    response_text = self._build_step_guidance(first_step, current_step)
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                        "step_statuses": step_statuses
                    }
                
                elif "FINISH_COOKING" in action_part:
                    response_text = "Congratulations! You've completed all the steps. Your dish should be ready now. Enjoy!"
                    audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                    return audio_data, response_text, ConversationState.COOKING, recipe_dict, None

            # Special handling for timer start requests
            if transcript.lower() in ['yes', 'yeah', 'sure', 'okay', 'ok', 'yes set a timer'] and current_step_data and current_step_data.get('timer'):
                timer_data = current_step_data["timer"]
                recipe_dict["metadata"]["timer_running"] = True
                recipe_dict["metadata"]["active_step"] = current_step
                self.parallel_task_service.start_timer_period(current_step)
                duration = int(timer_data["duration"])
                
                # Format response with timer and parallel tasks
                minutes = duration // 60
                seconds = duration % 60
                time_str = []
                if minutes:
                    time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds:
                    time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
                response_text = f"Starting a timer for {' and '.join(time_str)}."
                
                # Sort available tasks by priority (prep tasks first, then by estimated time)
                available_tasks = sorted(
                    context['available_tasks'],
                    key=lambda x: (
                        0 if any(word in x['instruction'].lower() for word in ['chop', 'dice', 'slice', 'mince', 'prepare', 'cut']) else 1,
                        x['estimated_time']
                    )
                )
                
                # If there are parallel tasks available, automatically guide to the first one
                if available_tasks:
                    next_task = available_tasks[0]
                    est_time = next_task['estimated_time']
                    est_str = f"{est_time // 60}m {est_time % 60}s" if est_time >= 60 else f"{est_time}s"
                    
                    # Update recipe state for the parallel task
                    recipe_dict["metadata"]["current_step"] = next_task['step_number']
                    active_parallel_steps = recipe_dict.get("metadata", {}).get("active_parallel_steps", [])
                    if next_task['step_number'] not in active_parallel_steps:
                        active_parallel_steps.append(next_task['step_number'])
                    recipe_dict["metadata"]["active_parallel_steps"] = active_parallel_steps
                    
                    # Update step statuses
                    step_statuses = recipe_dict.get("metadata", {}).get("step_statuses", {})
                    step_statuses[str(next_task['step_number'])] = "in_progress"  # Mark first parallel task as in progress
                    for task in available_tasks[1:]:
                        step_statuses[str(task['step_number'])] = "not_started"  # Mark other parallel tasks as not started
                    recipe_dict["metadata"]["step_statuses"] = step_statuses
                    
                    # Build response text based on the current step's context
                    current_step_instruction = steps[current_step - 1].get('instruction', '').lower()
                    if 'boil' in current_step_instruction and 'water' in current_step_instruction:
                        response_text += f"\n\nWhile waiting for the water to boil, let's move on to step {next_task['step_number']}: {next_task['instruction']} (estimated time: {est_str})"
                    else:
                        response_text += f"\n\nWhile waiting for step {current_step}, let's move on to step {next_task['step_number']}: {next_task['instruction']} (estimated time: {est_str})"
                    
                    if len(available_tasks) > 1:
                        response_text += "\n\nOther tasks you can work on:"
                        for task in available_tasks[1:]:
                            est_time = task['estimated_time']
                            est_str = f"{est_time // 60}m {est_time % 60}s" if est_time >= 60 else f"{est_time}s"
                            response_text += f"\n• Step {task['step_number']}: {task['instruction']} (estimated time: {est_str})"
                
                audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
                return audio_data, response_text, ConversationState.COOKING, recipe_dict, {
                    "duration": duration,
                    "type": timer_data["type"],
                    "step": current_step,
                    "warning_time": 20,
                    "parallel_tasks": available_tasks,
                    "step_statuses": recipe_dict["metadata"].get("step_statuses", {})
                }

            # Generate audio response for cases without specific actions
            audio_data, response_text = self.tts_service.generate_voice_response(response_text, ConversationState.COOKING)
            return audio_data, response_text, ConversationState.COOKING, recipe_dict, None

        except Exception as e:
            logger.error(f"Error processing cooking step: {e}")
            error_response = "I apologize, but I encountered an error processing your request. Would you like me to repeat the current step?"
            audio_data, error_response = self.tts_service.generate_voice_response(error_response, ConversationState.COOKING)
            return audio_data, error_response, ConversationState.COOKING, recipe_dict, None

    def _validate_step_transition(self, recipe_dict: Dict, from_step: int, to_step: int) -> Tuple[bool, str]:
        """
        Validate if a transition from one step to another is allowed.
        Returns (is_valid, reason)
        """
        steps = recipe_dict.get("steps", [])
        metadata = recipe_dict.get("metadata", {})
        step_statuses = metadata.get("step_statuses", {})
        timer_running = metadata.get("timer_running", False)
        active_step = metadata.get("active_step")
        completed_steps = metadata.get("completed_steps", [])

        # Validate step numbers
        if from_step < 1 or from_step > len(steps) or to_step < 1 or to_step > len(steps):
            return False, "Invalid step number"

        # If there's a timer running, check if the requested step is a parallel task
        if timer_running and active_step:
            available_tasks = self.parallel_task_service.get_available_parallel_tasks(
                active_step,
                steps[active_step - 1]["timer"]["duration"]
            )
            is_parallel = any(task['step_number'] == to_step for task in available_tasks)
            
            # Allow moving to parallel tasks or back to the timer step
            if not is_parallel and to_step != active_step:
                return False, f"Step {to_step} cannot be done while timer is running on step {active_step}. You can only work on parallel tasks or return to step {active_step}."

        # Check dependencies
        current_step_data = steps[to_step - 1]
        if hasattr(current_step_data, 'dependencies'):
            for dep in current_step_data.dependencies:
                if dep not in completed_steps:
                    return False, f"Step {dep} must be completed before moving to step {to_step}"

        return True, ""

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
            duration = int(step_data["timer"]["duration"])
            minutes = duration // 60
            seconds = duration % 60
            time_str = []
            if minutes > 0:
                time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if seconds > 0:
                time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            time_str = " and ".join(time_str) if time_str else "0 seconds"
            response += f" This will take about {time_str}. Would you like me to set a timer?"
        
        return response

    def _can_complete_step(self, recipe_dict: Dict, step_number: int) -> Tuple[bool, str]:
        """
        Check if a step can be marked as completed.
        Returns (can_complete, reason)
        """
        steps = recipe_dict.get("steps", [])
        metadata = recipe_dict.get("metadata", {})
        timer_running = metadata.get("timer_running", False)
        active_step = metadata.get("active_step")
        active_parallel_steps = metadata.get("active_parallel_steps", [])
        
        # Validate step number
        if step_number < 1 or step_number > len(steps):
            return False, "Invalid step number"
        
        step_data = steps[step_number - 1]
        
        # If this step is part of active parallel steps during a timer
        if timer_running and step_number in active_parallel_steps:
            # Allow completing parallel tasks
            return True, ""
        
        # If this is a timer step and timer is running
        if step_data.get("timer") and timer_running and active_step == step_number:
            # Allow completing timer steps - timer will be stopped when completed
            return True, ""
        
        # If there's a timer running and this isn't the timer step or a parallel task
        if timer_running and active_step and active_step != step_number:
            return False, f"Cannot complete step {step_number} while timer is running on step {active_step}"
        
        return True, ""

    def _handle_timer_start(self, recipe_dict: Dict, step_number: int) -> Tuple[bool, str, Optional[Dict]]:
        """
        Handle starting a timer for a step.
        Returns (can_start, message, timer_data)
        """
        steps = recipe_dict.get("steps", [])
        metadata = recipe_dict.get("metadata", {})
        timer_running = metadata.get("timer_running", False)
        active_step = metadata.get("active_step")
        
        # Validate step number
        if step_number < 1 or step_number > len(steps):
            return False, "Invalid step number", None
        
        step_data = steps[step_number - 1]
        
        # Check if step has a timer
        if not step_data.get("timer"):
            return False, "This step doesn't have a timer", None
        
        # Check if another timer is already running
        if timer_running and active_step and active_step != step_number:
            return False, f"Cannot start timer while another timer is running on step {active_step}", None
        
        # Get timer data
        timer_data = step_data["timer"]
        duration = int(timer_data["duration"])
        
        # Get available parallel tasks
        available_tasks = self.parallel_task_service.get_available_parallel_tasks(
            step_number,
            duration
        )
        
        # Format response with timer and parallel tasks
        minutes = duration // 60
        seconds = duration % 60
        time_str = []
        if minutes:
            time_str.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds:
            time_str.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        message = f"Starting a timer for {' and '.join(time_str)}."
        
        # Sort available tasks by priority (prep tasks first, then by estimated time)
        if available_tasks:
            available_tasks = sorted(
                available_tasks,
                key=lambda x: (
                    0 if any(word in x['instruction'].lower() for word in ['chop', 'dice', 'slice', 'mince', 'prepare', 'cut']) else 1,
                    x['estimated_time']
                )
            )
            
            message += "\n\nWhile we wait, here are tasks you can work on:"
            
            # Add recommended task
            recommended = available_tasks[0]
            est_time = recommended['estimated_time']
            est_str = f"{est_time // 60}m {est_time % 60}s" if est_time >= 60 else f"{est_time}s"
            message += f"\n\nRecommended: Step {recommended['step_number']}: {recommended['instruction']} (estimated time: {est_str})"
            
            # Add other tasks
            if len(available_tasks) > 1:
                message += "\n\nOther tasks:"
                for task in available_tasks[1:]:
                    est_time = task['estimated_time']
                    est_str = f"{est_time // 60}m {est_time % 60}s" if est_time >= 60 else f"{est_time}s"
                    message += f"\n• Step {task['step_number']}: {task['instruction']} (estimated time: {est_str})"
            
            message += "\n\nTo start any of these tasks, say 'start step X' or 'move to step X'."
        
        return True, message, {
            "duration": duration,
            "type": timer_data["type"],
            "step": step_number,
            "warning_time": 20,
            "parallel_tasks": available_tasks
        } 