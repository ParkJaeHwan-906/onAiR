import { useSocket } from "../utils/socketContext";
import { useEffect, useRef, useState } from "react";
import { VideoBuffer } from "../utils/VideoBuffer";
import { PlaybackClock } from "../utils/PlaybackClock";
import "../styles/Communication/VideoFrame.css";

function BackdoorPage() {
  const socket = useSocket(); // 연결되어있는 소켓 객체를 가져옴

  // 1. useState 제거 -> useRef로 변경
  const imgRef = useRef<HTMLImageElement>(null);

  // 🎬 비디오 버퍼 관리
  const videoBufferRef = useRef<VideoBuffer | null>(null);

  // 비디오/오디오 동기화를 위한 clock
  const clockRef = useRef<PlaybackClock | null>(null);

  // 연결 상태만 최소한으로 관리 (UI 표시용)
  const [isConnected, setIsConnected] = useState(false);

  // 페이지 이탈/창 닫기 감지 및 통신 종료 이벤트 전송
  useEffect(() => {
    if (!socket) return;

    // 브라우저 창/탭 닫기, 새로고침 감지
    const handleBeforeUnload = () => {
      socket.emit("communication_close", null);
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    // 컴포넌트 언마운트 시 (다른 페이지로 이동)
    return () => {
      // socket.emit("communication_close", null);
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [socket]);

  // 오디오 재생용 useEffect
  useEffect(() => {
    if (!socket) return;
    let workletNode: AudioWorkletNode;

    // 1️⃣ AudioContext 생성 (오디오 처리를 담당하는 컨텍스트)
    const audioContext = new AudioContext({
      latencyHint: 'interactive', 
      sampleRate: 48000 // 브라우저 기준
    });

    // AudioWorklet 모듈 등록
    audioContext.audioWorklet.addModule("/audio-processor.js").then(() => {
      workletNode = new AudioWorkletNode(audioContext, "audio-processor");
      workletNode.connect(audioContext.destination);

      // 소켓 이벤트 수신
      const handleAudioFrame = (data: { 
        timestamp: number; 
        frame: ArrayBuffer 
      }) => {
        console.log("[DEBUG] 오디오 프레임 수신: " + data.timestamp)
        const floatData = new Float32Array(data.frame);
        // AudioWorklet으로 전달
        workletNode.port.postMessage({
          type: "audio_frame", 
          frame: floatData,
          timestamp: data.timestamp
        });
      };

      socket.on("audio_frame", handleAudioFrame); // 이벤트 리스너 등록

      // 6️⃣ cleanup: 컴포넌트 언마운트 시 연결 해제 및 메모리 정리
      return () => {
        if (workletNode) workletNode.disconnect();
        audioContext.close();
        socket.off("audio_frame", handleAudioFrame);
      };
    });
  }, [socket]);


  // 비디오 재생용 useEffect (버퍼링 적용)
  useEffect(() => {
    if (!socket) return;

    // 🎬 VideoBuffer 초기화
    const videoBuffer = new VideoBuffer({
      maxBufferSize: 10,     // 최대 10프레임
      // 프레임 준비 완료 시 콜백
      onFrameReady: (blobUrl: string) => {
        if (imgRef.current) {
          // 이전 Blob URL 정리
          if (imgRef.current.src.startsWith("blob:")) {
            URL.revokeObjectURL(imgRef.current.src);
          }
          imgRef.current.src = blobUrl;
        }
      },
    });
    
    videoBufferRef.current = videoBuffer;

    // 비디오 프레임 수신 핸들러
    const handleVideoFrame = (data: { timestamp: number; frame: ArrayBuffer }) => {
      // 🎬 버퍼에 프레임 추가 (버퍼가 알아서 재생 관리)
      videoBuffer.enqueue(data.timestamp, data.frame);

      // 첫 프레임 수신 시 연결 상태 업데이트
      if (!isConnected) {
        setIsConnected(true);
      }
    };

    // 서버로부터 video_frame 이벤트 수신
    socket.on("video_frame", handleVideoFrame);

    // cleanup 시점에 사용할 ref 값 저장
    const currentImgRef = imgRef.current;

    return () => {
      socket.off("video_frame", handleVideoFrame);
      
      // 🎬 비디오 버퍼 정리
      videoBuffer.clear();

      // Blob URL 정리 (메모리 누수 방지)
      if (currentImgRef && currentImgRef.src.startsWith("blob:")) {
        URL.revokeObjectURL(currentImgRef.src);
      }
    };
  }, [socket, isConnected]);


  // 비디오/오디오 동기화용 useEffect
  useEffect(() => {
    // clock 생성
    const clock = new PlaybackClock();
    clock.start();
    clockRef.current = clock;
  
    // 타이머 루프 생성 (60fps)
    const interval = setInterval(() => {
      const now = clock.now();
  
      // ⏱ video worker로 clock 전달
      if (videoBufferRef.current) {
        videoBufferRef.current.updateClock(now);
      }
    }, 16); // 약 60fps
  
    return () => clearInterval(interval);
  }, []);


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
            display: "block"
          }}
        />
      </div>
    </div>
  );
};

export default BackdoorPage;