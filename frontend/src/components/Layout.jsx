import React, { useState } from 'react';

const Layout = ({ children, onSettingsClick, activeView, onViewChange }) => {
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="layout-root">
      {/* Global Navigation Bar */}
      <nav className="nav-global">
        <div className="logo-group" onClick={() => onViewChange('generator')} style={{ cursor: 'pointer' }}>
          <span className="logo-text">
            Video<span className="serif">Forge</span>
          </span>
        </div>
        
        <div style={{ flex: 1 }} />
        
        <div className="nav-actions">
          <button className="nav-link-btn" onClick={onSettingsClick}>
            API Settings
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
              Generator
            </button>
            <button 
              className={`sidebar-item ${activeView === 'videos' ? 'active' : ''}`}
              onClick={() => { onViewChange('videos'); setSidebarOpen(false); }}
            >
              My Videos
            </button>
            <button 
              className={`sidebar-item ${activeView === 'analytics' ? 'active' : ''}`}
              onClick={() => { onViewChange('analytics'); setSidebarOpen(false); }}
            >
              Analytics
            </button>
          </div>

          <div className="sidebar-footer" style={{ marginTop: 'auto' }}>
            <button className="sidebar-item secondary" onClick={onSettingsClick}>
              Settings
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
