import React, { useRef, useEffect, useState } from 'react';
import MessageBubble from './MessageBubble';

const STARTER_QUESTIONS = [
  'What materials do you use in your products?',
  "What's your return policy?",
  'Do you offer free shipping?',
  'Do you have any cashmere products?',
  'How do I care for silk garments?',
  'What sizes are available?',
];

/**
 * ChatWindow – the main scrollable chat container.
 */
export default function ChatWindow({
  messages,
  isLoading,
  error,
  onSendMessage,
  onCitationClick,
  onFeedback,
  onReset,
}) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const isEmpty = messages.length === 0;

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text || isLoading) return;
    setInputValue('');
    onSendMessage(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e);
    }
  };

  const handleStarterClick = (question) => {
    if (isLoading) return;
    onSendMessage(question);
  };

  return (
    <div className="chat-window">
      {/* Messages area */}
      <div className="messages-area" role="log" aria-live="polite" aria-label="Chat messages">
        {isEmpty ? (
          <div className="empty-state">
            <div className="empty-state-icon" aria-hidden="true">✦</div>
            <h2 className="empty-state-title">Hello, I'm Aurelia</h2>
            <p className="empty-state-subtitle">
              Your AI shopping assistant for Aurelia &amp; Co. Ask me anything about our
              products, policies, sizing, or care instructions.
            </p>
            <div className="starter-questions" role="list">
              {STARTER_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="starter-question-btn"
                  onClick={() => handleStarterClick(q)}
                  role="listitem"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onCitationClick={onCitationClick}
                onFeedback={onFeedback}
              />
            ))}

            {/* Loading dots when waiting for first token */}
            {isLoading && messages[messages.length - 1]?.content === '' && (
              <div className="loading-dots" aria-label="Thinking">
                <span /><span /><span />
              </div>
            )}
          </>
        )}

        {error && (
          <div className="chat-error" role="alert">
            ⚠ {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="input-area">
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            className="chat-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about products, shipping, returns…"
            rows={1}
            disabled={isLoading}
            aria-label="Chat message input"
          />
          <button
            type="submit"
            className="send-btn"
            disabled={isLoading || !inputValue.trim()}
            aria-label="Send message"
          >
            {isLoading ? (
              <span className="send-spinner" aria-hidden="true" />
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
                <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z" strokeLinejoin="round" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </form>

        {!isEmpty && (
          <button type="button" className="new-chat-btn" onClick={onReset}>
            New conversation
          </button>
        )}
      </div>
    </div>
  );
}

