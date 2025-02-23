import json
import logging
from typing import Dict, List
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
                        "checkpoints": ["check 1", "check 2"],
                        "estimated_time": 120,
                        "next_possible_steps": [2, 3],
                        "dependencies": []
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
            - 'estimated_time' is REQUIRED for EVERY step and MUST be the estimated time in seconds this step will take
            - 'next_possible_steps' is REQUIRED and must list step numbers that can be done after or during this step
            - 'dependencies' is REQUIRED and must list step numbers that must be completed before this step
            
            IMPORTANT: Optimize the sequence of steps for efficiency. When analyzing step relationships:
            1. For steps with timers, identify which steps can be done during the timer
            2. For prep steps (chopping, etc.), these should be done early and listed as dependencies for later steps
            3. For steps that use prepped ingredients, list the prep steps as dependencies
            4. When a step mentions "while X is Y-ing", make X a dependency and list this step in X's next_possible_steps
            5. Consider equipment conflicts - steps needing the same equipment can't be done simultaneously
            
            Example optimized sequence with dependencies:
            {
                "steps": [
                    {
                        "step": 1,
                        "instruction": "Fill a large pot with water and set it to boil",
                        "timer": {"duration": 300, "type": "preparation"},
                        "estimated_time": 300,
                        "next_possible_steps": [2],
                        "dependencies": []
                    },
                    {
                        "step": 2,
                        "instruction": "While water is boiling, chop garlic and parsley",
                        "estimated_time": 120,
                        "next_possible_steps": [3, 4],
                        "dependencies": []
                    },
                    {
                        "step": 3,
                        "instruction": "Heat oil in a pan",
                        "estimated_time": 30,
                        "next_possible_steps": [5],
                        "dependencies": []
                    },
                    {
                        "step": 4,
                        "instruction": "Add pasta to boiling water",
                        "timer": {"duration": 480, "type": "cooking"},
                        "estimated_time": 480,
                        "next_possible_steps": [5],
                        "dependencies": [1]
                    },
                    {
                        "step": 5,
                        "instruction": "Add chopped garlic to heated oil",
                        "estimated_time": 30,
                        "next_possible_steps": [6],
                        "dependencies": [2, 3]
                    }
                ]
            }
            
            For metadata:
            - 'servings' must be a number
            - 'prepTime' must be a string in the format "X minutes" or "X hours Y minutes"
            - 'cookTime' must be a string in the format "X minutes" or "X hours Y minutes"
            - 'difficulty' must be one of: "easy", "medium", "hard"
            
            Ensure all measurements are standardized and instructions are clear.
            Your response must be a valid JSON object.
            IMPORTANT: You MUST include estimated_time for EVERY step.
            IMPORTANT: Your response MUST be a valid JSON object with NO additional text before or after."""

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
                temperature=0.0,  # Use deterministic output
                max_tokens=2000,
                random_seed=42
            )

            logger.info("Received response from Mistral API")
            
            # Parse the response into structured format
            content = chat_response.choices[0].message.content
            content = content.replace('```json\n', '').replace('\n```', '').strip()
            
            try:
                parsed_recipe = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Mistral response as JSON: {e}")
                logger.error(f"Raw response: {content}")
                raise ValueError("Invalid JSON response from AI")

            # Validate the response has all required fields
            required_fields = {"title", "metadata", "ingredients", "steps", "equipment"}
            missing_fields = required_fields - set(parsed_recipe.keys())
            if missing_fields:
                logger.error(f"Missing fields in response: {missing_fields}")
                raise ValueError(f"Invalid recipe format: missing fields {missing_fields}")

            # Pre-process steps to ensure parallel_with and estimated_time fields
            steps = parsed_recipe["steps"]
            for i, step in enumerate(steps):
                step_num = i + 1
                step["step"] = step_num
                
                # Initialize fields
                if "parallel_with" not in step:
                    step["parallel_with"] = []
                if "estimated_time" not in step:
                    step["estimated_time"] = self._estimate_step_time(step)
                if "timer" not in step:
                    step["timer"] = None
                if "checkpoints" not in step:
                    step["checkpoints"] = None

                # Set estimated time based on timer if present
                if step.get("timer") and isinstance(step["timer"].get("duration"), (int, float)):
                    step["estimated_time"] = int(step["timer"]["duration"])

            # First pass: identify timer steps
            timer_steps = {}
            for i, step in enumerate(steps):
                step_num = i + 1
                if step.get("timer"):
                    timer_steps[step_num] = step["timer"]["duration"]

            # Second pass: analyze parallel relationships
            for i, step in enumerate(steps):
                step_num = i + 1
                instruction = step["instruction"].lower()

                # Check for explicit parallel indicators
                if "while" in instruction:
                    # Water boiling parallel
                    if "water" in instruction and "boil" in instruction:
                        step["parallel_with"].append(1)  # Step 1 is typically water boiling
                    
                    # Pasta cooking parallel
                    if "pasta" in instruction and "cook" in instruction:
                        step["parallel_with"].append(3)  # Step 3 is typically pasta cooking

                # Check for timer-based opportunities
                for timer_step, duration in timer_steps.items():
                    if timer_step != step_num and timer_step < step_num:  # Only consider previous timer steps
                        estimated_time = step.get("estimated_time", 0)
                        if estimated_time <= duration:  # Only parallel if this step takes less time than the timer
                            step["parallel_with"].append(timer_step)

                # Sort and remove duplicates
                step["parallel_with"] = sorted(list(set(step["parallel_with"])))

            # Update the recipe with processed steps
            parsed_recipe["steps"] = steps

            # Enhance recipe data with additional processing
            enhanced_recipe = self._enhance_recipe(parsed_recipe)

            # Final validation and cleanup
            for step in enhanced_recipe["steps"]:
                # Ensure parallel_with is a list
                if not isinstance(step["parallel_with"], list):
                    step["parallel_with"] = []
                # Ensure estimated_time is an integer
                if not isinstance(step["estimated_time"], (int, float)):
                    step["estimated_time"] = self._estimate_step_time(step)
                step["estimated_time"] = int(step["estimated_time"])
                # Sort and remove duplicates from parallel_with
                step["parallel_with"] = sorted(list(set(step["parallel_with"])))

            logger.info("Final recipe structure with parallel tasks:")
            for step in enhanced_recipe["steps"]:
                logger.info(f"Step {step['step']} parallel_with: {step['parallel_with']}, estimated_time: {step['estimated_time']}")

            return enhanced_recipe

        except Exception as e:
            logger.error(f"Error parsing recipe: {e}")
            raise

    def _enhance_recipe(self, recipe: Dict) -> Dict:
        """Enhance recipe data with additional details and validations."""
        try:
            logger.info("Starting recipe enhancement")
            logger.info(f"Original recipe steps: {json.dumps(recipe.get('steps', []), indent=2)}")

            # Validate and transform ingredients
            for ingredient in recipe["ingredients"]:
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

            # Analyze steps for optimization
            steps = recipe["steps"]
            logger.info(f"Analyzing {len(steps)} steps for optimization")

            # First pass: identify long timer steps and initialize fields
            long_timer_steps = []  # Steps with timers >= 5 minutes
            prep_steps = []        # Steps involving preparation
            cooking_steps = []     # Steps involving active cooking
            other_steps = []       # Other steps

            LONG_TIMER_THRESHOLD = 300  # 5 minutes in seconds

            for step in steps:
                instruction_lower = step["instruction"].lower()
                
                # Initialize required fields
                if "timer" not in step:
                    step["timer"] = None
                if "checkpoints" not in step:
                    step["checkpoints"] = None
                if "estimated_time" not in step:
                    step["estimated_time"] = self._estimate_step_time(step)
                if "next_possible_steps" not in step:
                    step["next_possible_steps"] = []
                if "dependencies" not in step:
                    step["dependencies"] = []
                if "can_be_parallel" not in step:
                    step["can_be_parallel"] = False

                # Categorize steps
                if step.get("timer") and step["timer"]["duration"] >= LONG_TIMER_THRESHOLD:
                    long_timer_steps.append(step)
                    logger.info(f"Found long timer step {step['step']}: {step['instruction']} ({step['timer']['duration']}s)")
                elif any(word in instruction_lower for word in ["chop", "dice", "mince", "slice", "prepare", "cut"]):
                    prep_steps.append(step)
                elif any(word in instruction_lower for word in ["cook", "fry", "sauté", "brown", "simmer"]):
                    cooking_steps.append(step)
                else:
                    other_steps.append(step)

            # Second pass: analyze dependencies and parallel opportunities
            for i, step in enumerate(steps):
                step_num = i + 1
                instruction_lower = step["instruction"].lower()

                # Find ingredient dependencies
                for j, prev_step in enumerate(steps[:i]):
                    if self._has_ingredient_dependency(step, prev_step):
                        step["dependencies"].append(j + 1)
                        prev_step["next_possible_steps"].append(step_num)

                # Special handling for long timer steps
                if step in long_timer_steps:
                    timer_duration = step["timer"]["duration"]
                    logger.info(f"\nAnalyzing parallel opportunities during step {step_num} ({timer_duration}s timer)")
                    
                    # Look ahead for steps that can be done during this timer
                    for next_step in steps[i+1:]:
                        # Skip steps that are already marked as parallel
                        if next_step.get("can_be_parallel"):
                            continue
                            
                        # Check if step can be done in parallel
                        if self._can_be_parallel_during_timer(next_step, timer_duration, step):
                            logger.info(f"Found parallel opportunity: Step {next_step['step']} can be done during step {step_num}'s timer")
                            step["next_possible_steps"].append(next_step["step"])
                            next_step["can_be_parallel"] = True
                            next_step["parallel_with"] = [step_num]
                            
                            # If this is a water boiling step, prioritize prep tasks
                            if "boil" in step["instruction"].lower() and "water" in step["instruction"].lower():
                                if any(word in next_step["instruction"].lower() for word in ["chop", "dice", "slice", "mince", "prepare", "cut"]):
                                    logger.info(f"Prioritizing prep task during water boiling: Step {next_step['step']}")
                                    # Move prep tasks to the front of next_possible_steps
                                    step["next_possible_steps"].remove(next_step["step"])
                                    step["next_possible_steps"].insert(0, next_step["step"])

                # Check for explicit "while" dependencies
                if "while" in instruction_lower:
                    for j, other_step in enumerate(steps[:i]):
                        other_instruction = other_step["instruction"].lower()
                        if self._steps_are_related(instruction_lower, other_instruction):
                            step["dependencies"].append(j + 1)
                            other_step["next_possible_steps"].append(step_num)

            # Third pass: validate and clean up
            for step in steps:
                # Remove duplicates and sort
                step["next_possible_steps"] = sorted(list(set(step["next_possible_steps"])))
                step["dependencies"] = sorted(list(set(step["dependencies"])))
                
                # Ensure estimated_time is an integer
                if not isinstance(step["estimated_time"], (int, float)):
                    step["estimated_time"] = self._estimate_step_time(step)
                step["estimated_time"] = int(step["estimated_time"])

                # Log parallel opportunities for long timer steps
                if step.get("timer") and step["timer"]["duration"] >= LONG_TIMER_THRESHOLD:
                    logger.info(f"\nLong timer step {step['step']} ({step['timer']['duration']}s):")
                    logger.info(f"Next possible steps: {step['next_possible_steps']}")

            recipe["steps"] = steps
            logger.info("Recipe enhancement completed")
            return recipe

        except Exception as e:
            logger.error(f"Error enhancing recipe: {e}", exc_info=True)
            raise

    def _can_be_parallel_during_timer(self, step: Dict, timer_duration: int, timer_step: Dict) -> bool:
        """Determine if a step can be done during a timer period."""
        logger.info(f"Checking if step can be parallel during timer: {step.get('instruction')}")
        
        # Step must be shorter than the timer duration
        estimated_time = step.get("estimated_time", self._estimate_step_time(step))
        if estimated_time > timer_duration:
            logger.info("Step takes too long for timer duration")
            return False

        instruction_lower = step["instruction"].lower()
        timer_instruction_lower = timer_step["instruction"].lower()

        # Check for explicit parallel indicators
        if "while" in instruction_lower and any(term in instruction_lower for term in self._extract_key_terms(timer_instruction_lower)):
            logger.info("Found explicit parallel relationship")
            return True

        # Identify prep tasks that can be done during boiling/cooking
        if ("boil" in timer_instruction_lower or "cook" in timer_instruction_lower):
            if any(word in instruction_lower for word in ["chop", "dice", "slice", "mince", "prepare", "cut"]):
                logger.info("Found prep task that can be done during boiling/cooking")
                return True

        # Step must not have temporal dependencies
        if self._has_temporal_dependency(step["instruction"]):
            logger.info("Step has temporal dependencies")
            return False

        # Step must not depend on the timer step
        if self._has_ingredient_dependency(step, timer_step):
            logger.info("Step has ingredient dependencies on timer step")
            return False

        # Step must not require constant attention
        if any(word in instruction_lower for word in ["constantly", "continuously", "stir until", "watch carefully"]):
            logger.info("Step requires constant attention")
            return False

        # Step must not use the same main equipment
        timer_equipment = self._extract_equipment(timer_step["instruction"])
        step_equipment = self._extract_equipment(step["instruction"])
        if timer_equipment & step_equipment:
            logger.info("Step uses same equipment as timer step")
            return False

        # For boiling water steps, most prep tasks can be done in parallel
        if "boil" in timer_instruction_lower and "water" in timer_instruction_lower:
            if any(word in instruction_lower for word in ["prepare", "get ready", "measure", "gather"]):
                logger.info("Found prep task that can be done during water boiling")
                return True

        logger.info("Step can be done in parallel")
        return True

    def _extract_equipment(self, instruction: str) -> set:
        """Extract cooking equipment mentioned in an instruction."""
        equipment_terms = {
            "pot", "pan", "skillet", "bowl", "oven", "stove",
            "cutting board", "knife", "colander", "strainer"
        }
        words = instruction.lower().split()
        return {word for word in words if word in equipment_terms}

    def _steps_are_related(self, instruction1: str, instruction2: str) -> bool:
        """Check if two step instructions are related."""
        # Extract key terms from both instructions
        terms1 = self._extract_key_terms(instruction1)
        terms2 = self._extract_key_terms(instruction2)
        
        # Check for overlapping terms
        return bool(set(terms1) & set(terms2))

    def _has_temporal_dependency(self, instruction: str) -> bool:
        """Check if an instruction has temporal dependencies."""
        temporal_markers = ["after", "once", "when done", "then", "following"]
        return any(marker in instruction.lower() for marker in temporal_markers)

    def _has_ingredient_dependency(self, step: Dict, other_step: Dict) -> bool:
        """Check if one step depends on ingredients or states from another step."""
        instruction1 = step["instruction"].lower()
        instruction2 = other_step["instruction"].lower()
        
        # List of cooking state changes and their results
        state_pairs = [
            ("chop", "chopped"),
            ("dice", "diced"),
            ("mince", "minced"),
            ("slice", "sliced"),
            ("mix", "mixed"),
            ("heat", "heated"),
            ("cook", "cooked"),
            ("boil", "boiled")
        ]
        
        # Check for state dependencies
        for action, state in state_pairs:
            if action in instruction2 and state in instruction1:
                return True
        
        return False

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text that might indicate relationships."""
        # Common cooking ingredients and actions
        key_terms = [
            "water", "boil", "heat", "chop", "slice", "dice",
            "mince", "mix", "stir", "cook", "bake", "fry",
            "garlic", "onion", "oil", "salt", "pepper",
            "pan", "pot", "bowl", "oven"
        ]
        
        words = text.lower().split()
        return [word for word in words if word in key_terms]

    def _estimate_step_time(self, step: Dict) -> int:
        """Estimate the time a step will take in seconds based on its instruction."""
        # If the step has a timer, use that duration
        if step.get("timer") and isinstance(step["timer"].get("duration"), (int, float)):
            return int(step["timer"]["duration"])

        instruction = step["instruction"].lower()
        
        # Quick actions (30 seconds)
        if any(word in instruction for word in ["add", "stir", "mix", "pour", "drain", "serve"]):
            return 30
            
        # Medium actions (2 minutes)
        if any(word in instruction for word in ["chop", "slice", "dice", "mince", "grate", "peel"]):
            return 120
            
        # Longer actions (5 minutes)
        if any(word in instruction for word in ["knead", "roll", "shape", "prepare", "marinate"]):
            return 300
            
        # Default to 3 minutes
        return 180 