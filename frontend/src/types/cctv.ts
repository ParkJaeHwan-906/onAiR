export interface CCTVItem {
  id: number;
  videoUrl: string;
  worker: {
    id: number;
    name: string;
  };
  equipment: {
    id: number;
    name: string;
  };
  // [TODO] 일단 타입 오류 때문에 임시로 추가했어요
  isLive: boolean;
}
