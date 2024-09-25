from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_migrate import Migrate
from openai import OpenAI
import anthropic
import os
import time
import logging
import requests
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

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
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # If no conversation_id is provided, create a new conversation
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
                        "media_type": "image/png",  # Adjust if needed
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
            
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                messages=formatted_messages,
                system="You are an AI assistant."
            )
            
            bot_message = response.content[0].text
            generation_id = response.id
            
            input_cost, output_cost = get_claude_costs(model)
            total_cost = (response.usage.input_tokens / 1000000 * input_cost) + (response.usage.output_tokens / 1000000 * output_cost)
            
            stats = {
                'tokens_prompt': response.usage.input_tokens,
                'tokens_completion': response.usage.output_tokens,
                'total_cost': total_cost
            }
        else:
            # Use OpenRouter for other models (no image support)
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
        
        return jsonify({
            "message": bot_message,
            "generation_stats": stats
        })
    except Exception as e:
        db.session.rollback()  # Rollback the session in case of any error
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

def get_claude_costs(model):
    costs = {
        'claude-3-5-sonnet-20240620': (3.00, 15.00),
        'claude-3-opus-20240229': (15.00, 75.00),
        'claude-3-sonnet-20240229': (3.00, 15.00),
        'claude-3-haiku-20240307': (0.25, 1.25)
    }
    return costs.get(model, (0, 0))

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
        if conversation_id:
            ChatMessage.query.filter_by(conversation_id=conversation_id).delete()
        else:
            ChatMessage.query.delete()
        db.session.commit()
        return jsonify({"status": "success", "message": "Chat history reset successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

# Add the new functions for silver data analysis
def fetch_silver_data(start_date, end_date):
    silver = yf.Ticker("SI=F")
    data = silver.history(start=start_date, end=end_date)
    return data['Close']

def calculate_daily_changes(prices):
    return prices.pct_change().dropna()

def compare_todays_change(changes):
    today_change = changes.iloc[-1]
    historical_changes = changes.iloc[:-1]
    
    percentile = (historical_changes < today_change).mean() * 100
    
    return today_change, percentile

def generate_histogram_data(changes):
    hist, bin_edges = np.histogram(changes.iloc[:-1], bins=50)
    return {
        "counts": hist.tolist(),
        "bin_edges": bin_edges.tolist(),
        "today_change": float(changes.iloc[-1])
    }

# Add a new route for silver data analysis
@app.route('/api/silver_analysis', methods=['GET'])
def silver_analysis():
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365*30)
        
        prices = fetch_silver_data(start_date, end_date)
        print(prices)
        changes = calculate_daily_changes(prices)
        
        today_change, percentile = compare_todays_change(changes)
        
        histogram_data = generate_histogram_data(changes)
        
        return jsonify({
            "today_change": float(today_change),
            "percentile": float(percentile),
            "histogram_data": histogram_data
        })
    except Exception as e:
        logger.error(f"Error in silver analysis: {str(e)}", exc_info=True)
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.before_first_request
def initialize_data():
    with app.app_context():
        # Create a default conversation if it doesn't exist
        default_conversation = Conversation.query.filter_by(name="Default Conversation").first()
        if not default_conversation:
            default_conversation = Conversation(name="Default Conversation")
            db.session.add(default_conversation)
            db.session.commit()

        # Assign the default conversation to all messages without a conversation
        ChatMessage.query.filter_by(conversation_id=None).update({ChatMessage.conversation_id: default_conversation.id})
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5000)