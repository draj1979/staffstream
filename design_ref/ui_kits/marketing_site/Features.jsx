/* global React, Icon */

const Features = () => (
  <section className="section">
    <div className="container">
      <div className="section-eyebrow">What LawGIQ does</div>
      <h2>Three categories of work, returned to you as <em>finished thought.</em></h2>
      <p className="section-lede">
        Research that reads the whole record. Drafting that cites itself. Verification that catches
        what citators miss. Each surface is an opinion, not a feature list.
      </p>
      <div className="feature-grid">
        <div className="feature">
          <div className="feature-num">01 — Research</div>
          <h3>Memo-grade answers, with the case in your hand.</h3>
          <p>Ask in plain English. LawGIQ pulls binding authority for your jurisdiction, distinguishes adverse
            holdings, and surfaces the controlling passage — not a synopsis.</p>
          <div className="feature-visual">
            <div style={{ fontSize: 11, color: 'var(--teal-700)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6 }}>§ LawGIQ · 4.2s</div>
            <div style={{ fontSize: 13, color: 'var(--fg1)', lineHeight: 1.4 }}>
              "Under Cal. Civ. Code <span style={{ background: '#EEF5F5', color: '#4E8487', fontFamily: 'var(--font-mono)', fontSize: 11, padding: '0 4px', borderRadius: 3 }}>§ 1714(a)</span> every
              person owes a duty of ordinary care…"
            </div>
          </div>
        </div>
        <div className="feature">
          <div className="feature-num">02 — Drafting</div>
          <h3>Briefs and memos that already cite themselves.</h3>
          <p>Generate sections in your firm's house style. Every assertion carries a citation, every
            citation carries a Shepard-style currency check. Edit inline, regenerate the surrounding
            paragraph without losing the rest.</p>
          <div className="feature-visual" style={{ background: '#fff' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--fg1)', lineHeight: 1.5 }}>
              The court held that a duty arises where <span style={{ background: '#FFE9A8', padding: '0 2px', borderRadius: 2 }}>foreseeability of harm</span> and
              the relationship between the parties support it.<sup style={{ background: '#FF5722', color: '#fff', fontFamily: 'var(--font-sans)', fontSize: 9, padding: '0 4px', borderRadius: 2, marginLeft: 2, verticalAlign: 'super', fontWeight: 600 }}>14</sup>
            </div>
          </div>
        </div>
        <div className="feature">
          <div className="feature-num">03 — Verification</div>
          <h3>Catches what KeyCite and Shepard's miss.</h3>
          <p>Every cite in your draft is checked against the full text of subsequent decisions —
            not just headnote signals. Distinctions, narrowings, and silent overrulings flagged inline.</p>
          <div className="feature-visual" style={{ background: '#FFF1EB', borderColor: '#FFD9C9' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <Icon name="close" size={16} style={{ color: '#E14918', marginTop: 2, flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#C53D14', lineHeight: 1.35, marginBottom: 4 }}>3 cites in this draft are stale</div>
                <div style={{ fontSize: 11, color: '#E14918', lineHeight: 1.5 }}>Wilson v. Marek (2021) narrows the rule you cited.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
);

window.Features = Features;
