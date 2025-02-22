Here's a concrete plan you can input into your build assistant (cursor) to get started:

---

## Project: Voice-Activated Cooking Assistant Web Demo

### **Overview**
Build a web app that accepts a plain-text recipe, parses it into a structured format, and then guides the user through the cooking process using voice interactions. The app will support:
- Interactive Q&A (e.g., "What's the next step?")
- Step-by-step voice guidance via TTS (using ElevenLabs)
- Timers/reminders for time-bound steps (e.g., "caramelize onions for 10 minutes")
- Image capture for real-time food assessment (e.g., checking if onions are caramelized)

### **Core Functionalities**
1. **Recipe Parsing & Structuring**
   - **Input:** Plain-text recipe or webpage URL
   - **Processing:** 
     - For plain text: Use Mistral's NLP capabilities
     - For URLs: Scrape webpage content and extract recipe data
     - Support major recipe websites (AllRecipes, Food Network, NYT Cooking, etc.)
   - **Output:** A structured JSON format
   - **Validation:** Add input validation and error handling for:
     - Malformed recipes
     - Invalid URLs
     - Blocked/failed webpage scraping
   - **Format Support:** 
     - Add support for common recipe formats and schema.org Recipe markup
     - Handle recipe websites' specific HTML structures
     - Extract recipe data from unstructured blog posts
   
2. **Interactive Q&A Module**
   - **Function:** Answer user questions related to the recipe and provide cooking assistance
   - **Implementation:** 
     - Use Mistral LLM as the primary query handler
     - Structure prompts to include:
       - Current recipe context
       - User's cooking history and preferences
       - Previous steps and actions taken
       - Common cooking knowledge
     - Cache frequent responses for performance
   - **Query Types:**
     - Recipe-specific questions (e.g., "How many eggs do I need?")
     - Navigation commands (e.g., "What's the next step?")
     - Ingredient substitutions (e.g., "Can I use margarine instead of butter?")
     - Troubleshooting help (e.g., "I added too much salt")
     - Technique explanations (e.g., "How do I fold in ingredients?")
   - **Knowledge Integration:**
     - Provide Mistral with structured cooking knowledge:
       ```json
       {
         "context": {
           "recipe": {
             "current_step": "Sauté onions until translucent",
             "progress": "4/10 steps completed",
             "active_timers": ["onions: 5 mins remaining"]
           },
           "user": {
             "skill_level": "beginner",
             "dietary_restrictions": ["dairy-free"],
             "available_equipment": ["stove", "oven", "blender"]
           }
         },
         "reference_data": {
           "substitutions": {
             "common_pairs": {...},
             "dietary_alternatives": {...}
           },
           "troubleshooting": {
             "common_issues": {...},
             "emergency_fixes": {...}
           }
         }
       }
       ```
   - **Prompt Engineering:**
     - Format: "Given {context} and {reference_data}, help user with: {query}"
     - Include safety constraints and cooking best practices
     - Maintain conversation history for context
   - **Context Awareness:** 
     - Track current step and previous actions
     - Remember user's dietary restrictions
     - Consider equipment limitations
   - **Fallback Mechanisms:**
     - Use structured responses for common queries
     - Fall back to general cooking principles
     - Clearly indicate when advice is generalized
     - Suggest seeking professional help for safety concerns

3. **Step-by-Step Guidance with TTS**
   - **Function:** Read out recipe steps using natural-sounding voices.
   - **Integration:** Call the ElevenLabs TTS API to generate audio instructions.
   - **User Commands:** Support commands like "next," "repeat," or "previous."
   - **Offline Support:** Cache commonly used audio instructions
   - **Voice Selection:** Allow users to choose from available voices
   - **Speed Control:** Support adjustable playback speed
   - **Emergency Commands:** Support "stop" and "pause" commands

4. **Timer & Reminder Functionality**
   - **Function:** For steps with specific time instructions, trigger a timer and then notify the user via a voice prompt.
   - **Implementation:** Use JavaScript timers (`setTimeout`) and the Web Notifications API or TTS output for reminders.
   - **Multiple Timers:** Support concurrent timers for complex recipes
   - **Background Operation:** Ensure timers work when device is locked
   - **Persistent Storage:** Save timer state in case of page refresh
   - **Audio Options:** Configurable timer sounds

5. **Image Capture & Food Assessment**
   - **Function:** Allow users to take a photo (via the device camera) to assess if a cooking step is complete.
   - **Integration:** Use the HTML5 `getUserMedia` API for image capture, and send the image to a backend endpoint where an ML model (using TensorFlow, PyTorch, or AWS Rekognition) analyzes the food doneness.
   - **Feedback:** Return results that are then read out via TTS.
   - **Progressive Enhancement:** Fallback text instructions when camera unavailable
   - **Image Guidelines:** Show reference images for comparison
   - **Local Processing:** Use TensorFlow.js for basic checks client-side
   - **Privacy:** Clear option to disable/enable camera features

