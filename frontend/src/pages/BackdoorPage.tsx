import { useSocket } from "../utils/socketContext";
import { useEffect, useRef } from "react";
import "../styles/Communication/VideoFrame.css";

function BackdoorPage() {
  const socket = useSocket();

  const videoCanvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);

  const ORI_W = 360;
  const ORI_H = 480;

  const getClassColor = (label: string) => {
    if (["AHU", "Boiler", "Chiler"].includes(label)) return "#2563eb";
    if (
      [
        "belt",
        "control_panel",
        "pressure_gauge",
        "thermometer",
        "temperature_FND",
        "AHU_pannel",
      ].includes(label)
    )
      return "#16a34a";
    if (
      [
        "run_light",
        "power_light",
        "overheat_light",
        "button_on",
        "button_off",
        "temperature_FND",
      ].includes(label)
    )
      return "#eab308";

    return "#9333ea";
  };

  /* -----------------------------------------------------
   * 1) 영상 그대로 그리기 (cover 제거)
   * -----------------------------------------------------*/
  const drawVideo = (img: HTMLImageElement, canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, ORI_W, ORI_H);
    ctx.drawImage(img, 0, 0, ORI_W, ORI_H);
  };

  /* -----------------------------------------------------
   * 2) Overlay 그대로 원본 좌표로 렌더링
   * -----------------------------------------------------*/
  const drawOverlay = (overlay: any) => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, ORI_W, ORI_H);

    ctx.lineWidth = 1.6;
    ctx.font = "12px Arial";

    overlay.boxes?.forEach((b: any) => {
      if (b.confidence < 0.4) return;

      const color = getClassColor(b.label);

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

  /* -----------------------------------------------------
   * 3) 영상 수신
   * -----------------------------------------------------*/
  useEffect(() => {
    if (!socket) return;

    const handleFrame = (data: { frame: ArrayBuffer }) => {
      const canvas = videoCanvasRef.current;
      if (!canvas) return;

      const img = new Image();
      img.onload = () => {
        drawVideo(img, canvas);
      };

      img.src = URL.createObjectURL(new Blob([data.frame]));
    };

    socket.on("video_frame", handleFrame);
    return () => {
      socket.off("video_frame", handleFrame);
    };
  }, [socket]);

  /* -----------------------------------------------------
   * 4) Overlay 수신
   * -----------------------------------------------------*/
  useEffect(() => {
    if (!socket) return;

    const handleOverlay = (data: any) => {
      drawOverlay(data);
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
