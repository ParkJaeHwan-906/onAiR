import React, { useEffect, useRef, useState } from "react";
import type { CCTVItem } from "../../types/cctv";
import { PhoneCall, Headphones, Mic } from "lucide-react";

import { useSocket } from "../../utils/socketContext";
import { VideoBuffer } from "../../utils/VideoBuffer";
import { PlaybackClock } from "../../utils/PlaybackClock";

import "../../styles/CCTV.css";

interface CameraDetailProps {
  camera: CCTVItem;
  onClose: () => void;
}

const CameraDetail: React.FC<CameraDetailProps> = ({ camera, onClose }) => {
  const socket = useSocket();

  const isTargetCamera = camera.id === 1;

  const imgRef = useRef<HTMLImageElement>(null);
  const videoBufferRef = useRef<VideoBuffer | null>(null);
  const clockRef = useRef<PlaybackClock | null>(null);

  const [isLiveConnected, setIsLiveConnected] = useState(false);

  /* --------------------------------------------
      LIVE (ID=1만)
  -------------------------------------------- */
  useEffect(() => {
    if (!socket || !isTargetCamera) return;

    const videoBuffer = new VideoBuffer({
      maxBufferSize: 12,
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
      clock (ID=1만)
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

  const isLive = isTargetCamera && isLiveConnected;

  return (
    <div className="detail-view">
      <button className="detail-close-inline" onClick={onClose}>
        ✕
      </button>

      <div className="detail-video-box">
        {isLive ? (
          <>
            <img ref={imgRef} className="detail-video-inline" alt="Live CCTV" />

            <div className="detail-info-inline">
              <div className="detail-label-inline">
                {camera.worker.name} | {camera.equipment.name}
                <span className="live-badge" style={{ marginLeft: 6 }}>
                  ● LIVE
                </span>
              </div>

              <div className="detail-inline-buttons">
                <button className="detail-ctrl-btn call">
                  <PhoneCall size={16} />
                </button>
                <button className="detail-ctrl-btn listen">
                  <Headphones size={16} />
                </button>
                <button className="detail-ctrl-btn talk">
                  <Mic size={16} />
                </button>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* ID=2~6 또는 1 OFFLINE → 더미 영상 */}
            <video
              src={camera.videoUrl}
              autoPlay
              muted
              loop
              playsInline
              className="detail-video-inline"
            />

            <div className="detail-info-inline">
              <div className="detail-label-inline">
                {camera.worker.name} | {camera.equipment.name}
              </div>

              <div className="detail-inline-buttons">
                <button className="detail-ctrl-btn call">
                  <PhoneCall size={16} />
                </button>
                <button className="detail-ctrl-btn listen">
                  <Headphones size={16} />
                </button>
                <button className="detail-ctrl-btn talk">
                  <Mic size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default CameraDetail;
