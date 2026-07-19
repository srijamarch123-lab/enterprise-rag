content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

old = '<textarea value={driveJson} onChange={e => setDriveJson(e.target.value)} placeholder=\'{ "type": "service_account", ... }\' rows={8} style={{ width: \'100%\', border: `1px solid ${color.border}`, borderRadius: radius.sm, padding: \'10px\', fontSize: \'12px\', fontFamily: \'monospace\', resize: \'vertical\', outline: \'none\', boxSizing: \'border-box\' }} />'

new = '''<input type="file" accept=".json" onChange={e => { const file = e.target.files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = (ev) => setDriveJson(ev.target?.result as string); reader.readAsText(file); }} style={{ width: \'100%\', padding: \'10px\', border: `1px solid ${color.border}`, borderRadius: radius.sm, fontSize: \'13px\', cursor: \'pointer\' }} />
            {driveJson && <div style={{ fontSize: \'11px\', color: color.chatAccent, marginTop: \'4px\' }}>JSON file loaded successfully</div>}'''

if old in content:
    content = content.replace(old, new)
    open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
