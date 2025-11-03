import axios from "axios";
import { refresh } from "./auth";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// 요청 인터셉터: accessToken 자동 추가
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("accessToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터: accessToken 만료 시 자동 재발급
// api.interceptors.response.use(
//   (res) => res,
//   async (error) => {
//     const originalRequest = error.config;

//     // accessToken 만료로 401일 때만 재시도
//     if (error.response?.status === 401 && !originalRequest._retry) {
//       originalRequest._retry = true;

//       const refreshToken = localStorage.getItem("refreshToken");
//       if (!refreshToken) {
//         console.warn("refreshToken이 없습니다. 재로그인 필요.");
//         return Promise.reject(error);
//       }

//       try {
//         // 새 토큰 발급 요청
//         const res = await refresh(refreshToken);
//         const { accessToken, refreshToken: newRefreshToken } = res.data.data;

//         // 새 토큰 저장
//         localStorage.setItem("accessToken", accessToken);
//         localStorage.setItem("refreshToken", newRefreshToken);

//         // 원래 요청에 새 토큰 적용해서 재시도
//         originalRequest.headers.Authorization = `Bearer ${accessToken}`;
//         return api(originalRequest);
//       } catch (refreshErr) {
//         console.error("토큰 재발급 실패:", refreshErr);
//         localStorage.clear();
//         window.location.href = "/login";
//         return Promise.reject(refreshErr);
//       }
//     }
//     return Promise.reject(error);
//   }
// );
