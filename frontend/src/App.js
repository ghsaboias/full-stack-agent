import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FaCopy, FaImage, FaTimes } from 'react-icons/fa';
// Add the following import
import ReactMarkdown from 'react-markdown';

function App() {
  const [message, setMessage] = useState('');
  const [chat, setChat] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const chatContainerRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchChatHistory();
  }, []);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chat]);

  const fetchChatHistory = async () => {
    try {
      const response = await fetch('/api/chat_history');
      const data = await response.json();
      setChat(data.map(msg => ({
        role: msg.role,
        content: msg.content,
        tokens_prompt: msg.tokens_prompt,
        tokens_completion: msg.tokens_completion,
        total_cost: msg.total_cost,
        imageUrl: msg.image_data  // Add this line
      })));
    } catch (error) {
      console.error('Error fetching chat history:', error);
    }
  };

  const sendMessage = async () => {
    if (!message.trim() && !imageUrl) return;
    setIsLoading(true);
    const userMessage = message;
    setChat(prevChat => [...prevChat, { role: 'user', content: userMessage, imageUrl }]);
    setMessage('');
    setImageUrl('');
    try {
      console.log("Sending image data:", imageUrl ? imageUrl.substring(0, 50) + "..." : "No image");
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ message: userMessage, image_data: imageUrl })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }
      if (data.error) {
        throw new Error(data.error);
      }
      const botResponse = {
        role: 'assistant',
        content: data.message,
        tokens_prompt: data.generation_stats.tokens_prompt,
        tokens_completion: data.generation_stats.tokens_completion,
        total_cost: data.generation_stats.total_cost
      };
      setChat(prevChat => [...prevChat, botResponse]);
    } catch (error) {
      console.error('Error:', error);
      let errorMessage = error.message || 'An unexpected error occurred';
      setChat(prevChat => [...prevChat, { role: 'assistant', content: `Error: ${errorMessage}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64Data = reader.result;
        setImageUrl(base64Data);
        console.log("Image encoded as base64:", base64Data.substring(0, 50) + "...");
      };
      reader.readAsDataURL(file);
    }
  };

  const removeImage = () => {
    setImageUrl('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetChat = async () => {
    try {
      const response = await fetch('/api/chat_history/reset', { method: 'POST' });
      const data = await response.json();
      if (data.status === 'success') {
        setChat([]);
        console.log('Chat history reset successfully');
      } else {
        console.error('Error resetting chat history:', data.message);
      }
    } catch (error) {
      console.error('Error resetting chat history:', error);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      alert('Code copied to clipboard!');
    }).catch(err => {
      console.error('Failed to copy: ', err);
    });
  };

  const renderMessage = (message) => {
    const codeBlockRegex = /```(\w+)\n([\s\S]*?)```/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    if (message.imageUrl) {
      parts.push(
        <div className="message-image" key="image">
          <img src={message.imageUrl} alt="User uploaded" />
        </div>
      );
    }

    while ((match = codeBlockRegex.exec(message.content)) !== null) {
      if (match.index > lastIndex) {
        parts.push(
          <ReactMarkdown key={`md-${match.index}`}>
            {message.content.slice(lastIndex, match.index)}
          </ReactMarkdown>
        );
      }
      const language = match[1];
      const code = match[2].trim();
      parts.push(
        <div className="code-block" key={`code-${match.index}`}>
          <div className="code-header">
            <span>{language}</span>
            <button onClick={() => copyToClipboard(code)} className="copy-button">
              <FaCopy /> Copy
            </button>
          </div>
          <SyntaxHighlighter language={language} style={vscDarkPlus} customStyle={{ margin: 0 }}>
            {code}
          </SyntaxHighlighter>
        </div>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < message.content.length) {
      parts.push(
        <ReactMarkdown key={`md-last`}>
          {message.content.slice(lastIndex)}
        </ReactMarkdown>
      );
    }

    return parts;
  };

  return (
    <div className="container">
      <h1 className="header">AI Chatbot</h1>
      <div className={`chat-container ${chat.length > 0 ? 'visible' : ''}`} ref={chatContainerRef}>
        {chat.map((message, index) => (
          <div key={index} className={`message ${message.role}-message`}>
            <div className="message-content">{renderMessage(message)}</div>
            {message.role === 'assistant' && message.tokens_prompt && (
              <div className="message-stats">
                <p>Prompt Tokens: {message.tokens_prompt}</p>
                <p>Completion Tokens: {message.tokens_completion}</p>
                <p>Total Cost: {message.total_cost !== null ? `$${message.total_cost.toFixed(6)}` : 'N/A'}</p>
              </div>
            )}
          </div>
        ))}
        {isLoading && <div className="message bot-message loading">Bot is thinking...</div>}
      </div>
      <div className="input-container">
        <input 
          className="input"
          type="text" 
          value={message} 
          onChange={e => setMessage(e.target.value)} 
          onKeyDown={handleKeyPress}
          placeholder="Type your message..."
        />
        <label className="image-upload-label">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            style={{ display: 'none' }}
            ref={fileInputRef}
          />
          <FaImage />
        </label>
        <button 
          className="send-button" 
          onClick={sendMessage} 
          disabled={isLoading}
        >
          Send
        </button>
      </div>
      {imageUrl && (
        <div className="image-preview">
          <img src={imageUrl} alt="Preview" />
          <button onClick={removeImage} className="remove-image">
            <FaTimes />
          </button>
        </div>
      )}
      <button 
        className="reset-button" 
        onClick={resetChat}
        disabled={isLoading}
      >
        Reset Chat
      </button>
    </div>
  );
}

export default App;