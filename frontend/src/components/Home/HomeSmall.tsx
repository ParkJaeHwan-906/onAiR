import "../../styles/HomeSmall.css";
import SemicircleGauge from "./SemicircleGauge";

type HomeSmallProps = {
  isGraph: boolean;
  numInfo: number;
  totalInfo?: number;
  title: string;
  value: number;
  icon: string;
};

function HomeSmall({
  isGraph,
  numInfo,
  // totalInfo,
  title,
  value,
  icon,
}: HomeSmallProps) {
  return (
    <div className="home-small">
      <div className="home-small-header">
        <span className="title">{title}</span>
        <img src={icon} alt="list" />
      </div>
      <div className="status">
        <span>{numInfo}</span>
        {/* {title === "작업 인원 수" && totalInfo !== undefined ? (
          <span>
            전체 {totalInfo}명 · 온라인 {numInfo}명
          </span>
        ) : (
          <span>{numInfo}</span>
        )} */}
      </div>
      <div className="content-wrapper">
        {isGraph && <SemicircleGauge value={value} />}
        {!isGraph && <span className="content-text">{numInfo}건</span>}
      </div>
    </div>
  );
}

export default HomeSmall;
