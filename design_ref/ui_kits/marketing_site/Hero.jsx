/* global React, Icon */

const Hero = () => (
  <section className="hero">
    <div className="container hero-row">
      <div>
        <div className="hero-eyebrow"><span className="dot"/>For attorneys, by design</div>
        <h1>
          The <em>research</em>,<br/>
          <span className="accent">drafting</span>, and citation<br/>
          assistant your matters deserve.
        </h1>
        <p className="lede">
          LawGIQ reads the record, retrieves binding authority, and drafts the memo — leaving the judgment,
          where it belongs, with you.
        </p>
        <div className="hero-cta">
          <button className="btn btn-primary btn-lg">Request a demo</button>
          <button className="btn btn-secondary btn-lg">Watch the product tour <Icon name="chevRight" size={14}/></button>
          <span className="hint">14-day trial · No card required</span>
        </div>
      </div>
      <div className="hero-vis">
        <div className="vis-hdr">
          <span className="vis-dot"/><span className="vis-dot"/><span className="vis-dot"/>
          <span className="vis-url">app.lawgiq.com/m/smith-v-jones</span>
        </div>
        <div className="vis-body">
          <div className="vis-eyebrow"><span className="glyph">§</span>LawGIQ · 4.2s · 12 sources</div>
          <h3>California recognizes negligence per se for OSHA violations — with limits.</h3>
          <p>
            Under <span className="vis-cite">Cal. Civ. Code § 1714(a)</span> every person owes a duty of ordinary
            care. The doctrine permits a presumption of negligence where a statute is violated and the plaintiff is
            within the protected class.
          </p>
          <div className="vis-row"><div className="num">01</div><div className="ttl">Elsner v. Uveges</div><div className="ref">34 Cal. 4th 915</div><span className="badge">Good law</span></div>
          <div className="vis-row"><div className="num">02</div><div className="ttl">Spencer v. MacDonald</div><div className="ref">63 Cal. App. 3d 836</div><span className="badge warn">Distinguished</span></div>
        </div>
      </div>
    </div>
  </section>
);

window.Hero = Hero;
