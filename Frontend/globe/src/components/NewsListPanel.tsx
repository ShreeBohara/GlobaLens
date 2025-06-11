// src/components/NewsListPanel.tsx
import React from 'react';
import { NewsPoint } from '../types';
import { format } from 'date-fns';
import clsx from 'clsx';

interface NewsListPanelProps {
  news: NewsPoint[];
  onSelect: (d: NewsPoint) => void;
  className?: string;
}

const NewsListPanel: React.FC<NewsListPanelProps> = ({ news, onSelect, className }) => {
  const displayNews = news.slice(0, 10); // Show up to 10 news items
  const hasMore = news.length > 10;

  return (
    <aside
      className={clsx(
        "backdrop-blur-md bg-white/10 border border-white/20 rounded-3xl shadow-2xl flex flex-col overflow-hidden",
        className
      )}
    >
      <div className="p-3 border-b border-white/10">
        <h2 className="text-md font-semibold text-white text-center">News in View</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {news.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-4">No news articles in the current view. Try searching or adjusting the globe.</p>
        )}
        {news.length > 0 &&
          displayNews.map(item => (
            <div
              key={item._id.$oid} // Use MongoDB ObjectId for the key
              className="bg-white/5 rounded-xl p-3 cursor-pointer hover:bg-white/15 transition-colors"
              onClick={() => onSelect(item)}
            >
              <h3 className="font-medium text-sm text-white line-clamp-2">{item.title}</h3>
              <p className="text-xs text-gray-300 mt-0.5">
                {/* Ensure item.timestamp is a valid date string or Date object */}
                {item.timestamp ? format(new Date(item.timestamp), 'MMM d, yyyy') : 'Date not available'}
              </p>
              {/*
                The section that displayed AvgTone has been removed to prevent the error.
                If you have other relevant tags or info from 'articles' (e.g., keywords), 
                you can add them here. For example:
                {item.keywords && Array.isArray(item.keywords) && item.keywords.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {item.keywords.slice(0, 3).map(keyword => (
                      <span key={keyword} className="px-2 py-0.5 rounded-full bg-gray-500/30 text-xs text-gray-200">
                        {keyword}
                      </span>
                    ))}
                  </div>
                )}
              */}
            </div>
          ))}
        {hasMore && (
          <p className="text-xs text-gray-400 text-center pt-2">
            And {news.length - 10} more articles in view.
          </p>
        )}
      </div>
    </aside>
  );
};

export default NewsListPanel;