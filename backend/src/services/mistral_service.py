import os
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import logging

logger = logging.getLogger(__name__)

# Initialize Mistral client
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("MISTRAL_API_KEY environment variable is not set")

mistral_client = MistralClient(api_key=api_key)

def get_mistral_response(prompt: str) -> str:
    """Get a response from Mistral AI for cooking questions."""
    try:
        # Create the chat messages
        messages = [
            ChatMessage(role="system", content="""You are an expert chef assistant helping someone cook. 
Focus ONLY on answering the current question with specific, practical guidance.
DO NOT suggest next steps or future actions.
DO NOT ask if they need more help or have other questions.
DO NOT remind them what to do next time.
Just provide clear, direct answers about their current question."""),
            ChatMessage(role="user", content=prompt)
        ]

        # Get response from Mistral
        chat_response = mistral_client.chat(
            model="mistral-small-latest",
            messages=messages,
            temperature=0.7,  # Slightly creative but still focused
            max_tokens=500,
            random_seed=42
        )

        # Extract and return the response text
        response = chat_response.choices[0].message.content
        logger.info(f"Got response from Mistral: {response[:100]}...")
        return response

    except Exception as e:
        logger.error(f"Error getting Mistral response: {e}")
        raise 