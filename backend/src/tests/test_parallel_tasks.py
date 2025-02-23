import pytest
import logging
from src.services.parallel_task_service import ParallelTaskService, TaskStatus
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.DEBUG)

@pytest.fixture
def parallel_task_service():
    return ParallelTaskService()

@pytest.fixture
def sample_recipe_steps() -> List[Dict]:
    return [
        {
            "step": 1,
            "instruction": "Bring a large pot of water to a boil. Add salt.",
            "timer": {"duration": 300, "type": "prep"}
        },
        {
            "step": 2,
            "instruction": "While waiting for water to boil, chop garlic and parsley.",
            "checkpoints": ["Garlic should be finely minced", "Parsley should be roughly chopped"],
            "parallel_with": [1],  # Can be done while step 1 is in progress
            "estimated_time": 120  # 2 minutes
        },
        {
            "step": 3,
            "instruction": "Add pasta to boiling water and cook until al dente.",
            "timer": {"duration": 480, "type": "cooking"}
        },
        {
            "step": 4,
            "instruction": "While pasta cooks, heat olive oil in a pan.",
            "parallel_with": [3],  # Can be done while step 3 is in progress
            "estimated_time": 60  # 1 minute
        },
        {
            "step": 5,
            "instruction": "Add chopped garlic to the heated oil.",
            "checkpoints": ["Garlic should turn golden, not brown"],
            "parallel_with": [3],  # Can be done while step 3 is in progress
            "estimated_time": 120  # 2 minutes
        }
    ]

def test_task_analysis(parallel_task_service, sample_recipe_steps):
    """Test loading of parallel tasks from recipe data."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Step 2 should be identified as a parallel task
    assert 2 in parallel_task_service.parallel_tasks
    
    # Step 2 should have step 1 as prerequisite
    assert 1 in parallel_task_service.parallel_tasks[2].prerequisites
    
    # Step 5 should depend on step 2 (needs chopped garlic)
    assert 5 in parallel_task_service.parallel_tasks[2].dependencies

def test_available_tasks_during_timer(parallel_task_service, sample_recipe_steps):
    """Test getting available tasks during a timer period."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    print("\nParallel tasks after analysis:", parallel_task_service.parallel_tasks)
    
    # Start first timer (boiling water)
    parallel_task_service.start_timer_period(1)
    available_tasks = parallel_task_service.get_available_parallel_tasks(1, 300)
    print("\nAvailable tasks during water boiling:", available_tasks)
    
    # Step 2 should be available during water boiling
    assert any(task['step_number'] == 2 for task in available_tasks)
    
    # Step 5 should not be available yet (depends on step 2)
    assert not any(task['step_number'] == 5 for task in available_tasks)

def test_task_completion(parallel_task_service, sample_recipe_steps):
    """Test marking tasks as completed and updating dependencies."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Complete step 1
    parallel_task_service.mark_step_completed(1)
    
    # Start timer for step 3
    parallel_task_service.start_timer_period(3)
    available_tasks = parallel_task_service.get_available_parallel_tasks(3, 480)
    
    # Step 4 should be available (parallel with step 3)
    assert any(task['step_number'] == 4 for task in available_tasks)
    
    # Complete step 2
    parallel_task_service.mark_step_completed(2)
    
    # Check task status
    assert parallel_task_service.parallel_tasks[2].status == TaskStatus.COMPLETED
    assert 2 in parallel_task_service.completed_steps

def test_timer_period_management(parallel_task_service, sample_recipe_steps):
    """Test starting and ending timer periods."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Start timer for step 1
    parallel_task_service.start_timer_period(1)
    assert parallel_task_service.active_timer_step == 1
    
    # Complete a parallel task
    parallel_task_service.mark_step_completed(2)
    
    # End timer period
    result = parallel_task_service.end_timer_period()
    
    # Check timer period results
    assert 2 in result['completed_parallel_tasks']
    assert result['next_main_step'] == 2
    assert parallel_task_service.active_timer_step is None

