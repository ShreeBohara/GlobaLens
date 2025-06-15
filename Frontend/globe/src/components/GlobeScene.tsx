import React, { useRef, useEffect, useCallback } from 'react';
import Globe from 'react-globe.gl';
import * as THREE from 'three';
import { NewsPoint } from '../types';

/** Convert lat/lon to a unit-sphere THREE.Vector3 (for back-face culling). */
const geoToVec = (lat: number, lng: number) =>
  new THREE.Vector3().setFromSphericalCoords(
    1,
    THREE.MathUtils.degToRad(90 - lat),
    THREE.MathUtils.degToRad(lng)
  );

interface Props {
  data: NewsPoint[];
  circleRadius: number;
  onSelect: (p: NewsPoint) => void;
  onPointsInViewChange: (pts: NewsPoint[]) => void;
  onInteractionStart: () => void;
  onInteractionEnd: () => void;
}

const GlobeScene: React.FC<Props> = ({
  data,
  circleRadius,
  onSelect,
  onPointsInViewChange,
  onInteractionStart,
  onInteractionEnd
}) => {
  const globeRef = useRef<any>(null);

  /** Re-compute which points sit inside the fixed selector circle. */
  const updatePointsInView = useCallback(() => {
    const globe = globeRef.current;
    if (!globe) return;

    const dom = globe.renderer().domElement as HTMLCanvasElement;
    const rect = dom.getBoundingClientRect();
    const cx   = rect.left + rect.width  / 2;
    const cy   = rect.top  + rect.height / 2;

    const camera = globe.camera();
    const camDir = camera.position.clone().normalize();

    const pts = data.filter(p => {
      /* Hide points on the far side of the globe. */
      if (camDir.dot(geoToVec(p.latitude, p.longitude)) < 0) return false;

      const screen = globe.getScreenCoords(p.latitude, p.longitude);
      if (!screen) return false;

      const dx = screen.x + rect.left - cx;
      const dy = screen.y + rect.top  - cy;
      return Math.hypot(dx, dy) <= circleRadius;
    });

    onPointsInViewChange(pts);
  }, [data, circleRadius, onPointsInViewChange]);

  /* Re-run when camera moves. */
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;

    const controls = globe.controls();
    const onMove   = () => requestAnimationFrame(updatePointsInView);

    controls.addEventListener('change', onMove);
    updatePointsInView();            // initial pass

    return () => controls.removeEventListener('change', onMove);
  }, [updatePointsInView]);

  /* Re-run when data changes (new fetch). */
  useEffect(updatePointsInView, [data, updatePointsInView]);

  /* Re-run on window resize. */
  useEffect(() => {
    const onResize = () => updatePointsInView();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [updatePointsInView]);

  return (
    <Globe
      ref={globeRef}
      className="h-full w-full"
      backgroundColor="#00061a"
      globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
      bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"

      /* PERFORMANCE: one instanced mesh instead of thousands of meshes */
      pointsMerge={true}

      /* Points */
      pointsData={data}
      pointLat="latitude"
      pointLng="longitude"
      pointRadius={0.2}
      pointColor={() => '#32ff7e'}
      onPointClick={p => onSelect(p as NewsPoint)}

      /* Drag feedback */
      onPointerDown={onInteractionStart}
      onPointerUp={onInteractionEnd}
      onGlobeReady={updatePointsInView}
    />
  );
};

export default GlobeScene;
