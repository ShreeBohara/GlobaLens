import React from 'react';
import { createPortal } from 'react-dom';
import { NewsPoint } from '../types';
import { format } from 'date-fns';

interface Props { news:NewsPoint|null; onClose:()=>void; }

const NewsModal:React.FC<Props>=({news,onClose})=>{
  if(!news) return null;
  return createPortal(
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm grid place-items-center z-50 px-4">
      <div className="bg-midnight text-white w-full max-w-md rounded-3xl p-8 relative animate-fadeIn border border-white/10">
        <button onClick={onClose} aria-label="Close" className="absolute top-4 right-4 text-xl text-gray-400 hover:text-white">✕</button>
        <h3 className="text-2xl font-bold mb-2">{news.title}</h3>
        <p className="text-xs text-gray-400 mb-4">{format(new Date(news.timestamp),'PPpp')}</p>
        <p className="leading-relaxed mb-6">{news.summary}</p>
        <a href={news.url} target="_blank" rel="noopener noreferrer" className="text-neon underline">Read full article ↗</a>
      </div>
    </div>,
    document.body
  );
};
export default NewsModal;