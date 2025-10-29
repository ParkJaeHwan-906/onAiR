export const checkWebRTCSupport = () => {
  const support = {
    webRTC: false,
    getUserMedia: false,
    mediaDevices : false,
    peerConnection: false,
    websocket: false,
  }

  try {
    support.webRTC = !!window.RTCPeerConnection;
    support.getUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
    support.mediaDevices = !!navigator.mediaDevices
    support.peerConnection = !! (window.RTCPeerConnection || window.RTCPeerConnection || window.RTCPeerConnection)
    support.websocket = !!window.WebSocket
  } catch (e) {
    console.error('Error checking WebRTC support: ', e)
  }
  return support
}
