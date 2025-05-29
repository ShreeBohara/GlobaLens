// src/components/CircleSelector.tsx
import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface CircleSelectorProps {
  size?: number;
  isAnimating?: boolean;
}

const CircleSelector: React.FC<CircleSelectorProps> = ({ size = 150, isAnimating = false }) => {
  const numRings = 3; // Number of sonar rings

  return (
    <div
      className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-30"
      style={{ width: size, height: size }}
    >
      {/* Main persistent circle (the border and center dot) */}
      <div
        className="absolute top-0 left-0 w-full h-full rounded-full border-2 border-white/50 flex items-center justify-center"
      >
        <div className="w-1 h-1 rounded-full bg-white"></div> {/* Center dot */}
      </div>

      {/* Animated Sonar Rings using Framer Motion */}
      <AnimatePresence>
        {isAnimating &&
          Array.from({ length: numRings }).map((_, i) => (
            <motion.div
              key={`sonar_ring_${i}`}
              // MODIFIED: Changed border-neon to border-cyan-400 for reliable color
              className="absolute top-0 left-0 w-full h-full rounded-full border border-cyan-400"
              initial={{
                scale: 1,
                opacity: 0.7,
              }}
              animate={{
                scale: 1.6,
                opacity: 0,
              }}
              transition={{
                duration: 2.0,
                ease: "circOut",
                delay: i * 0.5, 
                repeat: Infinity,
                repeatType: "loop",
              }}
            />
          ))}
      </AnimatePresence>
    </div>
  );
};

export default CircleSelector;