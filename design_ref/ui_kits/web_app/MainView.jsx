/* global React, Icon */
const { useState, useRef, useEffect } = React;

const Cite = ({ id, label, active, onClick }) => (
  <span className={"cite" + (active ? " active" : "")} onClick={() => onClick(id)}>{label}</span>
);

const AuthorityRow = ({ a, active, onPick, n }) => (
  <div className={"authority-row" + (active ? " active" : "")} onClick={() => onPick(a.id)}>
    <div className="num">{n}</div>
    <div className="body">
      <div className="ttl">{a.title}</div>
      <div className="sub">{a.cite} · {a.court}</div>
    </div>
    <span className={"status status-" + a.statusClass}><span className="d"/>{a.statusLabel}</span>
  </div>
);

const UserMsg = ({ text }) => (
  <div className="msg-user">
    <div className="who">Sara · 11:42</div>
    {text}
  </div>
);

const AiAnswer = ({ openCite, activeCiteId, authorities, openAuthority, activeAuthority }) => (
  <div className="msg-ai">
    <div className="who">
      <span className="glyph">§</span>
      LawGIQ · 4.2s · 12 sources
    </div>
    <h3>California recognizes negligence per se for OSHA violations — with limits.</h3>
    <p>
      Under <Cite id="c1" label="Cal. Civ. Code § 1714(a)" active={activeCiteId==='c1'} onClick={openCite}/>, every person owes a duty of ordinary care.
      The doctrine of negligence <em>per se</em> in California permits a presumption of negligence where
      the defendant violates a statute, the violation proximately caused the injury, and the plaintiff is within
      the class the statute was intended to protect <Cite id="c2" label="Evid. Code § 669" active={activeCiteId==='c2'} onClick={openCite}/>.
    </p>
    <p>
      Federal OSHA standards apply through Cal/OSHA's state plan. The Court of Appeal in
      {' '}<Cite id="c3" label="Elsner v. Uveges" active={activeCiteId==='c3'} onClick={openCite}/> held that Cal/OSHA regulations may be used to establish the standard of care,
      reversing the prior bar under former Labor Code § 6304.5. Subsequent decisions have <em>narrowed</em>
      {' '}application to plaintiffs within the protected class — typically employees, not bystanders.
    </p>
    <div className="t-eyebrow" style={{ marginTop: 18, marginBottom: 8 }}>Top authorities</div>
    <div className="authority-list">
      {authorities.map((a, i) => (
        <AuthorityRow key={a.id} a={a} n={String(i+1).padStart(2,'0')} active={a.id===activeAuthority} onPick={openAuthority} />
      ))}
    </div>
    <div className="ai-actions">
      <button className="ai-action-btn"><Icon name="copy" size={13}/> Copy answer</button>
      <button className="ai-action-btn"><Icon name="file" size={13}/> Insert into draft</button>
      <button className="ai-action-btn"><Icon name="download" size={13}/> Export</button>
      <button className="ai-action-btn"><Icon name="spark" size={13}/> Refine</button>
    </div>
  </div>
);

const Composer = ({ onSubmit }) => {
  const [val, setVal] = useState("");
  const ref = useRef(null);
  return (
    <div className="composer">
      <textarea ref={ref} value={val} onChange={e => setVal(e.target.value)}
        placeholder="Ask a follow-up — or paste a citation, jurisdiction, or fact pattern…"
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (val.trim()) { onSubmit(val); setVal(""); }
          }
        }} />
      <div className="composer-actions">
        <div className="left">
          <button className="btn-icon" title="Attach"><Icon name="paperclip" size={16}/></button>
          <button className="btn-icon" title="Sources"><Icon name="book" size={16}/></button>
          <button className="btn-icon" title="Templates"><Icon name="file" size={16}/></button>
        </div>
        <div className="right">
          <span className="source-chip"><Icon name="globe" size={12}/>9th Cir. · CA · Federal <Icon name="chevDown" size={12}/></span>
          <button className="btn-send" onClick={() => { if (val.trim()) { onSubmit(val); setVal(""); } }}>
            Ask LawGIQ <Icon name="arrowUp" size={14} strokeWidth={2}/>
          </button>
        </div>
      </div>
    </div>
  );
};

const MainView = ({ matter, messages, activeCiteId, openCite, authorities, openAuthority, activeAuthority, onSubmit }) => {
  const bodyRef = useRef(null);
  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight; }, [messages.length]);
  return (
    <main className="main">
      <div className="main-hdr">
        <div className="breadcrumbs">Matters · {matter.client} · {matter.ref}</div>
        <h1>{matter.title}</h1>
        <div className="meta-row">
          <span className="chip"><Icon name="globe" size={13}/> California · 9th Cir.</span>
          <span className="chip"><Icon name="clock" size={13}/> Updated 11 min ago</span>
          <span className="chip"><Icon name="file" size={13}/> 14 documents</span>
        </div>
        <div className="main-tabs">
          <div className="main-tab active">Research<span className="count">3</span></div>
          <div className="main-tab">Authorities<span className="count">28</span></div>
          <div className="main-tab">Drafts<span className="count">2</span></div>
          <div className="main-tab">Documents<span className="count">14</span></div>
          <div className="main-tab">Timeline</div>
        </div>
      </div>
      <div className="main-body" ref={bodyRef}>
        {messages.map((m, i) =>
          m.role === 'user'
            ? <UserMsg key={i} text={m.text} />
            : <AiAnswer key={i} openCite={openCite} activeCiteId={activeCiteId}
                authorities={authorities} openAuthority={openAuthority} activeAuthority={activeAuthority}/>
        )}
      </div>
      <div className="main-footer">
        <Composer onSubmit={onSubmit} />
      </div>
    </main>
  );
};

window.MainView = MainView;
