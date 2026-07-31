/* global React, Icon */

const ProductDetail = () => (
  <section className="detail">
    <div className="container">
      <div className="detail-row">
        <div>
          <div className="section-eyebrow" style={{ color: 'var(--teal-300)' }}>Inside the workspace</div>
          <h2>One matter, every <em>authority,</em> in context.</h2>
          <p className="section-lede">
            The workspace doesn't separate research from drafting from citation. They're the same
            surface — because that's how the work actually flows.
          </p>
          <div className="detail-list">
            <div className="detail-item">
              <div className="ico"><Icon name="book" size={18}/></div>
              <div><h4>Source-anchored answers</h4><p>Every passage links to the exact paragraph it was drawn from, in the cited decision. No black box.</p></div>
            </div>
            <div className="detail-item">
              <div className="ico"><Icon name="filter" size={18}/></div>
              <div><h4>Jurisdiction-aware</h4><p>Filter by federal circuit, state, or court level. LawGIQ knows the difference between persuasive and binding.</p></div>
            </div>
            <div className="detail-item">
              <div className="ico"><Icon name="settings" size={18}/></div>
              <div><h4>House-style aware</h4><p>Trained on your firm's filings — adopts your citation conventions, voice, and section structure.</p></div>
            </div>
            <div className="detail-item">
              <div className="ico"><Icon name="briefcase" size={18}/></div>
              <div><h4>Matter-isolated</h4><p>Documents, prompts, and outputs are siloed per matter. Confidentiality by architecture, not policy.</p></div>
            </div>
          </div>
        </div>
        <div className="product-shot">
          <div className="product-shot-bar">
            <span className="d"/><span className="d"/><span className="d"/>
          </div>
          <div className="product-shot-body">
            <div style={{ fontSize: 11, color: '#4E8487', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
              <span style={{ fontFamily: 'var(--font-display)', fontStyle: 'italic', color: '#FF5722', letterSpacing: 0, textTransform: 'none', fontSize: 14, marginRight: 6 }}>§</span>
              Supreme Court of California
            </div>
            <h4>Elsner v. Uveges, 34 Cal. 4th 915 (2004)</h4>
            <p>
              We hold that <span className="product-shot-hl">Cal-OSHA provisions may be admitted to establish a standard or duty of care</span> in
              all negligence actions, not merely those brought by employees against their employers.
            </p>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
              <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: 'var(--bg)', color: 'var(--fg2)', border: '1px solid var(--border)' }}>9th Cir.</span>
              <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: 'var(--bg)', color: 'var(--fg2)', border: '1px solid var(--border)' }}>2004</span>
              <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: 'var(--bg)', color: 'var(--fg2)', border: '1px solid var(--border)' }}>Cited 14×</span>
            </div>
            <div className="product-shot-row"><div className="num">01</div><div className="ttl">Cal. Civ. Code § 1714(a)</div><span className="badge">Good law</span></div>
            <div className="product-shot-row"><div className="num">02</div><div className="ttl">Evid. Code § 669</div><span className="badge">Good law</span></div>
          </div>
        </div>
      </div>
    </div>
  </section>
);

window.ProductDetail = ProductDetail;
