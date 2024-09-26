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
import yfinance as yf

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Model definitions
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    generation_id = db.Column(db.String(50))
    tokens_prompt = db.Column(db.Integer)
    tokens_completion = db.Column(db.Integer)
    total_cost = db.Column(db.Float)
    image_data = db.Column(db.Text)

# Tools
tools = [
    {
        "name": "fetch_stock_data",
        "description": "A function that fetches the current stock price for a given ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol."
                }
            },
            "required": ["ticker"]
        }
    }
]

# Helper functions
def get_claude_costs(model):
    costs = {
        'claude-3-5-sonnet-20240620': (3.00, 15.00),
        'claude-3-opus-20240229': (15.00, 75.00),
        'claude-3-sonnet-20240229': (3.00, 15.00),
        'claude-3-haiku-20240307': (0.25, 1.25)
    }
    return costs.get(model, (0, 0))

def fetch_stock_data(ticker): 
    try:
        stock = yf.Ticker(ticker)
        stock_info = stock.info
        return f"Here's the full stock information for {ticker}:\n{stock_info}"
    except Exception as e:
        return f"Error fetching data for {ticker}: {str(e)}"

def process_tool_call(tool_name, tool_input):
    if tool_name == "fetch_stock_data":
        ticker = tool_input["ticker"]
        return fetch_stock_data(ticker)
    else:
        return f"Unsupported tool: {tool_name}"
    
ALLOWED_MODELS = [
    'claude-3-haiku-20240307',
    'claude-3-5-sonnet-20240620',
    'claude-3-opus-20240229',
    'openai/gpt-4o-2024-08-06',
    'openai/gpt-4o-mini-2024-07-18'
]

# Routes
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    conversations = Conversation.query.order_by(Conversation.created_at.desc()).all()
    return jsonify([{"id": conv.id, "name": conv.name} for conv in conversations])

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    new_conversation = Conversation(name=f"Conversation {Conversation.query.count() + 1}")
    db.session.add(new_conversation)
    db.session.commit()
    return jsonify({"id": new_conversation.id, "name": new_conversation.name})

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    ChatMessage.query.filter_by(conversation_id=conversation_id).delete()
    db.session.delete(conversation)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        model = request.json.get('model', 'claude-3-haiku-20240307')
        image_data = request.json.get('image_data')
        conversation_id = request.json.get('conversation_id')
        generation_id = None
        
        if model not in ALLOWED_MODELS:
            return jsonify({"error": "Invalid model selected"}), 400

        print(f"Received request - Message: {user_message}, Model: {model}, Conversation ID: {conversation_id}")
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        if not conversation_id:
            new_conversation = Conversation(name=f"Conversation {Conversation.query.count() + 1}")
            db.session.add(new_conversation)
            db.session.commit()
            conversation_id = new_conversation.id

        new_user_message = ChatMessage(
            conversation_id=conversation_id,
            role='user',
            content=user_message or "",
            image_data=image_data
        )
        db.session.add(new_user_message)
        db.session.commit()

        chat_history = ChatMessage.query.filter_by(conversation_id=conversation_id).order_by(ChatMessage.timestamp).all()
        
        if 'claude' in model:
            formatted_messages = []
            for msg in chat_history:
                if not formatted_messages or formatted_messages[-1]['role'] != msg.role:
                    formatted_messages.append({"role": msg.role, "content": msg.content})
                else:
                    formatted_messages[-1]['content'] += f"\n\n{msg.content}"
            
            if image_data:
                image_content = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data.split(',')[1] if ',' in image_data else image_data,
                    },
                }
                
                if formatted_messages[-1]['role'] == 'user':
                    if isinstance(formatted_messages[-1]['content'], str):
                        formatted_messages[-1]['content'] = [{"type": "text", "text": formatted_messages[-1]['content']}]
                    formatted_messages[-1]['content'].append(image_content)
                else:
                    formatted_messages.append({"role": "user", "content": [image_content]})
                
                if user_message:
                    formatted_messages[-1]['content'].append({"type": "text", "text": user_message})
            
            print(f"Sending request to Claude API with {len(formatted_messages)} messages")
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                messages=formatted_messages,
                tools=tools
            )
            print(f"Claude response: {response}")

            if response.stop_reason == 'tool_use':
                tool_use = next((block for block in response.content if block.type == "tool_use"), None)
                if tool_use:
                    tool_name = tool_use.name
                    tool_input = tool_use.input

                    tool_result = process_tool_call(tool_name, tool_input)
                    
                    follow_up_response = anthropic_client.messages.create(
                        model=model,
                        max_tokens=2000,
                        messages=[
                            *formatted_messages,
                            {"role": "assistant", "content": response.content},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_use.id,
                                    "content": tool_result
                                    }
                                ]
                            }
                        ],
                        system="You are an AI assistant. Provide a concise and informative response based on the provided information.",
                        tools=tools
                    )
                    
                    bot_message = follow_up_response.content[0].text + "\n"
            else:
                bot_message = response.content[0].text + "\n"
            bot_message = bot_message.strip()

            print(f"Calculating costs for model: {model}")
            input_cost, output_cost = get_claude_costs(model)
            total_cost = (response.usage.input_tokens / 1000000 * input_cost) + (response.usage.output_tokens / 1000000 * output_cost)
            
            stats = {
                'tokens_prompt': response.usage.input_tokens,
                'tokens_completion': response.usage.output_tokens,
                'total_cost': total_cost
            }
            print(f"Generation stats: {stats}")
        else:
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

        print(f"Saving new message to database: {bot_message[:50]}...")
        new_message = ChatMessage(
            conversation_id=conversation_id,
            role='assistant',
            content=bot_message,
            generation_id=generation_id,
            tokens_prompt=stats['tokens_prompt'],
            tokens_completion=stats['tokens_completion'],
            total_cost=stats['total_cost']
        )
        db.session.add(new_message)
        db.session.commit()
        
        print("Returning response to client")
        return jsonify({
            "message": bot_message,
            "generation_stats": stats
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/api/chat_history/<int:conversation_id>', methods=['GET'])
def get_chat_history(conversation_id):
    messages = ChatMessage.query.filter_by(conversation_id=conversation_id).order_by(ChatMessage.timestamp).all()
    return jsonify([
        {
            "role": msg.role,
            "content": msg.content,
            "tokens_prompt": msg.tokens_prompt,
            "tokens_completion": msg.tokens_completion,
            "total_cost": msg.total_cost,
            "image_data": msg.image_data
        }
        for msg in messages
    ])

@app.route('/api/chat_history/reset', methods=['POST'])
def reset_chat_history():
    try:
        conversation_id = request.json.get('conversation_id')
        if not conversation_id:
            return jsonify({"status": "error", "message": "Conversation ID is required"}), 400

        print(f"Resetting chat history for conversation ID: {conversation_id}")
        ChatMessage.query.filter_by(conversation_id=conversation_id).delete()
        db.session.commit()
        return jsonify({"status": "success", "message": "Chat history reset successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.before_first_request
def initialize_data():
    with app.app_context():
        default_conversation = Conversation.query.filter_by(name="Default Conversation").first()
        if not default_conversation:
            default_conversation = Conversation(name="Default Conversation")
            db.session.add(default_conversation)
            db.session.commit()

        ChatMessage.query.filter_by(conversation_id=None).update({ChatMessage.conversation_id: default_conversation.id})
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5000)