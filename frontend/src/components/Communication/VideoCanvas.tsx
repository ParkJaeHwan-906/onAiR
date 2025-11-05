// import { VideoTrack } from "@livekit/components-react"
import type { DrawingLine } from "../../types/DrawingLine";
import { OverlayCanvas } from "./OverlayCanvas";
import { useSocket } from "../../utils/socketContext";
import { useEffect, useRef, useState } from "react";

interface VideoProps {
  handleSerialize: (lines: DrawingLine[]) => void;
  penColor: string;
  currentTool: string;
}

export const VideoCanvas = ({
  penColor,
  currentTool,
}: VideoProps) => {
  const socket = useSocket();   // 연결되어있는 소켓 객체를 가져옴
  
  // 1. useState 제거 -> useRef로 변경
  const imgRef = useRef<HTMLImageElement>(null);
  
  // 연결 상태만 최소한으로 관리 (UI 표시용)
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if(!socket) return;

    let frameCount = 0;
    let lastLogTime = performance.now();

    const handleVideoFrame = (data: {frame: string}) => {
      // 2. 리렌더링 없이 DOM 조작으로 이미지 교체
      if(imgRef.current){
        imgRef.current.src = `data:image/jpeg;base64,${data.frame}`;

        // 첫 프레임 수신 시 연결 상태 업데이트(한번만 실행됨)
        if(!isConnected){
          setIsConnected(true);
        }
      }

      // === 🔍 디버깅 코드 시작 ===
      frameCount++;
      const now = performance.now();
      // 1초마다 로그 출력
      if (now - lastLogTime >= 1000) {
        const fps = frameCount;
        // Base64 길이로 대략적인 이미지 크기(KB) 계산
        const sizeInKB = (data.frame.length * 0.75) / 1024;
        
        console.log(`📺 수신 FPS: ${fps} | 프레임 크기: 약 ${sizeInKB.toFixed(1)} KB`);

        frameCount = 0;
        lastLogTime = now;
      }
      // === 🔍 디버깅 코드 끝 ===
      
    }

    // 서버로부터 video_frame 이벤트 수신
    socket.on('video_frame', handleVideoFrame);

    return () => {
      socket.off('video_frame', handleVideoFrame); // clean up
    };
  }, [socket, isConnected]);

  return (
    <div
      style={{
        position: "relative",
        width: "940px",
        height: "857px",
        backgroundColor: "#333",
        borderRadius: "16px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          zIndex: 1,
        }}
      >
        {/* <VideoTrack /> */}
        {/* <p style={{ color: "white" }}>(Video)</p> */}
        
        {/* 3. ref 연결 및 초기 상태 제어 */}
        <img 
          ref={imgRef}
          alt="Video Stream"
          style={{ 
            width: '100%', 
            height: '100%', 
            objectFit: 'cover',
            display: isConnected ? 'block' : 'none' // 연결 전에는 숨김
          }}
        />
        
        {!isConnected && (
          <p style={{ 
            color: 'white',
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)'
          }}>
            연결 대기중...
          </p>
        )}
      </div>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          zIndex: 10,
        }}
      >
        <OverlayCanvas
          penColor={penColor}
          tool={currentTool}
        />
      </div>
    </div>
  );
};
