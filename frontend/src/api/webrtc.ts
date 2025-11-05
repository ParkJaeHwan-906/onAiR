import { api } from "./axiosInstance";

// 연결 요청 API
export const sendConnectionRequest = async (
  receiverAccountId: number,
  description: string
) => {
  try {
    const res = await api.post("/webrtc/request", {
      receiverAccountId,
      description,
    });
    return res.data;
  } catch (err: any) {
    console.error("연결 요청 중 오류:", err);
    return { success: false, message: "요청 처리 중 오류가 발생했습니다." };
  }
};

// 연결 요청 API
export const getLivekitToken = async (roomName: string) => {
  try {
    const res = await api.get(`/webrtc/create-token?roomName=${roomName}`);
    if (res.data.success) {
      return res.data.data; // 토큰 문자열 반환
    } else {
      console.error("토큰 발급 실패:", res.data.message);
      return null;
    }
  } catch (error) {
    console.error("토큰 요청 중 오류:", error);
    return null;
  }
};
