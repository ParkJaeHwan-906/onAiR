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
}
