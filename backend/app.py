from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate
from openai import OpenAI
import anthropic
import os
import time
import logging
import requests

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Initialize OpenAI client for OpenRouter
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Initialize Anthropic client
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Set up logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    generation_id = db.Column(db.String(50))
    tokens_prompt = db.Column(db.Integer)
    tokens_completion = db.Column(db.Integer)
    total_cost = db.Column(db.Float)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        model = request.json.get('model', 'claude-3-haiku-20240307')
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        new_user_message = ChatMessage(role='user', content=user_message)
        db.session.add(new_user_message)
        db.session.commit()

        chat_history = ChatMessage.query.order_by(ChatMessage.timestamp).all()
        
        if 'claude' in model:
            # Format messages for Anthropic API
            formatted_messages = []
            for msg in chat_history:
                if not formatted_messages or formatted_messages[-1]['role'] != msg.role:
                    formatted_messages.append({"role": msg.role, "content": msg.content})
                else:
                    formatted_messages[-1]['content'] += f"\n\n{msg.content}"
            
            # Ensure the last message is from the user
            if formatted_messages[-1]['role'] != 'user':
                formatted_messages.append({"role": "user", "content": user_message})
            
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                messages=formatted_messages,
                system="You are an AI assistant. Respond helpfully, but do not reproduce copyrighted material."
            )
            
            bot_message = response.content[0].text
            generation_id = response.id
            
            # Calculate cost based on the model
            input_cost, output_cost = get_claude_costs(model)
            total_cost = (response.usage.input_tokens / 1000000 * input_cost) + (response.usage.output_tokens / 1000000 * output_cost)
            
            stats = {
                'tokens_prompt': response.usage.input_tokens,
                'tokens_completion': response.usage.output_tokens,
                'total_cost': total_cost
            }
        else:
            # Use OpenRouter for other models
            messages = [{"role": msg.role, "content": msg.content} for msg in chat_history]
            messages.append({"role": "user", "content": user_message})
            messages.insert(0, {"role": "system", "content": "You are an AI assistant."})
            
            completion = openrouter_client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "AI Chatbot",
                },
                model=model,
                messages=messages,
                max_tokens=2000,
            )
            
            bot_message = completion.choices[0].message.content
            generation_id = completion.id

            time.sleep(2)

            try:
                stats_response = requests.get(
                    f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "AI Chatbot",
                    }
                )
                stats_response.raise_for_status()
                stats = stats_response.json()['data']
            except Exception as stats_error:
                logger.error(f"Error fetching generation stats: {str(stats_error)}")
                stats = {'tokens_prompt': None, 'tokens_completion': None, 'total_cost': None}

        new_message = ChatMessage(
            role='assistant',
            content=bot_message,
            generation_id=generation_id,
            tokens_prompt=stats['tokens_prompt'],
            tokens_completion=stats['tokens_completion'],
            total_cost=stats['total_cost']
        )
        db.session.add(new_message)
        db.session.commit()
        
        return jsonify({
            "message": bot_message,
            "generation_stats": stats
        })
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

def get_claude_costs(model):
    costs = {
        'claude-3-5-sonnet-20240620': (3.00, 15.00),
        'claude-3-opus-20240229': (15.00, 75.00),
        'claude-3-sonnet-20240229': (3.00, 15.00),
        'claude-3-haiku-20240307': (0.25, 1.25)
    }
    return costs.get(model, (0, 0))  # Default to (0, 0) if model not found

@app.route('/api/chat_history', methods=['GET'])
def get_chat_history():
    messages = ChatMessage.query.order_by(ChatMessage.timestamp).all()
    return jsonify([
        {
            "role": msg.role,
            "content": msg.content,
            "tokens_prompt": msg.tokens_prompt,
            "tokens_completion": msg.tokens_completion,
            "total_cost": msg.total_cost
        }
        for msg in messages
    ])

@app.route('/api/chat_history', methods=['POST'])
def save_chat_message():
    data = request.json
    new_message = ChatMessage(role=data['role'], content=data['content'])
    db.session.add(new_message)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/chat_history/reset', methods=['POST'])
def reset_chat_history():
    try:
        ChatMessage.query.delete()
        db.session.commit()
        return jsonify({"status": "success", "message": "Chat history reset successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

def clear_database():
    with app.app_context():
        db.drop_all()
        db.create_all()
    print("Database cleared and recreated.")

if __name__ == '__main__':
    clear_database()
    app.run(port=5000)