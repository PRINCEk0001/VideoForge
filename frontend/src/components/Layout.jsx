import React, { useState } from 'react';

const Layout = ({ children, onSettingsClick, activeView, onViewChange }) => {
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="layout-root">
      {/* Global Navigation Bar */}
      <nav className="nav-global">
        <div className="logo-group" onClick={() => onViewChange('generator')} style={{ cursor: 'pointer' }}>
          <div className="logo-icon">🎬</div>
          <span className="logo-text">
            Video<span>Forge</span>
          </span>
        </div>
        
        <div style={{ flex: 1 }} />
        
        <div className="nav-actions">
          <button className="nav-link-btn" onClick={onSettingsClick}>
            <span style={{ marginRight: '8px' }}>⚙️</span> API Settings
          </button>
          <div className="user-avatar" />
        </div>
        
        <button className="mobile-toggle" onClick={() => setSidebarOpen(!isSidebarOpen)}>
          {isSidebarOpen ? '✕' : '☰'}
        </button>
      </nav>

      <div className="layout-body">
        {/* Mobile-Ready Sidebar */}
        <aside className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-section">
            <div className="sidebar-label">WORKSPACE</div>
            <button 
              className={`sidebar-item ${activeView === 'generator' ? 'active' : ''}`}
              onClick={() => { onViewChange('generator'); setSidebarOpen(false); }}
            >
              <span className="sidebar-icon">🛠</span> Generator
            </button>
            <button 
              className={`sidebar-item ${activeView === 'videos' ? 'active' : ''}`}
              onClick={() => { onViewChange('videos'); setSidebarOpen(false); }}
            >
              <span className="sidebar-icon">📂</span> My Videos
            </button>
            <button 
              className={`sidebar-item ${activeView === 'analytics' ? 'active' : ''}`}
              onClick={() => { onViewChange('analytics'); setSidebarOpen(false); }}
            >
              <span className="sidebar-icon">📈</span> Analytics
            </button>
          </div>

          <div className="sidebar-footer" style={{ marginTop: 'auto' }}>
            <button className="sidebar-item secondary" onClick={onSettingsClick}>
              <span className="sidebar-icon">⚙️</span> Settings
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="main-content">
          <div className="content-container">
            {children}
          </div>
        </main>
      </div>

      {/* Mobile Overlay */}
      {isSidebarOpen && <div className="mobile-overlay" onClick={() => setSidebarOpen(false)} />}
    </div>
  );
};

export default Layout;
