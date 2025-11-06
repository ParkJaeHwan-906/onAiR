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
export const assignTaskToWorker = async (taskId: number, userAccountId: number) => {
  // 유효성 검증
  if (!taskId || !userAccountId) {
    throw new Error(`작업 할당 실패: taskId=${taskId}, userAccountId=${userAccountId}`);
  }
  
  const requestBody = {
    taskId,
    userAccountId,
  };
  
  console.log('=== assignTaskToWorker API 호출 (새 작업 할당) ===');
  console.log('요청 URL:', `${api.defaults.baseURL}/task/assign/re`);
  console.log('요청 메서드:', 'PATCH');
  console.log('요청 데이터:', requestBody);
  console.log('요청 데이터 타입:', {
    taskId: typeof taskId,
    userAccountId: typeof userAccountId,
    taskIdValue: taskId,
    userAccountIdValue: userAccountId
  });
  console.log('요청 데이터 JSON:', JSON.stringify(requestBody));
  
  // ⚠️ 중요: ID가 null이면 즉시 에러
  if (taskId === null || taskId === undefined || isNaN(taskId)) {
    console.error('❌ taskId가 null이거나 유효하지 않습니다:', taskId);
    throw new Error(`작업 ID가 유효하지 않습니다: ${taskId}`);
  }
  
  if (userAccountId === null || userAccountId === undefined || isNaN(userAccountId)) {
    console.error('❌ userAccountId가 null이거나 유효하지 않습니다:', userAccountId);
    throw new Error(`담당자 ID가 유효하지 않습니다: ${userAccountId}`);
  }
  
  console.log('✅ ID 검증 통과 - API 요청 전송');
  
  // Authorization 헤더 확인
  const token = localStorage.getItem("accessToken");
  console.log('Authorization 헤더:', token ? `Bearer ${token.substring(0, 20)}...` : '없음');
  console.log('토큰 존재 여부:', !!token);
  
  try {
    const res = await api.patch("/task/assign/re", requestBody);
    
    console.log('=== assignTaskToWorker API 응답 ===');
    console.log('응답 상태:', res.status);
    console.log('응답 데이터:', res.data);
    
    return res.data;
  } catch (error: any) {
    console.error('=== assignTaskToWorker API 에러 ===');
    console.error('에러 상태:', error.response?.status);
    console.error('에러 메시지:', error.message);
    console.error('요청 URL:', error.config?.url);
    console.error('요청 메서드:', error.config?.method);
    console.error('요청 데이터:', error.config?.data);
    console.error('요청 헤더:', error.config?.headers);
    console.error('Authorization 헤더 확인:', error.config?.headers?.Authorization ? '있음' : '없음');
    if (error.config?.headers?.Authorization) {
      console.error('Authorization 값:', error.config.headers.Authorization.substring(0, 30) + '...');
    }
    console.error('응답 데이터:', error.response?.data);
    console.error('응답 헤더:', error.response?.headers);
    console.error('=== 에러 전체 객체 ===');
    console.error('error:', error);
    console.error('error.response:', error.response);
    console.error('error.response.data (전체):', JSON.stringify(error.response?.data, null, 2));
    console.error('error.response.status:', error.response?.status);
    console.error('error.response.statusText:', error.response?.statusText);
    console.error('error.request:', error.request);
    console.error('=== 백엔드 로그 확인 필요 ===');
    console.error('백엔드 콘솔에서 다음 예외를 확인하세요:');
    console.error('- NullPointerException (emitters.get()이 null 반환)');
    console.error('- IOException (SSE 전송 실패)');
    console.error('- IllegalArgumentException (SSE 전송에 실패했습니다)');
    console.error('백엔드 로그 위치: TaskServiceImpl.reAssignTask() 또는 SseManager.taskAssign()');
    throw error;
  }
};

// 작업 완료
export const completeTask = async (taskId: number, solution: string) => {
  const res = await api.patch("/task/complete", {
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
    throw new Error(`작업 할당 실패: taskId=${taskId}, userAccountId=${userAccountId}`);
  }
  
  const requestBody = {
    taskId,
    userAccountId,
  };
  
  console.log('=== reAssignTask API 호출 ===');
  console.log('요청 URL:', `${api.defaults.baseURL}/task/assign/re`);
  console.log('요청 메서드:', 'PATCH');
  console.log('요청 데이터:', requestBody);
  console.log('요청 데이터 타입:', {
    taskId: typeof taskId,
    userAccountId: typeof userAccountId,
    taskIdValue: taskId,
    userAccountIdValue: userAccountId
  });
  console.log('요청 데이터 JSON:', JSON.stringify(requestBody));
  
  // Authorization 헤더 확인
  const token = localStorage.getItem("accessToken");
  console.log('Authorization 헤더:', token ? `Bearer ${token.substring(0, 20)}...` : '없음');
  console.log('토큰 존재 여부:', !!token);
  
  try {
    const res = await api.patch("/task/assign/re", requestBody);
    
    console.log('=== reAssignTask API 응답 ===');
    console.log('응답 상태:', res.status);
    console.log('응답 데이터:', res.data);
    
    return res.data;
  } catch (error: any) {
    console.error('=== reAssignTask API 에러 ===');
    console.error('에러 상태:', error.response?.status);
    console.error('에러 메시지:', error.message);
    console.error('요청 URL:', error.config?.url);
    console.error('요청 메서드:', error.config?.method);
    console.error('요청 데이터:', error.config?.data);
    console.error('요청 헤더:', error.config?.headers);
    console.error('Authorization 헤더 확인:', error.config?.headers?.Authorization ? '있음' : '없음');
    if (error.config?.headers?.Authorization) {
      console.error('Authorization 값:', error.config.headers.Authorization.substring(0, 30) + '...');
    }
    console.error('응답 데이터:', error.response?.data);
    throw error;
  }
};


