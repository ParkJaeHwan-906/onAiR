import { create } from "zustand";
import { getUserList, getUserDetail } from "../api/user";
import type { Employee } from "../types/employee";

interface UserState {
  employees: Employee[];
  selectedEmployee: Employee | null;
  myInfo: Employee | null;
  loading: boolean;
  error: string | null;

  fetchEmployees: (equipmentId?: number | null) => Promise<void>;
  selectEmployee: (emp: Employee) => void;
  fetchMyInfo: () => Promise<void>;
}

export const useUserStore = create<UserState>((set) => ({
  employees: [],
  selectedEmployee: null,
  myInfo: null,
  loading: false,
  error: null,

  fetchEmployees: async (equipmentId = null) => {
    try {
      set({ loading: true, error: null });
      const res = await getUserList(equipmentId);
      console.log(res.data);

      if (res.success) {
        set({ employees: res.data });
      } else {
        set({ error: res.message });
      }
    } catch {
      // set({ error: "직원 목록을 불러오는 중 오류가 발생했습니다." });
    } finally {
      set({ loading: false });
    }
  },

  selectEmployee: (emp) => set({ selectedEmployee: emp }),

  fetchMyInfo: async () => {
    try {
      set({ loading: true, error: null });
      const res = await getUserDetail();
      console.log(res.data);

      if (res.success) {
        set({ myInfo: res.data });
      } else {
        set({ error: res.message });
      }
    } catch {
      // set({ error: "내 정보를 불러오는 중 오류가 발생했습니다." });
    } finally {
      set({ loading: false });
    }
  },
}));
