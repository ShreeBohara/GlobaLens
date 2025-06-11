// src/types.ts

export interface NewsPoint {
  _id: { $oid: string }; // MongoDB ObjectId, primary key
  title: string;          // From articles.title
  summary: string;        // From articles.summary or articles.text
  url: string;            // From articles.url
  latitude: number;       // From articles.latitude
  longitude: number;      // From articles.longitude
  timestamp: string;      // From articles.SQLDATE
  // GLOBALEVENTID is removed, use _id.$oid for keys
  // avgTone is removed, assumed not available in 'articles' collection
}