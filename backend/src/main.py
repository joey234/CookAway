from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import json
import logging
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.exceptions import MistralException
from mistralai.models.chat_completion import ChatMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Mistral client
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("MISTRAL_API_KEY environment variable is not set")

mistral_client = MistralClient(api_key=api_key)

app = FastAPI(title="CookAway API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RecipeInput(BaseModel):
    content: str
    type: str = "text"  # "text" or "url"

class RecipeOutput(BaseModel):
    title: str
    metadata: dict
    ingredients: list
    steps: list
    equipment: list

@app.post("/api/recipes/import", response_model=RecipeOutput)
async def import_recipe(recipe_input: RecipeInput):
    try:
        logger.info(f"Processing recipe import request. Type: {recipe_input.type}")
        
        if not recipe_input.content.strip():
            raise HTTPException(status_code=400, detail="Recipe content cannot be empty")

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
                    "amount": 1,
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
                    "checkpoints": ["check 1", "check 2"]
                }
            ],
            "equipment": ["required equipment 1", "required equipment 2"]
        }
        
        Follow this exact JSON structure. All fields are required. Ensure measurements are standardized and instructions are clear.
        Your response must be a valid JSON object."""

        # Create the chat messages for Mistral
        messages = [
            ChatMessage(role="system", content=system_message),
            ChatMessage(role="user", content=recipe_input.content)
        ]

        logger.info("Sending request to Mistral API")
        
        # Get response from Mistral using the correct API format
        chat_response = mistral_client.chat(
            model="mistral-medium",  # Using medium model for better cost/performance ratio
            messages=messages,
            temperature=0.1,  # Lower temperature for more structured output
            max_tokens=2000,  # Ensure enough tokens for the response
            random_seed=42    # For consistent responses during testing
        )

        logger.info("Received response from Mistral API")
        
        # Log the raw response for debugging
        logger.debug(f"Raw Mistral response: {chat_response.choices[0].message.content}")

        # Parse the response into structured format
        try:
            parsed_recipe = json.loads(chat_response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Raw content: {chat_response.choices[0].message.content}")
            raise HTTPException(
                status_code=500,
                detail="Failed to parse recipe: Invalid JSON response from AI"
            )
        
        # Validate the response has all required fields
        required_fields = {"title", "metadata", "ingredients", "steps", "equipment"}
        missing_fields = required_fields - set(parsed_recipe.keys())
        if missing_fields:
            logger.error(f"Missing fields in response: {missing_fields}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid recipe format: missing fields {missing_fields}"
            )
        
        return RecipeOutput(**parsed_recipe)

    except MistralException as e:
        logger.error(f"Mistral API error: {e}")
        raise HTTPException(status_code=500, detail=f"Mistral API error: {str(e)}")
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Unexpected error during recipe import")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "mistral_api_key_configured": bool(api_key)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
