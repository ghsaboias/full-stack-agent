import React, { useState } from 'react';

const styles = {
  container: {
    maxWidth: '800px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: 'Arial, sans-serif',
    backgroundColor: '#f5f5f5',
    minHeight: '100vh',
  },
  header: {
    color: '#333',
    borderBottom: '2px solid #ddd',
    paddingBottom: '10px',
    marginBottom: '20px',
  },
  chatContainer: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '20px',
    marginBottom: '20px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  message: {
    marginBottom: '10px',
    padding: '10px',
    borderRadius: '4px',
  },
  userMessage: {
    backgroundColor: '#e1f5fe',
    textAlign: 'right',
  },
  botMessage: {
    backgroundColor: '#f0f4c3',
  },
  input: {
    width: '100%',
    padding: '10px',
    marginBottom: '10px',
    borderRadius: '4px',
    border: '1px solid #ddd',
  },
  button: {
    padding: '10px 20px',
    backgroundColor: '#4CAF50',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    marginRight: '10px',
  },
  counterContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: '20px',
  },
  counterButton: {
    padding: '5px 15px',
    fontSize: '18px',
    margin: '0 10px',
  },
};

function App() {
  const [message, setMessage] = useState('');
  const [chat, setChat] = useState([]);
  const [counter, setCounter] = useState(0);

  const sendMessage = async () => {
    if (!message.trim()) return;
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ message })
    });
    const data = await response.json();
    setChat([...chat, { user: message, bot: data.choices[0].message.content }]);
    setMessage('');
  };

  const increment = async () => {
    const response = await fetch('/api/counter/increment', { method: 'POST' });
    const data = await response.json();
    setCounter(data.counter);
  };

  const decrement = async () => {
    const response = await fetch('/api/counter/decrement', { method: 'POST' });
    const data = await response.json();
    setCounter(data.counter);
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>LLM Chatbot</h1>
      <div style={styles.chatContainer}>
        {chat.map((c, index) => (
          <div key={index}>
            <p style={{...styles.message, ...styles.userMessage}}><strong>You:</strong> {c.user}</p>
            <p style={{...styles.message, ...styles.botMessage}}><strong>Bot:</strong> {c.bot}</p>
          </div>
        ))}
      </div>
      <input 
        style={styles.input}
        type="text" 
        value={message} 
        onChange={e => setMessage(e.target.value)} 
        placeholder="Type your message..."
      />
      <button style={styles.button} onClick={sendMessage}>Send</button>
      <div style={styles.counterContainer}>
        <button style={{...styles.button, ...styles.counterButton}} onClick={decrement}>-</button>
        <h2>Counter: {counter}</h2>
        <button style={{...styles.button, ...styles.counterButton}} onClick={increment}>+</button>
      </div>
    </div>
  );
}

export default App;