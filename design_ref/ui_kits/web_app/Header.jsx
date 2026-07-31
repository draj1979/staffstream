/* global React, Icon */

const Header = ({ matter }) => (
  <header className="hdr">
    <div className="logo">
      <img src="../../assets/logo-wordmark.svg" alt="LawGIQ" />
    </div>
    <div className="matter-switch">
      <Icon name="briefcase" size={14} />
      <span>{matter.title}</span>
      <span className="ref">{matter.ref}</span>
      <Icon name="chevDown" size={14} style={{ color: 'var(--fg3)' }} />
    </div>
    <div className="search">
      <Icon name="search" size={15} />
      <input placeholder="Search across all matters, cases, statutes…" />
      <span className="kbd">⌘K</span>
    </div>
    <div className="hdr-right">
      <button className="hdr-icon-btn" title="Library"><Icon name="book" size={18} /></button>
      <button className="hdr-icon-btn" title="History"><Icon name="history" size={18} /></button>
      <button className="hdr-icon-btn" title="Notifications"><Icon name="bell" size={18} /></button>
      <div className="avatar" title="Sara Chen">SC</div>
    </div>
  </header>
);

window.Header = Header;
