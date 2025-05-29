// src/App.tsx
import React, { useMemo, useState, useCallback, useEffect } from 'react';
import GlobeScene from './components/GlobeScene';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import NewsModal from './components/NewsModal';
import CircleSelector from './components/CircleSelector';
import NewsListPanel from './components/NewsListPanel';
import { NewsPoint } from './types';
import { isAfter, isBefore, parseISO } from 'date-fns'; // Added parseISO

// Helper function to transform MongoDB data to our NewsPoint type
const transformData = (mongoDoc: any): NewsPoint => ({
  _id: mongoDoc._id,
  GLOBALEVENTID: mongoDoc.GLOBALEVENTID,
  title: mongoDoc.SOURCEURL, // Use source URL as title
  summary: `Event between ${mongoDoc.Actor1Name || 'N/A'} and ${mongoDoc.Actor2Name || 'N/A'}. Goldstein Scale: ${mongoDoc.GoldsteinScale}`,
  url: mongoDoc.SOURCEURL,
  latitude: mongoDoc.ActionGeo_Lat,
  longitude: mongoDoc.ActionGeo_Long,
  // Ensure timestamp is correctly parsed and then converted to ISO string
  timestamp: mongoDoc.SQLDATE ? new Date(mongoDoc.SQLDATE).toISOString() : new Date().toISOString(),
  avgTone: mongoDoc.AvgTone,
});


export default function App() {
  // State to hold only the news currently displayed on the globe
  const [displayedNews, setDisplayedNews] = useState<NewsPoint[]>([]);
  
  const [from, setFrom] = useState(''); // Stores date as yyyy-MM-DD string
  const [to, setTo] = useState('');   // Stores date as yyyy-MM-DD string
  
  const [selected, setSelected] = useState<NewsPoint | null>(null);
  const [pointsInView, setPointsInView] = useState<NewsPoint[]>([]);
  
  // Loading and message states
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('Loading initial news data...'); // Updated initial message
  const [currentSearchKeyword, setCurrentSearchKeyword] = useState<string | null>(null);


  const [isAnimatingSelector, setIsAnimatingSelector] = useState(false);
  const [userStoppedDragging, setUserStoppedDragging] = useState(false);

  const circleRadius = 35;

  // Central data fetching function
  const fetchNews = useCallback(async (searchParams: { q?: string; from?: string; to?: string; fetchAll?: boolean }) => {
    const params = new URLSearchParams();
    let isFetchingAll = searchParams.fetchAll || false;
    
    // Only add parameters if they have a value
    if (searchParams.q && searchParams.q.trim() !== "") params.append('q', searchParams.q.trim());
    if (searchParams.from) params.append('from', searchParams.from);
    if (searchParams.to) params.append('to', searchParams.to);

    // If no actual search criteria (keyword or valid date range), AND not fetching all, don't fetch.
    if (!isFetchingAll && params.toString() === "" && (!searchParams.q && !searchParams.from && !search_params.to)) {
        setDisplayedNews([]);
        setMessage('Please enter a search term or select a date range to find news.');
        setIsLoading(false); 
        return;
    }
    
    // If fetching all, ensure the backend knows not to apply its usual limit.
    // This might involve a specific parameter or the absence of other parameters.
    // For this example, we'll assume the backend handles an empty query string as "fetch all (no limit)".
    // You'll need to adjust your backend `app.py` to remove the MAX_RESULTS_LIMIT
    // when no 'q', 'from', or 'to' params are present.

    setIsLoading(true);
    setMessage(isFetchingAll ? 'Loading all news data...' : 'Fetching data...');
    try {
      const response = await fetch(`http://127.0.0.1:5001/api/news?${params.toString()}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Network response was not ok');
      }
      
      const data = await response.json();
      const validData = data.results.filter((item: any) => item.ActionGeo_Lat != null && item.ActionGeo_Long != null);
      const transformed = validData.map(transformData);
      
      setDisplayedNews(transformed);

      if (data.limit_applied && data.count >= data.limit_applied && !isFetchingAll) { // Only show limit message if not fetching all
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

  // Effect for initial data load
  useEffect(() => {
    // Fetch all data when the component mounts
    fetchNews({ fetchAll: true });
  }, [fetchNews]); // fetchNews is memoized, so this runs once.


  // Search handler (called by ChatPanel)
  const handleSearch = useCallback((keyword: string) => {
    const trimmedKeyword = keyword.trim();
    setCurrentSearchKeyword(trimmedKeyword); 
    // When searching, we are no longer fetching "all", so fetchAll is false (or omitted)
    fetchNews({ q: trimmedKeyword, from, to }); 
  }, [from, to, fetchNews]);
  
  // Effect to re-fetch when date filters change
  useEffect(() => {
    // This effect now only triggers if 'from' or 'to' dates change.
    // The initial load is handled by the separate useEffect above.
    // It will use the currentSearchKeyword if one exists.
    if (from || to || currentSearchKeyword) { // Fetch if any filter is active
        fetchNews({ q: currentSearchKeyword || undefined, from, to });
    } else if (!currentSearchKeyword && !from && !to) {
        // If all filters are cleared AFTER an initial load/search,
        // you might want to re-fetch all or clear. For now, let's fetch all again.
        // Or, set a message to prompt for new search.
        // Let's stick to re-fetching all if all filters are cleared by the user.
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
      {/* Main content area */}
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

        {/* Left Panel for NewsListPanel */}
        <div
          className="fixed left-4 top-1/2 -translate-y-1/2 z-40 flex flex-col h-3/5"
          style={{ width: '280px' }}
        >
          <NewsListPanel news={pointsInView} onSelect={setSelected} className="h-full" />
        </div>

        {/* Right Column for ChatPanel and Sidebar */}
        <div className="fixed right-4 top-4 bottom-4 z-40 flex flex-col space-y-4" style={{ width: '280px' }}>
          <ChatPanel onSearch={handleSearch} onApply={() => {}} className="flex-[2_2_0%] min-h-[150px]" />
          <Sidebar from={from} to={to} setFrom={setFrom} setTo={setTo} className="flex-[1_1_0%] min-h-[200px] w-full"/>
        </div>
      </div>
      
      {/* Footer for Status/Debug Info */}
      <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white text-xs p-2 text-center shadow-xl z-50">
        <span>{isLoading ? 'Loading news...' : debugInfo.message}</span>
        <span className="ml-4">| In View: {debugInfo.pointsInView} / Displayed: {debugInfo.totalPoints}</span>
      </div>

      <NewsModal news={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
