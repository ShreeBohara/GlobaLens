// src/App.tsx
import React, { useMemo, useState, useCallback, useEffect } from 'react';
import GlobeScene from './components/GlobeScene';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import NewsModal from './components/NewsModal';
import CircleSelector from './components/CircleSelector';
import NewsListPanel from './components/NewsListPanel';
import { NewsPoint } from './types';

const transformData = (mongoDoc: any): NewsPoint => ({
  _id: mongoDoc._id,
  title: mongoDoc.title || mongoDoc.SOURCEURL || 'No Title Available',
  summary: mongoDoc.summary || mongoDoc.text || 'No summary available.',
  url: mongoDoc.url || mongoDoc.SOURCEURL || '#',
  latitude: mongoDoc.latitude,
  longitude: mongoDoc.longitude,
  timestamp: mongoDoc.SQLDATE ? new Date(mongoDoc.SQLDATE).toISOString() : new Date().toISOString(),
});

export default function App() {
  const [displayedNews, setDisplayedNews] = useState<NewsPoint[]>([]);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [selected, setSelected] = useState<NewsPoint | null>(null);
  const [pointsInView, setPointsInView] = useState<NewsPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('Loading initial news data...');
  const [isAnimatingSelector, setIsAnimatingSelector] = useState(false);
  const [userStoppedDragging, setUserStoppedDragging] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const circleRadius = 35;

  const performFetch = useCallback(async (url: string, query: string = '') => {
    setIsLoading(true);
    // Message state is now primarily for the bottom bar, ChatPanel will manage its own messages
    setMessage(query ? `Searching for "${query}"...` : 'Fetching data...');
    setSearchQuery(query);
    try {
      const response = await fetch(url);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Network response was not ok');
      }
      const data = await response.json();
      const validData = data.results.filter((item: any) => item.latitude != null && item.longitude != null && item.SQLDATE != null);
      const transformed = validData.map(transformData);
      setDisplayedNews(transformed);

      let resultMessage = '';
      if (data.limit_applied) {
        resultMessage = `Showing first ${data.count} results. Refine your search.`;
      } else if (data.count === 0) {
        resultMessage = query ? `No results found for "${query}".` : 'No results found.';
      } else {
        resultMessage = query ? `Found ${data.count} results for "${query}".` : `Found ${data.count} results.`;
      }
      setMessage(resultMessage);
    } catch (error: any) {
      console.error("Failed to fetch news:", error);
      const errorMessage = error.message || 'Could not fetch data.';
      setMessage(`Error: ${errorMessage}`);
      setDisplayedNews([]);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  const fetchAllNews = useCallback(() => {
    const url = `http://127.0.0.1:5001/api/news?fetchAll=true`;
    performFetch(url);
  }, [performFetch]);

  const fetchVectorNews = useCallback((query: string) => {
    const url = `http://127.0.0.1:5001/api/vector_search?q=${encodeURIComponent(query)}`;
    performFetch(url, query);
  }, [performFetch]);

  // Initial load
  useEffect(() => { fetchAllNews(); }, [fetchAllNews]);
  
  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    fetchAllNews();
  }, [fetchAllNews]);

  const handleClearDates = useCallback(() => {
    setFrom('');
    setTo('');
    fetchAllNews();
  }, [fetchAllNews]);

  const handleDateFilter = useCallback(() => {
      if (!from && !to) return;
      const searchParams = new URLSearchParams();
      if(from) searchParams.append('from', from);
      if(to) searchParams.append('to', to);
      const url = `http://127.0.0.1:5001/api/news?${searchParams.toString()}`;
      performFetch(url, `dates between ${from} and ${to}`);
  }, [from, to, performFetch]);

  const handleInteractionStart = useCallback(() => setIsAnimatingSelector(true), []);
  const handleInteractionEnd = useCallback(() => setUserStoppedDragging(true), []);
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
        <CircleSelector size={circleRadius * 2} isAnimating={isAnimatingSelector} />
        <div className="fixed left-4 top-1/2 -translate-y-1/2 z-40 flex flex-col h-3/5" style={{ width: '280px' }}>
          <NewsListPanel news={pointsInView} onSelect={setSelected} className="h-full" />
        </div>
        <div className="fixed right-4 top-4 bottom-4 z-40 flex flex-col space-y-4" style={{ width: '280px' }}>
          {/* UPDATED: Pass isLoading prop to ChatPanel */}
          <ChatPanel 
            onSearch={fetchVectorNews}
            onClear={handleClearSearch}
            isLoading={isLoading}
            botMessage={message}
            className="flex-[2_2_0%] min-h-[150px]" 
          />
          <Sidebar 
            from={from} to={to} setFrom={setFrom} setTo={setTo} 
            onClear={handleClearDates} onFilter={handleDateFilter}
            className="flex-[1_1_0%] min-h-[200px] w-full"
          />
        </div>
      </div>
      
      <div 
        className="absolute bottom-0 bg-black/70 text-white text-xs p-2 text-center shadow-xl z-50"
        style={{ left: '296px', right: '296px' }}
      >
        <span>{isLoading ? 'Loading...' : debugInfo.message}</span>
        <span className="ml-4">| In View: {debugInfo.pointsInView} / Displayed: {debugInfo.totalPoints}</span>
      </div>

      <NewsModal news={selected} onClose={() => setSelected(null)} />
    </div>
  );
}