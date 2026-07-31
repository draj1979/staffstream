/* global React, Header, Sidebar, MainView, SourcePanel */
const { useState } = React;

const MATTERS = [
  { id: 'm1', title: 'Smith v. Jones', ref: 'CV-2024-0192', client: 'ACME Logistics', count: 28 },
  { id: 'm2', title: 'Re Westbrook estate', ref: 'PR-2024-0114', client: 'Westbrook family', count: 11 },
  { id: 'm3', title: 'Garcia employment claim', ref: 'EM-2024-0073', client: 'Garcia, M.',     count: 7  },
  { id: 'm4', title: 'TerraBio licensing review', ref: 'CO-2024-0244', client: 'TerraBio Inc.', count: 19 },
];

const RECENTS = [
  'Negligence per se — OSHA basis',
  'Standing for environmental nuisance',
  'Discovery cutoff CA Code Civ Proc §2024.020',
  'Forum selection clause — enforceability',
];

const AUTHORITIES = [
  { id: 'c1', title: 'Cal. Civ. Code § 1714(a)', cite: '§ 1714(a)', court: 'Cal. Civ. Code', statusLabel: 'Good law', statusClass: 'good' },
  { id: 'c2', title: 'Evidence Code § 669',      cite: 'Evid. Code § 669', court: 'Cal. Stat.', statusLabel: 'Good law', statusClass: 'good' },
  { id: 'c3', title: 'Elsner v. Uveges',         cite: '34 Cal. 4th 915 (2004)', court: 'Cal. Supreme Ct.', statusLabel: 'Good law', statusClass: 'good' },
  { id: 'c4', title: 'Spencer v. G.A. MacDonald Constr. Co.', cite: '63 Cal. App. 3d 836 (1976)', court: '2d Dist. Ct. App.', statusLabel: 'Distinguished', statusClass: 'warn' },
];

const SOURCES = {
  c1: {
    title: 'Cal. Civ. Code § 1714(a)',
    cite: '§ 1714(a) — General duty',
    court: 'California Civil Code',
    tags: ['Statute', 'CA', 'Good law'],
    passages: [
      'Everyone is responsible, not only for the result of his or her willful acts, but also for an injury occasioned to another by his or her <span class="hl">want of ordinary care or skill</span> in the management of his or her property or person, except so far as the latter has, willfully or by want of ordinary care, brought the injury upon himself or herself.',
      'The extent of liability in such cases is defined by the Title on Compensatory Relief. <span class="hl t">LawGIQ note: this is the principal foundational duty statute cited across 7 of your draft sections.</span>'
    ],
    pageRef: 'CAL. CIV. CODE · § 1714(a) · Enacted 1872'
  },
  c2: {
    title: 'Cal. Evid. Code § 669',
    cite: '§ 669 — Failure to exercise due care',
    court: 'California Evidence Code',
    tags: ['Statute', 'Evidentiary', 'Good law'],
    passages: [
      '(a) The failure of a person to exercise due care is presumed if: (1) He violated a statute, ordinance, or regulation of a public entity; (2) <span class="hl">The violation proximately caused death or injury to person or property</span>; (3) The death or injury resulted from an occurrence of the nature which the statute, ordinance, or regulation was designed to prevent; and (4) <span class="hl">The person suffering the death or the injury to his person or property was one of the class of persons for whose protection the statute, ordinance, or regulation was adopted</span>.',
      '(b) This presumption may be rebutted by proof that: (1) The person violating the statute did what might reasonably be expected of a person of ordinary prudence, acting under similar circumstances, who desired to comply with the law; or (2) The person had a legally sufficient excuse for the violation.'
    ],
    pageRef: 'CAL. EVID. CODE · § 669 · Enacted 1965'
  },
  c3: {
    title: 'Elsner v. Uveges',
    cite: '34 Cal. 4th 915, 22 Cal. Rptr. 3d 530 (2004)',
    court: 'Supreme Court of California',
    tags: ['9th Cir.', '2004', 'Cited 14×', 'Good law'],
    passages: [
      'We granted review to determine whether Labor Code former section 6304.5, which restricted use of Cal-OSHA provisions in personal injury actions, survives the 1999 amendment that broadened the scope of admissible safety standards. <span class="hl">We hold that Cal-OSHA provisions may be admitted to establish a standard or duty of care</span> in all negligence actions, not merely those brought by employees against their employers.<span class="pin">cited</span>',
      'The Legislature\'s 1999 amendment of section 6304.5 expressly states that "[s]ections 452 and 669 of the Evidence Code shall apply to" Cal-OSHA provisions. The legislative history confirms an intent to <span class="hl">restore the rule of <em>negligence per se</em></span> to its full pre-Brock vitality in actions where the plaintiff is within the class the regulation was designed to protect.',
      '<span class="hl t">LawGIQ note: this decision reverses the prior bar under <em>Brock v. State of California</em>, 81 Cal. App. 3d 752 (1978).</span>'
    ],
    pageRef: 'P. 924 · ¶ 14'
  },
  c4: {
    title: 'Spencer v. G.A. MacDonald Constr. Co.',
    cite: '63 Cal. App. 3d 836, 134 Cal. Rptr. 78 (1976)',
    court: 'Court of Appeal, 2d District',
    tags: ['CA App.', '1976', 'Distinguished'],
    passages: [
      'Where the plaintiff is not a member of the class the safety order is designed to protect, the doctrine of negligence per se does not apply. <span class="hl">A bystander injured at a construction site does not fall within the class of persons for whose protection Cal-OSHA was enacted</span>, which is limited to employees engaged in the work covered by the order.',
      '<span class="hl t">LawGIQ note: distinguished by <em>Elsner v. Uveges</em> (2004) on legislative-amendment grounds; still cited for the class-of-persons limitation.</span>'
    ],
    pageRef: 'P. 842 · ¶ 8'
  }
};

const App = () => {
  const [activeMatterId, setActiveMatterId] = useState('m1');
  const [activeCiteId, setActiveCiteId] = useState('c3');
  const [activeAuthority, setActiveAuthority] = useState('c3');
  const [messages, setMessages] = useState([
    { role: 'user', text: 'Does California recognize negligence per se for OSHA violations, and does that doctrine extend to non-employee bystanders?' },
    { role: 'ai' }
  ]);

  const matter = MATTERS.find(m => m.id === activeMatterId);

  const handleSubmit = (text) => {
    setMessages([...messages, { role: 'user', text }, { role: 'ai' }]);
  };

  const openCite = (id) => { setActiveCiteId(id); setActiveAuthority(id); };
  const openAuthority = (id) => { setActiveAuthority(id); setActiveCiteId(id); };

  return (
    <div className="app">
      <Header matter={matter} />
      <Sidebar
        matters={MATTERS}
        recents={RECENTS}
        activeMatterId={activeMatterId}
        onPick={setActiveMatterId}
        onNewChat={() => setMessages([{ role: 'ai' }])}
      />
      <MainView
        matter={matter}
        messages={messages}
        authorities={AUTHORITIES}
        activeCiteId={activeCiteId}
        openCite={openCite}
        openAuthority={openAuthority}
        activeAuthority={activeAuthority}
        onSubmit={handleSubmit}
      />
      <SourcePanel
        source={SOURCES[activeAuthority]}
        onClose={() => { setActiveAuthority(null); setActiveCiteId(null); }}
      />
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('app')).render(<App />);
