/* global React, Icon */

const Check = () => <Icon name="chevRight" size={14} strokeWidth={2}/>;

const Pricing = () => (
  <section className="pricing">
    <div className="container">
      <div className="section-eyebrow">Pricing</div>
      <h2>Plans built around <em>how lawyers bill,</em> not seats.</h2>
      <p className="section-lede">All tiers include unlimited matters, BYOK for Westlaw/Lexis, and SOC&nbsp;2 Type&nbsp;II controls.</p>
      <div className="pricing-grid">
        <div className="tier">
          <div className="tier-name">Solo</div>
          <div className="tier-price">$149<span className="per">/ attorney / mo</span></div>
          <div className="tier-desc">For solo practitioners and 2–3 person firms.</div>
          <ul className="tier-features">
            <li><Check/>Unlimited matters</li>
            <li><Check/>Federal + 1 state library</li>
            <li><Check/>Standard citators</li>
            <li><Check/>Email support</li>
          </ul>
          <button className="btn btn-secondary">Start 14-day trial</button>
        </div>
        <div className="tier featured">
          <div className="tier-name">Practice<span className="pill">Most chosen</span></div>
          <div className="tier-price">$349<span className="per">/ attorney / mo</span></div>
          <div className="tier-desc">For litigation, transactional, and regulatory teams up to 50.</div>
          <ul className="tier-features">
            <li><Check/>All 50 states + federal libraries</li>
            <li><Check/>House-style training on your filings</li>
            <li><Check/>Verification across full opinions</li>
            <li><Check/>Matter isolation &amp; audit log</li>
            <li><Check/>Priority support, 2hr SLA</li>
          </ul>
          <button className="btn btn-primary">Request a demo</button>
        </div>
        <div className="tier">
          <div className="tier-name">Firm</div>
          <div className="tier-price">Custom<span className="per"></span></div>
          <div className="tier-desc">For AmLaw firms and in-house legal departments.</div>
          <ul className="tier-features">
            <li><Check/>Single-tenant deployment</li>
            <li><Check/>SSO, SCIM, conflict-check integration</li>
            <li><Check/>Custom retention &amp; data residency</li>
            <li><Check/>Dedicated solutions engineer</li>
          </ul>
          <button className="btn btn-dark">Talk to sales</button>
        </div>
      </div>
    </div>
  </section>
);

window.Pricing = Pricing;
