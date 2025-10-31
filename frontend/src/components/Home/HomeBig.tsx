import '../../styles/HomeBig.css';
import WorkList from './WorkList';

const dummy = [
  {id: 1, userName: '손동현', solution: '네트워크 장비 교체', action: 2, actionStatus: '작업중', lastUpdateTime: '19:08:01'},
  {id: 2, userName: '최선우', solution: '개발 환경 구성', action: 2, actionStatus: '작업중', lastUpdateTime: '19:08:01'},
  {id: 3, userName: '박재환', solution: '커피 타기', action: 3, actionStatus: '완료', lastUpdateTime: '19:08:01'},
  {id: 4, userName: '김준혁', solution: '데이터 백업', action: 1, actionStatus: '대기', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', solution: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', solution: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', solution: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', solution: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', solution: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', solution: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
]

type HomeBigProps = {
  title: string;
  icon: string;
}

function HomeBig({ title, icon }: HomeBigProps) {
  return (
    <div className="home-big">
      <div className='home-big-header'>
        <span className='title'>{title}</span>
        <img src={icon} alt="list" />
      </div>
      <div className='list-header'>
        <div className='first'>
          요청자
        </div>
        <div className='second'>
          작업 내용
        </div>
        <div className='third'>
          상태
        </div>
        <div className='fourth'>
          변경시간
        </div>
      </div>
      <div className='list-body'>
        {dummy.map((item) => (
          <WorkList 
            key={item.id}
            userName={item.userName}
            solution={item.solution}
            action={item.action}
            actionStatus={item.actionStatus}
            lastUpdateTime={item.lastUpdateTime}
          />
        ))}
      </div>
    </div>
  );
};

export default HomeBig;
