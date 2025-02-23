from typing import Dict, List, Optional
import logging
import base64
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

logger = logging.getLogger(__name__)

class PhotoAnalysisService:
    def __init__(self, api_key: str):
        """Initialize with Mistral API key."""
        self.client = MistralClient(api_key=api_key)
        self.model = "pixtral-latest"  # Mistral's official Pixtral model

    def analyze_cooking_photo(self, photo_data: bytes, step_context: Dict) -> Dict:
        """
        Analyze a photo of the cooking process using Mistral's Pixtral model.
        Returns analysis results including visual characteristics and any issues.
        """
        try:
            # Convert photo to base64
            photo_base64 = base64.b64encode(photo_data).decode('utf-8')
            
            # Create messages for the chat
            messages = [
                ChatMessage(
                    role="user",
                    content=[
                        {
                            "type": "text",
                            "text": self._create_analysis_prompt(step_context)
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{photo_base64}"
                            }
                        }
                    ]
                )
            ]
            
            # Get analysis from Pixtral
            response = self.client.chat(
                model=self.model,
                messages=messages
            )
            
            # Parse the response into structured data
            return self._parse_analysis_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error analyzing photo with Pixtral: {e}")
            return {
                "visual_characteristics": ["Unable to analyze photo"],
                "potential_issues": ["Photo analysis failed"],
                "matching_expectations": []
            }

    def _create_analysis_prompt(self, step_context: Dict) -> str:
        """Create a prompt for Pixtral to analyze the cooking photo."""
        return f"""As an expert chef, analyze this photo of step {step_context.get('current_step')} in the cooking process.

CURRENT STEP DETAILS:
Instruction: {step_context['current_step_data'].get('instruction', '')}

Expected visual checkpoints:
{self._format_list(step_context['current_step_data'].get('checkpoints', []))}

Common issues to look for:
{self._format_list(step_context['current_step_data'].get('warnings', []))}

Please analyze the photo and tell me:
1. What visual characteristics can you identify in the food/cooking process?
2. Are there any potential issues or concerns you can spot?
3. How well does it match the expected characteristics for this step?

Focus on:
- Color and appearance (e.g., browning, caramelization)
- Texture and consistency (e.g., smoothness, crispiness)
- Doneness indicators (e.g., internal color, crust formation)
- Any signs of common cooking issues (e.g., burning, uneven cooking)
- Proper technique execution (e.g., knife cuts, mixing consistency)
- Safety concerns if any (e.g., undercooked meat, cross-contamination)

Format your response exactly as follows:
VISUAL_CHARACTERISTICS:
- [List each visual characteristic you observe]

POTENTIAL_ISSUES:
- [List any issues or concerns you identify]

MATCHING_EXPECTATIONS:
- [List how well the photo matches the expected state]"""

    def _parse_analysis_response(self, response: str) -> Dict:
        """Parse Pixtral's response into structured data."""
        sections = {
            "visual_characteristics": [],
            "potential_issues": [],
            "matching_expectations": []
        }
        
        current_section = None
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if "VISUAL_CHARACTERISTICS:" in line:
                current_section = "visual_characteristics"
            elif "POTENTIAL_ISSUES:" in line:
                current_section = "potential_issues"
            elif "MATCHING_EXPECTATIONS:" in line:
                current_section = "matching_expectations"
            elif line.startswith('-') and current_section:
                item = line[1:].strip()
                sections[current_section].append(item)
        
        return sections

    def _format_list(self, items: List[str]) -> str:
        """Format a list of items with bullet points."""
        if not items:
            return "None provided"
        return "\n".join(f"• {item}" for item in items) 