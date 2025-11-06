import { api } from "./axiosInstance";

// 설비 카테고리 목록 조회
export const getEquipmentCategoryList = async () => {
  const res = await api.get("/equipment/category/list");
  return res.data;
};

// 설비 카테고리 등록 (관리자만)
export const registEquipmentCategory = async (equipmentCategory: string) => {
  const res = await api.post("/equipment/category/regist", {
    equipmentCategory,
  });
  return res.data;
};

// 전체 설비 목록 조회
export const getEquipmentList = async () => {
  const res = await api.get("/equipment/list");
  return res.data;
};

// 설비 등록 (관리자만)
export const registEquipment = async (
  equipmentCategoryId: number,
  equipmentName: string,
  equipmentImage?: string
) => {
  const res = await api.post("/equipment/regist", {
    equipmentCategoryId,
    equipmentName,
    equipmentImage,
  });
  return res.data;
};

// 회사 장비 목록 조회
export const getCompanyEquipmentList = async () => {
  const res = await api.get("/company/equipment/list");
  return res.data;
};

// 회사에 장비 등록 (관리자만)
export const registCompanyEquipment = async (equipmentId: number) => {
  const res = await api.post("/company/equipment/regist", {
    equipmentId,
  });
  return res.data;
};

