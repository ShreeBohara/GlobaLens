// src/types.ts

// This interface now reflects the data from MongoDB
export interface NewsPoint {
  _id: { $oid: string }; // MongoDB ObjectId
  GLOBALEVENTID: number;
  // Use the URL as the title, as requested
  title: string;
  // A short summary or description (we can use Actor names for this)
  summary: string;
  url: string;
  latitude: number;
  longitude: number;
  timestamp: string;      // From SQLDATE
  // Use AvgTone as the primary category/metric
  avgTone: number;
}