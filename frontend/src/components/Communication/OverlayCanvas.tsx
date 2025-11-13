import { type KonvaEventObject } from "konva/lib/Node";
import { useEffect, useRef, useState, useMemo } from "react";
import { Layer, Line, Stage, Circle, RegularPolygon, Group } from "react-konva";
import type { DrawingLine } from "../../types/DrawingLine";
import { useRoomContext } from "@livekit/components-react";
import { useSocket } from "../../utils/socketContext";
import { throttle } from "lodash";

interface CanvasProps {
  penColor: string;
  tool?: string;
}

// AR 마커 타입 정의
type ArMarker = {
  idx: number;
  info: {
    x: number;
    y: number;
    size: number;
  };
  color: string;
  pulseScale?: number;
  pulseOpacity?: number;
  opacity?: number;
};

// 카메라 화면 size (고정값)
const CAMERA_WIDTH = 640;
const CAMERA_HEIGHT = 480;

export const OverlayCanvas = ({ penColor, tool = "pen" }: CanvasProps) => {
  const socket = useSocket();
  const room = useRoomContext();

  // 펜 선: opacity 값 포함
  const [lines, setLines] = useState<{ line: DrawingLine; opacity: number }[]>(
    []
  );

  // // 도형 관련 (주석처리)
  // const [shapes, setShapes] = useState<any[]>([]); // 도형 목록 관리
  // const [currentShape, setCurrentShape] = useState<any | null>(null); // 드래그 중 도형

  const [eraserPos, setEraserPos] = useState<{ x: number; y: number } | null>(
    null
  );
  const isDrawing = useRef(false);
  const startPos = useRef<{ x: number; y: number } | null>(null);

  // verlay canvas 크기 동적 설정
  const containerRef = useRef<HTMLDivElement>(null);
  const [stageSize, setStageSize] = useState({ width: 968, height: 857 });

  // 동적 scale 계산 (stageSize 변경 시에만 재계산)
  const scale = useMemo(
    () => stageSize.height / CAMERA_HEIGHT,
    [stageSize.height]
  );
  const scaledCameraWidth = useMemo(() => CAMERA_WIDTH * scale, [scale]);

  // convert stage -> camera (동적 값 사용)
  const convertStageToCamera = useMemo(() => {
    return (stageX: number, stageY: number) => {
      const horizontalCrop = (scaledCameraWidth - stageSize.width) / 2;
      const cameraX =
        ((stageX + horizontalCrop) / scaledCameraWidth) * CAMERA_WIDTH;
      const cameraY = (stageY / stageSize.height) * CAMERA_HEIGHT;

      return {
        x: Math.max(0, Math.min(CAMERA_WIDTH, Math.round(cameraX))),
        y: Math.max(0, Math.min(CAMERA_HEIGHT, Math.round(cameraY))),
      };
    };
  }, [stageSize, scaledCameraWidth]);

  // convert camera -> stage (동적 값 사용)
  const convertCameraToStage = useMemo(() => {
    return (cameraX: number, cameraY: number) => {
      const horizontalCrop = (scaledCameraWidth - stageSize.width) / 2;
      const stageX =
        (cameraX / CAMERA_WIDTH) * scaledCameraWidth - horizontalCrop;
      const stageY = (cameraY / CAMERA_HEIGHT) * stageSize.height;

      return {
        x: Math.round(stageX),
        y: Math.round(stageY),
      };
    };
  }, [stageSize, scaledCameraWidth]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setStageSize({ width, height });
      }
    };

    if (!containerRef.current) return;
    updateSize();
    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // LiveKit 데이터 전송
  const sendDrawingData = (data: object) => {
    if (!room) return;
    const jsonString = JSON.stringify(data);
    const byteArray = new TextEncoder().encode(jsonString);
    console.log(">>> [Web] SENDING DATA:", jsonString);
    room.localParticipant.publishData(byteArray, {
      reliable: false,
    });
  };

  const throttledSendDrawMove = throttle(
    (tool: String, x: number, y: number) => sendDrawingData({ event: "draw-move", tool, x, y }),
    10
  );

  const [arMarkers, setArMarkers] = useState<ArMarker[]>([]);

  // ------------------------------- Listen Socket Event -------------------------------
  useEffect(() => {
    if (!socket) return;

    // ar-info 이벤트 listen
    socket.on("ar-info", (data) => {
      console.log("receive ar info", data);

      // { markers: [...] } 형태의 데이터 처리
      const markersData = data as unknown as { markers: ArMarker[] };
      if (Array.isArray(markersData.markers)) {
        // 카메라 좌표를 Stage 좌표로 변환
        const convertedMarkers = markersData.markers.map((marker: ArMarker) => {
          const stagePos = convertCameraToStage(marker.info.x, marker.info.y);
          return {
            ...marker,
            info: {
              ...marker.info,
              x: stagePos.x,
              y: stagePos.y,
              size: marker.info.size * scale, // size도 스케일 적용
            },
          };
        });
        setArMarkers(convertedMarkers);
        console.log("converted AR Markers : ", convertedMarkers);
      } else {
        console.warn("data.markers is not an array:", markersData.markers);
        setArMarkers([]);
      }
    });

    // cleanup
    return () => {
      socket.off("ar-info");
    };
  }, [socket, convertCameraToStage, scale]);

  // Pulse 효과: 마커가 주기적으로 커졌다 작아짐
  useEffect(() => {
    const interval = setInterval(() => {
      setArMarkers((prev) =>
        prev.map((m) => {
          const newScale = (m.pulseScale ?? 1) + 0.05;
          const newOpacity = (m.pulseOpacity ?? 0.5) - 0.03;
          if (newScale > 1.8) {
            // 다시 초기화 (한 바퀴 돌면 원래 크기로)
            return { ...m, pulseScale: 1, pulseOpacity: 0.5 };
          }
          return { ...m, pulseScale: newScale, pulseOpacity: newOpacity };
        })
      );
    }, 50); // 0.05초마다 갱신
    return () => clearInterval(interval);
  }, []);

  // ------------------------------- 펜 서서히 사라짐 -------------------------------
  useEffect(() => {
    const interval = setInterval(() => {
      setLines((prev) =>
        prev
          .map((item) => ({
            ...item,
            opacity: Math.max(0, item.opacity - 0.05), // 점점 투명하게
          }))
          .filter((item) => item.opacity > 0)
      );
    }, 100); //
    return () => clearInterval(interval);
  }, []);

  // ------------------------------- 마우스 클릭 시작 -------------------------------
  const handleMouseDown = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    const pos = e.target.getStage()?.getPointerPosition();
    if (!pos) return;

    // 지우개
    if (tool == "eraser") {
      setArMarkers((prev) =>
        prev.filter(
          (m) =>
            Math.hypot(m.info.x - pos.x, m.info.y - pos.y) > m.info.size + 10
        )
      );
      sendDrawingData({
        event: "draw-start",
        tool,
        x: pos.x,
        y: pos.y,
      });
      return;
    }

    // 펜
    if (tool === "pen") {
      isDrawing.current = true;
      setLines((prev) => [
        ...prev,
        { line: { tool, color: penColor, points: [pos.x, pos.y] }, opacity: 1 },
      ]);
      sendDrawingData({
        event: "draw-start",
        tool,
        x: pos.x,
        y: pos.y,
      });
    }

    // 마커
    if (tool === "marker") {
      const cameraPos = convertStageToCamera(pos.x, pos.y);
      // 화면에 바로 표시 (UI 확인용)
      setArMarkers((prev) => [
        ...prev,
        {
          idx: Date.now(),
          info: { x: pos.x, y: pos.y, size: 20 },
          color: penColor,
        },
      ]);

      console.log(
        `ar-marker created: Stage(${pos.x}, ${pos.y}) -> Camera(${cameraPos.x}, ${cameraPos.y})`
      );

      // 소켓 이벤트 발신 (서버 있을 경우)
      socket.emit("ar-marker", {
        marker_x: cameraPos.x,
        marker_y: cameraPos.y,
      });
    }
  };

  // ------------------------------- 마우스 이동 -------------------------------
  const handleMouseMove = (e: KonvaEventObject<MouseEvent | TouchEvent>) => {
    const pos = e.target.getStage()?.getPointerPosition();
    if (!pos) return;

    if (tool === "eraser") {
      setEraserPos(pos);
      throttledSendDrawMove(tool, pos.x, pos.y);
      return;
    }

    if (tool === "pen") {
      if (!isDrawing.current) return;
      setLines((prevLines) => {
        const newLines = [...prevLines];
        const lastLine = { ...newLines[newLines.length - 1] };
        lastLine.line.points = [...lastLine.line.points, pos.x, pos.y];
        newLines[newLines.length - 1] = lastLine;
        return newLines;
      });
      throttledSendDrawMove(tool, pos.x, pos.y);
    }
    
    if (tool === "marker") {
      
    }

    // 도형 (주석처리)
    // else if (startPos.current && currentShape) {
    //   setCurrentShape({
    //     ...currentShape,
    //     endX: pos.x,
    //     endY: pos.y,
    //   });
    // }
  };

  // ------------------------------- 마우스 클릭 끝 -------------------------------
  const handleMouseUp = () => {
    // if (currentShape) {
    //   setShapes((prev) => [...prev, currentShape]);
    //   setCurrentShape(null);
    // }
    isDrawing.current = false;
    startPos.current = null;
    sendDrawingData({ event: "draw-end" });
  };

  // ------------------------------- 삭제 -------------------------------
  // const handleDeleteShape = (index: number) => {
  //   if (tool !== "eraser") return;
  //   setShapes((prev) => prev.filter((_, i) => i !== index));
  // };

  // ------------------------------- 도형 계산 함수 -------------------------------
  // const renderShape = (shape: any, i: number) => {
  //   const { type, startX, startY, endX, endY, color } = shape;
  //   switch (type) {
  //     case "circle": {
  //       const radius = Math.hypot(endX - startX, endY - startY) / 2;
  //       const centerX = (startX + endX) / 2;
  //       const centerY = (startY + endY) / 2;
  //       return (
  //         <Circle
  //           key={i}
  //           x={centerX}
  //           y={centerY}
  //           radius={radius}
  //           stroke={color}
  //           strokeWidth={3}
  //           hitStrokeWidth={15}
  //           onClick={() => handleDeleteShape(i)}
  //         />
  //       );
  //     }
  //     case "square": {
  //       const x = Math.min(startX, endX);
  //       const y = Math.min(startY, endY);
  //       const width = Math.abs(endX - startX);
  //       const height = Math.abs(endY - startY);
  //       return (
  //         <Rect
  //           key={i}
  //           x={x}
  //           y={y}
  //           width={width}
  //           height={height}
  //           stroke={color}
  //           strokeWidth={3}
  //           hitStrokeWidth={15}
  //           onClick={() => handleDeleteShape(i)}
  //         />
  //       );
  //     }
  //     case "triangle": {
  //       const centerX = (startX + endX) / 2;
  //       const centerY = (startY + endY) / 2;
  //       const size = Math.abs(endX - startX);
  //       return (
  //         <RegularPolygon
  //           key={i}
  //           x={centerX}
  //           y={centerY}
  //           sides={3}
  //           radius={size / 2}
  //           stroke={color}
  //           strokeWidth={3}
  //           hitStrokeWidth={15}
  //           onClick={() => handleDeleteShape(i)}
  //         />
  //       );
  //     }
  //     case "arrow": {
  //       return (
  //         <Arrow
  //           key={i}
  //           points={[startX, startY, endX, endY]}
  //           stroke={color}
  //           strokeWidth={3}
  //           pointerLength={12}
  //           pointerWidth={12}
  //           hitStrokeWidth={15}
  //           onClick={() => handleDeleteShape(i)}
  //         />
  //       );
  //     }
  //     default:
  //       return null;
  //   }
  // };

  // ------------------------------- 렌더링 -------------------------------
  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%" }}>
      <Stage
        width={stageSize.width}
        height={stageSize.height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchMove={handleMouseMove}
        onTouchEnd={handleMouseUp}
      >
        <Layer>
          {/* 펜 (3초간 서서히 사라짐) */}
          {lines.map((item, i) => (
            <Line
              key={`line-${i}`}
              points={item.line.points}
              stroke={"#ffffff"}
              strokeWidth={4}
              tension={0.5}
              lineCap="round"
              lineJoin="round"
              shadowColor={item.line.color || penColor}
              shadowBlur={15}
              shadowOffsetX={7}
              shadowOffsetY={7}
              shadowOpacity={0.8}
              opacity={item.opacity}
              globalCompositeOperation="lighter"
            />
          ))}

          {/* AR 마커 유지 */}
          {Array.isArray(arMarkers) &&
            arMarkers.map((marker) => (
              <Group key={marker.idx} x={marker.info.x} y={marker.info.y}>
                {/* 메인 원 (빛나는 부분) */}
                <Circle
                  radius={marker.info.size * 0.4}
                  fill={marker.color}
                  shadowColor={marker.color}
                  shadowBlur={15}
                  shadowOpacity={0.9}
                  opacity={marker.opacity ?? 1}
                />
                {/* 중심점 (하얀 불빛) */}
                <Circle
                  radius={marker.info.size * 0.15}
                  fill="#ffffff"
                  shadowColor="#fff"
                  shadowBlur={5}
                  opacity={0.9}
                />
                {/* 퍼지는 파동 (pulse 효과) */}
                <Circle
                  radius={marker.info.size * (marker.pulseScale ?? 1)}
                  stroke={marker.color}
                  strokeWidth={1.5}
                  opacity={marker.pulseOpacity ?? 0.5}
                />
              </Group>
            ))}

          {/* 지우개 */}
          {tool === "eraser" && eraserPos && (
            <Circle
              x={eraserPos.x}
              y={eraserPos.y}
              radius={8}
              stroke="#9ca3af"
              strokeWidth={2}
              dash={[4, 4]}
              listening={false}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
};