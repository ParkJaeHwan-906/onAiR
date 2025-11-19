import { useSocket } from "../utils/socketContext";
import { useEffect, useRef } from "react";
import "../styles/Communication/VideoFrame.css";

function BackdoorPage() {
  const socket = useSocket();

  const videoCanvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);

  const ORI_W = 360;
  const ORI_H = 480;

  /* ------------------------------------------
   * 색상 함수
   * ------------------------------------------ */
  const getClassColor = (label: string) => {
    if (["AHU", "Boiler", "Chiler"].includes(label)) return "#2563eb";
    if (
      [
        "belt",
        "control_panel",
        "pressure_gauge",
        "thermometer",
        "AHU_pannel",
      ].includes(label)
    )
      return "#16a34a";
    if (["button_on", "button_off", "button_right"].includes(label))
      return "#f97316";
    if (
      [
        "run_light",
        "power_light",
        "overheat_light",
        "temperature_FND",
        "power_lamp",
        "drive_lamp",
        "overheat_lamp",
      ].includes(label)
    )
      return "#eab308";

    return "#9333ea";
  };

  /* ------------------------------------------
   * 비디오 그리기
   * ------------------------------------------ */
  const drawVideo = (img: HTMLImageElement, canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, ORI_W, ORI_H);
    ctx.drawImage(img, 0, 0, ORI_W, ORI_H);
  };

  /* ------------------------------------------
   * 오버레이 그리기
   * ------------------------------------------ */
  const drawOverlay = (overlay: any) => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, ORI_W, ORI_H);
    ctx.lineWidth = 1.6;
    ctx.font = "12px Arial";

    overlay?.boxes?.forEach((b: any) => {
      if (b.confidence < 0.2) return;

      const color = b.anomaly ? "#ff3333" : getClassColor(b.label);

      ctx.strokeStyle = color;
      ctx.fillStyle = color;

      ctx.strokeRect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1);
      ctx.fillText(
        `${b.label} ${(b.confidence * 100).toFixed(1)}%`,
        b.x1,
        b.y1 - 4
      );
    });
  };

  /* ------------------------------------------
   * 싱크용 버퍼
   * ------------------------------------------ */
  const frameBuffer = useRef<any[]>([]);
  const overlayBuffer = useRef<any[]>([]);
  const MAX_BUFFER = 10;

  /* ------------------------------------------
   * 렌더 루프 + 언마운트 시 정리
   * ------------------------------------------ */
  const rafId = useRef<number | null>(null);

  useEffect(() => {
    const startRenderLoop = () => {
      const loop = () => {
        const canvas = videoCanvasRef.current;

        if (canvas && frameBuffer.current.length > 0) {
          const { img, timestamp } = frameBuffer.current.shift();
          drawVideo(img, canvas);

          // timestamp 기준 가장 가까운 overlay 찾기
          let bestOverlay = null;
          let smallestDiff = Infinity;

          overlayBuffer.current.forEach((ov) => {
            const diff = Math.abs(ov.timestamp - timestamp);
            if (diff < smallestDiff) {
              smallestDiff = diff;
              bestOverlay = ov;
            }
          });

          if (bestOverlay) drawOverlay(bestOverlay);
        }

        rafId.current = requestAnimationFrame(loop);
      };

      rafId.current = requestAnimationFrame(loop);
    };

    startRenderLoop();

    /* cleanup */
    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);

      const v = videoCanvasRef.current;
      const o = overlayCanvasRef.current;
      v?.getContext("2d")?.clearRect(0, 0, ORI_W, ORI_H);
      o?.getContext("2d")?.clearRect(0, 0, ORI_W, ORI_H);

      frameBuffer.current = [];
      overlayBuffer.current = [];
    };
  }, []);

  /* ------------------------------------------
   * 영상 수신 → buffer push
   * ------------------------------------------ */
  useEffect(() => {
    if (!socket) return;

    const handleFrame = (data: { frame: ArrayBuffer }) => {
      const canvas = videoCanvasRef.current;
      if (!canvas) return;

      const timestamp = Date.now();

      const img = new Image();
      img.onload = () => {
        frameBuffer.current.push({ img, timestamp });
        if (frameBuffer.current.length > MAX_BUFFER)
          frameBuffer.current.shift();
      };

      img.src = URL.createObjectURL(new Blob([data.frame]));
    };

    socket.on("video_frame", handleFrame);
    return () => {
      socket.off("video_frame", handleFrame);
    };
  }, [socket]);

  /* ------------------------------------------
   * Overlay 수신 → buffer push
   * ------------------------------------------ */
  useEffect(() => {
    if (!socket) return;

    const handleOverlay = (data: any) => {
      const timestamp = data.timestamp;
      // const hasAnomaly = data.boxes?.some((b: any) => b.anomaly) ?? false;
      // console.log("📌 frame anomaly:", hasAnomaly);

      // // 로그
      // console.group("🟦 YOLO Overlay 수신됨");
      // console.log("📌 timestamp:", timestamp);
      // // console.log("📌 anomaly:", hasAnomaly);
      // console.log("📌 total boxes:", data.boxes?.length || 0);
      // data.boxes?.forEach((b: any, idx: number) => {
      //   console.group(`▶ Box ${idx + 1}`);
      //   console.log("label:", b.label);
      //   console.log("confidence:", b.confidence.toFixed(3));
      //   console.log("x1:", b.x1, "y1:", b.y1);
      //   console.log("x2:", b.x2, "y2:", b.y2);
      //   console.log("anomaly:", b.anomaly);
      //   console.groupEnd();
      // });
      // console.groupEnd();

      overlayBuffer.current.push({ ...data, timestamp });
      if (overlayBuffer.current.length > MAX_BUFFER)
        overlayBuffer.current.shift();
    };

    socket.on("video_overlay", handleOverlay);
    return () => {
      socket.off("video_overlay", handleOverlay);
    };
  }, [socket]);

  return (
    <div className="backdoor-canvas">
      <canvas
        ref={videoCanvasRef}
        className="backdoor-canvas-image"
        width={360}
        height={480}
      />
      <canvas
        ref={overlayCanvasRef}
        className="backdoor-canvas-overlay"
        width={360}
        height={480}
      />
    </div>
  );
}

export default BackdoorPage;
