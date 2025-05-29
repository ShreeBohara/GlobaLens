// GlobeScene.tsx
import React, { useRef, useEffect, useState, useCallback } from 'react';
import GlobeController from 'react-globe.gl';
import { NewsPoint } from '../types';
import * as THREE from 'three';
// MODIFIED: Removed tiles-provider import
// import { getRasterTile } from 'tiles-provider';

// geoToVec function remains the same
const geoToVec = (lat: number, lng: number) =>
  new THREE.Vector3().setFromSphericalCoords(
    1,
    THREE.MathUtils.degToRad(90 - lat),
    THREE.MathUtils.degToRad(lng)
  );

interface Props {
  data: NewsPoint[];
  onSelect: (d: NewsPoint) => void;
  onPointsInViewChange: (points: NewsPoint[]) => void;
  circleRadius?: number;
  onInteractionStart?: () => void;
  onInteractionEnd?: () => void;
}

const GlobeScene: React.FC<Props> = ({
  data,
  onSelect,
  onPointsInViewChange,
  circleRadius = 75, // This default is overridden by App.tsx
  onInteractionStart,
  onInteractionEnd,
}) => {
  const globeRef = useRef<GlobeController>(null);
  const [globeReady, setGlobeReady] = useState(false);

  useEffect(() => {
    if (!globeRef.current) return;
    // Reset to a common initial view
    globeRef.current.pointOfView({ lat: 20, lng: -30, alt: 2.5 });
    const globe = globeRef.current;
    const checkIfReady = () => {
      if (globe.scene()) { setGlobeReady(true); } else { setTimeout(checkIfReady, 100); }
    };
    checkIfReady();
    console.log("GlobeScene: Reverted to static globe images (blue marble).");
  }, []);


  // updatePointsInView and other useEffects related to it remain the same
  const updatePointsInView = useCallback(() => {
    if (!globeRef.current || !globeRef.current.scene()) return;
    const globe = globeRef.current;
    const rendererDomElement = globe.renderer().domElement;
    if (!rendererDomElement) return;
    const rect = rendererDomElement.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const camera = globe.camera();
    if (!camera || !camera.position) return;
    const camDir = camera.position.clone().normalize();
    const effectiveRadius = circleRadius * 0.85;
    const next = data.filter(p => {
      if (camDir.dot(geoToVec(p.latitude, p.longitude)) < 0) return false;
      const screenCoords = globe.getScreenCoords(p.latitude, p.longitude);
      if (!screenCoords) return false;
      const { x, y } = screenCoords;
      const dx = x + rect.left - cx;
      const dy = y + rect.top - cy;
      return Math.hypot(dx, dy) <= effectiveRadius;
    });
    onPointsInViewChange(next);
  }, [data, circleRadius, onPointsInViewChange]);

  useEffect(() => {
    if (!globeRef.current || !globeReady) return;
    const globeInstance = globeRef.current;
    const controls = globeInstance.controls();
    const handleStart = () => { if (onInteractionStart) onInteractionStart(); };
    const handleEnd = () => { if (onInteractionEnd) onInteractionEnd(); requestAnimationFrame(updatePointsInView); };
    if (controls) { controls.addEventListener('start', handleStart); controls.addEventListener('end', handleEnd); }
    return () => { if (controls) { controls.removeEventListener('start', handleStart); controls.removeEventListener('end', handleEnd); }};
  }, [globeReady, onInteractionStart, onInteractionEnd, updatePointsInView]);

  useEffect(() => {
    if (!globeRef.current || !globeReady) return;
    const controls = globeRef.current.controls();
    if (!controls) return;
    const handleChange = () => { requestAnimationFrame(updatePointsInView); };
    controls.addEventListener('change', handleChange);
    updatePointsInView(); // Initial calculation
    return () => { if (controls) { controls.removeEventListener('change', handleChange); }};
  }, [globeReady, updatePointsInView]);

  useEffect(() => { if (globeReady) { updatePointsInView(); } }, [data, globeReady, updatePointsInView]);

  useEffect(() => {
    const handleResize = () => { if (globeReady) { updatePointsInView(); }};
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [globeReady, updatePointsInView]);


  return (
    <GlobeController
      ref={globeRef}
      className="h-full w-full"
      // MODIFIED: Restored original background color
      backgroundColor="#00061a"

      // MODIFIED: Restored original globeImageUrl
      globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
      // MODIFIED: Restored original bumpImageUrl
      bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"

      // MODIFIED: Ensure tileImageUrl is null
      tileImageUrl={null}

      showAtmosphere={true}
      atmosphereColor="#3d91ff"
      atmosphereAltitude={0.15}

      // Point settings
      pointsData={data}
      pointLat="latitude"
      pointLng="longitude"
      pointRadius={0.2}
      pointColor={() => '#32ff7e'}
      pointAltitude={0} // This keeps the points flat on the surface
      onPointClick={(p) => onSelect(p as NewsPoint)}
    />
  );
};

export default GlobeScene;
