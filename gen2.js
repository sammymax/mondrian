import { useEffect, useRef, useState, useCallback } from 'react';

const createNoise = () => {
  const perm = [];
  for (let i = 0; i < 256; i++) perm[i] = i;
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [perm[i], perm[j]] = [perm[j], perm[i]];
  }
  const p = [...perm, ...perm];
  const fade = t => t * t * t * (t * (t * 6 - 15) + 10);
  const lerp = (t, a, b) => a + t * (b - a);
  const grad = (hash, x) => (hash & 1 ? x : -x);
  return (x) => {
    const X = Math.floor(x) & 255;
    x -= Math.floor(x);
    return lerp(fade(x), grad(p[X], x), grad(p[X + 1], x - 1));
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
    
    let s = seed;
    const random = () => {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      return s / 0x7fffffff;
    };
    
    const noise = createNoise();
    
    const colors = {
      red: ['#e31c25', '#ff1744', '#d50000', '#ff0022'],
      yellow: ['#ffeb00', '#ffd600', '#ffea00', '#ffe100'],
      blue: ['#0055ff', '#2979ff', '#0044cc', '#304ffe'],
      black: ['#1a1a1a', '#212121'],
      white: ['#fafafa', '#f5f5f5', '#fff8e1'],
      lightBlue: ['#40c4ff', '#00b0ff', '#80d8ff'],
      lightGray: ['#eceff1', '#e0e0e0']
    };
    
    const pick = arr => arr[Math.floor(random() * arr.length)];
    
    // Background
    ctx.fillStyle = '#f8f5ef';
    ctx.fillRect(0, 0, W, H);
    
    // Paper texture
    for (let i = 0; i < 40000; i++) {
      ctx.fillStyle = `rgba(0,0,0,${random() * 0.025})`;
      ctx.fillRect(random() * W, random() * H, 1, 1);
    }
    
    // Draw wobbly line segment
    const drawLine = (x1, y1, x2, y2, thickness) => {
      const len = Math.hypot(x2 - x1, y2 - y1);
      const steps = Math.max(15, len / 6);
      const off = random() * 1000;
      
      ctx.save();
      ctx.lineCap = 'round';
      
      for (let stroke = 0; stroke < 3; stroke++) {
        ctx.beginPath();
        ctx.strokeStyle = stroke === 0 ? '#0a0a0a' : `rgba(20,15,10,${0.25 - stroke * 0.08})`;
        ctx.lineWidth = thickness * (1 - stroke * 0.15) + random() * 0.3;
        
        for (let i = 0; i <= steps; i++) {
          const t = i / steps;
          let px = x1 + (x2 - x1) * t;
          let py = y1 + (y2 - y1) * t;
          
          const angle = Math.atan2(y2 - y1, x2 - x1) + Math.PI / 2;
          const wobble = noise(i * 0.25 + off) * 1.8;
          px += Math.cos(angle) * wobble;
          py += Math.sin(angle) * wobble;
          
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
      ctx.restore();
    };
    
    // Draw painted rectangle
    const drawRect = (x, y, w, h, colorKey) => {
      const col = pick(colors[colorKey]);
      const off = random() * 1000;
      const wobble = 2.5;
      
      for (let layer = 0; layer < 3; layer++) {
        ctx.save();
        ctx.beginPath();
        
        const pts = [];
        const st = 15;
        
        for (let i = 0; i <= st; i++) pts.push([x + w * i / st, y + noise(i * 0.4 + off) * wobble]);
        for (let i = 0; i <= st; i++) pts.push([x + w + noise(i * 0.4 + off + 50) * wobble, y + h * i / st]);
        for (let i = st; i >= 0; i--) pts.push([x + w * i / st, y + h + noise(i * 0.4 + off + 100) * wobble]);
        for (let i = st; i >= 0; i--) pts.push([x + noise(i * 0.4 + off + 150) * wobble, y + h * i / st]);
        
        ctx.moveTo(pts[0][0], pts[0][1]);
        pts.forEach(([px, py]) => ctx.lineTo(px, py));
        ctx.closePath();
        
        ctx.fillStyle = col;
        ctx.globalAlpha = layer === 0 ? 0.92 : 0.2;
        ctx.fill();
        ctx.restore();
      }
      
      // Texture
      ctx.save();
      ctx.beginPath();
      ctx.rect(x, y, w, h);
      ctx.clip();
      for (let i = 0; i < w * h * 0.008; i++) {
        ctx.fillStyle = `rgba(255,255,255,${random() * 0.12})`;
        ctx.fillRect(x + random() * w, y + random() * h, random() * 2 + 1, random() * 2 + 1);
      }
      ctx.restore();
    };
    
    // Generate ad-hoc lines (NOT a regular grid)
    const lines = [];
    
    // Some longer structural lines (sparse)
    const numLongLines = 2 + Math.floor(random() * 2);
    for (let i = 0; i < numLongLines; i++) {
      const isVert = random() > 0.5;
      const thickness = 2.5 + random() * 4;
      
      if (isVert) {
        const x = 60 + random() * (W - 120);
        const y1 = random() * 80 - 20;
        const y2 = H - random() * 80 + 20;
        // Maybe don't go full length
        const actualY1 = random() > 0.3 ? y1 : 50 + random() * 150;
        const actualY2 = random() > 0.3 ? y2 : H - 50 - random() * 150;
        lines.push({ x1: x, y1: actualY1, x2: x, y2: actualY2, t: thickness, type: 'vert' });
      } else {
        const y = 60 + random() * (H - 120);
        const x1 = random() * 80 - 20;
        const x2 = W - random() * 80 + 20;
        const actualX1 = random() > 0.3 ? x1 : 50 + random() * 150;
        const actualX2 = random() > 0.3 ? x2 : W - 50 - random() * 150;
        lines.push({ x1: actualX1, y1: y, x2: actualX2, y2: y, t: thickness, type: 'horiz' });
      }
    }
    
    // Medium length segments (sparse)
    const numMedLines = 3 + Math.floor(random() * 3);
    for (let i = 0; i < numMedLines; i++) {
      const isVert = random() > 0.5;
      const thickness = 2 + random() * 3;
      const length = 80 + random() * 200;
      
      if (isVert) {
        const x = 30 + random() * (W - 60);
        const y = random() * (H - length);
        lines.push({ x1: x, y1: y, x2: x, y2: y + length, t: thickness, type: 'vert' });
      } else {
        const y = 30 + random() * (H - 60);
        const x = random() * (W - length);
        lines.push({ x1: x, y1: y, x2: x + length, y2: y, t: thickness, type: 'horiz' });
      }
    }
    
    // Short accent lines (sparse)
    const numShortLines = 4 + Math.floor(random() * 5);
    for (let i = 0; i < numShortLines; i++) {
      const isVert = random() > 0.5;
      const thickness = 1.5 + random() * 2.5;
      const length = 30 + random() * 80;
      
      if (isVert) {
        const x = 20 + random() * (W - 40);
        const y = random() * (H - length);
        lines.push({ x1: x, y1: y, x2: x, y2: y + length, t: thickness, type: 'vert' });
      } else {
        const y = 20 + random() * (H - 40);
        const x = random() * (W - length);
        lines.push({ x1: x, y1: y, x2: x + length, y2: y, t: thickness, type: 'horiz' });
      }
    }
    
    // Tiny dashes (sparse)
    const numDashes = 2 + Math.floor(random() * 4);
    for (let i = 0; i < numDashes; i++) {
      const isVert = random() > 0.5;
      const thickness = 1 + random() * 2;
      const length = 15 + random() * 40;
      
      if (isVert) {
        const x = random() * W;
        const y = random() * (H - length);
        lines.push({ x1: x, y1: y, x2: x, y2: y + length, t: thickness, type: 'vert' });
      } else {
        const y = random() * H;
        const x = random() * (W - length);
        lines.push({ x1: x, y1: y, x2: x + length, y2: y, t: thickness, type: 'horiz' });
      }
    }
    
    // Place color blocks more frequently with vibrant colors
    const colorKeys = ['red', 'yellow', 'blue', 'red', 'yellow', 'blue', 'black', 'lightBlue'];
    const numBlocks = 10 + Math.floor(random() * 8);
    const blocks = [];
    
    for (let i = 0; i < numBlocks; i++) {
      const w = 40 + random() * 140;
      const h = 40 + random() * 140;
      const x = 20 + random() * (W - w - 40);
      const y = 20 + random() * (H - h - 40);
      const col = colorKeys[Math.floor(random() * colorKeys.length)];
      
      // Skip if too much overlap with existing blocks
      let overlap = false;
      for (const b of blocks) {
        const ox = Math.max(0, Math.min(x + w, b.x + b.w) - Math.max(x, b.x));
        const oy = Math.max(0, Math.min(y + h, b.y + b.h) - Math.max(y, b.y));
        if (ox * oy > w * h * 0.7) {
          overlap = true;
          break;
        }
      }
      
      if (!overlap) {
        blocks.push({ x, y, w, h, col });
      }
    }
    
    // Draw blocks first
    blocks.forEach(b => {
      if (b.col !== 'white') {
        drawRect(b.x, b.y, b.w, b.h, b.col);
      }
    });
    
    // Draw all lines on top
    lines.forEach(l => drawLine(l.x1, l.y1, l.x2, l.y2, l.t));
    
    // Final texture overlay
    ctx.globalCompositeOperation = 'multiply';
    for (let i = 0; i < 15000; i++) {
      ctx.fillStyle = `rgba(180,170,150,${random() * 0.015})`;
      ctx.fillRect(random() * W, random() * H, 2, 2);
    }
    ctx.globalCompositeOperation = 'source-over';
    
  }, [seed]);
  
  useEffect(() => {
    generate();
  }, [generate]);
  
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
          onClick={() => setSeed(Date.now())}
          className="px-6 py-2 bg-white text-neutral-900 font-medium rounded hover:bg-neutral-200 transition-colors"
        >
          Generate New
        </button>
        <button
          onClick={() => {
            const link = document.createElement('a');
            link.download = `mondrian-${seed}.png`;
            link.href = canvasRef.current.toDataURL('image/png');
            link.click();
          }}
          className="px-6 py-2 bg-neutral-700 text-white font-medium rounded hover:bg-neutral-600 transition-colors"
        >
          Download PNG
        </button>
      </div>
      
      <p className="text-neutral-500 text-sm">Seed: {seed}</p>
    </div>
  );
}
