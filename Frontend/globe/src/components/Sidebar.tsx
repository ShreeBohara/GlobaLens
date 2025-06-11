// src/components/Sidebar.tsx
import React from 'react';
import { format } from 'date-fns';
import clsx from 'clsx';

interface SidebarProps {
  from: string;
  to: string;
  setFrom: (v: string) => void;
  setTo: (v: string) => void;
  onClear: () => void;
  onFilter: () => void; // New prop to trigger filtering
  className?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ from, to, setFrom, setTo, onClear, onFilter, className }) => (
  <aside
    className={clsx(
      "backdrop-blur-md bg-white/10 border border-white/20 rounded-3xl shadow-2xl p-5 flex flex-col gap-5",
      className
    )}
  >
    <h2 className="text-lg font-semibold text-white text-center">Filter by Date</h2>

    <div className="flex flex-col gap-1.5">
      <label htmlFor="date-from" className="text-sm text-gray-200">From</label>
      <input
        id="date-from"
        type="date"
        value={from}
        onChange={e => setFrom(e.target.value)}
        className="bg-white/20 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:ring-1 focus:ring-neon appearance-none"
        style={{ colorScheme: 'dark' }}
      />
    </div>

    <div className="flex flex-col gap-1.5">
      <label htmlFor="date-to" className="text-sm text-gray-200">To</label>
      <input
        id="date-to"
        type="date"
        value={to}
        onChange={e => setTo(e.target.value)}
        className="bg-white/20 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:ring-1 focus:ring-neon appearance-none"
        style={{ colorScheme: 'dark' }}
      />
    </div>
    
    <div className="flex items-center space-x-2 mt-2">
       {/* UPDATED: Button for filtering */}
      <button
        onClick={onFilter}
        className="flex-1 bg-blue-500/50 hover:bg-blue-500/80 text-white font-semibold text-sm py-2 rounded-lg transition-colors"
      >
        Filter
      </button>
      {/* UPDATED: Button for clearing dates */}
      <button
        onClick={onClear}
        className="flex-1 bg-gray-500/40 hover:bg-gray-500/60 text-white font-semibold text-sm py-2 rounded-lg transition-colors"
      >
        Clear Dates
      </button>
    </div>

    <p className="text-xs text-gray-300 mt-auto text-center">
      Showing news from <br />
      <span className="font-medium text-neon">{from ? format(new Date(from), 'PP') : 'Anytime'}</span> to <span className="font-medium text-neon">{to ? format(new Date(to), 'PP') : 'Anytime'}</span>
    </p>
  </aside>
);

export default Sidebar;