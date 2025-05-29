// Sidebar.tsx
import React from 'react';
import { format } from 'date-fns';
import clsx from 'clsx'; // Import clsx

interface SidebarProps {
  from: string;
  to: string;
  setFrom: (v: string) => void;
  setTo: (v: string) => void;
  className?: string; // Allow className to be passed
}

const Sidebar: React.FC<SidebarProps> = ({ from, to, setFrom, setTo, className }) => (
  // MODIFIED: Removed fixed positioning classes, using passed className for flex sizing
  // Removed inline width style, can be controlled by parent or new classes if needed
  <aside
    className={clsx(
      "backdrop-blur-md bg-white/10 border border-white/20 rounded-3xl shadow-2xl p-5 flex flex-col gap-5", // Removed z-50 as it might not be needed, or can be added back if stacking issues occur
      className // Apply passed className (e.g., for flex properties)
    )}
    // style={{ width: '280px' }} // This can be removed if width is handled by parent column, or set to w-full
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

    <p className="text-xs text-gray-300 mt-auto text-center">
      Showing news from <br />
      <span className="font-medium text-neon">{from ? format(new Date(from), 'PP') : 'Anytime'}</span> to <span className="font-medium text-neon">{to ? format(new Date(to), 'PP') : 'Anytime'}</span>
    </p>
  </aside>
);

export default Sidebar;