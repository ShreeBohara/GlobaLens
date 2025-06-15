import React, { useMemo, useState, useCallback, useEffect } from 'react';
import GlobeScene     from './components/GlobeScene';
import Sidebar        from './components/Sidebar';
import ChatPanel      from './components/ChatPanel';
import NewsModal      from './components/NewsModal';
import CircleSelector from './components/CircleSelector';
import NewsListPanel  from './components/NewsListPanel';
import { NewsPoint }  from './types';

const API_ROOT      = 'http://127.0.0.1:5001';
const DEFAULT_LIMIT = 2000;

/* map raw Mongo doc to typed object used in UI */
const transformData = (doc: any): NewsPoint => ({
  _id:       doc._id,
  title:     doc.title    || doc.SOURCEURL || 'No Title',
  summary:   doc.summary  || doc.text      || 'No summary.',
  url:       doc.url      || doc.SOURCEURL || '#',
  latitude:  doc.latitude,
  longitude: doc.longitude,
  timestamp: doc.SQLDATE ? new Date(doc.SQLDATE).toISOString()
                          : new Date().toISOString()
});

export default function App() {
  // ── state ──────────────────────────────────────────────────────────────────
  const [displayedNews, setDisplayedNews] = useState<NewsPoint[]>([]);
  const [pointsInView,  setPointsInView]  = useState<NewsPoint[]>([]);
  const [selected,      setSelected]      = useState<NewsPoint|null>(null);
  const [from, setFrom] = useState('');   const [to, setTo] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message,   setMessage]   = useState('Loading initial news data…');
  const [isDragging,setIsDragging]= useState(false);

  const circleRadius = 35;

  // ── generic fetch helper ───────────────────────────────────────────────────
  const performFetch = useCallback(
    async (endpoint: string, humanLabel = '') => {
      setIsLoading(true);
      setMessage(humanLabel || 'Fetching data…');
      try {
        const res  = await fetch(`${API_ROOT}${endpoint}`);
        if (!res.ok) throw new Error(await res.text());
        const { results, count, limit_applied } = await res.json();

        const clean = (results as any[])
          .filter(d => d.latitude != null && d.longitude != null)
          .map(transformData);

        setDisplayedNews(clean);
        setMessage(
          count === 0        ? 'No results found.'
        : limit_applied      ? `Showing first ${count} results – zoom or refine.`
        : humanLabel         ? `Found ${count} results for “${humanLabel}”.`
                             : `Loaded ${count} articles.`
        );
      } catch (err:any) {
        console.error(err);
        setDisplayedNews([]);
        setMessage('Error fetching data.');
      } finally { setIsLoading(false); }
    }, []);

  // ── dedicated wrappers ------------------------------------------------------
  const fetchInitial = useCallback(() => {
    /* fire-and-forget so useEffect doesn’t return a Promise */
    performFetch(`/api/news?limit=${DEFAULT_LIMIT}`);
  }, [performFetch]);

  const fetchVector = useCallback(
    (q: string) =>
      performFetch(`/api/vector_search?q=${encodeURIComponent(q)}&limit=${DEFAULT_LIMIT}`, q),
    [performFetch]);

  const fetchByDate = useCallback(
    () => {
      if (!from && !to) return;
      const sp = new URLSearchParams({ limit: DEFAULT_LIMIT.toString() });
      if (from) sp.append('from', from);
      if (to)   sp.append('to',   to);
      performFetch(`/api/news?${sp.toString()}`,
                   `dates between ${from || '…'} and ${to || '…'}`);
    },
    [from, to, performFetch]);

  // ── lifecycle --------------------------------------------------------------
  useEffect(() => { fetchInitial(); }, [fetchInitial]);

  // ── globe-selector callbacks ----------------------------------------------
  const handlePointsInView = useCallback((pts: NewsPoint[]) => setPointsInView(pts), []);

  // ── render -----------------------------------------------------------------
  return (
    <div className="h-screen w-screen relative overflow-hidden bg-black flex flex-col">
      <div className="flex-grow relative">
        <GlobeScene
          data={displayedNews}
          onSelect={setSelected}
          onPointsInViewChange={handlePointsInView}
          circleRadius={circleRadius}
          onInteractionStart={() => setIsDragging(true)}
          onInteractionEnd={()   => setIsDragging(false)}
        />
        <CircleSelector size={circleRadius * 2} isAnimating={isDragging} />

        {/* left list ---- */}
        <div className="fixed left-4 top-1/2 -translate-y-1/2 z-40 h-3/5 w-[280px]">
          <NewsListPanel news={pointsInView} onSelect={setSelected} className="h-full" />
        </div>

        {/* right side controls ---- */}
        <div className="fixed right-4 top-4 bottom-4 z-40 flex flex-col space-y-4 w-[280px]">
          <ChatPanel
            onSearch={fetchVector}
            onClear={fetchInitial}
            isLoading={isLoading}
            botMessage={message}
          />
          <Sidebar
            from={from} to={to}
            setFrom={setFrom} setTo={setTo}
            onClear={() => { setFrom(''); setTo(''); fetchInitial(); }}
            onFilter={fetchByDate}
          />
        </div>
      </div>

      {/* small debug bar */}
      <div className="absolute bottom-0 left-[296px] right-[296px] bg-black/70 text-white text-xs p-2 text-center shadow-xl z-50">
        {isLoading ? 'Loading…' : message}
        <span className="ml-4">| In view: {pointsInView.length} / {displayedNews.length}</span>
      </div>

      <NewsModal news={selected} onClose={() => setSelected(null)} />
    </div>
  );
}


