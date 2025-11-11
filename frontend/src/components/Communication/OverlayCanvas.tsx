import { type KonvaEventObject } from "konva/lib/Node";
import { useEffect, useRef, useState } from "react";
import {
  Layer,
  Line,
  Stage,
  Circle,
  Rect,
  RegularPolygon,
  Arrow,
} from "react-konva";
import type { DrawingLine } from "../../types/DrawingLine";
import { useRoomContext } from "@livekit/components-react";
import { useSocket } from "../../utils/socketContext";
import { throttle } from "lodash";

interface CanvasProps {
  penColor: string;
  tool?: string;
}

export const OverlayCanvas = ({
  penColor,
  tool = "pen",
}: CanvasProps) => {
  const socket = useSocket();   // 연결되어있는 소켓 객체를 가져옴

  const [lines, setLines] = useState<DrawingLine[]>([]);
  const [shapes, setShapes] = useState<any[]>([]); // 도형 목록 관리
  const [currentShape, setCurrentShape] = useState<any | null>(null); // 드래그 중 도형
  const [eraserPos, setEraserPos] = useState<{ x: number; y: number } | null>(
    null
  );
  const isDrawing = useRef(false);
  const startPos = useRef<{ x: number; y: number } | null>(null);
  const room = useRoomContext()
  const sendDrawingData = (data: object) => {
      if (!room) return
  
      const jsonString = JSON.stringify(data)
      const byteArray = new TextEncoder().encode(jsonString)
      console.log(">>> [Web] SENDING DATA:", jsonString);
      room.localParticipant.publishData(byteArray, {
        reliable: false,
      })
    }
  
    const throttledSendDrawMove = throttle(
      (x: number, y:number) => sendDrawingData({event: 'draw-move', x, y}), 30
    )
  
  const [arMarkers, setArMarkers] = useState<Array<{
    idx: number;
    info: {
      x: number;
      y: number;
      size: number;
    };
  }>>([
    // 테스트용으로 초기 마커 생성
    {
      idx: 0,
      info: {
        x: 200,
        y: 300,
        size: 50
      }
    },
    {
      idx: 1,
      info: {
        x: 500,
        y: 400,
        size: 30
      }
    }
  ]);

  // ------------------------------- Listen Socket Event -------------------------------
  useEffect(() => {
      if(!socket) return;

      // ar-info 이벤트 listen
      socket.on('ar-info', (data) => {
        console.log('receive ar info', data);
        console.log('data type:', typeof data, 'isArray:', Array.isArray(data));
        console.log('data constructor:', data?.constructor?.name);
        
        // 배열인지 확인하고 안전하게 처리
        if (Array.isArray(data)) {
          setArMarkers(data);
        } else if (data && typeof data === 'object' && 'markers' in data) {
          // 객체로 감싸져 있는 경우 (예: { markers: [...] })
          const markersData = data as { markers: unknown };
          if (Array.isArray(markersData.markers)) {
            setArMarkers(markersData.markers);
          } else {
            console.warn('data.markers is not an array:', markersData.markers);
            setArMarkers([]);
          }
        } else {
          console.error('Invalid ar-info data:', data);
          setArMarkers([]);
        }
      });

      // cleanup
      return () => {
        socket.off('ar-info');
      };
  }, [socket])


  // ------------------------------- 마우스 클릭 시작 -------------------------------
  const handleMouseDown = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    const pos = e.target.getStage()?.getPointerPosition();
    if (!pos) return;

    if (tool === "eraser") return;

    // 펜 / 지우개 모드
    if (tool === "pen") {
      isDrawing.current = true;
      setLines((prev) => [
        ...prev,
        { tool, color: penColor, points: [pos.x, pos.y] },
      ]);
      sendDrawingData({
      event: 'draw-start',
      x: pos.x,
      y: pos.y
    })
    } else if (["circle", "square", "triangle"].includes(tool)) {
      startPos.current = pos;
      setCurrentShape({
        type: tool,
        startX: pos.x,
        startY: pos.y,
        endX: pos.x,
        endY: pos.y,
        color: penColor,
      });
    } else if (["arrow"].includes(tool)){
      startPos.current = pos;
      console.log(`ar-marker created: ${pos.x}, ${pos.y}`);
      socket.emit("ar-marker", {marker_x: pos.x, marker_y: pos.y});
    }

  };

  // ------------------------------- 마우스 이동 -------------------------------
  const handleMouseMove = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    const pos = e.target.getStage()?.getPointerPosition();
    if (!pos) return;

    if (tool === "eraser") {
      setEraserPos(pos);
      return;
    }

    if (tool === "pen") {
      if (!isDrawing.current) return;
      setLines((prevLines) => {
        const newLines = [...prevLines];
        const lastLine = { ...newLines[newLines.length - 1] };
        lastLine.points = [...lastLine.points, pos.x, pos.y];
        newLines[newLines.length - 1] = lastLine;
        return newLines;
      });
      throttledSendDrawMove(pos.x, pos.y)
    } else if (startPos.current && currentShape) {
      setCurrentShape({
        ...currentShape,
        endX: pos.x,
        endY: pos.y,
      });
    }
  };

  // ------------------------------- 마우스 클릭 끝 -------------------------------
  const handleMouseUp = () => {
    if (currentShape) {
      // 드래그 종료 시 도형 목록에 추가
      setShapes((prev) => [...prev, currentShape]);
      setCurrentShape(null);
    }
    isDrawing.current = false;
    startPos.current = null;
    sendDrawingData({event: 'draw-end'})
  };

  // ------------------------------- 삭제 -------------------------------
  const handleDeleteShape = (index: number) => {
    if (tool !== "eraser") return;
    setShapes((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDeleteLine = (index: number) => {
    if (tool !== "eraser") return;
    setLines((prev) => prev.filter((_, i) => i !== index));
  };

  // ------------------------------- 도형 계산 함수 -------------------------------
  const renderShape = (shape: any, i: number) => {
    const { type, startX, startY, endX, endY, color } = shape;
    switch (type) {
      case "circle": {
        const radius = Math.hypot(endX - startX, endY - startY) / 2;
        const centerX = (startX + endX) / 2;
        const centerY = (startY + endY) / 2;
        return (
          <Circle
            key={i}
            x={centerX}
            y={centerY}
            radius={radius}
            stroke={color}
            strokeWidth={3}
            hitStrokeWidth={15}
            onClick={() => handleDeleteShape(i)}
          />
        );
      }
      case "square": {
        const x = Math.min(startX, endX);
        const y = Math.min(startY, endY);
        const width = Math.abs(endX - startX);
        const height = Math.abs(endY - startY);
        return (
          <Rect
            key={i}
            x={x}
            y={y}
            width={width}
            height={height}
            stroke={color}
            strokeWidth={3}
            hitStrokeWidth={15}
            onClick={() => handleDeleteShape(i)}
          />
        );
      }
      case "triangle": {
        const centerX = (startX + endX) / 2;
        const centerY = (startY + endY) / 2;
        const size = Math.abs(endX - startX);
        return (
          <RegularPolygon
            key={i}
            x={centerX}
            y={centerY}
            sides={3}
            radius={size / 2}
            stroke={color}
            strokeWidth={3}
            hitStrokeWidth={15}
            onClick={() => handleDeleteShape(i)}
          />
        );
      }
      case "arrow": {
        return (
          <Arrow
            key={i}
            points={[startX, startY, endX, endY]}
            stroke={color}
            strokeWidth={3}
            pointerLength={12}
            pointerWidth={12}
            hitStrokeWidth={15}
            onClick={() => handleDeleteShape(i)}
          />
        );
      }
      default:
        return null;
    }
  };

  return (
    <>
      <Stage
        width={968}
        height={857}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchMove={handleMouseMove}
        onTouchEnd={handleMouseUp}
      >
        <Layer>
          {/* 펜 / 지우개 */}
          {lines.map((line, i) => (
            <Line
              key={`line-${i}`}
              points={line.points}
              stroke={line.color || penColor}
              strokeWidth={5}
              tension={0.5}
              lineCap="round"
              lineJoin="round"
              globalCompositeOperation="source-over"
              hitStrokeWidth={15}
              onClick={() => handleDeleteLine(i)}
            />
          ))}

          {/* 기존 도형 */}
          {shapes.map((shape, i) => renderShape(shape, i))}

          {/* 현재 드래그 중인 도형 (실시간 크기 변화) */}
          {currentShape && renderShape(currentShape, -1)}

          {/* AR 마커 렌더링 */}
          {Array.isArray(arMarkers) && arMarkers.length > 0 && arMarkers.map((marker) => (
            <Circle
              key={marker.idx}
              x={marker.info.x}
              y={marker.info.y}
              radius={marker.info.size} 
              fill="rgba(255, 0, 0, 0.3)" // 반투명 빨간색
              stroke="#ff0000"
              strokeWidth={2}
              listening={tool === "eraser"} // eraser 선택 시 클릭 이벤트 활성화
              onClick={() => {
                console.log('AR 마커 클릭:', marker.idx);
                // 마커 관련 동작
                socket.emit("delete-marker", {idx: marker.idx});
              }}
            />
          ))}

          {/* 지우개 커서 */}
          {tool === "eraser" && eraserPos && (
            <Circle
              x={eraserPos.x}
              y={eraserPos.y}
              radius={15}
              stroke="#9ca3af"
              strokeWidth={2}
              dash={[4, 4]}
              listening={false}
            />
          )}
        </Layer>
      </Stage>
    </>
  );
};
