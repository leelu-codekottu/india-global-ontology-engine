import React, { useState, useRef, useEffect } from 'react';
import { askQuestion, flagClaim } from '../api';
import ResponsePanel from '../components/ResponsePanel';

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activePayload, setActivePayload] = useState(null); // latest full backend response
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const suggestedQuestions = [
    'How will Iran–USA tensions affect India\'s oil imports and inflation?',
    'What happens to India if the Strait of Hormuz is blockaded?',
    'How does crude oil price impact India\'s industrial production?',
    'What are India\'s alternative energy import routes?',
  ];

  const handleSend = async (text) => {
    const question = text || input.trim();
    if (!question || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: question }]);
    setLoading(true);
    setActivePayload(null);

    try {
      const result = await askQuestion(question);
      setActivePayload(result);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: result.answer || 'No answer generated.',
          payload: result,
        },
      ]);
    } catch (err) {
      setActivePayload(null);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠ Error: ${err.message}. Ensure the FastAPI server is running on port 8000.`,
        },
      ]);
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFlag = async (source, relationship, target, reason) => {
    await flagClaim(source, relationship, target, reason);
  };

  const showWelcome = messages.length === 0 && !loading;

  return (
    <div className="chat-container">
      {/* Welcome + suggested questions */}
      {showWelcome && (
        <div className="chat-welcome">
          <div className="chat-welcome-icon">◈</div>
          <h2 className="chat-welcome-title">India Global Ontology Engine</h2>
          <p className="chat-welcome-desc">
            Ask about geopolitical impacts on India — energy security, trade dynamics, inflation drivers, and strategic risks.
          </p>
          <div className="chat-suggestions">
            {suggestedQuestions.map((q, i) => (
              <button key={i} className="btn btn-ghost chat-suggestion-btn" onClick={() => handleSend(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages feed */}
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.role === 'user' ? (
              <div className="message-bubble">
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
              </div>
            ) : msg.payload ? (
              /* Full response panel for assistant messages with payload */
              <div className="message-response-panel">
                <ResponsePanel payload={msg.payload} loading={false} onFlag={handleFlag} />
              </div>
            ) : (
              <div className="message-bubble">
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
              </div>
            )}
            <div className="message-meta">
              {msg.role === 'assistant' ? 'Ontology Engine' : 'You'} •{' '}
              {new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        ))}

        {/* Loading state — shows graph build animation */}
        {loading && (
          <div className="chat-message assistant">
            <div className="message-response-panel">
              <ResponsePanel payload={null} loading={true} onFlag={handleFlag} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Ask about India's geopolitical landscape..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            aria-label="Type your question"
          />
          <button
            className="chat-send-btn"
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            title="Send"
            aria-label="Send question"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}
