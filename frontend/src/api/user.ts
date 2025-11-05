import { api } from "./axiosInstance";

// 직원 목록 조회
export const getUserList = async (equipmentId: number | null = null) => {
  const res = await api.get("/user/list", {
    params: { equipmentId },
  });
  return res.data;
};

// 직원 상세 조회
export const getUserDetail = async () => {
  const res = await api.get("/user/detail");
  return res.data;
};
