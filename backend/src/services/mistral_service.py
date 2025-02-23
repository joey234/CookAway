import os
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Initialize Mistral client
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("MISTRAL_API_KEY environment variable is not set")

mistral_client = MistralClient(api_key=api_key)

def get_mistral_response(prompt: str, context: Dict = None) -> str:
    """Get a response from Mistral AI for cooking questions."""
    try:
        # Create the system message based on whether we're handling a cooking step or general question
        system_message = """You are an expert chef assistant helping someone cook. 
You have access to the full recipe context and progress.
Your responses should be natural and conversational, while also being precise about cooking instructions.

When responding to user input during cooking:
1. First provide a natural, helpful response to their input
2. Then, if their input requires a state change, add a SYSTEM_ACTION: tag followed by the action:
   - MARK_COMPLETED:X (where X is the step number to mark as completed)
   - START_TIMER:X (where X is the step number to start timer for)
   - STOP_TIMER (to stop the current timer)
   - NEXT_STEP (to move to the next step)
   - START_COOKING (to begin cooking with step 1)
   - FINISH_COOKING (to end the cooking session)

Example responses with actions:
"That looks perfect! The garlic is nicely minced and ready to use.
SYSTEM_ACTION: MARK_COMPLETED:2"

"I'll start the timer for boiling the pasta. While that's going, you can prepare the sauce.
SYSTEM_ACTION: START_TIMER:3"

Example responses without actions:
"Al dente means the pasta is cooked but still has a slight firmness when bitten. You can test this by taking a piece of pasta and biting into it - there should be a tiny white dot in the center."

"The oil should be hot enough that a small piece of garlic sizzles when added, but not so hot that it browns immediately."

Remember:
1. Keep responses conversational and encouraging
2. Only include SYSTEM_ACTION if the user's input requires a state change
3. If the user asks a question, focus on answering it clearly without any system action
4. If multiple steps could be completed, ask for clarification"""

        # Create the chat messages
        messages = [
            ChatMessage(role="system", content=system_message),
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