6. **Recipe Search & Suggestions**
   - **Function:** Allow users to search for recipes and get personalized suggestions
   - **Implementation:**
     - Natural language recipe search (e.g., "show me quick pasta dishes")
     - Filter by ingredients, cuisine, dietary restrictions, cooking time
     - Save favorite recipes and cooking history
   - **Data Sources:**
     - Integration with recipe APIs (Spoonacular, Edamam, etc.)
     - User-contributed recipes database
     - Ability to import recipes from popular cooking websites
   - **Smart Suggestions:**
     - Based on user preferences and past cooking history
     - Seasonal recipe recommendations
     - Dietary restrictions awareness
     - Pantry-based suggestions (what can I cook with what I have?)

### **Tech Stack**
- **Frontend:**
  - **Framework:** React
  - **UI Components:** Chakra UI (for accessible, responsive design)
  - **Voice Interaction:** Web Speech API for speech recognition; integration with ElevenLabs TTS via Fetch/Axios.
  - **Camera Integration:** HTML5 `getUserMedia`
  
- **Backend:**
  - **Language/Framework:** Python with FastAPI (or Node.js with Express)
  - **Web Scraping:** 
    - Cheerio/Puppeteer (Node.js) or BeautifulSoup/Playwright (Python)
    - Support for JavaScript-rendered content
    - Rate limiting and respectful crawling
  - **Endpoints:**
    - URL validation and recipe extraction
    - Recipe parsing (integrates with Mistral for NLP)
    - Q&A and step retrieval
    - Timer management (if needed for more complex logic)
    - Image analysis (integrates with an ML model for food assessment)
  - **APIs:** Connect to ElevenLabs TTS and Mistral for text processing.
  - **Search Infrastructure:**
    - **Engine:** Elasticsearch or Meilisearch
    - **Features:** 
      - Full-text recipe search
      - Fuzzy matching for ingredient names
      - Recipe similarity scoring
      - Faceted search for filtering
  
- **Hosting & Deployment:**
  - **Platform:** Vercel (for deploying both front-end and serverless backend functions)
  
- **Additional Integrations (Optional):**
  - **Analytics:** PostHog for user interaction tracking.
  - **Authentication:** Clerk for secure user accounts.
  - **Workflow Automation:** Make for automating secondary tasks (e.g., adding ingredients to a grocery list).

- **State Management:**
  - **Library:** Zustand or Redux Toolkit for global state
  - **Persistence:** localStorage/IndexedDB for offline support

- **Testing Stack:**
  - **Unit Tests:** Vitest or Jest
  - **E2E Tests:** Playwright
  - **Voice Testing:** Custom test helpers for Web Speech API

- **Error Handling & Monitoring:**
  - **Error Tracking:** Sentry
  - **Performance:** Web Vitals monitoring
  - **Logging:** Winston or Pino

### **Architecture & Workflow**
1. **Recipe Input:**  
   The user can:
   - Input/paste a plain-text recipe
   - Paste a URL to a recipe webpage
   - Import from supported recipe websites via browser extension
2. **URL Processing (new):**
   ```json
   {
     "url_processor": {
       "supported_domains": [
         "allrecipes.com",
         "foodnetwork.com",
         "epicurious.com",
         "cooking.nytimes.com"
       ],
       "extraction_methods": {
         "schema_org": "Parse schema.org/Recipe markup",
         "site_specific": "Use site-specific selectors",
         "fallback": "Use ML-based content extraction"
       },
       "error_handling": {
         "blocked": "Suggest manual copy-paste",
         "paywall": "Request user authentication",
         "not_found": "Validate URL and retry"
       }
     }
   }
   ```
3. **Parsing:**  
   The backend (FastAPI) processes the text with Mistral to generate a JSON object:
   ```json
   {
     "title": "Spaghetti Bolognese",
     "metadata": {
       "servings": 4,
       "prepTime": "15 minutes",
       "cookTime": "45 minutes",
       "difficulty": "medium"
     },
     "ingredients": [
       {
         "item": "spaghetti",
         "amount": 400,
         "unit": "g",
         "notes": "dried"
       }
     ],
     "steps": [
       {
         "step": 1,
         "instruction": "Boil water and cook spaghetti for 10 minutes.",
         "timer": {
           "duration": 600,
           "type": "cooking"
         },
         "checkpoints": ["water boiling", "pasta al dente"]
       }
     ],
     "equipment": [
       "large pot",
       "colander"
     ]
   }
   ```
4. **Guidance:**  
   The app reads out step 1 using ElevenLabs TTS.  
   The user can use voice commands (via the Web Speech API) to navigate: "next," "repeat," etc.
5. **Timer & Reminder:**  
   For time-bound steps, a timer is set in the frontend. When time's up, the app notifies the user (via TTS or a notification).
