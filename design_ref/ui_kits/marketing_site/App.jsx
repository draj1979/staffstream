/* global React, Nav, Hero, TrustedBy, Features, ProductDetail, Quote, Pricing, CTA, Footer */

const App = () => (
  <>
    <Nav />
    <Hero />
    <TrustedBy />
    <Features />
    <ProductDetail />
    <Quote />
    <Pricing />
    <CTA />
    <Footer />
  </>
);

ReactDOM.createRoot(document.getElementById('app')).render(<App />);
