import { useState, useRef, useCallback, useEffect } from 'react';
import { streamChatMessage, sendFeedback } from '../api';

function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function useChat() {
  const [sessionId, setSessionId] = useState(() => {
    const saved = localStorage.getItem('aurelia_chat_session_id');
    if (saved) return saved;
    const fresh = generateUUID();
    localStorage.setItem('aurelia_chat_session_id', fresh);
    return fresh;
  });

  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  // Send message handler
  const sendMessage = useCallback(
    async (text) => {
      const userText = text.trim();
      if (!userText || isLoading) return;

      setError(null);
      setIsLoading(true);

      const userMsgId = `user-${Date.now()}`;
      const assistantMsgId = `assistant-${Date.now()}`;

      // Append user message immediately
      setMessages((prev) => [
        ...prev,
        {
          id: userMsgId,
          role: 'user',
          content: userText,
          created_at: new Date().toISOString(),
        },
        {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          sources: [],
          message_id: null,
          isStreaming: true,
          created_at: new Date().toISOString(),
        },
      ]);

      abortControllerRef.current = streamChatMessage(sessionId, userText, {
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMsgId) {
                return { ...msg, content: msg.content + token };
              }
              return msg;
            })
          );
        },
        onSources: (data) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMsgId) {
                return {
                  ...msg,
                  sources: data.sources || [],
                  message_id: data.message_id || null,
                };
              }
              return msg;
            })
          );
        },
        onDone: () => {
          setIsLoading(false);
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMsgId) {
                return { ...msg, isStreaming: false };
              }
              return msg;
            })
          );
        },
        onError: (err) => {
          setIsLoading(false);
          setError(err.message || 'Error receiving assistant response');
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === assistantMsgId) {
                const fallback = msg.content
                  ? msg.content + '\n\n*(Connection interrupted)*'
                  : 'I apologize, but I encountered an issue retrieving information. Please try again.';
                return { ...msg, content: fallback, isStreaming: false };
              }
              return msg;
            })
          );
        },
      });
    },
    [sessionId, isLoading]
  );

  // Submit feedback
  const handleFeedback = useCallback(async (messageId, rating, comment = null) => {
    try {
      await sendFeedback(messageId, rating, comment);
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.message_id === messageId) {
            return { ...msg, feedback: rating };
          }
          return msg;
        })
      );
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  }, []);

  // Clear chat
  const resetChat = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const freshId = generateUUID();
    localStorage.setItem('aurelia_chat_session_id', freshId);
    setSessionId(freshId);
    setMessages([]);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    sessionId,
    messages,
    isLoading,
    error,
    sendMessage,
    handleFeedback,
    resetChat,
  };
}
