import { type KonvaEventObject } from "konva/lib/Node";
import { useRef, useState } from "react";
import { Layer, Line, Stage } from "react-konva";
import type { DrawingLine } from "../types/DrawingLine";
import { useRoomContext } from "@livekit/components-react";
import { throttle } from "lodash";

interface CanvasProps {
  handleSerialize : (lines : DrawingLine[]) => void
}

export const OverlayCanvas = (
  { handleSerialize } : CanvasProps
) => {
  const room = useRoomContext()
  console.log("OverlayCanvas 렌더링됨. room 객체:", room);
  const [tool, setTool] = useState<string>('brush')
  const [lines, setLines] = useState<DrawingLine[]>([])
  const isDrawing = useRef(false)

  const sendDrawingData = (data: object) => {
    if (!room) return

    const jsonString = JSON.stringify(data)
    const byteArray = new TextEncoder().encode(jsonString)
    console.log(">>> [Web] SENDING DATA:", jsonString);
    room.localParticipant.publishData(byteArray, {
      reliable: false,
      // topic: 'drawing-data'
    })
  }

  const throttledSendDrawMove = throttle(
    (x: number, y:number) => sendDrawingData({event: 'draw-move', x, y}), 30
  )

  const handleMouseDown = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    alert("클릭! 이벤트 발사 성공!");
    isDrawing.current = true
    const pos = e.target.getStage()?.getPointerPosition()
    if (!pos) return
    setLines([...lines, {tool, points: [pos.x, pos.y] }])
    sendDrawingData({
      event: 'draw-start',
      x: pos.x,
      y: pos.y
    })
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
    throttledSendDrawMove(point.x, point.y)
  }

  const handleMouseUp = () => {
    isDrawing.current = false
    sendDrawingData({event: 'draw-end'})
  }

  return (
    <div
      style={{
        position: 'relative',
        width: 800,
        height: 600
      }}>
      <select
        value={tool}
        onChange={(e) => {
          setTool(e.target.value)
        }}
        style={{
          position: 'absolute',
          zIndex: 1
        }}
      >
        <option value={'brush'}>Brush</option>
        <option value={'eraser'}>Eraser</option>
      </select>
      <button
        onClick={() => handleSerialize(lines)}
        style={{
          position: 'absolute',
          top: '10px',
          left: '10px',
          zIndex: 1
        }}
      >
        Serialize
      </button>
      <Stage 
        width= {800} 
        height={600}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchMove={handleMouseMove}
        onTouchEnd={handleMouseUp}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          zIndex: 0
        }}
      >
        <Layer>
          {lines.map((line, i) => (
            <Line
              key={i}
              points={line.points}
              stroke={"#ffffff"}
              strokeWidth={5}
              tension={0.5}
              lineCap="round"
              lineJoin="round"
              shadowColor="red"
              shadowBlur={20}
              shadowOffsetX={5}
              shadowOffsetY={5}
              shadowOpacity={0.7}
              globalCompositeOperation={
                line.tool === 'eraser' ? 'destination-out' : 'source-over'
              }
            />
          ))}
        </Layer>

      </Stage>
    </div>

  )
}