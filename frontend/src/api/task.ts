import { api } from "./axiosInstance";

// 작업 등록 (관리자만)
export const registTask = async (equipmentId: number, request: string) => {
  const res = await api.post("/task/regist", {
    equipmentId,
    request,
  });
  return res.data;
};

// 작업 목록 조회
export const getTaskList = async (
  equipmentId?: number | null,
  action?: number | null
) => {
  const params: any = {};
  if (equipmentId !== null && equipmentId !== undefined) {
    params.equipmentId = equipmentId;
  }
  if (action !== null && action !== undefined) {
    params.action = action;
  }
  const res = await api.get("/task/list", { params });
  return res.data;
};

// 작업 할당 (작업자가 자신에게 할당된 작업 가져오기)
export const assignTask = async () => {
  const res = await api.patch("/task/assign");
  return res.data;
};

// 새 작업 할당 (관리자가 작업을 작업자에게 할당) - /task/assign/re 사용
export const assignTaskToWorker = async (
  taskId: number,
  userAccountId: number
) => {
  // 유효성 검증
  if (!taskId || !userAccountId) {
    throw new Error(
      `작업 할당 실패: taskId=${taskId}, userAccountId=${userAccountId}`
    );
  }

  const requestBody = {
    taskId,
    userAccountId,
  };

  // ID가 null이면 즉시 에러
  if (taskId === null || taskId === undefined || isNaN(taskId)) {
    throw new Error(`작업 ID가 유효하지 않습니다: ${taskId}`);
  }

  if (
    userAccountId === null ||
    userAccountId === undefined ||
    isNaN(userAccountId)
  ) {
    throw new Error(`담당자 ID가 유효하지 않습니다: ${userAccountId}`);
  }

  try {
    const res = await api.patch("/task/assign/re", requestBody);
    return res.data;
  } catch (error: any) {
    console.error(
      "작업 할당 실패:",
      error.response?.data?.message || error.message
    );
    throw error;
  }
};

// 작업 완료
export const completeTask = async (taskId: number, solution: string) => {
  const res = await api.patch("/task/end", {
    taskId,
    solution,
  });
  return res.data;
};

// 작업 취소
export const cancelTask = async (taskId: number, solution: string) => {
  const res = await api.patch("/task/cancel", {
    taskId,
    solution,
  });
  return res.data;
};

// 작업 재할당 (관리자만)
export const reAssignTask = async (taskId: number, userAccountId: number) => {
  // 유효성 검증
  if (!taskId || !userAccountId) {
    throw new Error(
      `작업 할당 실패: taskId=${taskId}, userAccountId=${userAccountId}`
    );
  }

  const requestBody = {
    taskId,
    userAccountId,
  };

  try {
    const res = await api.patch("/task/assign/re", requestBody);
    return res.data;
  } catch (error: any) {
    console.error(
      "작업 재할당 실패:",
      error.response?.data?.message || error.message
    );
    throw error;
  }
};
