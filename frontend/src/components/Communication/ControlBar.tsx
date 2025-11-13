import React, { useState, useRef, useEffect } from "react";
import { useSocket } from "../../utils/socketContext";
import { Eraser, MapPin, PenLine, Phone } from "lucide-react";
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
  // // 열려있는 메뉴: color, shape, eraser, none
  const [openMenu, setOpenMenu] = useState<
    "none" | "color" | "shape" | "eraser"
  >("none");

  // // 전체 바 감싸는 ref (외부 클릭 감지용)
  const wrapperRef = useRef<HTMLDivElement>(null);
  // 펜 색상 선택용 팔레트
  const colors = ["#000000", "#ff0000", "#0000ff", "#00ff00", "#ffff00"];

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
    const newTool = currentTool === tool ? "" : tool;
    console.log("🎨 [ControlBar] tool 변경:", newTool);
    setCurrentTool(newTool);
    setOpenMenu("none");
  };

  return (
    <div className="control-bar">
      <div className="control-inner">
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
          <PenLine className="icon" size={14} />
        </button>

        <button
          className={`icon-button ${currentTool === "marker" ? "active" : ""}`}
          onClick={() => handleToolChange("marker")}
        >
          <MapPin className="icon" size={14} />
        </button>

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
            socket.emit("communication_close", null);
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
