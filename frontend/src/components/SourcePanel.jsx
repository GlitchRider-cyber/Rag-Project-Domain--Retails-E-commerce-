import React from 'react';
import ProductCard from './ProductCard';

/**
 * SourcePanel – slide-in side panel showing full source passage details.
 */
export default function SourcePanel({ source, onClose }) {
  if (!source) return null;

  const isProduct = source.doc_type === 'product';

  return (
    <aside className="source-panel" role="complementary" aria-label="Source passage">
      <div className="source-panel-header">
        <div className="source-panel-title-row">
          <span className={`doc-type-badge doc-type-${source.doc_type || 'faq'}`}>
            {source.doc_type || 'source'}
          </span>
          <h3 className="source-panel-title">
            {source.section || 'Source Passage'}
          </h3>
        </div>
        <button
          className="source-panel-close"
          onClick={onClose}
          aria-label="Close source panel"
          type="button"
        >
          ✕
        </button>
      </div>

      <div className="source-panel-body">
        {isProduct && source.metadata && (
          <ProductCard
            metadata={source.metadata}
            name={source.section}
          />
        )}

        <div className="source-panel-content">
          <p className="source-panel-label">Passage</p>
          <div className="source-panel-text">
            {source.content}
          </div>
        </div>

        {source.score !== undefined && (
          <div className="source-panel-score">
            Relevance score: <strong>{(source.score * 100).toFixed(1)}%</strong>
          </div>
        )}
      </div>
    </aside>
  );
}

