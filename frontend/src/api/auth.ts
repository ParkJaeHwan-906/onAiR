import { api } from "./axiosInstance";

// 로그인 api
export const login = async (email: string, password: string) => {
  const res = await api.post("/auth/login", { email, password });
  return res.data;
};

// 토큰 갱신 api
export const refresh = async (refreshToken: string) => {
  const res = await api.post("/auth/refresh", { refreshToken });
  return res.data;
};

// 회원가입 api
export const signup = async (data: any) => {
  const res = await api.post("/auth/signup", data);
  return res.data;
};

// 이메일 중복 확인 api
export const checkEmail = async (email: string) => {
  const res = await api.post("/auth/check/email", { email });
  return res.data;
};

// 비밀번호 중복 확인 api
export const checkPassword = async (password: string) => {
  const res = await api.post("/auth/check/password", { password });
  return res.data;
};

// 사용자 정보 조회
export const getUserInfo = async () => {
  const res = await api.get("/user/detail");
  return res.data;
};