6. **Image Capture & Assessment:**  
   The user takes a photo using `getUserMedia`.  
   The image is sent to the backend for analysis (using a pre-trained ML model) to determine if the food is cooked properly, and feedback is provided.

### **Development Plan**
1. **Setup Project Repository & Vercel Deployment:**  
   - Initialize the React app.
   - Set up the FastAPI backend.
2. **Implement Recipe Import System (new priority):**
   - Build URL validation and processing
   - Implement web scraping with error handling
   - Create site-specific extractors for major recipe websites
   - Add schema.org Recipe parser
   - Build fallback content extraction
   - Test with various recipe website formats
3. **Implement Recipe Search & Discovery:**
   - Set up search infrastructure
   - Integrate with recipe APIs
   - Build search filters and suggestion algorithm
   - Create recipe import functionality
4. **Implement Recipe Parsing:**  
   - Create an endpoint for recipe text input.
   - Integrate Mistral to output structured JSON.
5. **Build Interactive Guidance Module:**
   - Integrate voice recognition and command mapping
   - Connect to ElevenLabs TTS to read instructions
   - Set up Mistral LLM integration:
     - Design context-aware prompts
     - Implement response caching
     - Create safety filters
   - Build conversation history management
   - Test with various cooking scenarios:
     - Ingredient substitutions
     - Emergency fixes
     - Technique questions
     - Safety concerns
6. **Develop Timer & Reminder Functionality:**  
   - Implement JavaScript timers and notification logic.
7. **Implement Image Capture & Processing:**  
   - Integrate camera functionality on the front-end.
   - Build a backend endpoint for image analysis using a suitable ML model.
8. **Testing & Iteration:**  
   - Conduct usability tests with an emphasis on accessibility.
   - Refine voice command handling and NLP accuracy.
9. **Final Deployment & Demo Preparation:**  
   - Deploy the app on Vercel.
   - Prepare documentation and demo instructions.
10. **Accessibility & Internationalization:**
    - Implement ARIA labels and roles
    - Add keyboard navigation support
    - Set up i18n infrastructure
    - Test with screen readers
11. **Progressive Web App Features:**
    - Add service worker for offline support
    - Implement install prompts
    - Enable push notifications
    - Cache critical resources
12. **Performance Optimization:**
    - Implement code splitting
    - Optimize asset loading
    - Add performance monitoring
    - Implement lazy loading

### **Data Management**
1. **Recipe Database:**
   - Schema design for efficient search
   - Regular updates for seasonal recipes
   - Version control for recipe modifications

2. **User Preferences:**
   - Dietary restrictions
   - Cooking skill level
   - Kitchen equipment inventory
   - Favorite cuisines and ingredients

3. **Search Analytics:**
   - Track popular searches
   - Monitor failed searches
   - Analyze seasonal trends
   - Improve suggestion accuracy

### **Security Considerations**
1. **User Input:**
   - Sanitize recipe inputs
   - Rate limit API calls
   - Validate file uploads
2. **API Security:**
   - Implement CORS properly
   - Add API key rotation
   - Set up request signing
3. **Data Privacy:**
   - Clear camera permissions after use
   - Don't store sensitive data
   - Add privacy policy

### Final Summary
Input this detailed plan into your build assistant to scaffold your project. Your voice-activated cooking assistant will use Vercel for hosting, Mistral for text processing, ElevenLabs for natural TTS, and integrate voice, timer, and image analysis functionalities to guide users step by step through recipes—all while ensuring a seamless, accessible cooking experience.

Happy coding!

---

**Note:** This refined plan adds more robust error handling, security considerations, and progressive enhancement while maintaining the core functionality. It also includes more detailed JSON structure and considerations for offline support and accessibility.

```json
{
  "qa_handlers": {
    "substitutions": {
      "ingredients": {
        "butter": [
          {
            "substitute": "margarine",
            "ratio": "1:1",
            "notes": "May affect texture in baking",
            "dietary_tags": ["vegan", "dairy-free"]
          },
          {
            "substitute": "coconut oil",
            "ratio": "1:1",
            "notes": "Best for high-heat cooking",
            "dietary_tags": ["vegan", "paleo"]
          }
        ]
      }
    },
    "troubleshooting": {
      "too_salty": [
        {
          "solution": "Add raw potato chunks",
          "instructions": "Cook for additional 15 minutes, then remove",
          "alternative": "Increase recipe volume with unsalted ingredients"
        }
      ],
      "too_spicy": [
        {
          "solution": "Add dairy or coconut milk",
          "instructions": "Gradually stir in until heat is manageable",
          "alternative": "Add sweetener to counterbalance"
        }
      ]
    },
    "techniques": {
      "fold_in": {
        "explanation": "Gently combine ingredients without losing air",
        "steps": [
          "Cut through center with spatula",
          "Scrape bottom and fold over top",
          "Rotate bowl and repeat"
        ],
        "video_ref": "folding_technique.mp4"
      }
    }
  }
}
```