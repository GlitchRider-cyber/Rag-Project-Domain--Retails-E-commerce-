import React from 'react';

/**
 * CitationChip component for inline citations [1], [2], etc.
 */
export default function CitationChip({ index, chunkId, source, onClick }) {
  return (
    <button
      type="button"
      className="citation-chip"
      onClick={() => onClick(chunkId, source)}
      title={source ? `View source: ${source.section || source.doc_type}` : `View source [${index}]`}
    >
      [{index}]
    </button>
  );
}
