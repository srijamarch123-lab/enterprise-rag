content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = """      <aside className="chat-page-sidebar">
        {isAdmin && (
          <button onClick={() => navigate('/documents')} className="chat-page-sidebar-link" aria-label="Back to dashboard">
            <ArrowLeft size={15} strokeWidth={2} />
            Back to dashboard
          </button>
        )}
        <div className="chat-page-sidebar-top">
          <button onClick={handleNewChat} className="chat-page-button chat-page-button-primary">
            <Plus size={16} strokeWidth={2.25} />
            New chat
          </button>
        </div>
        <div className="chat-page-sidebar-list">
          <div className="chat-page-sidebar-heading">Chats</div>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => { setActiveId(c.id); void loadSessionMessages(c.id) }}
              className={`chat-page-chat-item ${c.id === activeId ? 'active' : ''}`}
              aria-current={c.id === activeId ? 'page' : undefined}
            >
              <MessageSquare size={14} />
              <span className="chat-page-chat-title">{c.title}</span>
            </button>
          ))}
        </div>
        <div className="chat-page-sidebar-footer">
          <button onClick={handleLogout} className="chat-page-sidebar-link" aria-label="Log out">
            <LogOut size={15} strokeWidth={2} />
            Log out
          </button>
        </div>
      </aside>"""

new = """      <aside className="chat-page-sidebar">
        {/* Header */}
        <div style={{ padding: '16px 14px 10px', borderBottom: `1px solid ${color.border}` }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: color.chatAccent, marginBottom: '10px', letterSpacing: '-0.01em' }}>Enterprise RAG</div>
          <button onClick={handleNewChat} className="chat-page-button chat-page-button-primary" style={{ width: '100%', justifyContent: 'center' }}>
            <Plus size={15} strokeWidth={2.25} /> New chat
          </button>
        </div>

        {/* Search */}
        <div style={{ padding: '10px 12px 0' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: color.textTertiary, pointerEvents: 'none' }} />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ width: '100%', padding: '6px 8px 6px 28px', fontSize: '12px', border: `1px solid ${color.border}`, borderRadius: '6px', background: '#f9f7f4', color: color.textPrimary, outline: 'none', boxSizing: 'border-box' }}
            />
          </div>
        </div>

        {/* Group by */}
        <div style={{ padding: '8px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '11px', color: color.textTertiary }}>Group by:</span>
          <button onClick={() => setGroupBy('none')} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '20px', border: `1px solid ${groupBy === 'none' ? color.chatAccent : color.border}`, background: groupBy === 'none' ? color.chatAccentSoft : 'transparent', color: groupBy === 'none' ? color.chatAccent : color.textSecondary, cursor: 'pointer' }}>None</button>
          <button onClick={() => setGroupBy('date')} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '20px', border: `1px solid ${groupBy === 'date' ? color.chatAccent : color.border}`, background: groupBy === 'date' ? color.chatAccentSoft : 'transparent', color: groupBy === 'date' ? color.chatAccent : color.textSecondary, cursor: 'pointer' }}>Date</button>
        </div>

        {isAdmin && (
          <button onClick={() => navigate('/documents')} className="chat-page-sidebar-link" style={{ margin: '0 8px 4px', borderRadius: '6px' }} aria-label="Back to dashboard">
            <ArrowLeft size={14} strokeWidth={2} /> Dashboard
          </button>
        )}

        {/* Chat list */}
        <div className="chat-page-sidebar-list" style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
          {filteredConversations.length === 0 && (
            <div style={{ fontSize: '12px', color: color.textTertiary, textAlign: 'center', padding: '20px 0' }}>No chats found</div>
          )}
          {groupBy === 'none' ? (
            filteredConversations.map((c) => (
              <ChatItem key={c.id} c={c} activeId={activeId} setActiveId={setActiveId} loadSessionMessages={loadSessionMessages} menuOpenId={menuOpenId} setMenuOpenId={setMenuOpenId} handleRename={handleRename} handleDelete={handleDelete} color={color} />
            ))
          ) : (
            Object.entries(groupedConversations).map(([group, chats]) => (
              <div key={group}>
                <div style={{ fontSize: '10px', fontWeight: 600, color: color.textTertiary, textTransform: 'uppercase', letterSpacing: '0.05em', padding: '8px 4px 4px' }}>{group}</div>
                {(chats as any[]).map((c: any) => (
                  <ChatItem key={c.id} c={c} activeId={activeId} setActiveId={setActiveId} loadSessionMessages={loadSessionMessages} menuOpenId={menuOpenId} setMenuOpenId={setMenuOpenId} handleRename={handleRename} handleDelete={handleDelete} color={color} />
                ))}
              </div>
            ))
          )}
        </div>

        <div className="chat-page-sidebar-footer">
          <button onClick={handleLogout} className="chat-page-sidebar-link" aria-label="Log out">
            <LogOut size={15} strokeWidth={2} /> Log out
          </button>
        </div>
      </aside>"""

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
    idx = content.find('chat-page-sidebar">')
    print('Sidebar found at:', idx)
