// import { VideoTrack } from "@livekit/components-react"
import type { DrawingLine } from "../types/DrawingLine"
import { OverlayCanvas } from "./OverlayCanvas"

interface VideoProps {
  handleSerialize : (lines : DrawingLine[]) => void
}
export const VideoCanvas = ({handleSerialize} : VideoProps) => {
  return (
    <div
      style={{
        position: 'relative',
        width: '800px',
        height: '600px',
        backgroundColor: '#333'
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          zIndex: 1
        }}
      >
        {/* <VideoTrack /> */}
        <p style={{color: 'white'}}>(Video)</p>
      </div>
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          zIndex: 10
        }}
      >
        <OverlayCanvas
          handleSerialize={handleSerialize}
        />

      </div>
    </div>
  )
}