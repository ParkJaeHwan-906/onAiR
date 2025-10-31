// import { Room } from "livekit-client";
// import { OverlayCanvas } from "../components/OverlayCanvas"
import { VideoCanvas } from "../components/VideoCanvas";
import type { DrawingLine } from "../types/DrawingLine";
// import { useEffect, useState } from "react";
import { LiveKitRoom } from "@livekit/components-react";

export const CommunicationPage = () => {
  const handleSerialize = (lines : DrawingLine[]) => {
    const json = JSON.stringify(lines)
    console.log(json);    
  }

  // const [room] = useState(() => new Room({}))

  // useEffect(() => {
  //   room.connect('your-server-url', 'your-token')
  //   return () => {
  //     room.disconnect()
  //   }
  // }, [room])

  return (
    <>
      <LiveKitRoom 
        token="<livekit-token>" serverUrl="<url-to-livekit-server>" connect={true}
      >
        <VideoCanvas
          handleSerialize={handleSerialize}
        />
      </LiveKitRoom>
    </>
  )
}