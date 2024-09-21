# AI Chatbot

An AI-powered chatbot using OpenRouter's API with a Flask backend and React frontend.

## Features

- Real-time chat interface
- Code syntax highlighting
- Chat history persistence
- Token usage and cost tracking
- Chat history reset

## Prerequisites

- Python 3.7+
- Node.js 12+
- npm or yarn

## Setup

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS and Linux: `source venv/bin/activate`

4. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

5. Set up your environment variables:
   Create a `.env` file in the backend directory and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_api_key_here
   ```

6. Initialize the database:
   ```
   flask db init
   flask db migrate
   flask db upgrade
   ```

7. Run the Flask server:
   ```
   python app.py
   ```

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install the required packages:
   ```
   npm install
   ```

3. Start the React development server:
   ```
   npm start
   ```

## Usage

1. Open your web browser and go to `http://localhost:3000`
2. Type your message in the input field and press Enter or click the Send button
3. The AI will respond, and the conversation will be displayed in the chat window
4. You can reset the chat history using the Reset Chat button

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).