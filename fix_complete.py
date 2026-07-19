content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Find and replace the entire aside block
start = content.find('      <aside className="chat-page-sidebar"')
end = content.find('</aside>', start) + 8

new_aside = """      <aside className="chat-page-sidebar" style={{
        width: sidebarOpen ? '260px' : '0',
        minWidth: sidebarOpen ? '260px' : '0',
        overflow: 'hidden',
        transition: 'width 0.2s ease, min-width 0.2s ease',
        background: isDark ? '#1a1a1a' : '#f0f4f0',
        borderRight: `1px solid ${isDark ? '#2e2e2e' : '#d0dbd0'}`,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        flexShrink: 0,
      }}>
        {/* Top: Dashboard link (admin only) */}
        {isAdmin && (
          <button onClick={() => navigate('/documents')}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '14px 16px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', fontWeight: 500, color: isDark ? '#6E9163' : '#4a7a5a', width: '100%', textAlign: 'left', borderBottom: `1px solid ${isDark ? '#2e2e2e' : '#d0dbd0'}` }}>
            <ArrowLeft size={14} /> Back to Dashboard
          </button>
        )}

        {/* Enterprise RAG title */}
        <div style={{ padding: '14px 16px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '15px', fontWeight: 700, color: isDark ? '#6E9163' : '#3a6b3a', letterSpacing: '-0.02em' }}>Enterprise RAG</span>
        </div>

        {/* New chat button */}
        <div style={{ padding: '0 12px 10px' }}>
          <button onClick={handleNewChat}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '9px', borderRadius: '8px', border: `1px solid ${isDark ? '#3a3a3a' : '#c0d0c0'}`, background: isDark ? '#252525' : 'white', color: isDark ? '#e0e0e0' : '#2a2a2a', fontSize: '13px', fontWeight: 500, cursor: 'pointer' }}>
            <Plus size={15} /> New chat
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '0 12px 8px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)', color: isDark ? '#666' : '#888', pointerEvents: 'none' }} />
            <input type="text" placeholder="Search chats..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              style={{ width: '100%', padding: '7px 8px 7px 30px', fontSize: '12px', border: `1px solid ${isDark ? '#3a3a3a' : '#c0d0c0'}`, borderRadius: '7px', background: isDark ? '#252525' : 'white', color: isDark ? '#e0e0e0' : '#2a2a2a', outline: 'none', boxSizing: 'border-box' }} />
          </div>
        </div>

        {/* Group by */}
        <div style={{ padding: '0 12px 8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '11px', color: isDark ? '#666' : '#888' }}>Group by:</span>
          {(['none', 'date'] as const).map(g => (
            <button key={g} onClick={() => setGroupBy(g)}
              style={{ fontSize: '11px', padding: '3px 10px', borderRadius: '20px', border: `1px solid ${groupBy === g ? '#6E9163' : (isDark ? '#3a3a3a' : '#c0d0c0')}`, background: groupBy === g ? '#6E9163' : 'transparent', color: groupBy === g ? 'white' : (isDark ? '#999' : '#666'), cursor: 'pointer', textTransform: 'capitalize' }}>
              {g === 'none' ? 'None' : 'Date'}
            </button>
          ))}
        </div>

        {/* Chat list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
          {filteredConversations.length === 0 && searchQuery && (
            <div style={{ fontSize: '12px', color: isDark ? '#666' : '#999', textAlign: 'center', padding: '20px 0' }}>No chats found</div>
          )}
          {groupBy === 'none' ? filteredConversations.map((c) => (
            <div key={c.id} style={{ position: 'relative', display: 'flex', alignItems: 'center', borderRadius: '7px', marginBottom: '2px', background: c.id === activeId ? (isDark ? '#2e2e2e' : '#dceadc') : 'transparent' }}
              onMouseEnter={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn) btn.style.opacity = '1' }}
              onMouseLeave={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn && menuOpenId !== c.id) btn.style.opacity = '0' }}>
              <button onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
                style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', overflow: 'hidden', color: c.id === activeId ? (isDark ? '#e0e0e0' : '#1a3a1a') : (isDark ? '#b0b0b0' : '#3a3a3a'), fontSize: '13px' }}>
                <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
              </button>
              <button className="dots-btn" onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === c.id ? null : c.id) }}
                style={{ opacity: c.id === activeId ? 1 : 0, transition: 'opacity 0.1s', padding: '6px 6px', border: 'none', background: 'transparent', cursor: 'pointer', color: isDark ? '#888' : '#666', flexShrink: 0 }}>
                <MoreHorizontal size={14} />
              </button>
              {menuOpenId === c.id && (
                <div style={{ position: 'absolute', right: '4px', top: '100%', background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${isDark ? '#3a3a3a' : '#d0d0d0'}`, borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.15)', zIndex: 50, minWidth: '150px', padding: '4px' }} onClick={e => e.stopPropagation()}>
                  <button onClick={() => { const t = prompt('Rename chat:', c.title); if (t) handleRename(c.id, t); setMenuOpenId(null) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#e0e0e0' : '#2a2a2a', borderRadius: '6px' }}
                    onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#f5f5f5'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <Pencil size={13} /> Rename
                  </button>
                  <button onClick={() => { handleDelete(c.id); setMenuOpenId(null) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: '#e05050', borderRadius: '6px' }}
                    onMouseEnter={e => e.currentTarget.style.background = isDark ? '#2e1a1a' : '#fff0f0'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <Trash2 size={13} /> Delete
                  </button>
                </div>
              )}
            </div>
          )) : Object.entries(groupedConversations).map(([group, chats]) => (
            <div key={group}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: isDark ? '#555' : '#999', textTransform: 'uppercase', letterSpacing: '0.07em', padding: '8px 10px 4px' }}>{group}</div>
              {(chats as Conversation[]).map((c) => (
                <div key={c.id} style={{ position: 'relative', display: 'flex', alignItems: 'center', borderRadius: '7px', marginBottom: '2px', background: c.id === activeId ? (isDark ? '#2e2e2e' : '#dceadc') : 'transparent' }}
                  onMouseEnter={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn) btn.style.opacity = '1' }}
                  onMouseLeave={e => { const btn = e.currentTarget.querySelector('.dots-btn') as HTMLElement; if (btn && menuOpenId !== c.id) btn.style.opacity = '0' }}>
                  <button onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', overflow: 'hidden', color: c.id === activeId ? (isDark ? '#e0e0e0' : '#1a3a1a') : (isDark ? '#b0b0b0' : '#3a3a3a'), fontSize: '13px' }}>
                    <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
                  </button>
                  <button className="dots-btn" onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === c.id ? null : c.id) }}
                    style={{ opacity: c.id === activeId ? 1 : 0, transition: 'opacity 0.1s', padding: '6px 6px', border: 'none', background: 'transparent', cursor: 'pointer', color: isDark ? '#888' : '#666', flexShrink: 0 }}>
                    <MoreHorizontal size={14} />
                  </button>
                  {menuOpenId === c.id && (
                    <div style={{ position: 'absolute', right: '4px', top: '100%', background: isDark ? '#2a2a2a' : 'white', border: `1px solid ${isDark ? '#3a3a3a' : '#d0d0d0'}`, borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.15)', zIndex: 50, minWidth: '150px', padding: '4px' }} onClick={e => e.stopPropagation()}>
                      <button onClick={() => { const t = prompt('Rename chat:', c.title); if (t) handleRename(c.id, t); setMenuOpenId(null) }}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#e0e0e0' : '#2a2a2a', borderRadius: '6px' }}
                        onMouseEnter={e => e.currentTarget.style.background = isDark ? '#333' : '#f5f5f5'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                        <Pencil size={13} /> Rename
                      </button>
                      <button onClick={() => { handleDelete(c.id); setMenuOpenId(null) }}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: '#e05050', borderRadius: '6px' }}
                        onMouseEnter={e => e.currentTarget.style.background = isDark ? '#2e1a1a' : '#fff0f0'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                        <Trash2 size={13} /> Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* Footer: dark mode toggle + logout */}
        <div style={{ padding: '10px 12px', borderTop: `1px solid ${isDark ? '#2e2e2e' : '#d0dbd0'}`, display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <button onClick={() => { const newDark = !isDark; setIsDark(newDark); localStorage.setItem('darkMode', String(newDark)) }}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: `1px solid ${isDark ? '#3a3a3a' : '#c0d0c0'}`, borderRadius: '7px', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#b0b0b0' : '#555', width: '100%' }}>
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
            {isDark ? 'Light mode' : 'Dark mode'}
          </button>
          <button onClick={handleLogout}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: isDark ? '#888' : '#666', width: '100%' }}>
            <LogOut size={14} /> Log out
          </button>
        </div>
      </aside>"""

if start > 0 and end > start:
    content = content[:start] + new_aside + content[end:]
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done - aside replaced')
else:
    print('FAILED - aside not found')
