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
    const errorMessage =
      err.response?.data?.message ||
      err.message ||
      "요청 처리 중 오류가 발생했습니다.";
    return { success: false, message: errorMessage };
  }
};

// 연결 응답 API
export const sendConnectionResponse = async (
  senderAccountId: number,
  senderName: string,
  acceptConnection: boolean
) => {
  try {
    const res = await api.post("/webrtc/response", {
      senderAccountId,
      senderName,
      acceptConnection,
    });
    return res.data;
  } catch (err: any) {
    console.error("연결 응답 중 오류:", err);
    const errorMessage =
      err.response?.data?.message ||
      err.message ||
      "응답 처리 중 오류가 발생했습니다.";
    console.error("상세 에러 정보:", {
      status: err.response?.status,
      data: err.response?.data,
      requestData: { senderAccountId, senderName, acceptConnection },
    });
    return { success: false, message: errorMessage };
  }
};
