from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# Load environment variables
load_dotenv()

# Initialize Mistral client
mistral_client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))

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
        # Prepare the system message for recipe parsing
        system_message = """You are a recipe parsing expert. Convert the given recipe text into a structured format with the following fields:
        - title: The recipe name
        - metadata: Dictionary containing servings, prepTime, cookTime, difficulty
        - ingredients: List of dictionaries with item, amount, unit, and notes
        - steps: List of dictionaries with step number, instruction, timer (if applicable), and checkpoints
        - equipment: List of required kitchen equipment
        
        Ensure all measurements are standardized and instructions are clear."""

        # Create the chat message for Mistral
        messages = [
            ChatMessage(role="system", content=system_message),
            ChatMessage(role="user", content=recipe_input.content)
        ]

        # Get response from Mistral
        chat_response = mistral_client.chat(
            model="mistral-medium",
            messages=messages
        )

        # Parse the response into structured format
        # Note: The response will be in JSON format as per our system message
        parsed_recipe = eval(chat_response.choices[0].message.content)
        
        return RecipeOutput(**parsed_recipe)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
