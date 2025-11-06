import { useEffect, useState } from 'react';
import '../styles/WorkPage.css';
import WorkBig from '../components/Work/WorkBig';
import WorkAdd from '../components/Work/WorkAdd';
import WorkAssign from '../components/Work/WorkAssign';
import { useUserStore } from '../store/useUserStore';

function WorkPage () {
  const [refreshKey, setRefreshKey] = useState(0);
  const { fetchMyInfo, myInfo } = useUserStore();

  useEffect(() => {
    fetchMyInfo();
  }, []);

  const handleTaskAdded = () => {
    // 작업 추가 후 목록 새로고침을 위한 키 업데이트
    setRefreshKey((prev) => prev + 1);
  };

  const handleTaskReassigned = () => {
    // 작업 재할당 후 목록 새로고침을 위한 키 업데이트
    setRefreshKey((prev) => prev + 1);
  };

  const handleTaskUpdated = () => {
    // 작업 완료/취소 후 목록 새로고침을 위한 키 업데이트
    setRefreshKey((prev) => prev + 1);
  };

  const isAdmin = myInfo?.role === "관리자";

  return (
    <div className='work-page-wrapper'>
      <WorkBig key={refreshKey} onTaskUpdated={handleTaskUpdated} />
      {isAdmin && (
        <div className='work-page-left'>
          <WorkAdd onTaskAdded={handleTaskAdded} />
          <WorkAssign onTaskReassigned={handleTaskReassigned} />
        </div>
      )}
    </div>
  );
}

export default WorkPage;