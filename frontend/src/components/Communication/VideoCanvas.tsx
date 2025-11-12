// import { VideoTrack } from "@livekit/components-react"
import type { DrawingLine } from "../../types/DrawingLine";
import { OverlayCanvas } from "./OverlayCanvas";
import { useSocket } from "../../utils/socketContext";
import { useEffect, useRef, useState } from "react";
import "../../styles/Communication/VideoFrame.css";

interface VideoProps {
  handleSerialize: (lines: DrawingLine[]) => void;
  penColor: string;
  currentTool: string;
}

export const VideoCanvas = ({ penColor, currentTool }: VideoProps) => {
  const socket = useSocket(); // 연결되어있는 소켓 객체를 가져옴

  // 1. useState 제거 -> useRef로 변경
  const imgRef = useRef<HTMLImageElement>(null);

  // 오디오 재생을 위한 ref
  const audioContextRef = useRef<AudioContext | null>(null);

  // 연결 상태만 최소한으로 관리 (UI 표시용)
  const [isConnected, setIsConnected] = useState(false);


  // 오디오 재생용 useEffect
  useEffect(() => {
    if (!socket) return;

    // 1️⃣ AudioContext 생성 (오디오 처리를 담당하는 컨텍스트)
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    // AudioWorklet 모듈 등록
    audioContext.audioWorklet.addModule("/audio-processor.js").then(() => {
      const workletNode = new AudioWorkletNode(audioContext, "audio-processor");
      workletNode.connect(audioContext.destination);

      // 소켓 이벤트 수신
      const handleAudioFrame = (data: ArrayBuffer) => {
        const floatData = new Float32Array(data);
        // AudioWorklet으로 전달
        workletNode.port.postMessage({type: "audio_frame", frame: floatData});
      };

      socket.on("audio_frame", handleAudioFrame); // 이벤트 리스너 등록

      // 6️⃣ cleanup: 컴포넌트 언마운트 시 연결 해제 및 메모리 정리
      return () => {
        socket.off("audio_frame", handleAudioFrame);
        workletNode.disconnect();
        audioContext.close();
      };
    });
  }, [socket]);


  // 비디오 재생용 useEffect
  useEffect(() => {
    if (!socket) return;

    const handleVideoFrame = (data: ArrayBuffer) => {
      // 2. 리렌더링 없이 DOM 조작으로 이미지 교체
      if (imgRef.current) {
        // ArrayBuffer를 Blob으로 변환
        const blob = new Blob([data], { type: "image/jpeg" });
        // 이전 Blob URL 정리 (메모리 누수 방지)
        if (imgRef.current.src.startsWith("blob:")) {
          URL.revokeObjectURL(imgRef.current.src);
        }
        const imageUrl = URL.createObjectURL(blob);

        imgRef.current.src = imageUrl;

        // 첫 프레임 수신 시 연결 상태 업데이트(한번만 실행됨)
        if (!isConnected) {
          setIsConnected(true);
        }
      }
    };

    // 서버로부터 video_frame 이벤트 수신
    socket.on("video_frame", handleVideoFrame);

    // cleanup 시점에 사용할 ref 값 저장
    const currentImgRef = imgRef.current;

    return () => {
      socket.off("video_frame", handleVideoFrame); // clean up

      // Blob URL 정리 (메모리 누수 방지)
      if (currentImgRef && currentImgRef.src.startsWith("blob:")) {
        URL.revokeObjectURL(currentImgRef.src);
      }
    };
  }, [socket, isConnected]);

  return (
    <div className="video-canvas">
      <div className="video-canvas-inner">
        {/* <VideoTrack /> */}
        {/* <p style={{ color: "white" }}>(Video)</p> */}

        {/* 3. ref 연결 및 초기 상태 제어 */}
        <img
          ref={imgRef}
          alt="Video Stream"
          className="video-canvas-image"
          style={{
            display: isConnected ? "block" : "none", // 연결 전에는 숨김
          }}
        />

        {!isConnected && <p className="video-canvas-waiting">연결 대기중...</p>}
      </div>
      <div className="video-canvas-overlay">
        <OverlayCanvas penColor={penColor} tool={currentTool} />
      </div>
    </div>
  );
};
