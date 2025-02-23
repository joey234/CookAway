import pytest
import logging
from services.voice_interaction_service import VoiceInteractionService
from services.tts_service import TTSService
from services.recipe_service import RecipeService
from services.substitution_service import SubstitutionService
from services.parallel_task_service import ParallelTaskService
from services.recipe_parser_service import RecipeParserService
from mistralai.client import MistralClient
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@pytest.fixture
def services():
    """Initialize all required services."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        pytest.skip("MISTRAL_API_KEY not set in environment")
    
    mistral_client = MistralClient(api_key=api_key)
    tts_service = TTSService()
    recipe_parser_service = RecipeParserService(mistral_client)
    recipe_service = RecipeService(recipe_parser_service)
    substitution_service = SubstitutionService(mistral_client)
    parallel_task_service = ParallelTaskService()
    
    voice_interaction_service = VoiceInteractionService(
        tts_service=tts_service,
        recipe_service=recipe_service,
        substitution_service=substitution_service,
        parallel_task_service=parallel_task_service
    )
    
    return {
        'voice_interaction': voice_interaction_service,
        'recipe_service': recipe_service,
        'parallel_task_service': parallel_task_service
    }

@pytest.fixture
def test_recipe(services):
    """Get the test recipe."""
    recipe_id = services['recipe_service'].get_test_recipe_id()
    return services['recipe_service'].get_recipe(recipe_id).__dict__

def test_basic_cooking_question(services, test_recipe):
    """Test basic cooking question about al dente."""
    # Initialize recipe and start cooking
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    test_recipe['metadata']['current_step'] = 3  # Set to pasta cooking step
    
    # Ask about al dente
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "What does al dente mean?",
        test_recipe
    )
    
    # Verify response contains relevant information
    assert "al dente" in response_text.lower()
    assert "bite" in response_text.lower()
    assert "texture" in response_text.lower() or "firm" in response_text.lower()
    assert timer_data is None  # Question shouldn't affect timer

def test_temperature_question(services, test_recipe):
    """Test question about cooking temperature."""
    # Set current step to oil heating
    test_recipe['metadata']['current_step'] = 4
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about oil temperature
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "How hot should the oil be?",
        test_recipe
    )
    
    # Verify response contains temperature guidance
    assert "temperature" in response_text.lower() or "heat" in response_text.lower()
    assert "medium" in response_text.lower()
    assert "smoking" in response_text.lower()  # Should mention avoiding smoking oil
    assert timer_data is None

def test_visual_cue_question(services, test_recipe):
    """Test question about visual indicators."""
    # Set current step to garlic cooking
    test_recipe['metadata']['current_step'] = 5
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about garlic appearance
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "How should the garlic look?",
        test_recipe
    )
    
    # Verify response contains visual guidance
    assert "golden" in response_text.lower()
    assert "brown" in response_text.lower()  # Should mention avoiding browning
    assert timer_data is None

def test_technique_question(services, test_recipe):
    """Test question about cooking technique."""
    # Set current step to chopping
    test_recipe['metadata']['current_step'] = 2
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about chopping technique
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "How should I chop the garlic?",
        test_recipe
    )
    
    # Verify response contains technique guidance
    assert "slice" in response_text.lower() or "chop" in response_text.lower()
    assert "thin" in response_text.lower()
    assert "knife" in response_text.lower()
    assert timer_data is None

def test_problem_solving_question(services, test_recipe):
    """Test handling of problem-solving questions."""
    # Set current step to pasta cooking
    test_recipe['metadata']['current_step'] = 3
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about pasta sticking
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "Help! My pasta is sticking together",
        test_recipe
    )
    
    # Verify response contains problem-solving advice
    assert "stir" in response_text.lower()
    assert "water" in response_text.lower()
    assert timer_data is None

def test_timing_question(services, test_recipe):
    """Test question about timing and doneness."""
    # Set current step to pasta cooking
    test_recipe['metadata']['current_step'] = 3
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about pasta doneness
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "How do I know when the pasta is done?",
        test_recipe
    )
    
    # Verify response contains timing and doneness indicators
    assert "test" in response_text.lower()
    assert "bite" in response_text.lower()
    assert "texture" in response_text.lower() or "firm" in response_text.lower()
    assert timer_data is None

def test_equipment_question(services, test_recipe):
    """Test question about equipment usage."""
    # Set current step to oil heating
    test_recipe['metadata']['current_step'] = 4
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about pan size
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "What kind of pan should I use?",
        test_recipe
    )
    
    # Verify response contains equipment guidance
    assert "pan" in response_text.lower()
    assert "large" in response_text.lower() or "wide" in response_text.lower()
    assert timer_data is None

def test_ingredient_question(services, test_recipe):
    """Test question about ingredient handling."""
    # Set current step to garlic preparation
    test_recipe['metadata']['current_step'] = 2
    services['parallel_task_service'].analyze_recipe_for_parallel_tasks(test_recipe['steps'])
    
    # Ask about parsley preparation
    audio_data, response_text, state, recipe_dict, timer_data = services['voice_interaction'].process_cooking_step(
        "How finely should I chop the parsley?",
        test_recipe
    )
    
    # Verify response contains ingredient guidance
    assert "parsley" in response_text.lower()
    assert "chop" in response_text.lower()
    assert timer_data is None 