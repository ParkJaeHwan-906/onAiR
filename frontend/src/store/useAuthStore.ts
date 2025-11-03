import { create } from "zustand";
import { login, getUserInfo } from "../api/auth";

interface User {
  email: string;
  name?: string;
  part?: string;
  companyName?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isRestoring: boolean;

  loginUser: (email: string, password: string) => Promise<void>;
  logoutUser: () => void;
  restoreSession: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isRestoring: true,

  // 로그인
  loginUser: async (email, password) => {
    try {
      const res = await login(email, password);

      if (res.success) {
        const { accessToken, refreshToken } = res.data;

        // 토큰 저장
        localStorage.setItem("accessToken", accessToken);
        localStorage.setItem("refreshToken", refreshToken);

        // 사용자 정보 조회
        const infoRes = await getUserInfo();
        if (infoRes.success) {
          set({
            user: infoRes.data,
            accessToken,
            refreshToken,
            isAuthenticated: true,
          });
        }
      } else {
        throw new Error(res.message || "로그인 실패");
      }
    } catch (error) {
      console.error("로그인 중 오류:", error);
      throw error;
    }
  },

  // 로그아웃
  logoutUser: () => {
    localStorage.clear();
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isRestoring: false,
    });
  },

  // 새로고침 시 세션 복구
  restoreSession: async () => {
    const accessToken = localStorage.getItem("accessToken");
    const refreshToken = localStorage.getItem("refreshToken");

    if (!accessToken || !refreshToken) {
      set({ isRestoring: false });
      return;
    }

    try {
      const infoRes = await getUserInfo();
      if (infoRes.success) {
        set({
          user: infoRes.data,
          accessToken,
          refreshToken,
          isAuthenticated: true,
          isRestoring: false,
        });
      } else {
        localStorage.clear();
        set({ isRestoring: false });
      }
    } catch (err) {
      localStorage.clear();
      set({ isRestoring: false });
    }
  },
}));
