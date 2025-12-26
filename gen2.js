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

// Parse hex to RGB
const hexToRgb = (hex) => {
  const v = parseInt(hex.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
};

// RGB to hex
const rgbToHex = (r, g, b) => 
  '#' + [r, g, b].map(x => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')).join('');

// Vary a color slightly
const varyColor = (hex, random, amount = 20) => {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(
    r + (random() - 0.5) * amount,
    g + (random() - 0.5) * amount,
    b + (random() - 0.5) * amount
  );
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
      red: ['#e31c25', '#ff1744', '#d50000'],
      yellow: ['#ffeb00', '#ffd600', '#ffea00'],
      blue: ['#0055ff', '#2979ff', '#0044cc'],
      black: ['#1a1a1a', '#212121'],
      lightBlue: ['#40c4ff', '#00b0ff', '#80d8ff'],
    };
    
    const pick = arr => arr[Math.floor(random() * arr.length)];
    
    // Background with subtle canvas texture
    ctx.fillStyle = '#f8f5ef';
    ctx.fillRect(0, 0, W, H);
    
    // Canvas weave texture
    for (let y = 0; y < H; y += 2) {
      for (let x = 0; x < W; x += 2) {
        const v = (noise(x * 0.1) * noise(y * 0.1) + 1) * 0.5;
        ctx.fillStyle = `rgba(0,0,0,${v * 0.03})`;
        ctx.fillRect(x, y, 2, 2);
      }
    }
    
    // Draw a single brush stroke
    const drawBrushStroke = (x1, y1, x2, y2, color, width, alpha) => {
      const len = Math.hypot(x2 - x1, y2 - y1);
      const steps = Math.max(10, len / 2);
      const angle = Math.atan2(y2 - y1, x2 - x1);
      const perpAngle = angle + Math.PI / 2;
      const off = random() * 1000;
      
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = color;
      
      // Draw multiple bristle lines
      const bristles = 3 + Math.floor(random() * 4);
      for (let b = 0; b < bristles; b++) {
        const bristleOffset = (b - bristles / 2) * (width / bristles) * 0.8;
        ctx.lineWidth = width / bristles * (0.5 + random() * 0.8);
        
        ctx.beginPath();
        for (let i = 0; i <= steps; i++) {
          const t = i / steps;
          // Taper at ends
          const taper = Math.sin(t * Math.PI) * 0.3 + 0.7;
          
          let px = x1 + (x2 - x1) * t;
          let py = y1 + (y2 - y1) * t;
          
          // Add wobble
          const wobble = noise(i * 0.3 + off + b * 10) * 3 * taper;
          px += Math.cos(perpAngle) * (bristleOffset + wobble);
          py += Math.sin(perpAngle) * (bristleOffset + wobble);
          
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
      ctx.restore();
    };
    
    // Paint a rectangle with brush strokes
    const paintRect = (x, y, w, h, colorKey) => {
      const baseColor = pick(colors[colorKey]);
      const [br, bg, bb] = hexToRgb(baseColor);
      
      // Decide brush direction (mostly horizontal or vertical)
      const horizontal = random() > 0.5;
      
      // Multiple layers of strokes
      const layers = 3;
      for (let layer = 0; layer < layers; layer++) {
        const layerAlpha = layer === 0 ? 0.7 : 0.4;
        
        // Stroke parameters for this layer
        const strokeWidth = 8 + random() * 12;
        const spacing = strokeWidth * (0.3 + random() * 0.3);
        
        if (horizontal) {
          // Horizontal strokes
          for (let sy = y + spacing; sy < y + h - spacing / 2; sy += spacing * (0.8 + random() * 0.4)) {
            // Vary color per stroke
            const strokeColor = rgbToHex(
              br + (random() - 0.5) * 35,
              bg + (random() - 0.5) * 35,
              bb + (random() - 0.5) * 35
            );
            
            // Stroke doesn't always go edge to edge
            const startX = x + random() * 10 - 5;
            const endX = x + w + random() * 10 - 5;
            const startY = sy + (random() - 0.5) * 4;
            const endY = sy + (random() - 0.5) * 8;
            
            drawBrushStroke(startX, startY, endX, endY, strokeColor, strokeWidth, layerAlpha);
          }
        } else {
          // Vertical strokes
          for (let sx = x + spacing; sx < x + w - spacing / 2; sx += spacing * (0.8 + random() * 0.4)) {
            const strokeColor = rgbToHex(
              br + (random() - 0.5) * 35,
              bg + (random() - 0.5) * 35,
              bb + (random() - 0.5) * 35
            );
            
            const startY = y + random() * 10 - 5;
            const endY = y + h + random() * 10 - 5;
            const startX = sx + (random() - 0.5) * 4;
            const endX = sx + (random() - 0.5) * 8;
            
            drawBrushStroke(startX, startY, startX + (endX - startX), endY, strokeColor, strokeWidth, layerAlpha);
          }
        }
      }
      
      // Edge buildup - extra strokes near edges
      const edgeStrokes = 4 + Math.floor(random() * 4);
      for (let i = 0; i < edgeStrokes; i++) {
        const edge = Math.floor(random() * 4);
        const strokeColor = varyColor(baseColor, random, 25);
        const strokeWidth = 6 + random() * 8;
        
        if (edge === 0) { // Top
          const sy = y + random() * 15;
          drawBrushStroke(x, sy, x + w, sy + (random() - 0.5) * 6, strokeColor, strokeWidth, 0.5);
        } else if (edge === 1) { // Bottom
          const sy = y + h - random() * 15;
          drawBrushStroke(x, sy, x + w, sy + (random() - 0.5) * 6, strokeColor, strokeWidth, 0.5);
        } else if (edge === 2) { // Left
          const sx = x + random() * 15;
          drawBrushStroke(sx, y, sx + (random() - 0.5) * 6, y + h, strokeColor, strokeWidth, 0.5);
        } else { // Right
          const sx = x + w - random() * 15;
          drawBrushStroke(sx, y, sx + (random() - 0.5) * 6, y + h, strokeColor, strokeWidth, 0.5);
        }
      }
      
      // Highlight/texture strokes
      const highlightStrokes = 2 + Math.floor(random() * 3);
      for (let i = 0; i < highlightStrokes; i++) {
        const hx = x + random() * w * 0.8;
        const hy = y + random() * h * 0.8;
        const hlen = 30 + random() * 60;
        const hangle = horizontal ? (random() - 0.5) * 0.3 : Math.PI / 2 + (random() - 0.5) * 0.3;
        
        const lightColor = rgbToHex(
          Math.min(255, br + 40 + random() * 30),
          Math.min(255, bg + 40 + random() * 30),
          Math.min(255, bb + 40 + random() * 30)
        );
        
        drawBrushStroke(
          hx, hy,
          hx + Math.cos(hangle) * hlen,
          hy + Math.sin(hangle) * hlen,
          lightColor, 4 + random() * 6, 0.3
        );
      }
    };
    
    // Draw wobbly black line
    const drawLine = (x1, y1, x2, y2, thickness) => {
      const len = Math.hypot(x2 - x1, y2 - y1);
      const steps = Math.max(15, len / 6);
      const off = random() * 1000;
      
      ctx.save();
      ctx.lineCap = 'round';
      
      for (let stroke = 0; stroke < 3; stroke++) {
        ctx.beginPath();
        ctx.strokeStyle = stroke === 0 ? '#0a0a0a' : `rgba(20,15,10,${0.25 - stroke * 0.08})`;
        ctx.lineWidth = thickness * (1 - stroke * 0.15);
        
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
    
    // Generate sparse ad-hoc lines
    const lines = [];
    
    const numLongLines = 2 + Math.floor(random() * 2);
    for (let i = 0; i < numLongLines; i++) {
      const isVert = random() > 0.5;
      const thickness = 2.5 + random() * 4;
      if (isVert) {
        const x = 60 + random() * (W - 120);
        const y1 = random() > 0.3 ? -20 : 50 + random() * 150;
        const y2 = random() > 0.3 ? H + 20 : H - 50 - random() * 150;
        lines.push({ x1: x, y1, x2: x, y2, t: thickness });
      } else {
        const y = 60 + random() * (H - 120);
        const x1 = random() > 0.3 ? -20 : 50 + random() * 150;
        const x2 = random() > 0.3 ? W + 20 : W - 50 - random() * 150;
        lines.push({ x1, y1: y, x2, y2: y, t: thickness });
      }
    }
    
    const numMedLines = 3 + Math.floor(random() * 3);
    for (let i = 0; i < numMedLines; i++) {
      const isVert = random() > 0.5;
      const thickness = 2 + random() * 3;
      const length = 80 + random() * 200;
      if (isVert) {
        const x = 30 + random() * (W - 60);
        const y = random() * (H - length);
        lines.push({ x1: x, y1: y, x2: x, y2: y + length, t: thickness });
      } else {
        const y = 30 + random() * (H - 60);
        const x = random() * (W - length);
        lines.push({ x1: x, y1: y, x2: x + length, y2: y, t: thickness });
      }
    }
    
    const numShortLines = 4 + Math.floor(random() * 5);
    for (let i = 0; i < numShortLines; i++) {
      const isVert = random() > 0.5;
      const thickness = 1.5 + random() * 2.5;
      const length = 30 + random() * 80;
      if (isVert) {
        const x = 20 + random() * (W - 40);
        const y = random() * (H - length);
        lines.push({ x1: x, y1: y, x2: x, y2: y + length, t: thickness });
      } else {
        const y = 20 + random() * (H - 40);
        const x = random() * (W - length);
        lines.push({ x1: x, y1: y, x2: x + length, y2: y, t: thickness });
      }
    }
    
    // Color blocks
    const colorKeys = ['red', 'yellow', 'blue', 'red', 'yellow', 'blue', 'black', 'lightBlue'];
    const numBlocks = 10 + Math.floor(random() * 8);
    const blocks = [];
    
    for (let i = 0; i < numBlocks; i++) {
      const w = 50 + random() * 130;
      const h = 50 + random() * 130;
      const x = 15 + random() * (W - w - 30);
      const y = 15 + random() * (H - h - 30);
      const col = colorKeys[Math.floor(random() * colorKeys.length)];
      
      let overlap = false;
      for (const b of blocks) {
        const ox = Math.max(0, Math.min(x + w, b.x + b.w) - Math.max(x, b.x));
        const oy = Math.max(0, Math.min(y + h, b.y + b.h) - Math.max(y, b.y));
        if (ox * oy > w * h * 0.6) { overlap = true; break; }
      }
      if (!overlap) blocks.push({ x, y, w, h, col });
    }
    
    // Draw blocks
    blocks.forEach(b => paintRect(b.x, b.y, b.w, b.h, b.col));
    
    // Draw lines on top
    lines.forEach(l => drawLine(l.x1, l.y1, l.x2, l.y2, l.t));
    
  }, [seed]);
  
  useEffect(() => { generate(); }, [generate]);
  
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
