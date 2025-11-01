import '../../styles/WorkBig.css';
import WorkList from '../Work/WorkList';

const dummy = [
  {id: 1, userName: '손동현', request: '네트워크 장비 교체', action: 2, actionStatus: '작업중', lastUpdateTime: '19:08:01'},
  {id: 2, userName: '최선우', request: '개발 환경 구성', action: 2, actionStatus: '작업중', lastUpdateTime: '19:08:01'},
  {id: 3, userName: '박재환', request: '커피 타기', action: 3, actionStatus: '완료', lastUpdateTime: '19:08:01'},
  {id: 4, userName: '김준혁', request: '데이터 백업', action: 1, actionStatus: '대기', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', request: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', request: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', request: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', request: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', request: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
  {id: 5, userName: '김나영', request: '서버 점검', action: 0, actionStatus: '취소', lastUpdateTime: '19:08:01'},
]

function WorkBig() {
  return (
    <div className="work-big">
      <div className='work-big-header'>
        <span className='title'>오늘의 작업 목록</span>
        <img src='icons/list.png' alt="list" />
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
            request={item.request}
            action={item.action}
            actionStatus={item.actionStatus}
            lastUpdateTime={item.lastUpdateTime}
          />
        ))}
      </div>
    </div>
  );
};

export default WorkBig;
