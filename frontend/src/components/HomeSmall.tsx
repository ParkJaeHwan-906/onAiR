import '../styles/HomeSmall.css';
import SemicircleGauge from './SemicircleGauge';

function HomeSmall() {
  return (
    <div className="home-small">
      <div className='home-small-header'>
        <span className='title'>오늘의 작업 수</span>
        <img src='icons/list.png' alt="list" />
      </div>
      <div className='status'>
        <span>10</span>
      </div>
      <div className='gauge-wrapper'>
        <SemicircleGauge value={20} />
      </div>
    </div>
  );
};

export default HomeSmall;
