import React, { useEffect, useRef, useState } from "react";
import "../../styles/CCTV.css";
import type { CCTVItem } from "../../types/cctv";

import { useSocket } from "../../utils/socketContext";
import { VideoBuffer } from "../../utils/VideoBuffer";
import { PlaybackClock } from "../../utils/PlaybackClock";

interface CameraTileProps {
  camera: CCTVItem;
  onClick: () => void;
}

const CameraTile: React.FC<CameraTileProps> = ({ camera, onClick }) => {
  const socket = useSocket();

  // 1번 카메라인지 체크
  const isTargetCamera = camera.id === 1;

  const imgRef = useRef<HTMLImageElement>(null);
  const videoBufferRef = useRef<VideoBuffer | null>(null);
  const clockRef = useRef<PlaybackClock | null>(null);

  const [isLiveConnected, setIsLiveConnected] = useState(false);

  /* --------------------------------------------
      실시간 영상 (ID=1만)
  -------------------------------------------- */
  useEffect(() => {
    if (!socket) return;
    if (!isTargetCamera) return; // 나머지 카메라는 WebSocket 연결 안 함

    const videoBuffer = new VideoBuffer({
      maxBufferSize: 10,
      onFrameReady: (blobUrl) => {
        if (imgRef.current) {
          if (imgRef.current.src.startsWith("blob:")) {
            URL.revokeObjectURL(imgRef.current.src);
          }
          imgRef.current.src = blobUrl;
        }
      },
    });

    videoBufferRef.current = videoBuffer;

    const handleVideoFrame = (data: {
      timestamp: number;
      frame: ArrayBuffer;
    }) => {
      videoBuffer.enqueue(data.timestamp, data.frame);
      if (!isLiveConnected) setIsLiveConnected(true);
    };

    socket.on("video_frame", handleVideoFrame);

    const imgNode = imgRef.current;

    return () => {
      socket.off("video_frame", handleVideoFrame);
      videoBuffer.clear();
      if (imgNode?.src.startsWith("blob:")) URL.revokeObjectURL(imgNode.src);
    };
  }, [socket, isTargetCamera, isLiveConnected]);

  /* --------------------------------------------
      playback clock (ID=1만)
  -------------------------------------------- */
  useEffect(() => {
    if (!isTargetCamera || !isLiveConnected) return;

    const clock = new PlaybackClock();
    clock.start();
    clockRef.current = clock;

    const interval = setInterval(() => {
      const now = clock.now();
      videoBufferRef.current?.updateClock(now);
    }, 16);

    return () => clearInterval(interval);
  }, [isTargetCamera, isLiveConnected]);

  /* --------------------------------------------
      렌더링 (ID=1만 실시간 or offline)
      나머지는 항상 더미 영상 재생
  -------------------------------------------- */
  return (
    <div
      className={`cctv-tile ${
        isTargetCamera && !isLiveConnected ? "disabled" : ""
      }`}
      onClick={() =>
        isTargetCamera ? isLiveConnected && onClick() : onClick()
      }
    >
      {/* ID=1 → LIVE or OFFLINE */}
      {/* {isTargetCamera ? (
        isLiveConnected ? (
          <>
            <img ref={imgRef} className="cctv-video" alt="Live CCTV" />

            <div className="cctv-label live">
              {camera.worker.name} | {camera.equipment.name}
              <span className="live-badge">● LIVE</span>
            </div>
          </>
        ) : (
          <>
            <div className="cctv-offline-box">
              <span className="offline-title">OFFLINE</span>
              <span className="offline-sub">연결된 영상 없음</span>
            </div>

            <div className="cctv-label offline">
              {camera.worker.name} | {camera.equipment.name}
            </div>
          </>
        )
      ) : (
        <>
          <video
            src={camera.videoUrl}
            autoPlay
            muted
            loop
            playsInline
            className="cctv-video"
          />

          <div className="cctv-label live">
            {camera.worker.name} | {camera.equipment.name}
            <span className="live-badge">● LIVE</span>
          </div>
        </>
      )} */}
      {/* 전체 다 더미데이터로 변경 */}
      <>
        <video
          src={camera.videoUrl}
          autoPlay
          muted
          loop
          playsInline
          className="cctv-video"
        />

        <div className="cctv-label live">
          {camera.worker.name} | {camera.equipment.name}
          <span className="live-badge">● LIVE</span>
        </div>
      </>
    </div>
  );
};

export default CameraTile;
