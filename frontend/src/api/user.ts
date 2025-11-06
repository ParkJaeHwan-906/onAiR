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

// 출근 처리
export const checkIn = async () => {
  const res = await api.get("/user/check/in");
  return res.data;
};

// 퇴근 처리
export const checkOut = async () => {
  const res = await api.get("/user/check/out");
  return res.data;
};

// 설비 지정 (관리자만)
export const assignEquipment = async (userAccountId: number, equipmentId: number) => {
  const res = await api.patch("/user/equipment", {
    userAccountId,
    equipmentId,
  });
  return res.data;
};
