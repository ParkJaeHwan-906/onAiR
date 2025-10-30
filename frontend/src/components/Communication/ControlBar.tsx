import React from "react";
import { Mic, Video, Settings, PenTool, Circle, Maximize2, Phone } from "lucide-react";
import "../../styles/Communication/ControlBar.css";

const ControlBar = () => {
  return (
    <div className="control-bar">
      <div className="control-inner">
        {/* 왼쪽 그룹 */}
        <div className="icon-group">
          <button className="icon-button">
            <PenTool className="icon" size={18}/>
          </button>
          <button className="icon-button">
            <Circle className="icon" size={18}/>
          </button>
          <button className="icon-button">
            <Maximize2 className="icon" size={18}/>
          </button>
        </div>

        {/* 중앙 종료 버튼 */}
        <button className="icon-button end-call">
          <Phone className="icon end-call-icon" size={18}/>
        </button>

        {/* 오른쪽 그룹 */}
        <div className="icon-group">
          <button className="icon-button">
            <Mic className="icon" size={18}/>
          </button>
          <button className="icon-button">
            <Video className="icon" size={18}/>
          </button>
          <button className="icon-button">
            <Settings className="icon" size={18}/>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ControlBar;
