import React, { useRef, useEffect, useState } from 'react'; // Added useEffect, useState
import { createPortal } from 'react-dom';
import { NewsPoint } from '../types';
import { format } from 'date-fns';

interface Props {
  news: NewsPoint | null;
  onClose: () => void;
}

const NewsModal: React.FC<Props> = ({ news, onClose }) => {
  if (!news) return null;

  const scrollableContentRef = useRef<HTMLDivElement>(null);
  const [isContentScrollable, setIsContentScrollable] = useState(false);

  useEffect(() => {
    const checkScrollable = () => {
      if (scrollableContentRef.current) {
        const { scrollHeight, clientHeight } = scrollableContentRef.current;
        setIsContentScrollable(scrollHeight > clientHeight);
      } else {
        setIsContentScrollable(false);
      }
    };

    // Check after a short delay to ensure content is rendered and dimensions are accurate.
    // This is important because scrollHeight might not be correct immediately on render.
    const timerId = setTimeout(checkScrollable, 100);

    // Re-check on window resize if the modal width changes, affecting text flow.
    window.addEventListener('resize', checkScrollable);

    return () => {
      clearTimeout(timerId);
      window.removeEventListener('resize', checkScrollable);
    };
  }, [news]); // Re-calculate when the news item (and thus its summary) changes.

  return createPortal(
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm grid place-items-center z-50 px-4 py-8">
      <div className="bg-midnight text-white w-full max-w-md rounded-3xl p-8 relative animate-fadeIn border border-white/10 flex flex-col max-h-[90vh]">
        <div className="flex-shrink-0">
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute top-4 right-4 text-xl text-gray-400 hover:text-white z-10"
          >
            ✕
          </button>
          <h3 className="text-2xl font-bold mb-2">{news.title}</h3>
          <p className="text-xs text-gray-400 mb-4">
            {news.timestamp ? format(new Date(news.timestamp), 'PPpp') : 'Date not available'}
          </p>
        </div>

        {/* Scrollable content area */}
        <div
          ref={scrollableContentRef}
          className="flex-grow overflow-y-auto pr-2 relative" // Added `relative` for positioning the gradient
        >
          <p className="leading-relaxed mb-6 whitespace-pre-wrap">{news.summary}</p>
          
          {/* Scroll indicator: Gradient fade */}
          {isContentScrollable && (
            <div
              className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-midnight to-transparent pointer-events-none mr-2"
              // `mr-2` ensures the gradient doesn't overlay the scrollbar track area (due to parent's pr-2)
              // `h-16` (64px) creates a taller, more noticeable fade. Adjust as needed.
              // `from-midnight` ensures the fade matches the modal background.
            />
          )}
        </div>

        <div className="flex-shrink-0 mt-auto pt-4">
          <a
            href={news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-neon underline hover:text-glow-neon transition-colors"
          >
            Read full article ↗
          </a>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default NewsModal;