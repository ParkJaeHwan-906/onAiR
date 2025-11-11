import React, { useState, useRef, useEffect } from "react";
import { useSocket } from "../../utils/socketContext";
import {
  Eraser,
  Circle,
  Square,
  Triangle,
  MoveUpRight,
  PenLine,
  Phone,
} from "lucide-react";
import "../../styles/Communication/ControlBar.css";

/**
 * ControlBar 컴포넌트
 * - 영상 하단에 툴바를 구성하는 영역
 * - 펜, 도형, 지우개, 종료 버튼 포함
 */

interface ControlBarProps {
  currentTool: string;
  setCurrentTool: React.Dispatch<React.SetStateAction<string>>;
  penColor: string;
  setPenColor: React.Dispatch<React.SetStateAction<string>>;
  onEndCall?: () => void;
}

const ControlBar = ({
  currentTool,
  setCurrentTool,
  penColor,
  setPenColor,
  onEndCall,
}: ControlBarProps) => {
  // socket 인스턴스 가져오기
  const socket = useSocket();
  // 열려있는 메뉴: color, shape, eraser, none
  const [openMenu, setOpenMenu] = useState<
    "none" | "color" | "shape" | "eraser"
  >("none");
  // 현재 선택된 도형 (버튼에 표시용)
  const [selectedShape, setSelectedShape] = useState("square");
  // 전체 바 감싸는 ref (외부 클릭 감지용)
  const wrapperRef = useRef<HTMLDivElement>(null);
  // 펜 색상 선택용 팔레트
  const colors = ["#000000", "#ff0000", "#0000ff", "#00ff00", "#ffff00"];
  // 도형 선택용 (Circle, Square, Triangle, Arrow)
  const shapes = [
    { name: "circle", icon: <Circle className="icon" size={14} /> },
    { name: "square", icon: <Square className="icon" size={14} /> },
    { name: "triangle", icon: <Triangle className="icon" size={14} /> },
    { name: "arrow", icon: <MoveUpRight className="icon" size={14} /> },
  ];

  // 외부 클릭 시 메뉴 자동 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setOpenMenu("none");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  /**
   * 도구 버튼 클릭 시 툴 변경
   * - 같은 툴을 다시 클릭하면 비활성화
   * - 다른 메뉴 비활성화
   */
  const handleToolChange = (tool: string) => {
    setCurrentTool((prev) => (prev === tool ? "" : tool));
    setOpenMenu("none");
  };

  return (
    <div className="control-bar">
      <div ref={wrapperRef} className="control-inner">
        {/* 색상 버튼 */}
        <div className="pen-wrapper">
          <button
            className="icon-button color-button"
            style={{ backgroundColor: penColor }}
            onClick={() => setOpenMenu(openMenu === "color" ? "none" : "color")}
          >
            <div
              className="color-preview"
              style={{ backgroundColor: penColor }}
            />
          </button>

          {/* 색상 선택 메뉴 */}
          <div
            className={`color-palette ${openMenu === "color" ? "visible" : ""}`}
          >
            {colors.map((color) => (
              <button
                key={color}
                className={`color-dot ${penColor === color ? "selected" : ""}`}
                style={{ backgroundColor: color }}
                onClick={() => {
                  setPenColor(color);
                  setOpenMenu("none");
                }}
              />
            ))}
          </div>
        </div>

        {/* 펜 */}
        <button
          className={`icon-button ${currentTool === "pen" ? "active" : ""}`}
          onClick={() => handleToolChange("pen")}
        >
          <PenLine className="icon" size={14} style={{ color: "#111827" }} />
        </button>

        {/* 도형 */}
        <div className="shape-wrapper">
          <button
            className={`icon-button ${
              ["circle", "square", "triangle", "arrow"].includes(currentTool)
                ? "active"
                : ""
            }`}
            onClick={() => {
              handleToolChange("shape");
              setOpenMenu(openMenu === "shape" ? "none" : "shape");
            }}
          >
            {shapes.find((s) => s.name === selectedShape)?.icon || (
              <Square className="icon" size={14} />
            )}
          </button>

          {/* 도형 선택 메뉴 */}
          <div
            className={`shape-palette ${openMenu === "shape" ? "visible" : ""}`}
          >
            {shapes.map((shape) => (
              <button
                key={shape.name}
                className={`icon-button ${
                  currentTool === shape.name ? "active" : ""
                }`}
                onClick={() => {
                  handleToolChange(shape.name);
                  setSelectedShape(shape.name);
                }}
              >
                {shape.icon}
              </button>
            ))}
          </div>
        </div>

        {/* 지우개 */}
        <div className="eraser-wrapper">
          <button
            className={`icon-button ${
              currentTool === "eraser" ? "active" : ""
            }`}
            onClick={() => handleToolChange("eraser")}
          >
            <Eraser className="icon" size={14} />
          </button>
        </div>

        {/* 중앙 종료 버튼 */}
        <button
          className="icon-button end-call"
          onClick={() => {
            setOpenMenu("none");
            socket.emit("video_stream", { state: "on" });
            if (onEndCall) {
              onEndCall();
            }
          }}
        >
          <Phone className="icon end-call-icon" size={14} />
        </button>
      </div>
    </div>
  );
};

export default ControlBar;
