// components/KnowledgeGraph.tsx
"use client";

import React, { useCallback, useEffect } from "react";
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "@dagrejs/dagre";
import { GraphNode, GraphEdge } from "@/lib/api";

interface KnowledgeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Layout nodes using dagre (top-down hierarchy)
const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: "TB", nodesep: 80, ranksep: 100 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 150, height: 60 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 75,
        y: nodeWithPosition.y - 30,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

// Custom node styles based on status - UPGRADED with glow effects
const getNodeStyle = (status: string, color: string) => {
  const baseStyle = {
    padding: "12px 24px",
    borderRadius: "16px",
    fontSize: "13px",
    fontWeight: "600",
    fontFamily: "ui-monospace, monospace",
    textAlign: "center" as const,
    minWidth: "140px",
    border: "2px solid",
    transition: "all 0.5s ease",
    backdropFilter: "blur(8px)",
  };

  if (status === "mastered") {
    return {
      ...baseStyle,
      background: "rgba(34, 197, 94, 0.1)",
      borderColor: "#22c55e",
      color: "#4ade80",
      boxShadow: "0 0 20px rgba(34, 197, 94, 0.5), 0 0 40px rgba(34, 197, 94, 0.2)",
    };
  } else if (status === "failed") {
    return {
      ...baseStyle,
      background: "rgba(239, 68, 68, 0.1)",
      borderColor: "#ef4444",
      color: "#f87171",
      boxShadow: "0 0 20px rgba(239, 68, 68, 0.6), 0 0 40px rgba(239, 68, 68, 0.3)",
      animation: "pulse 2s ease-in-out infinite",
    };
  } else {
    return {
      ...baseStyle,
      background: "rgba(39, 39, 42, 0.8)",
      borderColor: "#52525b",
      color: "#a1a1aa",
    };
  }
};

export default function KnowledgeGraph({ nodes, edges }: KnowledgeGraphProps) {
  // Convert API data to ReactFlow format
  const initialNodes: Node[] = nodes.map((node) => ({
    id: node.id,
    data: { 
      label: node.label,
      status: node.status,
    },
    position: { x: 0, y: 0 },
    style: getNodeStyle(node.status, node.color),
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  }));

  const initialEdges: Edge[] = edges.map((edge, index) => ({
    id: `e${index}`,
    source: edge.source,
    target: edge.target,
    animated: true,
    style: { stroke: "#4a4a4a", strokeWidth: 2 },
  }));

  const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
    initialNodes,
    initialEdges
  );

  const [flowNodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [flowEdges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  // Update nodes when props change
  useEffect(() => {
    const updatedNodes: Node[] = nodes.map((node) => ({
      id: node.id,
      data: { 
        label: node.label,
        status: node.status,
      },
      position: { x: 0, y: 0 },
      style: getNodeStyle(node.status, node.color),
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    }));

    const updatedEdges: Edge[] = edges.map((edge, index) => ({
      id: `e${index}`,
      source: edge.source,
      target: edge.target,
      animated: true,
      style: { stroke: "#4a4a4a", strokeWidth: 2 },
    }));

    const layouted = getLayoutedElements(updatedNodes, updatedEdges);
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
  }, [nodes, edges, setNodes, setEdges]);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.5 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1a1a1a" gap={20} />
        <Controls className="!bg-zinc-800 !border-zinc-700" />
      </ReactFlow>
    </div>
  );
}