// import { VideoTrack } from "@livekit/components-react"
import { useTracks, VideoTrack } from "@livekit/components-react";
import type { DrawingLine } from "../../types/DrawingLine";
import { OverlayCanvas } from "./OverlayCanvas";
import { Track } from "livekit-client";

interface VideoProps {
  handleSerialize: (lines: DrawingLine[]) => void;
  penColor: string;
  currentTool: string;
}

export const VideoCanvas = ({
  penColor,
  currentTool,
}: VideoProps) => {
  const cameraTracks = useTracks([Track.Source.Camera])
  if (cameraTracks.length === 0) {
    return <div>Loading...</div>
  }
  const androidTrackRef = cameraTracks[0]
  return (
    <div
      style={{
        position: "relative",
        width: "940px",
        height: "857px",
        backgroundColor: "#333",
        borderRadius: "16px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          zIndex: 1,
        }}
      >
        <VideoTrack
          trackRef={androidTrackRef}
          style={{ width: "100%", height: "100%" }}
        />
        {/* <p style={{ color: "white" }}>(Video)</p> */}
      </div>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          zIndex: 10,
        }}
      >
        <OverlayCanvas
          penColor={penColor}
          tool={currentTool}
        />
      </div>
    </div>
  );
};
