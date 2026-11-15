import { useState, useCallback } from 'react';
import { useChat } from './hooks/useChat';
import ChatWindow from './components/ChatWindow';
import SourcePanel from './components/SourcePanel';
import { getSource } from './api';
import './App.css';

export default function App() {
  const { messages, isLoading, error, sendMessage, handleFeedback, resetChat } = useChat();
  const [activeSource, setActiveSource] = useState(null);
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);

  const handleCitationClick = useCallback(async (chunkId, sourcePreview) => {
    // Show what we already have immediately
    if (sourcePreview) {
      setActiveSource(sourcePreview);
      setSourcePanelOpen(true);
    }
    // Then fetch the full content
    if (chunkId !== undefined && chunkId !== null) {
      try {
        const full = await getSource(chunkId);
        setActiveSource(full);
        setSourcePanelOpen(true);
      } catch (err) {
        console.error('Could not fetch source details:', err);
      }
    }
  }, []);

  const handleCloseSourcePanel = useCallback(() => {
    setSourcePanelOpen(false);
    setTimeout(() => setActiveSource(null), 300);
  }, []);

  const handleReset = useCallback(() => {
    resetChat();
    setActiveSource(null);
    setSourcePanelOpen(false);
  }, [resetChat]);

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand-logo" aria-label="Aurelia & Co.">
            <span className="brand-mark">✦</span>
            <div className="brand-text">
              <span className="brand-name">Aurelia &amp; Co.</span>
              <span className="brand-tagline">AI Shopping Assistant</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className={`app-main ${sourcePanelOpen ? 'panel-open' : ''}`}>
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          error={error}
          onSendMessage={sendMessage}
          onCitationClick={handleCitationClick}
          onFeedback={handleFeedback}
          onReset={handleReset}
        />

        {/* Source panel */}
        <div className={`source-panel-container ${sourcePanelOpen ? 'open' : ''}`}>
          <SourcePanel
            source={activeSource}
            onClose={handleCloseSourcePanel}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <span>Answers are grounded in Aurelia &amp; Co. knowledge base only.</span>
        <span className="footer-sep">·</span>
        <a href="mailto:support@aureliaandco.com">support@aureliaandco.com</a>
      </footer>
    </div>
  );
}
