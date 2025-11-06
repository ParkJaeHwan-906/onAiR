export type Work = {
  id: number;
  equipmentId: number;
  equipmentName: string;
  request: string;
  userAccountId: number | null; // 할당되지 않은 작업은 null일 수 있음
  userName: string;
  action: number;
  actionStatus: string;
  solution: string | null;
  lastUpdateTime: string;
};
