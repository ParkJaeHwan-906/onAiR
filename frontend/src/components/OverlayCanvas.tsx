import { type KonvaEventObject } from "konva/lib/Node";
import { useRef, useState } from "react";
import { Layer, Line, Stage } from "react-konva";

interface Line {
  tool : string,
  points : number[]
}
export const OverlayCanvas = () =>{
  const [tool, setTool] = useState<string>('brush')
  const [lines, setLines] = useState<Line[]>([])
  const isDrawing = useRef(false)

  const handleMouseDown = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    isDrawing.current = true
    const pos = e.target.getStage()?.getPointerPosition()
    if (!pos) return
    setLines([...lines, {tool, points: [pos.x, pos.y] }])
  }

  const handleMouseMove = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (!isDrawing.current) {
      return
    }
    const stage = e.target.getStage()
    const point = stage?.getPointerPosition()

    if (!point) return

    setLines(prevLines => {
      const newLines = [...prevLines]
      const lastLine = {...newLines[newLines.length - 1]}
      lastLine.points = [...lastLine.points, point.x, point.y]
      newLines[newLines.length - 1] = lastLine
      return newLines
    })
  }

  const handleMouseUp = () => {
    isDrawing.current = false
  }

  return (
    <>
      <select
        value={tool}
        onChange={(e) => {
          setTool(e.target.value)
        }}
      >
        <option value={'brush'}>Brush</option>
        <option value={'eraser'}>Eraser</option>
      </select>
      <Stage 
        width={window.innerWidth} 
        height={window.innerHeight}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchMove={handleMouseMove}
        onTouchEnd={handleMouseUp}
      >
        <Layer>
          {lines.map((line, i) => (
            <Line
              key={i}
              points={line.points}
              stroke={"#000000"}
              strokeWidth={5}
              tension={0.5}
              lineCap="round"
              lineJoin="round"
              globalCompositeOperation={
                line.tool === 'eraser' ? 'destination-out' : 'source-over'
              }
            />
          ))}
        </Layer>

      </Stage>
    </>

  )
}