// import { config } from 'process';
// import { useEffect, useRef, useState } from 'react';

// interface WebRTCProps {
//   roomId: string;
// }

// const WebRTCComponent = (
//   { roomId }: WebRTCProps
// ) => {
//   const [localStream, setLocalStream] = useState<MediaStream | null>(null)
//   const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null)
//   const [isConnected, setIsConnected] = useState(false)
//   const [isCallStarted, setIsCallStarted] = useState(false)
//   const [initError, setInitError] = useState<string | null>(null)
  
//   const localVideoRef = useRef<HTMLVideoElement>(null)
//   const remoteVideoRef = useRef<HTMLVideoElement>(null)
//   const peerConnection = useRef<RTCPeerConnection | null>(null)
//   const websocket = useRef<WebSocket | null>(null)

//   const configuration: RTCConfiguration = {
//     iceServers: [
//       {
//         urls: 'turn:[]:3478',
//         username: 'turnuser',
//         credential: ''
//       }
//     ]
//   }

//   useEffect(() => {
//     const init = async () => {
//       try {
//         console.log('Checking WebRTC support...');
//         const support = checkWebRTCSupport()
//         if (!support.webRTC || !support.getUserMedia) {
//           throw new Error('Your browser does not support required WebRTC features')
//         }

//         console.log('Initializing WebRTC support...')

//         // WebSocket 연결
//         websocket.current = new WebSocket('ws://[WEBSOCKET_SERVER_URL]/signal')

//         websocket.current.onopen = () => {
//           console.log('WebSocket connected');
//           sendSignalingMessage({
//             type: 'join',
//             roomId
//           })   
//         }

//         let stream: MediaStream
//         try {
//           stream = await navigator.mediaDevices.getUserMedia({
//             video: {
//               width: { ideal:1280 },
//               height: { ideal: 720 }
//             },
//             audio: true
//           })
//           console.log('Local media stream obtained');
//         } catch (mediaError) {
//           console.error('Media access error:', mediaError);
//           throw new Error("Unable to access camera and microphone");          
//         }

//         setLocalStream(stream)
//         if (localVideoRef.current) {
//           localVideoRef.current.srcObject = stream
//         }

//         peerConnection.current = new RTCPeerConnection(configuration)
//         console.log('PeerConnection created with config: ', configuration)

//         peerConnection.current = new RTCPeerConnection(configuration)
//         console.log('PeerConnection created with config: ', configuration)

//         stream.getTracks().forEach(track => {
//           if(peerConnection.current) {
//             console.log('Adding track to peer connection:');
//             peerConnection.current.addTrack(track, stream)
//           }
//         })


//         peerConnection.current.onicecandidate = (event) => {
//           if (event.candidate) {
//             console.log('Sending ICE candidate');
//             sendSignalingMessage({
//               type: 'ice-candidate',
//               data: event.candidate,
//               roomId
//             })
            
//           }
//         } 
//         peerConnection.current.onconnectionstatechange = () => {
//           console.log('Connection state changed:', peerConnection.current?.connectionState)
//           setIsConnected(peerConnection.current?.connectionState === 'connected')
//         }

//         peerConnection.current.oniceconnectionstatechange = () => {
//           console.log('ICE connection state: ', peerConnection.current?.iceConnectionState);
          
//         }

//         websocket.current.onmessage = async (event) {
//           try {
//             const message = JSON.parse(event.data);
//             console.log('Received message: ', message.type);
            
//             switch (message.type) {
//               case 'offer':
//                 await handleOffer(message.data)
//                 break;
//               case 'answer':
//                 await handleAnswer(message.data);
//                 break;
//               case 'ice-candidate':
//                 await handleIceCandidate(message.data)
//                 break
//               default:
//                 console.log('Unknown message type:', message.type);
//                 break;
//             }
//           } catch (error) {
            
//           }
//         }
//       }
//     }
//   })



//   return ()
// }