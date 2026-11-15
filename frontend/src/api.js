/**
 * API client for Aurelia & Co. RAG Assistant backend
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Send a chat message and stream tokens via Server-Sent Events (SSE).
 *
 * @param {string} sessionId - Chat session UUID
 * @param {string} message - User message
 * @param {object} callbacks - { onToken, onSources, onDone, onError }
 * @returns {AbortController} - To allow cancelling the request
 */
export function streamChatMessage(sessionId, message, { onToken, onSources, onDone, onError }) {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: message,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Chat request failed with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep the last partial line in buffer
        buffer = lines.pop() || '';

        let currentEvent = 'message';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            currentEvent = 'message';
            continue;
          }

          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.slice(6).trim();
          } else if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim();
            if (currentEvent === 'token') {
              if (onToken) onToken(dataStr);
            } else if (currentEvent === 'sources') {
              try {
                const parsed = JSON.parse(dataStr);
                if (onSources) onSources(parsed);
              } catch (e) {
                console.error('Failed to parse sources data', e, dataStr);
              }
            } else if (currentEvent === 'done') {
              if (onDone) onDone();
            } else if (currentEvent === 'error') {
              if (onError) onError(new Error(dataStr || 'Error from server stream'));
            }
          }
        }
      }

      if (onDone) onDone();
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Chat stream aborted by user');
      } else {
        console.error('SSE Stream error:', err);
        if (onError) onError(err);
      }
    }
  })();

  return controller;
}

/**
 * Fetch full content & metadata of a retrieved chunk
 */
export async function getSource(chunkId) {
  const res = await fetch(`${API_BASE}/sources/${chunkId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch source: ${res.statusText}`);
  }
  return await res.json();
}

/**
 * Submit thumbs up/down rating for an assistant message
 */
export async function sendFeedback(messageId, rating, comment = null) {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message_id: messageId,
      rating: rating,
      comment: comment,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to send feedback: ${res.statusText}`);
  }
  return await res.json();
}

/**
 * Backend health check
 */
export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return await res.json();
}
