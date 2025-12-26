import { useEffect, useRef, useState, useCallback } from 'react';

// Simple noise function for hand-painted effect
const createNoise = () => {
  const permutation = [];
  for (let i = 0; i < 256; i++) permutation[i] = i;
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [permutation[i], permutation[j]] = [permutation[j], permutation[i]];
  }
  const p = [...permutation, ...permutation];
  
  const fade = t => t * t * t * (t * (t * 6 - 15) + 10);
  const lerp = (t, a, b) => a + t * (b - a);
  const grad = (hash, x) => (hash & 1 ? x : -x);
  
  return (x) => {
    const X = Math.floor(x) & 255;
    x -= Math.floor(x);
    const u = fade(x);
    return lerp(u, grad(p[X], x), grad(p[X + 1], x - 1));
  };
};

export default function MondrianGenerator() {
  const canvasRef = useRef(null);
  const [seed, setSeed] = useState(Date.now());
  
  const generate = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    
    // Seeded random
    let s = seed;
    const random = () => {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      return s / 0x7fffffff;
    };
    
    const noise = createNoise();
    
    // Colors palette
    const colors = {
      red: ['#c41e3a', '#d32f2f', '#b71c1c', '#e53935'],
      yellow: ['#f9a825', '#fbc02d', '#f57f17', '#ffeb3b'],
      blue: ['#1565c0', '#1976d2', '#0d47a1', '#2196f3'],
      black: ['#1a1a1a', '#212121', '#0d0d0d'],
      white: ['#fafafa', '#f5f5f5', '#eeeeee', '#fff8e1'],
      lightBlue: ['#bbdefb', '#90caf9', '#e3f2fd', '#b3e5fc'],
      lightGray: ['#eceff1', '#e0e0e0', '#f5f5f5']
    };
    
    const pickColor = (arr) => arr[Math.floor(random() * arr.length)];
    
    // Fill background with off-white texture
    ctx.fillStyle = '#f8f6f0';
    ctx.fillRect(0, 0, W, H);
    
    // Add paper texture
    for (let i = 0; i < 50000; i++) {
      const x = random() * W;
      const y = random() * H;
      const alpha = random() * 0.03;
      ctx.fillStyle = `rgba(0,0,0,${alpha})`;
      ctx.fillRect(x, y, 1, 1);
    }
    
    // Generate grid divisions
    const xDivs = [0];
    const yDivs = [0];
    
    let x = 0;
    while (x < W - 60) {
      x += 40 + random() * 120;
      if (x < W - 30) xDivs.push(x);
    }
    xDivs.push(W);
    
    let y = 0;
    while (y < H - 60) {
      y += 40 + random() * 120;
      if (y < H - 30) yDivs.push(y);
    }
    yDivs.push(H);
    
    // Create cells
    const cells = [];
    for (let i = 0; i < xDivs.length - 1; i++) {
      for (let j = 0; j < yDivs.length - 1; j++) {
        cells.push({
          x: xDivs[i],
          y: yDivs[j],
          w: xDivs[i + 1] - xDivs[i],
          h: yDivs[j + 1] - yDivs[j],
          color: null
        });
      }
    }
    
    // Merge some cells randomly
    const mergedCells = [...cells];
    for (let i = 0; i < 5; i++) {
      if (random() > 0.3) {
        const idx = Math.floor(random() * mergedCells.length);
        const cell = mergedCells[idx];
        // Try to expand
        if (random() > 0.5 && cell.x + cell.w < W - 20) {
          cell.w += 30 + random() * 60;
        }
        if (random() > 0.5 && cell.y + cell.h < H - 20) {
          cell.h += 30 + random() * 60;
        }
      }
    }
    
    // Assign colors to some cells
    const colorKeys = ['red', 'yellow', 'blue', 'black', 'lightBlue', 'lightGray'];
    mergedCells.forEach(cell => {
      if (random() > 0.6) {
        cell.color = colorKeys[Math.floor(random() * colorKeys.length)];
      }
    });
    
    // Draw wobbly filled rectangle
    const drawPaintedRect = (x, y, w, h, colorKey) => {
      const baseColor = pickColor(colors[colorKey]);
      const wobble = 3;
      const offset = random() * 1000;
      
      // Draw with slight offset variations for painterly effect
      for (let layer = 0; layer < 3; layer++) {
        ctx.save();
        ctx.beginPath();
        
        const points = [];
        const steps = 20;
        
        // Top edge
        for (let i = 0; i <= steps; i++) {
          const px = x + (w * i / steps);
          const py = y + noise(px * 0.05 + offset) * wobble;
          points.push([px, py]);
        }
        // Right edge
        for (let i = 0; i <= steps; i++) {
          const px = x + w + noise((y + h * i / steps) * 0.05 + offset + 100) * wobble;
          const py = y + (h * i / steps);
          points.push([px, py]);
        }
        // Bottom edge
        for (let i = steps; i >= 0; i--) {
          const px = x + (w * i / steps);
          const py = y + h + noise(px * 0.05 + offset + 200) * wobble;
          points.push([px, py]);
        }
        // Left edge
        for (let i = steps; i >= 0; i--) {
          const px = x + noise((y + h * i / steps) * 0.05 + offset + 300) * wobble;
          const py = y + (h * i / steps);
          points.push([px, py]);
        }
        
        ctx.moveTo(points[0][0], points[0][1]);
        points.forEach(([px, py]) => ctx.lineTo(px, py));
        ctx.closePath();
        
        ctx.fillStyle = baseColor;
        ctx.globalAlpha = layer === 0 ? 0.9 : 0.3;
        ctx.fill();
        ctx.restore();
      }
      
      // Add texture within the rectangle
      ctx.save();
      ctx.beginPath();
      ctx.rect(x - 5, y - 5, w + 10, h + 10);
      ctx.clip();
      
      for (let i = 0; i < w * h * 0.01; i++) {
        const tx = x + random() * w;
        const ty = y + random() * h;
        ctx.fillStyle = `rgba(255,255,255,${random() * 0.1})`;
        ctx.fillRect(tx, ty, random() * 3, random() * 3);
      }
      ctx.restore();
    };
    
    // Draw colored cells
    mergedCells.forEach(cell => {
      if (cell.color) {
        drawPaintedRect(
          cell.x + 2 + random() * 4,
          cell.y + 2 + random() * 4,
          cell.w - 4 - random() * 4,
          cell.h - 4 - random() * 4,
          cell.color
        );
      }
    });
    
    // Draw wobbly line
    const drawWobblyLine = (x1, y1, x2, y2, thickness) => {
      const len = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
      const steps = Math.max(20, len / 5);
      const offset = random() * 1000;
      
      ctx.save();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      
      // Draw multiple strokes for painterly effect
      for (let stroke = 0; stroke < 3; stroke++) {
        ctx.beginPath();
        ctx.strokeStyle = stroke === 0 ? '#0a0a0a' : `rgba(10,10,10,${0.3 - stroke * 0.1})`;
        ctx.lineWidth = thickness * (1 - stroke * 0.2) + random() * 0.5;
        
        for (let i = 0; i <= steps; i++) {
          const t = i / steps;
          const px = x1 + (x2 - x1) * t;
          const py = y1 + (y2 - y1) * t;
          
          // Add wobble perpendicular to line direction
          const angle = Math.atan2(y2 - y1, x2 - x1) + Math.PI / 2;
          const wobbleAmt = noise(i * 0.3 + offset) * 2 * (1 + stroke * 0.5);
          
          const wx = px + Math.cos(angle) * wobbleAmt;
          const wy = py + Math.sin(angle) * wobbleAmt;
          
          if (i === 0) ctx.moveTo(wx, wy);
          else ctx.lineTo(wx, wy);
        }
        ctx.stroke();
      }
      ctx.restore();
    };
    
    // Draw grid lines with variation
    const drawnLines = new Set();
    
    // Vertical lines
    xDivs.slice(1, -1).forEach(xPos => {
      const thickness = 2 + random() * 4;
      const startY = random() * 20 - 10;
      const endY = H + random() * 20 - 10;
      
      // Sometimes break the line
      if (random() > 0.2) {
        drawWobblyLine(xPos, startY, xPos, endY, thickness);
      } else {
        const breakPoint = H * (0.3 + random() * 0.4);
        drawWobblyLine(xPos, startY, xPos, breakPoint - 20, thickness);
        drawWobblyLine(xPos, breakPoint + 20, xPos, endY, thickness);
      }
    });
    
    // Horizontal lines
    yDivs.slice(1, -1).forEach(yPos => {
      const thickness = 2 + random() * 4;
      const startX = random() * 20 - 10;
      const endX = W + random() * 20 - 10;
      
      if (random() > 0.2) {
        drawWobblyLine(startX, yPos, endX, yPos, thickness);
      } else {
        const breakPoint = W * (0.3 + random() * 0.4);
        drawWobblyLine(startX, yPos, breakPoint - 20, yPos, thickness);
        drawWobblyLine(breakPoint + 20, yPos, endX, yPos, thickness);
      }
    });
    
    // Add some extra short lines for complexity
    for (let i = 0; i < 8; i++) {
      if (random() > 0.5) {
        const isHorizontal = random() > 0.5;
        const thickness = 1.5 + random() * 3;
        
        if (isHorizontal) {
          const yPos = 50 + random() * (H - 100);
          const startX = random() * W * 0.3;
          const length = 50 + random() * 150;
          drawWobblyLine(startX, yPos, startX + length, yPos, thickness);
        } else {
          const xPos = 50 + random() * (W - 100);
          const startY = random() * H * 0.3;
          const length = 50 + random() * 150;
          drawWobblyLine(xPos, startY, xPos, startY + length, thickness);
        }
      }
    }
    
    // Add subtle overall texture
    ctx.globalCompositeOperation = 'multiply';
    for (let i = 0; i < 20000; i++) {
      const tx = random() * W;
      const ty = random() * H;
      ctx.fillStyle = `rgba(200,190,170,${random() * 0.02})`;
      ctx.fillRect(tx, ty, 2, 2);
    }
    ctx.globalCompositeOperation = 'source-over';
    
  }, [seed]);
  
  useEffect(() => {
    generate();
  }, [generate]);
  
  const regenerate = () => setSeed(Date.now());
  
  const download = () => {
    const canvas = canvasRef.current;
    const link = document.createElement('a');
    link.download = `mondrian-${seed}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };
  
  return (
    <div className="min-h-screen bg-neutral-900 flex flex-col items-center justify-center p-4 gap-4">
      <h1 className="text-white text-xl font-light tracking-wide">Procedural Mondrian</h1>
      
      <canvas
        ref={canvasRef}
        width={600}
        height={600}
        className="border border-neutral-700 shadow-2xl"
        style={{ maxWidth: '100%', height: 'auto' }}
      />
      
      <div className="flex gap-3">
        <button
          onClick={regenerate}
          className="px-6 py-2 bg-white text-neutral-900 font-medium rounded hover:bg-neutral-200 transition-colors"
        >
          Generate New
        </button>
        <button
          onClick={download}
          className="px-6 py-2 bg-neutral-700 text-white font-medium rounded hover:bg-neutral-600 transition-colors"
        >
          Download PNG
        </button>
      </div>
      
      <p className="text-neutral-500 text-sm">Seed: {seed}</p>
    </div>
  );
}
