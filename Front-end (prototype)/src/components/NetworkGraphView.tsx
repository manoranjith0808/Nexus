import React, { useState, useMemo, useRef, useEffect } from "react";
import { NetworkGraph, NetworkNode } from "../types.js";
import { Shield, Smartphone, Globe, Landmark, DollarSign, ZoomIn, ZoomOut, RefreshCw } from "lucide-react";

interface NetworkGraphViewProps {
  graph: NetworkGraph;
  title?: string;
  onNodeClick?: (node: NetworkNode) => void;
}

export default function NetworkGraphView({ graph, title, onNodeClick }: NetworkGraphViewProps) {
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDraggingPan, setIsDraggingPan] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

  // Update dimensions from ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width || 600,
          height: entry.contentRect.height || 400
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Compute node positions using an automated circular/star layout centered on target
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});

  useEffect(() => {
    if (!graph || graph.nodes.length === 0) return;

    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;

    const positions: Record<string, { x: number; y: number }> = {};
    
    // Find central node (one with target label or highest risk)
    const targetNode = graph.nodes.find(n => n.id.includes("Target") || n.id.includes("Eduardo") || n.id.includes("Sofía")) || graph.nodes[0];
    
    positions[targetNode.id] = { x: centerX, y: centerY };

    // Place remaining nodes in a circle around center
    const externalNodes = graph.nodes.filter(n => n.id !== targetNode.id);
    const radius = Math.min(dimensions.width, dimensions.height) * 0.35;

    externalNodes.forEach((node, idx) => {
      const angle = (idx / externalNodes.length) * 2 * Math.PI;
      positions[node.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      };
    });

    setNodePositions(positions);
  }, [graph, dimensions.width, dimensions.height]);

  const handleMouseDownContainer = (e: React.MouseEvent) => {
    if (draggedNodeId) return;
    setIsDraggingPan(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMoveContainer = (e: React.MouseEvent) => {
    if (isDraggingPan) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    } else if (draggedNodeId) {
      // Drag node
      const rect = containerRef.current?.getBoundingClientRect();
      if (rect) {
        // Convert screen coordinates to SVG coordinates accounting for zoom and pan
        const svgX = (e.clientX - rect.left - pan.x - dimensions.width / 2) / zoom + dimensions.width / 2;
        const svgY = (e.clientY - rect.top - pan.y - dimensions.height / 2) / zoom + dimensions.height / 2;
        
        setNodePositions(prev => ({
          ...prev,
          [draggedNodeId]: { x: svgX, y: svgY }
        }));
      }
    }
  };

  const handleMouseUpContainer = () => {
    setIsDraggingPan(false);
    setDraggedNodeId(null);
  };

  const handleNodeMouseDown = (nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDraggedNodeId(nodeId);
  };

  const handleNodeClickEvent = (node: NetworkNode, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedNode(node);
    if (onNodeClick) onNodeClick(node);
  };

  const resetLayout = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectedNode(null);
  };

  // Helper to determine node icon
  const getNodeIcon = (type: string) => {
    switch (type) {
      case "account":
        return <Shield className="w-5 h-5 text-emerald-400" />;
      case "device":
        return <Smartphone className="w-5 h-5 text-indigo-400" />;
      case "ip":
        return <Globe className="w-5 h-5 text-amber-400" />;
      case "merchant":
        return <Landmark className="w-5 h-5 text-sky-400" />;
      default:
        return <DollarSign className="w-5 h-5 text-rose-400" />;
    }
  };

  // Helper to color nodes based on type/risk
  const getNodeColor = (node: NetworkNode) => {
    if (node.riskScore !== undefined) {
      if (node.riskScore >= 0.8) return "stroke-rose-500 fill-zinc-900";
      if (node.riskScore >= 0.5) return "stroke-amber-500 fill-zinc-900";
      return "stroke-emerald-500 fill-zinc-900";
    }
    switch (node.type) {
      case "account": return "stroke-emerald-400 fill-zinc-900";
      case "device": return "stroke-indigo-400 fill-zinc-900";
      case "ip": return "stroke-amber-400 fill-zinc-900";
      case "merchant": return "stroke-sky-400 fill-zinc-900";
      default: return "stroke-rose-400 fill-zinc-900";
    }
  };

  return (
    <div className="relative w-full h-full bg-zinc-950/60 rounded-xl border border-zinc-800 flex flex-col overflow-hidden">
      {/* Header controls */}
      <div className="flex items-center justify-between p-3 border-b border-zinc-800 bg-zinc-900/40">
        <span className="text-xs font-mono font-bold text-zinc-400 tracking-wider uppercase">
          {title || "NEOPARK COMPLIANCE LINK SUBGRAPH"}
        </span>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setZoom(z => Math.min(z + 0.15, 2.5))}
            className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoom(z => Math.max(z - 0.15, 0.4))}
            className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={resetLayout}
            className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition cursor-pointer"
            title="Center Graph"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="relative flex-1 select-none cursor-grab active:cursor-grabbing overflow-hidden bg-radial from-zinc-900 to-zinc-950"
        onMouseDown={handleMouseDownContainer}
        onMouseMove={handleMouseMoveContainer}
        onMouseUp={handleMouseUpContainer}
        onMouseLeave={handleMouseUpContainer}
      >
        {graph.nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-500 font-mono text-sm">
            No subgraph loaded for this case.
          </div>
        ) : (
          <svg
            className="w-full h-full"
            style={{ pointerEvents: "all" }}
          >
            {/* Legend */}
            <g transform="translate(15, 15)" className="opacity-80 pointer-events-none">
              <rect width="180" height="110" rx="6" className="fill-zinc-900/90 stroke-zinc-800" />
              <text x="12" y="20" className="fill-zinc-400 font-mono font-bold text-[10px]">NODE LEGEND</text>
              <circle cx="18" cy="40" r="5" className="fill-zinc-900 stroke-2 stroke-emerald-400" />
              <text x="30" y="43" className="fill-zinc-300 font-mono text-[9px]">Account / CBU / Card</text>
              
              <circle cx="18" cy="60" r="5" className="fill-zinc-900 stroke-2 stroke-indigo-400" />
              <text x="30" y="63" className="fill-zinc-300 font-mono text-[9px]">Device / Hardware Fingerprint</text>

              <circle cx="18" cy="80" r="5" className="fill-zinc-900 stroke-2 stroke-amber-400" />
              <text x="30" y="83" className="fill-zinc-300 font-mono text-[9px]">IP Address / Network</text>

              <circle cx="18" cy="100" r="5" className="fill-zinc-900 stroke-2 stroke-sky-400" />
              <text x="30" y="103" className="fill-zinc-300 font-mono text-[9px]">Merchant / ATM Location</text>
            </g>

            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Render Links */}
              {graph.links.map((link, idx) => {
                const sourcePos = nodePositions[link.source];
                const targetPos = nodePositions[link.target];
                if (!sourcePos || !targetPos) return null;

                // Calculate control point for slightly curved links
                const dx = targetPos.x - sourcePos.x;
                const dy = targetPos.y - sourcePos.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                // Straight lines for simplicity
                const midX = (sourcePos.x + targetPos.x) / 2;
                const midY = (sourcePos.y + targetPos.y) / 2;

                return (
                  <g key={`link-${idx}`}>
                    <line
                      x1={sourcePos.x}
                      y1={sourcePos.y}
                      x2={targetPos.x}
                      y2={targetPos.y}
                      className="stroke-zinc-700/60 stroke-2"
                    />
                    {/* Link Label */}
                    <g transform={`translate(${midX}, ${midY})`}>
                      <rect
                        x="-50"
                        y="-7"
                        width="100"
                        height="14"
                        rx="3"
                        className="fill-zinc-900/90 stroke-zinc-800"
                      />
                      <text
                        textAnchor="middle"
                        y="3"
                        className="fill-zinc-400 font-mono text-[8px]"
                      >
                        {link.label.length > 18 ? link.label.slice(0, 16) + ".." : link.label}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Render Nodes */}
              {graph.nodes.map((node) => {
                const pos = nodePositions[node.id];
                if (!pos) return null;

                const isSelected = selectedNode?.id === node.id;
                const r = node.val || 20;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    className="cursor-pointer"
                    onMouseDown={(e) => handleNodeMouseDown(node.id, e)}
                    onClick={(e) => handleNodeClickEvent(node, e)}
                  >
                    <circle
                      r={isSelected ? r + 6 : r}
                      className={`stroke-[3px] transition-all duration-150 ${getNodeColor(node)} ${isSelected ? "animate-pulse" : ""}`}
                    />
                    
                    {/* Icon inside Node */}
                    <g transform="translate(-10, -10)" className="pointer-events-none">
                      {getNodeIcon(node.type)}
                    </g>

                    {/* Node Text Label (placed underneath) */}
                    <text
                      y={r + 14}
                      textAnchor="middle"
                      className="fill-zinc-200 font-mono font-medium text-[9px] drop-shadow-md select-none"
                    >
                      {node.id.length > 20 ? node.id.slice(0, 18) + ".." : node.id}
                    </text>

                    {/* Score badge indicator if has risk */}
                    {node.riskScore !== undefined && (
                      <g transform={`translate(${r - 5}, -${r - 5})`}>
                        <circle r="7.5" className="fill-zinc-950 stroke-rose-500 stroke-1" />
                        <text
                          textAnchor="middle"
                          y="3"
                          className="fill-rose-400 font-mono text-[7px] font-bold"
                        >
                          {Math.round(node.riskScore * 10)}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>
        )}

        {/* Selected Node Drawer */}
        {selectedNode && (
          <div className="absolute bottom-3 right-3 left-3 md:left-auto md:w-80 bg-zinc-900/95 border border-zinc-850 rounded-lg p-3.5 shadow-2xl backdrop-blur-md transition-all">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                {getNodeIcon(selectedNode.type)}
                <div>
                  <h4 className="text-xs font-mono font-bold text-zinc-100">{selectedNode.id}</h4>
                  <p className="text-[10px] font-mono text-zinc-400 uppercase">{selectedNode.type}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-zinc-500 hover:text-zinc-300 text-xs font-mono font-bold px-1 rounded hover:bg-zinc-800 cursor-pointer"
              >
                ×
              </button>
            </div>
            
            <div className="space-y-1.5 text-[10px] font-mono text-zinc-300 border-t border-zinc-800 pt-2">
              <div className="flex justify-between">
                <span>Node Label:</span>
                <span className="text-zinc-100 font-bold">{selectedNode.label}</span>
              </div>
              {selectedNode.riskScore !== undefined && (
                <div className="flex justify-between">
                  <span>Risk Score:</span>
                  <span className="text-rose-400 font-bold">{(selectedNode.riskScore * 100).toFixed(0)}%</span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Connection Type:</span>
                <span className="text-zinc-400 capitalize">{selectedNode.type}</span>
              </div>
              <p className="text-[9px] text-zinc-500 mt-1 italic">
                * Drag node to manually reposition the graph topology.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
