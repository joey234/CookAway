from pydantic import BaseModel
from typing import Optional, List, Union
from enum import Enum

class RecipeInput(BaseModel):
    content: str
    type: str = "text"  # "text" or "url"

class RecipeMetadata(BaseModel):
    servings: int
    prepTime: str
    cookTime: str
    difficulty: str

class RecipeIngredient(BaseModel):
    item: str
    amount: float
    unit: str
    notes: Optional[str] = None

class RecipeStep(BaseModel):
    step: int
    instruction: str
    timer: Optional[dict] = None
    checkpoints: Optional[List[str]] = None
    parallel_with: Optional[List[int]] = []
    estimated_time: Optional[int] = None

class RecipeOutput(BaseModel):
    id: str
    title: str
    metadata: RecipeMetadata
    ingredients: List[RecipeIngredient]
    steps: List[RecipeStep]
    equipment: List[str]

class SubstitutionRequest(BaseModel):
    recipe_id: str
    ingredient: str

class ConversationState(str, Enum):
    INITIAL_SUMMARY = "initial_summary"
    ASKING_SUBSTITUTION = "asking_substitution"
    READY_TO_COOK = "ready_to_cook"
    COOKING = "cooking"
    ASKING_SERVINGS = "asking_servings"

class VoiceInput(BaseModel):
    recipe_id: str
    transcript: str
    current_state: ConversationState

class VoiceResponse(BaseModel):
    audio_content: bytes
    next_state: ConversationState
    updated_recipe_id: Optional[str] = None
    substitutions: Optional[List[dict]] = None 