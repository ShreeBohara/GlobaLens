// src/components/ChatPanel.tsx
import React, { useRef, useState, useEffect } from 'react';
import clsx from 'clsx';

interface Msg { id: number; role: 'user' | 'bot'; text: string; }
interface ChatPanelProps {
  onSearch: (kw: string) => void;
  onClear: () => void;
  isLoading: boolean; // New prop to track loading state
  botMessage: string;
  className?: string;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ onSearch, onClear, isLoading, botMessage, className }) => {
  const [messages, setMessages] = useState<Msg[]>([{ id: 0, role: 'bot', text: 'Hi! Ask me anything, like "war in Asia" or "tech innovations".' }]);
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // This effect updates the bot's final message once loading is complete
  useEffect(() => {
    if (!isLoading) {
      // Find the last message; if it's a "Searching..." placeholder, update it.
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage?.role === 'bot' && lastMessage.text === 'Searching...') {
          // Replace "Searching..." with the final message from the server
          return prev.slice(0, -1).concat({ ...lastMessage, text: botMessage });
        }
        return prev;
      });
    }
  }, [isLoading, botMessage]);

  const handleClear = () => {
    onClear();
    setMessages([{ id: Date.now(), role: 'bot', text: 'Search cleared. Ask me a new question!' }]);
  }

  const send = () => {
    const query = input.trim();
    if (!query) return;

    const timestamp = Date.now();
    // Add user message, then immediately add a "Searching..." placeholder for the bot
    setMessages(prev => [
      ...prev,
      { id: timestamp, role: 'user', text: query },
      { id: timestamp + 1, role: 'bot', text: 'Searching...' }
    ]);
    
    onSearch(query);
    setInput('');
  };

  return (
    <aside className={clsx("backdrop-blur-md bg-white/10 border border-white/20 rounded-3xl shadow-2xl flex flex-col overflow-hidden", className)}>
      <div className="p-3 border-b border-white/10 flex justify-between items-center">
        <h2 className="text-md font-semibold text-white">Semantic Search</h2>
        <button 
          onClick={handleClear} 
          className="text-xs text-cyan-300 hover:text-white transition-colors"
        >
          Clear Search
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((m) => (
          <div key={m.id} className={clsx('flex', {
            'justify-end': m.role === 'user',
            'justify-start': m.role === 'bot',
          })}>
            {/* FIXED: User message now has a distinct, beautiful style */}
            <p className={clsx('max-w-[90%] text-sm leading-relaxed px-3 py-2 rounded-xl shadow-lg', {
              'bg-cyan-500 text-white': m.role === 'user',
              'bg-white/20 text-white': m.role === 'bot'
            })}>{m.text}</p>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form className="p-2.5 border-t border-white/10" onSubmit={e => { e.preventDefault(); send(); }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question…"
          className="w-full bg-white/20 text-sm px-2.5 py-1.5 rounded-lg text-white placeholder:text-gray-300 outline-none focus:ring-1 focus:ring-cyan-400"
        />
      </form>
    </aside>
  );
};

export default ChatPanel;