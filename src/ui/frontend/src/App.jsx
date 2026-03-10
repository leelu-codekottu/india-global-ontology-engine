import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import IntroAnimation from './components/IntroAnimation';
import ChatPage from './pages/ChatPage';
import GraphPage from './pages/GraphPage';

const PAGES = {
  chat: { label: 'Ask Engine', labelHi: 'प्रश्न इंजन', icon: '⊛', component: ChatPage },
  graph: { label: 'Knowledge Graph', labelHi: 'ज्ञान ग्राफ़', icon: '◎', component: GraphPage },
};

export default function App() {
  const [showIntro, setShowIntro] = useState(true);
  const [activePage, setActivePage] = useState('chat');

  if (showIntro) {
    return <IntroAnimation onComplete={() => setShowIntro(false)} />;
  }

  return (
    <div className="app-shell">
      <Sidebar pages={PAGES} activePage={activePage} onNavigate={setActivePage} />
      <div className="main-content">
        <TopBar
          title={PAGES[activePage].label}
          titleHi={PAGES[activePage].labelHi}
        />
        <div className="page-container">
          {/* Render all pages but hide inactive — preserves chat state across navigation */}
          {Object.entries(PAGES).map(([key, page]) => {
            const PageComp = page.component;
            return (
              <div key={key} style={{ display: activePage === key ? 'block' : 'none', height: '100%' }}>
                <PageComp onNavigate={setActivePage} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
