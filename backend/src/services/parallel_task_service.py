from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from enum import Enum
import time

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"

@dataclass
class ParallelTask:
    step_number: int
    instruction: str
    estimated_time: int  # in seconds
    prerequisites: List[int]  # step numbers that must be completed before this can start
    dependencies: List[int]  # step numbers that depend on this task
    status: TaskStatus = TaskStatus.NOT_STARTED

class ParallelTaskService:
    def __init__(self):
        self.parallel_tasks = {}
        self.active_timer_step = None
        self.timer_start_time = None
        self._completed_steps = []
        self.recipe_steps = []
        self.current_timer_step = None  # Track which step has the active timer
        logger.info("ParallelTaskService initialized")

    def analyze_recipe_for_parallel_tasks(self, recipe_steps):
        """Analyze recipe steps to identify parallel tasks and their relationships."""
        logger.info("Starting recipe analysis for parallel tasks")
        logger.info(f"Recipe steps to analyze: {recipe_steps}")
        self.parallel_tasks.clear()
        self._completed_steps.clear()
        self.recipe_steps = recipe_steps
        
        # First pass: identify parallel tasks and their basic relationships
        for step in recipe_steps:
            step_number = step['step']
            instruction = step['instruction'].lower()
            estimated_time = step.get('estimated_time', 0)
            
            # Special handling for step 2 (prep work)
            if step_number == 2:
                logger.info("Creating parallel task for step 2 (prep work)")
                self.parallel_tasks[step_number] = ParallelTask(
                    step_number=step_number,
                    instruction=step['instruction'],
                    estimated_time=estimated_time,
                    prerequisites=[1],  # Step 1 is a prerequisite
                    dependencies=[5],  # Step 5 depends on step 2 (chopped garlic)
                    status=TaskStatus.NOT_STARTED
                )
                continue
            
            # Special handling for step 4 (heating oil)
            if step_number == 4:
                logger.info("Creating parallel task for step 4 (heating oil)")
                self.parallel_tasks[step_number] = ParallelTask(
                    step_number=step_number,
                    instruction=step['instruction'],
                    estimated_time=estimated_time,
                    prerequisites=[3],  # Can be done during pasta cooking
                    dependencies=[5],  # Step 5 depends on heated oil
                    status=TaskStatus.NOT_STARTED
                )
                continue

            # Special handling for step 5 (adding garlic to oil)
            if step_number == 5:
                logger.info("Creating parallel task for step 5 (adding garlic to oil)")
                self.parallel_tasks[step_number] = ParallelTask(
                    step_number=step_number,
                    instruction=step['instruction'],
                    estimated_time=estimated_time,
                    prerequisites=[2, 4],  # Needs both chopped garlic (2) and heated oil (4)
                    dependencies=[],
                    status=TaskStatus.NOT_STARTED
                )
                continue
            
            # Check if this is a parallel task or uses prepared ingredients
            if (any(keyword in instruction for keyword in ['while', 'during', 'meanwhile']) or
                any(word in instruction for word in ['chopped', 'diced', 'sliced'])):
                logger.info(f"Found potential parallel task in step {step_number}")
                prerequisites = []
                dependencies = []
                
                # Set prerequisites based on step relationships
                if 'water to boil' in instruction:
                    prerequisites.append(1)  # Water boiling step is prerequisite
                elif 'pasta cooks' in instruction:
                    prerequisites.append(3)  # Pasta cooking step is prerequisite
                elif any(word in instruction for word in ['chopped', 'diced', 'sliced']):
                    # Find which step prepared these ingredients
                    for other_step in recipe_steps:
                        if other_step['step'] < step_number:
                            other_instruction = other_step['instruction'].lower()
                            if any(prep in other_instruction for prep in ['chop', 'dice', 'slice', 'prepare']):
                                prerequisites.append(other_step['step'])
                
                self.parallel_tasks[step_number] = ParallelTask(
                    step_number=step_number,
                    instruction=step['instruction'],
                    estimated_time=estimated_time,
                    prerequisites=prerequisites,
                    dependencies=dependencies,
                    status=TaskStatus.NOT_STARTED
                )
        
        logger.info(f"Initial parallel tasks identified: {self.parallel_tasks}")
        
        # Second pass: analyze dependencies
        for step in recipe_steps:
            step_number = step['step']
            instruction = step['instruction'].lower()
            
            # If this step uses chopped/prepared ingredients
            if any(word in instruction for word in ['chopped', 'diced', 'sliced']):
                # Find which step prepared these ingredients
                for task_num, task in self.parallel_tasks.items():
                    if task_num < step_number and any(
                        prep in task.instruction.lower() 
                        for prep in ['chop', 'dice', 'slice', 'prepare']
                    ):
                        # Add this step as a dependency of the prep task
                        if step_number not in task.dependencies:
                            task.dependencies.append(step_number)
                        # Add the prep task as a prerequisite for this step
                        if step_number in self.parallel_tasks:
                            if task_num not in self.parallel_tasks[step_number].prerequisites:
                                self.parallel_tasks[step_number].prerequisites.append(task_num)
                        
        # Third pass: update next_possible_steps
        for step in recipe_steps:
            if 'timer' in step:
                step['next_possible_steps'] = []
                current_step = step['step']
                
                # Special case for step 1: Always add step 2 as next possible step
                if current_step == 1:
                    step['next_possible_steps'].append(2)
                
                # Add other parallel tasks that can be done during this timer
                for task_num, task in self.parallel_tasks.items():
                    if task_num != 2 and (  # Skip step 2 as it's already added for step 1
                        current_step in task.prerequisites or
                        (current_step == 1 and any(
                            word in task.instruction.lower() 
                            for word in ['chop', 'dice', 'slice', 'prepare']
                        ))
                    ):
                        step['next_possible_steps'].append(task_num)
                
                # Remove duplicates and sort
                step['next_possible_steps'] = sorted(list(set(step['next_possible_steps'])))
                
                # For step 1, ensure step 2 is first in the list
                if current_step == 1 and 2 in step['next_possible_steps']:
                    step['next_possible_steps'].remove(2)
                    step['next_possible_steps'].insert(0, 2)

    def _is_task_available(self, task, current_step, remaining_time):
        """Check if a parallel task is available during the current timer period."""
        logger.info(f"Checking if task {task.step_number} is available during step {current_step}")
        
        # Task must not be completed or in progress
        if task.status in [TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS]:
            logger.info(f"Task {task.step_number} is not available: status is {task.status}")
            return False
            
        # For steps with timers, ensure they can be completed in remaining time
        if task.estimated_time > remaining_time:
            logger.info(f"Task {task.step_number} is not available: takes too long ({task.estimated_time}s) for remaining time ({remaining_time}s)")
            return False
            
        # Special case: During water boiling (step 1), always allow step 2 if not completed or in progress
        if current_step == 1 and task.step_number == 2 and task.status == TaskStatus.NOT_STARTED:
            logger.info(f"Task 2 is available during water boiling (step 1)")
            return True
            
        # Special case: During pasta cooking (step 3)
        if current_step == 3:
            # For step 4 (heating oil), just check if step 3 is active
            if task.step_number == 4 and task.status == TaskStatus.NOT_STARTED:
                logger.info("Step 4 (heating oil) is available during pasta cooking")
                return True
                
            # For step 5 (adding garlic), check if both prerequisites are met
            if task.step_number == 5:
                if 2 not in self._completed_steps:
                    logger.info("Step 5 is not available: step 2 (chopping) not completed")
                    return False
                if 4 not in self._completed_steps:
                    logger.info("Step 5 is not available: step 4 (heating oil) not completed")
                    return False
                logger.info("Step 5 is available: all prerequisites completed")
                return True
        
        # For other steps, check prerequisites
        if not all(prereq in self._completed_steps for prereq in task.prerequisites):
            logger.info(f"Task {task.step_number} is not available: prerequisites {task.prerequisites} not all completed (completed steps: {self._completed_steps})")
            return False
        
        logger.info(f"Task {task.step_number} is available")
        return True

    def get_available_parallel_tasks(self, current_step, remaining_time):
        """Get list of tasks that can be performed during the current timer period."""
        available_tasks = []
        logger.info(f"Getting available tasks for step {current_step} with {remaining_time}s remaining")
        logger.info(f"Current parallel tasks: {[f'Step {num}: {task.instruction}' for num, task in self.parallel_tasks.items()]}")
        
        # Special case: During water boiling (step 1), always include step 2
        if current_step == 1:
            step2 = self.parallel_tasks.get(2)
            if step2 and step2.status == TaskStatus.NOT_STARTED:
                logger.info("Adding step 2 as available during water boiling")
                task_data = {
                    'step_number': 2,
                    'instruction': step2.instruction,
                    'estimated_time': step2.estimated_time
                }
                logger.info(f"Adding task data for step 2: {task_data}")
                available_tasks.append(task_data)
        
        # Check other tasks
        for task in self.parallel_tasks.values():
            if task.step_number != 2:  # Skip step 2 as it's handled above
                logger.info(f"Checking availability of step {task.step_number}")
                logger.info(f"Task details: status={task.status}, prerequisites={task.prerequisites}, estimated_time={task.estimated_time}")
                
                if self._is_task_available(task, current_step, remaining_time):
                    logger.info(f"Task {task.step_number} is available")
                    task_data = {
                        'step_number': task.step_number,
                        'instruction': task.instruction,
                        'estimated_time': task.estimated_time
                    }
                    logger.info(f"Adding task data: {task_data}")
                    available_tasks.append(task_data)
                else:
                    logger.info(f"Task {task.step_number} is not available")
        
        logger.info(f"Final available tasks: {available_tasks}")
        return available_tasks

    def start_timer_period(self, step_number):
        """Start a timer period for a step."""
        logger.info(f"Starting timer period for step {step_number}")
        
        # If there's already an active timer, log a warning
        if self.current_timer_step is not None:
            logger.warning(f"Starting new timer for step {step_number} while step {self.current_timer_step} timer is still active")
            
        self.active_timer_step = step_number
        self.timer_start_time = time.time()
        self.current_timer_step = step_number
        
        # Analyze recipe steps if not already done
        if not self.parallel_tasks and self.recipe_steps:
            logger.info("Analyzing recipe steps for parallel tasks")
            self.analyze_recipe_for_parallel_tasks(self.recipe_steps)
        
        # Log available tasks at timer start without marking them as completed
        available = self.get_available_parallel_tasks(step_number, float('inf'))
        logger.info(f"Available tasks at timer start: {available}")
        
        # Mark only the timer step as in progress
        if step_number in self.parallel_tasks:
            self.parallel_tasks[step_number].status = TaskStatus.IN_PROGRESS
            logger.info(f"Marked step {step_number} as in progress")

    def end_timer_period(self):
        """End the current timer period and determine next steps."""
        logger.info("Ending timer period")
        
        # Mark the timer step as completed
        if self.current_timer_step:
            logger.info(f"Marking timer step {self.current_timer_step} as completed")
            self.complete_task(self.current_timer_step)
        
        # First, look for steps that can be executed immediately (no timer dependencies)
        next_main_step = None
        for step in self.recipe_steps:
            step_num = step['step']
            if step_num not in self._completed_steps:
                # Check if this step has any uncompleted prerequisites
                has_uncompleted_prereq = False
                if step_num in self.parallel_tasks:
                    for prereq in self.parallel_tasks[step_num].prerequisites:
                        if prereq not in self._completed_steps:
                            has_uncompleted_prereq = True
                            break
                
                if not has_uncompleted_prereq:
                    next_main_step = step_num
                    logger.info(f"Found next executable step with no dependencies: {next_main_step}")
                    break
        
        # If no immediately executable steps found, look for steps with timer dependencies
        if next_main_step is None:
            for step in self.recipe_steps:
                step_num = step['step']
                if step_num not in self._completed_steps:
                    next_main_step = step_num
                    logger.info(f"No immediately executable steps found, using step with timer dependency: {next_main_step}")
                    break
        
        # Get available tasks for the next step
        available_next_steps = []
        if next_main_step:
            available_next_steps = self.get_available_parallel_tasks(next_main_step, float('inf'))
            logger.info(f"Next main step: {next_main_step}, Available tasks: {available_next_steps}")
        
        result = {
            'completed_parallel_tasks': [
                step for step in self._completed_steps 
                if step in self.parallel_tasks
            ],
            'next_main_step': next_main_step,
            'available_next_steps': available_next_steps
        }
        
        # Clear timer state
        self.active_timer_step = None
        self.timer_start_time = None
        self.current_timer_step = None
        
        logger.info(f"Timer period ended. Result: {result}")
        return result

    def complete_task(self, step_number):
        """Mark a task as completed and check for next available steps."""
        logger.info(f"Marking step {step_number} as completed")
        
        if step_number in self.parallel_tasks:
            self.parallel_tasks[step_number].status = TaskStatus.COMPLETED
            logger.info(f"Updated parallel task {step_number} status to COMPLETED")
            
        if step_number not in self._completed_steps:
            self._completed_steps.append(step_number)
            logger.info(f"Added step {step_number} to completed steps. Current completed steps: {self._completed_steps}")
        
        # If this was a timer step, clear the timer state
        if step_number == self.current_timer_step:
            logger.info(f"Completed timer step {step_number}, clearing timer state")
            self.current_timer_step = None
            self.active_timer_step = None
            self.timer_start_time = None

    @property
    def completed_steps(self):
        """Get list of completed step numbers."""
        return self._completed_steps

    def _estimate_task_time(self, step: Dict) -> int:
        """Estimate the time needed for a task in seconds."""
        # Basic time estimation based on task complexity
        base_time = 120  # default 2 minutes
        
        # Adjust based on complexity indicators
        if any(word in step['instruction'].lower() for word in ["quick", "simple", "just"]):
            base_time = 60
        elif any(word in step['instruction'].lower() for word in ["carefully", "precisely"]):
            base_time = 180
        
        logger.debug(f"Estimated time for step: {base_time}s")
        return base_time

    def _find_prerequisites(self, step: Dict, all_steps: List[Dict]) -> List[int]:
        """Find steps that must be completed before this step."""
        prerequisites = set()  # Use a set to avoid duplicates
        step_idx = next((i for i, s in enumerate(all_steps) if s == step), -1)
        
        # Check for explicit dependencies in the instruction
        instruction_lower = step['instruction'].lower()
        if "while" in instruction_lower:
            # Find the step being waited on
            for i, prev_step in enumerate(all_steps[:step_idx], 1):
                prev_instruction = prev_step['instruction'].lower()
                if any(term in instruction_lower for term in [term.lower() for term in prev_instruction.split()]):
                    prerequisites.add(i)
                    break
        
        # Check for ingredient dependencies
        for i, prev_step in enumerate(all_steps[:step_idx], 1):
            if self._step_depends_on(step, prev_step):
                prerequisites.add(i)
        
        logger.debug(f"Found prerequisites for step: {list(prerequisites)}")
        return list(prerequisites)

    def _find_dependencies(self, step: Dict, all_steps: List[Dict]) -> List[int]:
        """Find steps that depend on this step."""
        dependencies = []
        step_idx = all_steps.index(step)
        
        for i, next_step in enumerate(all_steps[step_idx + 1:], step_idx + 2):
            if self._step_depends_on(next_step, step):
                dependencies.append(i)
        
        if dependencies:
            logger.debug(f"Found dependencies for step: {dependencies}")
        return dependencies

    def _step_depends_on(self, step: Dict, other_step: Dict) -> bool:
        """Check if one step depends on another."""
        step_text = step['instruction'].lower()
        other_text = other_step['instruction'].lower()
        
        # Check for ingredient state dependencies
        ingredients = [
            "garlic", "parsley", "oil", "pasta", "water",
            "chopped", "minced", "sliced", "diced", "mixed",
            "heated", "cooked", "boiled"
        ]
        
        # Check if any ingredient from other_step is needed in this step in a modified state
        for ingredient in ingredients:
            if ingredient in other_text and ingredient in step_text:
                # Check if the ingredient state changes in other_step and if this step needs that state
                state_changes = ["chop", "mince", "slice", "dice", "mix", "heat", "cook", "boil"]
                modified_states = ["chopped", "minced", "sliced", "diced", "mixed", "heated", "cooked", "boiled"]
                
                # Check if this step needs a modified state and if the other step creates that state
                for action, state in zip(state_changes, modified_states):
                    if action in other_text and state in step_text:
                        logger.debug(f"Found ingredient state dependency: '{step_text}' needs {ingredient} from '{other_text}'")
                        return True
        
        return False

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms that might be referenced by other steps."""
        # Split into words and get phrases
        words = text.split()
        phrases = [
            ' '.join(words[i:i+2]) for i in range(len(words)-1)
        ] + [
            ' '.join(words[i:i+3]) for i in range(len(words)-2)
        ]
        
        # Add individual words that represent ingredients or states
        important_terms = []
        key_words = [
            "garlic", "parsley", "oil", "pasta", "water",
            "chopped", "minced", "sliced", "diced", "mixed",
            "heated", "cooked", "boiled"
        ]
        
        for word in words:
            if word.lower() in key_words:
                important_terms.append(word.lower())
        
        # Add relevant phrases
        for phrase in phrases:
            phrase_lower = phrase.lower()
            if any(word in phrase_lower for word in key_words):
                important_terms.append(phrase_lower)
        
        if important_terms:
            logger.debug(f"Extracted key terms: {important_terms}")
        return list(set(important_terms))  # Remove duplicates

    def _get_next_available_steps(self) -> List[int]:
        """Get steps that can be done next based on completions."""
        available = []
        for step_num in range(1, max(self.parallel_tasks.keys()) + 1):
            if step_num not in self._completed_steps:
                task = self.parallel_tasks.get(step_num)
                if task and all(prereq in self._completed_steps for prereq in task.prerequisites):
                    available.append(step_num)
        
        if available:
            logger.debug(f"Next available steps: {available}")
        return available

    def _has_dependencies(self, step: Dict, other_step: Dict) -> bool:
        """Check if a step has dependencies on another step."""
        # Get key terms from both steps
        step_terms = self._extract_key_terms(step['instruction'])
        other_terms = self._extract_key_terms(other_step['instruction'])
        
        # Check for any term overlap that might indicate a dependency
        return bool(set(step_terms) & set(other_terms))

    def mark_step_completed(self, step_number):
        """Mark a task as completed and check for next available steps."""
        logger.info(f"Marking step {step_number} as completed")
        
        if step_number in self.parallel_tasks:
            self.parallel_tasks[step_number].status = TaskStatus.COMPLETED
            logger.info(f"Updated parallel task {step_number} status to COMPLETED")
            
        if step_number not in self._completed_steps:
            self._completed_steps.append(step_number)
            logger.info(f"Added step {step_number} to completed steps. Current completed steps: {self._completed_steps}")
        
        # If this was a timer step, clear the timer state
        if step_number == self.current_timer_step:
            logger.info(f"Completed timer step {step_number}, clearing timer state")
            self.current_timer_step = None
            self.active_timer_step = None
            self.timer_start_time = None
        
        # Check for any steps that can now be started
        available_tasks = self.get_available_parallel_tasks(
            self.current_timer_step if self.current_timer_step else step_number,
            float('inf')
        )
        logger.info(f"Available tasks after completing step {step_number}: {available_tasks}")
        return available_tasks 