// ChatPanel.tsx
import React, { useRef, useState, useEffect } from 'react';
import { NewsPoint } from '../types';
import clsx from 'clsx';

interface Msg { role: 'user' | 'bot'; text: string; }
interface ChatPanelProps {
  onSearch: (kw: string) => NewsPoint[];
  onApply: (res: NewsPoint[]) => void;
  className?: string; // Allow className to be passed
}

const ChatPanel: React.FC<ChatPanelProps> = ({ onSearch, onApply, className }) => {
  const [messages, setMessages] = useState<Msg[]>([{ role: 'bot', text: 'Hi! Ask me for topics like "crime news" or "war reports".' }]);
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = () => {
    const q = input.trim(); if (!q) return;
    const newMessages: Msg[] = [...messages, { role: 'user', text: q }];

    const res = onSearch(q);
    onApply(res);

    const replyText = res.length ?
      `Found ${res.length} article(s). Globe updated!` :
      `Sorry, I couldn't find anything about "${q}".`;

    setMessages([...newMessages, { role: 'bot', text: replyText }]);
    setInput('');
  };

  return (
    // MODIFIED: Removed inline flexBasis, using passed className for flex sizing
    <aside
      className={clsx(
        "backdrop-blur-md bg-white/10 border border-white/20 rounded-3xl shadow-2xl flex flex-col overflow-hidden",
        className // Apply passed className (e.g., for flex-grow properties)
      )}
      // style={{ minHeight: '150px' }} // minHeight can be kept or adjusted
    >
      <div className="p-3 border-b border-white/10">
        <h2 className="text-md font-semibold text-white">Search News</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((m, i) => (
          <p key={i} className={clsx('relative max-w-[90%] text-xs leading-relaxed px-3 py-1.5 rounded-xl before:content-[""] before:absolute before:w-0 before:h-0', {
            'ml-auto bg-neon text-black before:right-[-5px] before:top-1.5 before:border-l-6 before:border-l-neon before:border-y-6 before:border-y-transparent': m.role === 'user',
            'bg-white/20 text-white before:left-[-5px] before:top-1.5 before:border-r-6 before:border-r-white/20 before:border-y-6 before:border-y-transparent': m.role === 'bot'
          })}>{m.text}</p>
        ))}
        <div ref={endRef} />
      </div>
      <form className="p-2.5 border-t border-white/10" onSubmit={e => { e.preventDefault(); send(); }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question…"
          className="w-full bg-white/20 text-xs px-2.5 py-1.5 rounded-lg text-white placeholder:text-gray-300 outline-none focus:ring-1 focus:ring-neon"
        />
      </form>
    </aside>
  );
};
export default ChatPanel;