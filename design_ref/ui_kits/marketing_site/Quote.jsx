/* global React */

const Quote = () => (
  <section className="quote">
    <div className="container quote-row">
      <div className="quote-attr">
        <div className="avatar">MO</div>
        <div className="name">Maya Okonkwo</div>
        <div className="role">Senior Litigation Associate</div>
        <div className="firm">Halverson &amp; Pratt LLP</div>
      </div>
      <div>
        <p className="quote-body">
          I used to spend Sunday afternoons running KeyCite on every authority in a brief. LawGIQ
          surfaces silent overrulings before I'm even done drafting — and tells me which paragraph
          in <em>Elsner</em> changed the rule. That's the part Westlaw never did.
        </p>
      </div>
    </div>
  </section>
);

window.Quote = Quote;
