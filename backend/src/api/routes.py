from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import logging
from typing import List
import json

from models.schemas import (
    RecipeInput, RecipeOutput, SubstitutionRequest,
    VoiceInput, ConversationState
)
from services.recipe_service import RecipeService
from services.tts_service import TTSService
from services.voice_interaction_service import VoiceInteractionService
from services.substitution_service import SubstitutionService

logger = logging.getLogger(__name__)

router = APIRouter()

def init_router(
    recipe_service: RecipeService,
    tts_service: TTSService,
    voice_interaction_service: VoiceInteractionService,
    substitution_service: SubstitutionService
):
    
    @router.post("/recipes/import", response_model=RecipeOutput)
    async def import_recipe(recipe_input: RecipeInput):
        try:
            recipe = await recipe_service.import_recipe(recipe_input.content, recipe_input.type)
            return RecipeOutput(
                id=recipe.id,
                title=recipe.title,
                metadata=recipe.metadata,
                ingredients=recipe.ingredients,
                steps=recipe.steps,
                equipment=recipe.equipment
            )
        except Exception as e:
            logger.exception("Error importing recipe")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/recipes", response_model=List[RecipeOutput])
    async def list_recipes():
        recipes = recipe_service.list_recipes()
        return [
            RecipeOutput(
                id=recipe.id,
                title=recipe.title,
                metadata=recipe.metadata,
                ingredients=recipe.ingredients,
                steps=recipe.steps,
                equipment=recipe.equipment
            )
            for recipe in recipes
        ]

    @router.get("/test-recipe")
    async def get_test_recipe_id():
        """Get the ID of the test recipe for debugging."""
        return {"id": recipe_service.get_test_recipe_id()}

    @router.get("/recipes/{recipe_id}", response_model=RecipeOutput)
    async def get_recipe(recipe_id: str):
        logger.info(f"Getting recipe with ID: {recipe_id}")
        recipe = recipe_service.get_recipe(recipe_id)
        if not recipe:
            logger.error(f"Recipe not found: {recipe_id}")
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Get the current state from metadata
        current_state = recipe.metadata.get("current_state", "initial_summary")
        logger.info(f"Current recipe state: {current_state}")
        logger.info(f"Recipe steps count before filtering: {len(recipe.steps)}")
        
        # Determine if we should include steps in the response
        include_steps = current_state in ["cooking", "ready_to_cook"]
        has_made_substitutions = recipe.metadata.get("has_made_substitutions", False)
        is_servings_adjusted = recipe.metadata.get("servings_adjusted", False)
        
        logger.info(f"Step inclusion check: state={current_state}, has_subs={has_made_substitutions}, servings_adjusted={is_servings_adjusted}")
        
        # Create the response with or without steps based on state and workflow
        response_data = {
            "id": recipe.id,
            "title": recipe.title,
            "metadata": recipe.metadata,
            "ingredients": recipe.ingredients,
            "steps": recipe.steps if include_steps else [],
            "equipment": recipe.equipment
        }
        
        logger.info(f"Response steps count: {len(response_data['steps'])}")
        logger.info(f"Response metadata: {response_data['metadata']}")
        
        return RecipeOutput(**response_data)

    @router.post("/recipes/{recipe_id}/summary/audio")
    async def get_recipe_summary_audio(recipe_id: str):
        recipe = recipe_service.get_recipe(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        try:
            audio_bytes = tts_service.generate_recipe_summary(recipe.__dict__)
            return Response(content=audio_bytes, media_type="audio/mpeg")
        except Exception as e:
            logger.exception("Error generating audio summary")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/recipes/{recipe_id}")
    async def delete_recipe(recipe_id: str):
        if not recipe_service.delete_recipe(recipe_id):
            raise HTTPException(status_code=404, detail="Recipe not found")
        return {"message": "Recipe deleted successfully"}

    @router.post("/recipes/{recipe_id}/substitute", response_model=RecipeOutput)
    async def suggest_substitution(recipe_id: str, request: SubstitutionRequest):
        recipe = recipe_service.get_recipe(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        try:
            substitution_data = substitution_service.get_substitution_suggestions(
                request.ingredient,
                recipe.__dict__
            )
            
            if "updated_recipe" in substitution_data:
                # Create new recipe with the substitution
                updated_recipe = recipe_service.create_recipe(**substitution_data["updated_recipe"])
                return RecipeOutput(
                    id=updated_recipe.id,
                    title=updated_recipe.title,
                    metadata=updated_recipe.metadata,
                    ingredients=updated_recipe.ingredients,
                    steps=updated_recipe.steps,
                    equipment=updated_recipe.equipment
                )
            else:
                raise ValueError("Invalid substitution response format")
        except Exception as e:
            logger.exception("Error processing substitution request")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process substitution request: {str(e)}"
            )

    def make_header_safe(text: str) -> str:
        """Make text safe for use in HTTP headers by encoding to base64."""
        import base64
        if isinstance(text, str):
            return base64.b64encode(text.encode('utf-8')).decode('ascii')
        return text

    def create_header_summary(text: str, max_length: int = 100) -> str:
        """Create a concise summary for headers from the full response text."""
        # Get first sentence or up to first newline
        summary = text.split('\n')[0].split('.')[0]
        
        # If summary is too long, truncate it
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return summary

    @router.post("/recipes/{recipe_id}/voice-interaction")
    async def handle_voice_interaction(recipe_id: str, voice_input: VoiceInput):
        recipe = recipe_service.get_recipe(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        try:
            # Handle empty transcript (initial request)
            if not voice_input.transcript.strip():
                response_data, next_state = None, voice_input.current_state
                
                if voice_input.current_state == ConversationState.INITIAL_SUMMARY:
                    audio_data, response_text = tts_service.generate_recipe_summary(recipe.__dict__, voice_input.current_state)
                    next_state = ConversationState.ASKING_SERVINGS
                else:
                    if voice_input.current_state == ConversationState.ASKING_SERVINGS:
                        audio_data, response_text = tts_service.generate_voice_response(
                            "How many servings would you like to make?",
                            voice_input.current_state
                        )
                    elif voice_input.current_state == ConversationState.ASKING_SUBSTITUTION:
                        audio_data, response_text = tts_service.generate_voice_response(
                            "Do you need to substitute any ingredients? If yes, please tell me which ingredient.",
                            voice_input.current_state
                        )
                    elif voice_input.current_state == ConversationState.READY_TO_COOK:
                        audio_data, response_text = tts_service.generate_recipe_summary(recipe.__dict__, voice_input.current_state)
                
                # Create a summary for headers
                header_summary = create_header_summary(response_text)
                
                headers = {
                    "X-Next-State": next_state,
                    "X-Response-Text": make_header_safe(header_summary),
                    "X-Full-Response": make_header_safe(response_text),
                    "X-Response-Text-Encoded": "true",
                    "Access-Control-Expose-Headers": "X-Next-State, X-Updated-Recipe-Id, X-Response-Text, X-Full-Response, X-Response-Text-Encoded"
                }
                
                return Response(
                    content=audio_data,
                    media_type="audio/mpeg",
                    headers=headers
                )

            # Handle normal voice interaction based on current state
            if voice_input.current_state in [ConversationState.INITIAL_SUMMARY, ConversationState.ASKING_SERVINGS]:
                audio_data, response_text, next_state, updated_recipe = voice_interaction_service.process_servings_request(
                    voice_input.transcript,
                    recipe.__dict__
                )
                
                if updated_recipe:
                    updated_recipe = recipe_service.create_recipe(**updated_recipe)
                    recipe_id = updated_recipe.id
                
                # Create a summary for headers
                header_summary = create_header_summary(response_text)
                
                headers = {
                    "X-Next-State": next_state,
                    "X-Updated-Recipe-Id": recipe_id if updated_recipe else None,
                    "X-Response-Text": make_header_safe(header_summary),
                    "X-Full-Response": make_header_safe(response_text),
                    "X-Response-Text-Encoded": "true",
                    "Access-Control-Expose-Headers": "X-Next-State, X-Updated-Recipe-Id, X-Response-Text, X-Full-Response, X-Response-Text-Encoded"
                }

            elif voice_input.current_state == ConversationState.ASKING_SUBSTITUTION:
                audio_data, response_text, next_state, updated_recipe, substitutions = voice_interaction_service.process_substitution_request(
                    voice_input.transcript,
                    recipe.__dict__
                )
                
                if updated_recipe:
                    updated_recipe = recipe_service.create_recipe(**updated_recipe)
                    recipe_id = updated_recipe.id
                
                # Create a summary for headers
                header_summary = create_header_summary(response_text)
                
                headers = {
                    "X-Next-State": next_state,
                    "X-Updated-Recipe-Id": recipe_id if updated_recipe else None,
                    "X-Response-Text": make_header_safe(header_summary),
                    "X-Full-Response": make_header_safe(response_text),
                    "X-Response-Text-Encoded": "true",
                    "Access-Control-Expose-Headers": "X-Next-State, X-Updated-Recipe-Id, X-Response-Text, X-Full-Response, X-Response-Text-Encoded, X-Substitution-Options"
                }
                
                if substitutions:
                    # Ensure substitutions JSON is header-safe
                    substitutions_json = json.dumps(substitutions)
                    headers["X-Substitution-Options"] = make_header_safe(substitutions_json)

            elif voice_input.current_state == ConversationState.READY_TO_COOK:
                audio_data, response_text, next_state, updated_recipe = voice_interaction_service.process_ready_to_cook(
                    voice_input.transcript,
                    recipe.__dict__
                )
                
                if updated_recipe:
                    updated_recipe = recipe_service.create_recipe(**updated_recipe)
                    recipe_id = updated_recipe.id
                
                # Create a summary for headers
                header_summary = create_header_summary(response_text)
                
                headers = {
                    "X-Next-State": next_state,
                    "X-Updated-Recipe-Id": recipe_id if updated_recipe else None,
                    "X-Response-Text": make_header_safe(header_summary),
                    "X-Full-Response": make_header_safe(response_text),
                    "X-Response-Text-Encoded": "true",
                    "Access-Control-Expose-Headers": "X-Next-State, X-Updated-Recipe-Id, X-Response-Text, X-Full-Response, X-Response-Text-Encoded"
                }

            elif voice_input.current_state == ConversationState.COOKING:
                audio_data, response_text, next_state, updated_recipe, timer_data = voice_interaction_service.process_cooking_step(
                    voice_input.transcript,
                    recipe.__dict__
                )
                
                if updated_recipe:
                    updated_recipe = recipe_service.create_recipe(**updated_recipe)
                    recipe_id = updated_recipe.id
                
                # Create a summary for headers
                header_summary = create_header_summary(response_text)
                
                headers = {
                    "X-Next-State": next_state,
                    "X-Updated-Recipe-Id": recipe_id if updated_recipe else None,
                    "X-Response-Text": make_header_safe(header_summary),
                    "X-Full-Response": make_header_safe(response_text),
                    "X-Response-Text-Encoded": "true",
                    "Access-Control-Expose-Headers": "X-Next-State, X-Updated-Recipe-Id, X-Response-Text, X-Full-Response, X-Response-Text-Encoded, X-Timer-Data"
                }
                
                if timer_data:
                    headers["X-Timer-Data"] = make_header_safe(json.dumps(timer_data))

            return Response(
                content=audio_data,
                media_type="audio/mpeg",
                headers=headers
            )
        
        except Exception as e:
            logger.exception("Error processing voice interaction")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process voice interaction: {str(e)}"
            )

    return router 