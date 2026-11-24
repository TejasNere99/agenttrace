import { useCallback, useEffect, useMemo } from 'react'
import { Background, Controls, MiniMap, ReactFlow, Handle, Position, type Edge, type Node, type NodeProps, MarkerType, useEdgesState, useNodesState } from '@xyflow/react'
import { Activity, BrainCircuit, Check, Database, Flag, Play, ChartNoAxesColumnIncreasing, CircleAlert, LoaderCircle } from 'lucide-react'
import '@xyflow/react/dist/style.css'

type TraceNodeData = { label: string; kind: string; duration: string; tone: string; icon: string; status?: 'success' | 'running' | 'error' }
function TraceNode({ data, selected }: NodeProps<Node<TraceNodeData>>) {
  const icons = { input: Play, planner: BrainCircuit, data: Database, analysis: ChartNoAxesColumnIncreasing, answer: Flag }
  const Icon = icons[data.icon as keyof typeof icons] ?? Activity
  return <div className={`trace-node tone-${data.tone} ${selected ? 'node-selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <span className="node-icon"><Icon size={16} /></span><span className="node-copy"><b>{data.label}</b><small>{data.kind} · {data.duration}</small></span>
    <span className={`node-status status-${data.status ?? 'success'}`}>{data.status === 'error' ? <CircleAlert size={10} /> : data.status === 'running' ? <LoaderCircle size={10} /> : <Check size={10} />}</span><Handle type="source" position={Position.Right} />
  </div>
}

const initialNodes: Node<TraceNodeData>[] = [
  { id: 'input', type: 'trace', position: { x: 22, y: 152 }, data: { label: 'User Input', kind: 'Prompt', duration: '0.1s', tone: 'blue', icon: 'input' } },
  { id: 'planner', type: 'trace', position: { x: 228, y: 152 }, data: { label: 'Planner', kind: 'Agent', duration: '1.2s', tone: 'violet', icon: 'planner' } },
  { id: 'data', type: 'trace', position: { x: 438, y: 56 }, data: { label: 'Data Agent', kind: 'Tool call', duration: '3.8s', tone: 'blue', icon: 'data' } },
  { id: 'analysis', type: 'trace', position: { x: 438, y: 248 }, data: { label: 'Analysis Agent', kind: 'Agent', duration: '2.4s', tone: 'teal', icon: 'analysis' } },
  { id: 'answer', type: 'trace', position: { x: 650, y: 152 }, data: { label: 'Final Answer', kind: 'Output', duration: '0.9s', tone: 'indigo', icon: 'answer' } },
]
const initialEdges: Edge[] = [
  { id: 'e1', source: 'input', target: 'planner', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#a3a8c5' } },
  { id: 'e2', source: 'planner', target: 'data', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#a3a8c5' } },
  { id: 'e3', source: 'planner', target: 'analysis', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#a3a8c5' } },
  { id: 'e4', source: 'data', target: 'answer', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#a3a8c5' } },
  { id: 'e5', source: 'analysis', target: 'answer', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#a3a8c5' } },
]

export function ExecutionGraph({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, , onEdgesChange] = useEdgesState(initialEdges)
  const nodeTypes = useMemo(() => ({ trace: TraceNode }), [])
  const click = useCallback((_event: React.MouseEvent, node: Node) => onSelect(node.id), [onSelect])
  useEffect(() => { setNodes(current => current.map(node => ({ ...node, selected: node.id === selected }))) }, [selected, setNodes])
  return <div className="graph-canvas"><ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={click} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: .17 }} minZoom={.35} maxZoom={1.6} proOptions={{ hideAttribution: true }}>
    <Background color="#e6e9f3" gap={20} size={1} /><Controls showInteractive={false} position="top-left" /><MiniMap pannable zoomable nodeColor={(node) => node.id === 'answer' ? '#6c63ef' : node.id === 'planner' ? '#8a69ee' : '#5d9df6'} maskColor="rgba(248,249,253,.65)" />
  </ReactFlow><span className="graph-hint">Drag to pan · Scroll to zoom</span></div>
}
