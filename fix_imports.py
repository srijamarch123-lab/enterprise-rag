content = open('frontend/src/pages/ChatPage.tsx', 'r', encoding='utf-8', errors='ignore').read()

idx = content.find("from 'lucide-react'")
line_start = content.rfind('\n', 0, idx) + 1
old_line = content[line_start:idx + len("from 'lucide-react'")]
print('Current import line:', repr(old_line[:100]))

new_line = "import { Send, Plus, MessageSquare, ArrowLeft, LogOut, FileText, Loader2, Mic, ThumbsUp, ThumbsDown, HardDrive, Upload, X, MoreHorizontal, Pencil, Trash2, Search, PanelLeftClose, PanelLeftOpen } from 'lucide-react'"

content = content[:line_start] + new_line + content[idx + len("from 'lucide-react'"):]
open('frontend/src/pages/ChatPage.tsx', 'w', encoding='utf-8').write(content)
print('Done')
