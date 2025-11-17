import React, { useEffect, useRef, useState } from "react";
import "../../styles/CCTV.css";
import type { CCTVItem } from "../../types/cctv";

// 소켓
import { useSocket } from "../../utils/socketContext";

// Backdoor 스트림 처리 유틸
import { VideoBuffer } from "../../utils/VideoBuffer";
import { PlaybackClock } from "../../utils/PlaybackClock";

interface CameraTileProps {
  camera: CCTVItem;
  onClick: () => void;
}

const CameraTile: React.FC<CameraTileProps> = ({ camera, onClick }) => {
  const socket = useSocket();

  // img에 blob url 넣기 위한 ref
  const imgRef = useRef<HTMLImageElement>(null);
  const videoBufferRef = useRef<VideoBuffer | null>(null);
  const clockRef = useRef<PlaybackClock | null>(null);

  // 🔥 실제 영상 프레임이 들어오면 true 되는 값
  const [isLiveConnected, setIsLiveConnected] = useState(false);

  /* --------------------------------------------
      실시간 영상 프레임 수신 처리
  -------------------------------------------- */
  useEffect(() => {
    if (!socket) return;

    // 1) 비디오 버퍼 초기화
    const videoBuffer = new VideoBuffer({
      maxBufferSize: 8,
      onFrameReady: (blobUrl) => {
        if (imgRef.current) {
          // 이전 blob 정리
          if (imgRef.current.src.startsWith("blob:")) {
            URL.revokeObjectURL(imgRef.current.src);
          }
          imgRef.current.src = blobUrl;
        }
      },
    });

    videoBufferRef.current = videoBuffer;

    // 소켓 프레임 수신
    const handleVideoFrame = (data: {
      timestamp: number;
      frame: ArrayBuffer;
    }) => {
      videoBuffer.enqueue(data.timestamp, data.frame);

      // 첫 프레임 들어온 순간 → LIVE
      if (!isLiveConnected) setIsLiveConnected(true);
    };

    socket.on("video_frame", handleVideoFrame);

    const imgNode = imgRef.current;

    return () => {
      socket.off("video_frame", handleVideoFrame);
      videoBuffer.clear();

      if (imgNode?.src.startsWith("blob:")) URL.revokeObjectURL(imgNode.src);
    };
  }, [socket, isLiveConnected]);

  /* --------------------------------------------
      비디오 재생 clock (프레임 간 시간 맞추기)
  -------------------------------------------- */
  useEffect(() => {
    if (!isLiveConnected) return;

    const clock = new PlaybackClock();
    clock.start();
    clockRef.current = clock;

    const interval = setInterval(() => {
      const now = clock.now();
      if (videoBufferRef.current) {
        videoBufferRef.current.updateClock(now);
      }
    }, 16); // 약 60fps

    return () => clearInterval(interval);
  }, [isLiveConnected]);

  /* --------------------------------------------
      렌더링
  -------------------------------------------- */
  return (
    <div
      className={`cctv-tile ${isLiveConnected ? "" : "disabled"}`}
      onClick={() => isLiveConnected && onClick()} // 오프라인 클릭 불가
    >
      {isLiveConnected ? (
        <>
          {/* 🔴 LIVE 영상 (img로 표시) */}
          <img
            ref={imgRef}
            className="cctv-video"
            alt="Live CCTV"
            style={{ display: "block" }}
          />

          <div className="cctv-label live">
            {camera.worker.name} | {camera.equipment.name}
            <span className="live-badge">● LIVE</span>
          </div>
        </>
      ) : (
        <>
          {/* ⚪ 오프라인 상태 UI */}
          <div className="cctv-offline-box">
            <span className="offline-title">OFFLINE</span>
            <span className="offline-sub">연결된 영상 없음</span>
          </div>

          <div className="cctv-label offline">
            {camera.worker.name} | {camera.equipment.name}
          </div>
        </>
      )}
    </div>
  );
};

export default CameraTile;
