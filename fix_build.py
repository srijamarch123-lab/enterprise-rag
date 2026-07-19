content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

# Fix 1: Remove any remaining 'theme' references
if "const { color, font, radius } = theme" in content:
    content = content.replace("const { color, font, radius } = theme", "")
    print('Removed old theme destructure')

# Fix 2: Check line 10 for theme reference
lines = content.split('\n')
for i, line in enumerate(lines[:15], 1):
    print(f'Line {i}: {line[:100]}')

# Fix 3: Add Square to imports
old_import = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen } from 'lucide-react'"
new_import = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen, Square } from 'lucide-react'"
if old_import in content:
    content = content.replace(old_import, new_import)
    print('Square import added')
else:
    print('Import line not found')

open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
