/* global React, Icon */

const Sidebar = ({ matters, activeMatterId, onPick, onNewChat, recents }) => (
  <aside className="sb">
    <div className="sb-newchat" onClick={onNewChat}>
      <Icon name="plus" size={14} strokeWidth={2} />
      New research
      <span className="kbd">⌘N</span>
    </div>

    <div className="sb-section">
      <h4>Matters <span className="add" title="New matter"><Icon name="plus" size={12} strokeWidth={2}/></span></h4>
      {matters.map(m => (
        <div key={m.id}
          className={"sb-item" + (m.id === activeMatterId ? " active" : "")}
          onClick={() => onPick(m.id)}>
          <span className="dot" />
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.title}</span>
          <span className="meta">{m.count}</span>
        </div>
      ))}
    </div>

    <div className="sb-section">
      <h4>Recent threads</h4>
      {recents.map((r, i) => (
        <div key={i} className="sb-item">
          <Icon name="message" size={14} style={{ color: 'var(--fg3)' }} />
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r}</span>
        </div>
      ))}
    </div>

    <div className="sb-section">
      <h4>Library</h4>
      <div className="sb-item"><Icon name="book" size={14} style={{ color:'var(--fg3)' }}/> Saved authorities <span className="meta">214</span></div>
      <div className="sb-item"><Icon name="bookmark" size={14} style={{ color:'var(--fg3)' }}/> Saved searches <span className="meta">12</span></div>
      <div className="sb-item"><Icon name="file" size={14} style={{ color:'var(--fg3)' }}/> Templates <span className="meta">8</span></div>
    </div>

    <div className="sb-section" style={{ marginTop: 'auto' }}>
      <div className="sb-item"><Icon name="settings" size={14} style={{ color:'var(--fg3)' }}/> Workspace settings</div>
    </div>
  </aside>
);

window.Sidebar = Sidebar;
