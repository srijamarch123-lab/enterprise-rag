content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = '      <aside className="chat-page-sidebar">'
idx = content.find(old)
if idx < 0:
    print('FAILED')
else:
    # Find closing </aside>
    end = content.find('</aside>', idx) + 8
    print('Found aside from', idx, 'to', end)
    
    new_aside = """      <aside className="chat-page-sidebar">
        {/* Header */}
        <div style={{ padding: '16px 14px 10px', borderBottom: `1px solid ${color.border}` }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: color.chatAccent, marginBottom: '10px' }}>Enterprise RAG</div>
          <button onClick={handleNewChat} className="chat-page-button chat-page-button-primary" style={{ width: '100%', justifyContent: 'center' }}>
            <Plus size={15} /> New chat
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '10px 12px 4px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: color.textTertiary, pointerEvents: 'none' }} />
            <input type="text" placeholder="Search chats..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              style={{ width: '100%', padding: '6px 8px 6px 28px', fontSize: '12px', border: `1px solid ${color.border}`, borderRadius: '6px', background: '#f9f7f4', color: color.textPrimary, outline: 'none', boxSizing: 'border-box' }} />
          </div>
        </div>

        {/* Group by */}
        <div style={{ padding: '6px 14px 8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '11px', color: color.textTertiary }}>Group by:</span>
          <button onClick={() => setGroupBy('none')} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '20px', border: `1px solid ${groupBy === 'none' ? color.chatAccent : color.border}`, background: groupBy === 'none' ? color.chatAccentSoft : 'transparent', color: groupBy === 'none' ? color.chatAccent : color.textSecondary, cursor: 'pointer' }}>None</button>
          <button onClick={() => setGroupBy('date')} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '20px', border: `1px solid ${groupBy === 'date' ? color.chatAccent : color.border}`, background: groupBy === 'date' ? color.chatAccentSoft : 'transparent', color: groupBy === 'date' ? color.chatAccent : color.textSecondary, cursor: 'pointer' }}>Date</button>
        </div>

        {isAdmin && (
          <button onClick={() => navigate('/documents')} className="chat-page-sidebar-link" style={{ margin: '0 8px 4px', borderRadius: '6px' }}>
            <ArrowLeft size={14} /> Dashboard
          </button>
        )}

        {/* Chat list */}
        <div className="chat-page-sidebar-list">
          {filteredConversations.length === 0 && searchQuery && (
            <div style={{ fontSize: '12px', color: color.textTertiary, textAlign: 'center', padding: '20px 0' }}>No chats found</div>
          )}
          {groupBy === 'none' ? filteredConversations.map((c) => (
            <div key={c.id} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <button
                onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
                className={`chat-page-chat-item ${c.id === activeId ? 'active' : ''}`}
                style={{ flex: 1, overflow: 'hidden' }}
              >
                <MessageSquare size={14} />
                <span className="chat-page-chat-title">{c.title}</span>
              </button>
              <button onClick={(e) => { e.stopPropagation(); setMenuOpenId(menuOpenId === c.id ? null : c.id) }}
                style={{ position: 'absolute', right: '4px', background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px', color: color.textTertiary, opacity: menuOpenId === c.id || c.id === activeId ? 1 : 0, transition: 'opacity 0.1s' }}
                onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                onMouseLeave={e => { if (menuOpenId !== c.id && c.id !== activeId) e.currentTarget.style.opacity = '0' }}
              >
                <MoreHorizontal size={14} />
              </button>
              {menuOpenId === c.id && (
                <div style={{ position: 'absolute', right: '4px', top: '100%', background: 'white', border: `1px solid ${color.border}`, borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.1)', zIndex: 50, minWidth: '160px', padding: '4px' }}>
                  <button onClick={() => { const t = prompt('Rename chat:', c.title); if (t) handleRename(c.id, t); setMenuOpenId(null) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: color.textPrimary, borderRadius: '6px' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f5f3ef'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  ><Pencil size={13} /> Rename</button>
                  <button onClick={() => { handleDelete(c.id); setMenuOpenId(null) }}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px', color: '#c00', borderRadius: '6px' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#fff0f0'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  ><Trash2 size={13} /> Delete</button>
                </div>
              )}
            </div>
          )) : Object.entries(groupedConversations).map(([group, chats]) => (
            <div key={group}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: color.textTertiary, textTransform: 'uppercase', letterSpacing: '0.05em', padding: '8px 10px 4px' }}>{group}</div>
              {(chats as Conversation[]).map((c) => (
                <div key={c.id} style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <button onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
                    className={`chat-page-chat-item ${c.id === activeId ? 'active' : ''}`} style={{ flex: 1 }}>
                    <MessageSquare size={14} />
                    <span className="chat-page-chat-title">{c.title}</span>
                  </button>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className="chat-page-sidebar-footer">
          <button onClick={handleLogout} className="chat-page-sidebar-link" aria-label="Log out">
            <LogOut size={15} strokeWidth={2} /> Log out
          </button>
        </div>
      </aside>"""
    
    content = content[:idx] + new_aside + content[end:]
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
