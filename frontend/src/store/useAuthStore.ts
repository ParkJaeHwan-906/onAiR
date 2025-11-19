import { create } from "zustand";
import { login, getUserInfo } from "../api/auth";
import { checkIn, checkOut } from "../api/user";

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

          // 로그인 시 자동으로 출근 처리 (온라인 상태로 변경)
          try {
            await checkIn();
          } catch (error: any) {
            // 이미 출근처리 되었거나 에러가 발생해도 무시 (로그인은 성공)
          }
        }
      } else {
        throw new Error(res.message || "로그인 실패");
      }
    } catch (error) {
      // console.error("로그인 중 오류:", error);
      throw error;
    }
  },

  // 로그아웃
  logoutUser: async () => {
    // 로그아웃 시 자동으로 퇴근 처리 (오프라인 상태로 변경)
    try {
      await checkOut();
    } catch (error: any) {
      // 출근 기록이 없거나 에러가 발생해도 무시 (로그아웃은 진행)
    }

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

        // 새로고침 시에는 출근 처리를 하지 않음
        // (이미 로그인 시 출근 처리가 되었거나, 로그아웃 후 재로그인 시에만 출근 처리)
        // getUserInfo()로 받은 정보에 online 상태가 포함되어 있으므로 그대로 사용
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
