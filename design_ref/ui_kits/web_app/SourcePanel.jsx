/* global React, Icon */

const SourcePanel = ({ source, onClose }) => {
  if (!source) {
    return (
      <aside className="panel">
        <div className="panel-empty">
          <div className="ico"><Icon name="book" size={22}/></div>
          <h4>No source open</h4>
          <p>Click any citation in the answer to read the cited passage in context.</p>
        </div>
      </aside>
    );
  }
  return (
    <aside className="panel">
      <div className="panel-hdr">
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
          <div style={{ flex: 1 }}>
            <div className="eyebrow">{source.court}</div>
            <h3>{source.title}</h3>
            <div className="ref">{source.cite}</div>
          </div>
          <button className="hdr-icon-btn" onClick={onClose} title="Close"><Icon name="close" size={16}/></button>
        </div>
        <div className="tags">
          {source.tags.map((t, i) => <span key={i} className="tag">{t}</span>)}
        </div>
        <div className="panel-actions">
          <button className="ai-action-btn"><Icon name="pin" size={13}/> Save to matter</button>
          <button className="ai-action-btn"><Icon name="external" size={13}/> Westlaw</button>
          <button className="ai-action-btn"><Icon name="copy" size={13}/> Cite</button>
        </div>
      </div>
      <div className="panel-body">
        {source.passages.map((p, i) => (
          <p key={i} className="para" dangerouslySetInnerHTML={{ __html: p }} />
        ))}
        <div className="pgnum">{source.pageRef}</div>
      </div>
    </aside>
  );
};

window.SourcePanel = SourcePanel;
