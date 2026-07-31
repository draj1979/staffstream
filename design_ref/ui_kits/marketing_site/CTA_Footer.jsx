/* global React */

const CTA = () => (
  <section className="cta">
    <div className="container">
      <h2>Spend your <em>judgment</em> where it matters.</h2>
      <p>14-day trial. No card required. Bring your own Westlaw or Lexis credentials.</p>
      <div className="cta-buttons">
        <button className="btn btn-primary btn-lg">Request a demo</button>
        <button className="btn btn-secondary btn-lg">Start a trial</button>
      </div>
    </div>
  </section>
);

const Footer = () => (
  <footer className="ftr">
    <div className="container">
      <div className="ftr-row">
        <div className="ftr-brand">
          <img src="../../assets/logo-wordmark-inverse.svg" alt="LawGIQ"/>
          <p>An AI-powered legal assistant built for the way attorneys actually research, draft, and verify.</p>
        </div>
        <div className="ftr-col">
          <h5>Product</h5>
          <ul>
            <li><a href="#">Research</a></li>
            <li><a href="#">Drafting</a></li>
            <li><a href="#">Verification</a></li>
            <li><a href="#">Integrations</a></li>
            <li><a href="#">Changelog</a></li>
          </ul>
        </div>
        <div className="ftr-col">
          <h5>Solutions</h5>
          <ul>
            <li><a href="#">Litigation</a></li>
            <li><a href="#">Transactional</a></li>
            <li><a href="#">Regulatory</a></li>
            <li><a href="#">In-house counsel</a></li>
            <li><a href="#">Solo &amp; small firm</a></li>
          </ul>
        </div>
        <div className="ftr-col">
          <h5>Company</h5>
          <ul>
            <li><a href="#">About</a></li>
            <li><a href="#">Customers</a></li>
            <li><a href="#">Careers</a></li>
            <li><a href="#">Press</a></li>
            <li><a href="#">Contact</a></li>
          </ul>
        </div>
        <div className="ftr-col">
          <h5>Resources</h5>
          <ul>
            <li><a href="#">Documentation</a></li>
            <li><a href="#">Security</a></li>
            <li><a href="#">Trust center</a></li>
            <li><a href="#">Bar-approved CLE</a></li>
            <li><a href="#">API</a></li>
          </ul>
        </div>
      </div>
      <div className="ftr-bottom">
        <div>© 2026 LawGIQ, Inc. · LawGIQ is not a law firm and does not provide legal advice.</div>
        <div className="links">
          <a href="#">Terms</a>
          <a href="#">Privacy</a>
          <a href="#">DPA</a>
          <a href="#">Cookies</a>
        </div>
      </div>
    </div>
  </footer>
);

window.CTA = CTA;
window.Footer = Footer;
