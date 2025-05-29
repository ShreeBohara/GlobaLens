// src/components/NewsListPanel.tsx
import React from 'react';
import { NewsPoint } from '../types';
import { format } from 'date-fns';
import clsx from 'clsx';

// ... (interface remains the same)

const NewsListPanel: React.FC<NewsListPanelProps> = ({ news, onSelect, className }) => {
  const displayNews = news.slice(0, 3);
  const hasMore = news.length > 10;

  return (
    <aside
      // ... (className logic remains the same)
    >
      {/* ... (header remains the same) */}

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* ... (empty message remains the same) */}
        {news.length > 0 &&
          displayNews.map(item => (
            <div
              key={item.GLOBALEVENTID} // Use a unique key from the data
              className="bg-white/5 rounded-xl p-3 cursor-pointer hover:bg-white/15 transition-colors"
              onClick={() => onSelect(item)}
            >
              <h3 className="font-medium text-sm text-white line-clamp-2">{item.title}</h3>
              <p className="text-xs text-gray-300 mt-0.5">
                {format(new Date(item.timestamp), 'MMM d, yyyy')}
              </p>
              {/* MODIFIED: Display AvgTone */}
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                <span className="px-2 py-0.5 rounded-full bg-blue-500/30 text-xs text-blue-200">
                  Avg Tone: {item.avgTone.toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        {/* ... (hasMore message remains the same) */}
      </div>
    </aside>
  );
};

export default NewsListPanel;