def test_task_prerequisites(parallel_task_service, sample_recipe_steps):
    """Test handling of task prerequisites."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    print("\nParallel tasks after analysis:", parallel_task_service.parallel_tasks)
    
    # Start timer for step 3 (pasta cooking)
    parallel_task_service.start_timer_period(3)
    available_tasks = parallel_task_service.get_available_parallel_tasks(3, 480)
    print("\nAvailable tasks before completing prerequisites:", available_tasks)
    
    # Step 5 should not be available (needs step 2 completed)
    assert not any(task['step_number'] == 5 for task in available_tasks)
    
    # Complete prerequisites
    parallel_task_service.mark_step_completed(1)
    parallel_task_service.mark_step_completed(2)
    print("\nCompleted steps:", parallel_task_service.completed_steps)
    
    # Check available tasks again
    available_tasks = parallel_task_service.get_available_parallel_tasks(3, 480)
    print("\nAvailable tasks after completing prerequisites:", available_tasks)
    
    # Step 5 should now be available
    assert any(task['step_number'] == 5 for task in available_tasks)

def test_estimated_task_time(parallel_task_service, sample_recipe_steps):
    """Test task time estimation logic."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Check if step 2 has the correct estimated time from recipe data
    step2_task = parallel_task_service.parallel_tasks[2]
    assert step2_task.estimated_time == 120  # Should be 2 minutes as specified in recipe data

def test_constant_attention_detection(parallel_task_service):
    """Test detection of steps requiring constant attention."""
    steps_with_attention = [{
        "step": 1,
        "instruction": "Stir constantly until thickened",
    }]
    
    parallel_task_service.analyze_recipe_for_parallel_tasks(steps_with_attention)
    
    # Step should not be identified as parallel task
    assert 1 not in parallel_task_service.parallel_tasks 

def test_water_boiling_parallel_tasks(parallel_task_service, sample_recipe_steps):
    """Test that prep tasks are correctly identified during water boiling."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Start timer for step 1 (water boiling)
    parallel_task_service.start_timer_period(1)
    available_tasks = parallel_task_service.get_available_parallel_tasks(1, 300)  # 5 minutes = 300 seconds
    
    # Log the analysis results
    print("\nAvailable tasks during water boiling:", available_tasks)
    print("All parallel tasks:", parallel_task_service.parallel_tasks)
    
    # Step 2 (chopping garlic and parsley) should be available during water boiling
    assert any(task['step_number'] == 2 for task in available_tasks), "Step 2 (chopping) should be available during water boiling"
    
    # Verify the task details
    chopping_task = next(task for task in available_tasks if task['step_number'] == 2)
    assert "chop garlic and parsley" in chopping_task['instruction'].lower()
    assert chopping_task['estimated_time'] == 120  # 2 minutes

def test_parallel_task_priorities(parallel_task_service, sample_recipe_steps):
    """Test that prep tasks are prioritized during water boiling."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Get step 1's next possible steps
    step1 = next(step for step in sample_recipe_steps if step['step'] == 1)
    
    # Prep tasks should be at the start of next_possible_steps
    assert 2 in step1.get('next_possible_steps', []), "Step 2 should be in next_possible_steps"
    if len(step1.get('next_possible_steps', [])) > 1:
        assert step1['next_possible_steps'][0] == 2, "Prep task (Step 2) should be prioritized"

def test_step_prioritization(parallel_task_service, sample_recipe_steps):
    """Test that non-timer steps are prioritized over steps waiting on timers."""
    parallel_task_service.analyze_recipe_for_parallel_tasks(sample_recipe_steps)
    
    # Start and complete step 1 (water boiling)
    parallel_task_service.start_timer_period(1)
    parallel_task_service.mark_step_completed(1)
    
    # Complete step 2 (chopping)
    parallel_task_service.mark_step_completed(2)
    
    # Start step 3 (pasta cooking) but don't complete it
    parallel_task_service.start_timer_period(3)
    
    # End the timer period for step 1
    result = parallel_task_service.end_timer_period()
    
    # Should suggest step 4 (heating oil) next, not step 3 (which is waiting for pasta to cook)
    assert result['next_main_step'] == 4, "Should prioritize heating oil over pasta cooking"
    
    # Complete step 4
    parallel_task_service.mark_step_completed(4)
    
    # Now step 5 should be available (adding garlic to oil)
    result = parallel_task_service.end_timer_period()
    assert result['next_main_step'] == 5, "Should move to step 5 after completing step 4" 