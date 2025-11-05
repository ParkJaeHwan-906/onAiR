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
  const videoCanvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(new Image());
  const [isConnected, setIsConnected] = useState(false); // 첫 프레임 수신 여부


  useEffect(() => {
    const canvas = videoCanvasRef.current;
    const ctx = canvas?.getContext('2d');
    const img = imgRef.current;
    if (!canvas || !ctx) return;

    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      if (!isConnected) setIsConnected(true);
    };

    // 서버로부터 video_frame 이벤트 수신
    socket.on('video_frame', (data) => {
      img.src = `data:image/jpeg;base64,${data.frame}`;
    });

    return () => {
      socket.off('video_frame'); // clean up
    };
  }, [socket]);

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
        <canvas 
          ref={videoCanvasRef}
          width={940}
          height={857}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
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
