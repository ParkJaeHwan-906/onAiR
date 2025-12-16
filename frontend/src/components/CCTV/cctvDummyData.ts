import demo0 from "../../assets/cctv/cam1/test.mp4";
import demo1 from "../../assets/cctv/cam1/demo1.mp4";
import demo2 from "../../assets/cctv/cam1/demo2.mp4";
import demo3 from "../../assets/cctv/cam1/demo3.mp4";
import demo4 from "../../assets/cctv/cam1/demo4.mp4";
import demo5 from "../../assets/cctv/cam1/demo5.mp4";

export const cctvList = [
  {
    id: 1,
    videoUrl: demo0,
    worker: { id: 4, name: "김나영" },
    equipment: { id: 1, name: "AHU" },
  },
  {
    id: 2,
    videoUrl: demo1,
    worker: { id: 4, name: "이병헌" },
    equipment: { id: 1, name: "AHU" },
  },
  {
    id: 3,
    videoUrl: demo2,
    worker: { id: 2, name: "최선우" },
    equipment: { id: 2, name: "Chiller" },
  },
  {
    id: 4,
    videoUrl: demo3,
    worker: { id: 3, name: "손동현" },
    equipment: { id: 3, name: "Chiller" },
  },
  {
    id: 5,
    videoUrl: demo4,
    worker: { id: 4, name: "박재환" },
    equipment: { id: 4, name: "AHU" },
  },
  {
    id: 6,
    videoUrl: demo5,
    worker: { id: 5, name: "김준혁" },
    equipment: { id: 5, name: "Boiler" },
  },
];
