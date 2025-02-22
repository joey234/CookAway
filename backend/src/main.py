from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from dotenv import load_dotenv
from mistralai.client import MistralClient

from services.tts_service import TTSService
from services.recipe_service import RecipeService
from services.voice_interaction_service import VoiceInteractionService
from services.substitution_service import SubstitutionService
from services.recipe_parser_service import RecipeParserService
from api.routes import init_router

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

# Initialize services
tts_service = TTSService()
recipe_parser_service = RecipeParserService(mistral_client)
recipe_service = RecipeService(recipe_parser_service)
substitution_service = SubstitutionService(mistral_client)
voice_interaction_service = VoiceInteractionService(tts_service, recipe_service, substitution_service)

app = FastAPI(title="CookAway API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize and include API routes
router = init_router(recipe_service, tts_service, voice_interaction_service, substitution_service)
app.include_router(router, prefix="/api")

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "mistral_api_key_configured": bool(api_key),
        "elevenlabs_api_key_configured": bool(os.getenv("ELEVEN_LABS_API_KEY"))
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 