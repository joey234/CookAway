# CookAway - Voice-Activated Cooking Assistant

A web application that helps users cook by providing voice-activated recipe guidance, step-by-step instructions, and real-time assistance.

## Features

- Recipe parsing and structuring
- Interactive voice Q&A
- Step-by-step voice guidance
- Smart timers and reminders
- Real-time food assessment via camera
- Recipe search and suggestions

## Tech Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Python
- AI/ML: Mistral AI for NLP, ElevenLabs for TTS
- Additional: Web Speech API, HTML5 Camera API

## Setup Instructions

### Prerequisites

- Node.js (v18 or later)
- Python 3.9 or later
- API keys for:
  - Mistral AI
  - ElevenLabs

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a .env file and add your API keys:
   ```
   MISTRAL_API_KEY=your_mistral_api_key_here
   ELEVEN_LABS_API_KEY=your_eleven_labs_api_key_here
   ```

5. Start the backend server:
   ```bash
   python src/main.py
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

## Usage

1. Open your browser and navigate to `http://localhost:5173`
2. Input a recipe (text or URL)
3. Follow the voice-guided cooking instructions
4. Use voice commands for navigation and questions

## Development

- Backend API runs on `http://localhost:8000`
- Frontend dev server runs on `http://localhost:5173`
- API documentation available at `http://localhost:8000/docs`

## License

MIT 