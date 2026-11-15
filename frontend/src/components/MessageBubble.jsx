import React from 'react';
import CitationChip from './CitationChip';

/**
 * Parse assistant text and replace [1], [2], etc. with CitationChip components.
 */
function parseMessageContent(text, sources, onCitationClick) {
  if (!sources || sources.length === 0) {
    return <span>{text}</span>;
  }

  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, idx) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const citationIndex = parseInt(match[1], 10);
      const source = sources[citationIndex - 1];
      return (
        <CitationChip
          key={idx}
          index={citationIndex}
          chunkId={source?.chunk_id}
          source={source}
          onClick={onCitationClick}
        />
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

/**
 * MessageBubble – renders a single chat message (user or assistant).
 */
export default function MessageBubble({ message, onCitationClick, onFeedback }) {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;

  return (
    <div className={`message-bubble-wrapper ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="assistant-avatar" aria-hidden="true">
          A
        </div>
      )}

      <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        {/* Message text */}
        <div className="message-text">
          {isUser ? (
            message.content
          ) : (
            <>
              {parseMessageContent(
                message.content,
                message.sources,
                onCitationClick
              )}
              {isStreaming && (
                <span className="streaming-cursor" aria-label="Typing" />
              )}
            </>
          )}
        </div>

        {/* Citation list under assistant messages */}
        {!isUser && message.sources && message.sources.length > 0 && !isStreaming && (
          <div className="message-citations">
            {message.sources.map((src, idx) => (
              <CitationChip
                key={src.chunk_id || idx}
                index={idx + 1}
                chunkId={src.chunk_id}
                source={src}
                onClick={onCitationClick}
              />
            ))}
          </div>
        )}

        {/* Feedback buttons for assistant messages */}
        {!isUser && !isStreaming && message.message_id && (
          <div className="message-feedback">
            <button
              type="button"
              className={`feedback-btn ${message.feedback === 1 ? 'active-positive' : ''}`}
              onClick={() => onFeedback && onFeedback(message.message_id, 1)}
              aria-label="Helpful"
              title="Helpful"
            >
              👍
            </button>
            <button
              type="button"
              className={`feedback-btn ${message.feedback === -1 ? 'active-negative' : ''}`}
              onClick={() => onFeedback && onFeedback(message.message_id, -1)}
              aria-label="Not helpful"
              title="Not helpful"
            >
              👎
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

