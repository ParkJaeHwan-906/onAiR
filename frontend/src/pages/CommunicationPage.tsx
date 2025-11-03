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
  const TOKEN : string = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJBUElZRGhEQVVQckxMNDciLCJleHAiOjE3NjIxNDI4NDEsInN1YiI6IjMiLCJuYW1lIjoi6rmA7KSA7ZiBIiwibWV0YWRhdGEiOiJtZXRhZGF0YSIsInZpZGVvIjp7InJvb21Kb2luIjp0cnVlLCJyb29tIjoicm9vbV8yMDI1LTExLTAzVDAzOjU3OjE2Ljg0NDQ1MzYxNCJ9LCJzaXAiOnt9fQ.DjdeFAthS-bZ_rJs_GeGEqS1ZkRjchNqFAHCXdJeUsc"

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
        token={TOKEN} serverUrl="wss://onair-tbfd0pr1.livekit.cloud" connect={true}
      >
        <VideoCanvas
          handleSerialize={handleSerialize}
        />
      </LiveKitRoom>
    </>
  )
}