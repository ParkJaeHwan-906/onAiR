import React from "react";
// import VideoCanvas from "../VideoCanvas" // 비디오 박스
import ControlBar from "./ControlBar"
import "../../styles/Communication/VideoFrame.css"

const VideoFrame = () => {
    return (
        <div className="video-frame">
            <div className="video-canvas-wrap">
                {/* <VideoCanvas /> */}
            </div>
            <div className="control-bar-wrap">
                <ControlBar />
            </div>
        </div>
    );
};

export default VideoFrame;
