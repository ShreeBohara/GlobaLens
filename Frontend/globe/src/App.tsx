// src/App.tsx
import React, { useMemo, useState, useCallback, useEffect } from 'react';
import GlobeScene from './components/GlobeScene';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import NewsModal from './components/NewsModal';
import CircleSelector from './components/CircleSelector';
import NewsListPanel from './components/NewsListPanel';
import { NewsPoint } from './types';
import { parseISO } from 'date-fns'; // Keep if still used, otherwise remove

// Helper function to transform MongoDB data (from 'articles' collection) to our NewsPoint type
const transformData = (mongoDoc: any): NewsPoint => ({
  _id: mongoDoc._id, // Already has $oid structure from backend
  title: mongoDoc.title || mongoDoc.SOURCEURL || 'No Title Available', // Use title, fallback to SOURCEURL or default
  summary: mongoDoc.summary || mongoDoc.text || 'No summary available.', // Use summary from backend, fallback to text or default
  url: mongoDoc.url || mongoDoc.SOURCEURL || '#', // Use url, fallback to SOURCEURL or default
  latitude: mongoDoc.latitude,
  longitude: mongoDoc.longitude,
  // Ensure timestamp is correctly parsed and then converted to ISO string
  timestamp: mongoDoc.SQLDATE ? new Date(mongoDoc.SQLDATE).toISOString() : new Date().toISOString(),
  // avgTone is removed as per new type
  // GLOBALEVENTID is removed
});


export default function App() {
  const [displayedNews, setDisplayedNews] = useState<NewsPoint[]>([]);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [selected, setSelected] = useState<NewsPoint | null>(null);
  const [pointsInView, setPointsInView] = useState<NewsPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('Loading initial news data...');
  const [currentSearchKeyword, setCurrentSearchKeyword] = useState<string | null>(null);
  const [isAnimatingSelector, setIsAnimatingSelector] = useState(false);
  const [userStoppedDragging, setUserStoppedDragging] = useState(false);

  const circleRadius = 35;

  const fetchNews = useCallback(async (searchParams: { q?: string; from?: string; to?: string; fetchAll?: boolean }) => {
    const params = new URLSearchParams();
    let isFetchingAll = searchParams.fetchAll || false;
    
    if (searchParams.q && searchParams.q.trim() !== "") params.append('q', searchParams.q.trim());
    if (searchParams.from) params.append('from', searchParams.from);
    if (searchParams.to) params.append('to', searchParams.to);

    // Corrected typo: search_params.to -> searchParams.to
    if (!isFetchingAll && params.toString() === "" && (!searchParams.q && !searchParams.from && !searchParams.to)) {
        setDisplayedNews([]);
        setMessage('Please enter a search term or select a date range to find news.');
        setIsLoading(false); 
        return;
    }
    
    setIsLoading(true);
    setMessage(isFetchingAll ? 'Loading all news data...' : 'Fetching data...');
    try {
      const response = await fetch(`http://127.0.0.1:5001/api/news?${params.toString()}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Network response was not ok');
      }
      
      const data = await response.json();
      // Ensure latitude and longitude are not null or undefined before transformation
      const validData = data.results.filter((item: any) => item.latitude != null && item.longitude != null && item.SQLDATE != null);
      const transformed = validData.map(transformData);
      
      setDisplayedNews(transformed);

      if (data.limit_applied && data.count >= data.limit_applied && !isFetchingAll) {
        setMessage(`Showing first ${data.count} results (limit reached). Please refine your search or date range.`);
      } else if (data.count === 0) {
        setMessage(`No results found for your criteria.`);
      } else {
        setMessage(`Found ${data.count} results.`);
      }

    } catch (error: any) {
      console.error("Failed to fetch news:", error);
      setMessage(`Error: ${error.message || 'Could not fetch data.'}`);
      setDisplayedNews([]); 
    } finally {
      setIsLoading(false);
    }
  }, []); 

  useEffect(() => {
    fetchNews({ fetchAll: true });
  }, [fetchNews]);

  const handleSearch = useCallback((keyword: string) => {
    const trimmedKeyword = keyword.trim();
    setCurrentSearchKeyword(trimmedKeyword); 
    fetchNews({ q: trimmedKeyword, from, to }); 
  }, [from, to, fetchNews]);
  
  useEffect(() => {
    if (from || to || currentSearchKeyword) {
        fetchNews({ q: currentSearchKeyword || undefined, from, to });
    } else if (!currentSearchKeyword && !from && !to) {
        // This condition means all filters were cleared after an initial load/search
        // Re-fetch all data when filters are cleared by the user
        fetchNews({ fetchAll: true }); 
    }
  }, [from, to, currentSearchKeyword, fetchNews]);


  const handleInteractionStart = useCallback(() => {
    setIsAnimatingSelector(true);
    setUserStoppedDragging(false);
  }, []);

  const handleInteractionEnd = useCallback(() => {
    setUserStoppedDragging(true);
  }, []);

  const handlePointsInViewChange = useCallback((points: NewsPoint[]) => {
    setPointsInView(points);
    if (userStoppedDragging) {
      setIsAnimatingSelector(false);
      setUserStoppedDragging(false); 
    }
  }, [userStoppedDragging]);

  const debugInfo = useMemo(() => ({
    totalPoints: displayedNews.length,
    pointsInView: pointsInView.length,
    message: message,
  }), [displayedNews.length, pointsInView.length, message]);

  return (
    <div className="h-screen w-screen relative overflow-hidden bg-black flex flex-col">
      <div className="flex-grow relative">
        <GlobeScene
          data={displayedNews}
          onSelect={setSelected}
          onPointsInViewChange={handlePointsInViewChange}
          circleRadius={circleRadius}
          onInteractionStart={handleInteractionStart}
          onInteractionEnd={handleInteractionEnd}
        />

        <CircleSelector
          size={circleRadius * 2}
          isAnimating={isAnimatingSelector && displayedNews.length > 0} 
        />

        <div
          className="fixed left-4 top-1/2 -translate-y-1/2 z-40 flex flex-col h-3/5"
          style={{ width: '280px' }}
        >
          <NewsListPanel news={pointsInView} onSelect={setSelected} className="h-full" />
        </div>

        <div className="fixed right-4 top-4 bottom-4 z-40 flex flex-col space-y-4" style={{ width: '280px' }}>
          <ChatPanel onSearch={handleSearch} onApply={() => {}} className="flex-[2_2_0%] min-h-[150px]" />
          <Sidebar from={from} to={to} setFrom={setFrom} setTo={setTo} className="flex-[1_1_0%] min-h-[200px] w-full"/>
        </div>
      </div>
      
      <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white text-xs p-2 text-center shadow-xl z-50">
        <span>{isLoading ? 'Loading news...' : debugInfo.message}</span>
        <span className="ml-4">| In View: {debugInfo.pointsInView} / Displayed: {debugInfo.totalPoints}</span>
      </div>

      <NewsModal news={selected} onClose={() => setSelected(null)} />
    </div>
  );
}