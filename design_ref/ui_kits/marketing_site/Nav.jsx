/* global React, Icon */
const { useState, useEffect } = React;

const Nav = () => {
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const fn = () => setStuck(window.scrollY > 4);
    window.addEventListener('scroll', fn);
    return () => window.removeEventListener('scroll', fn);
  }, []);
  return (
    <nav className={"nav" + (stuck ? " stuck" : "")}>
      <div className="container nav-row">
        <a className="nav-logo" href="#"><img src="../../assets/logo-wordmark.svg" alt="LawGIQ"/></a>
        <div className="nav-links">
          <span className="nav-link">Product <Icon name="chevDown" size={13}/></span>
          <span className="nav-link">Solutions <Icon name="chevDown" size={13}/></span>
          <span className="nav-link">Pricing</span>
          <span className="nav-link">Security</span>
          <span className="nav-link">Resources <Icon name="chevDown" size={13}/></span>
        </div>
        <div className="nav-right">
          <button className="btn btn-ghost">Sign in</button>
          <button className="btn btn-dark">Request a demo</button>
        </div>
      </div>
    </nav>
  );
};

window.Nav = Nav;
