import { useEffect, useState } from "react";
import "../styles/WorkPage.css";
import WorkBig from "../components/Work/WorkBig";
import WorkAdd from "../components/Work/WorkAdd";
import WorkAssign from "../components/Work/WorkAssign";
import WorkDetail from "../components/Work/WorkDetail";
import { useUserStore } from "../store/useUserStore";
import { getTaskList } from "../api/task";
import type { Work } from "../types/work";

function WorkPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [selectedWork, setSelectedWork] = useState<Work | null>(null);
  const { fetchMyInfo, myInfo } = useUserStore();

  useEffect(() => {
    fetchMyInfo();
  }, []);

  // 선택된 작업 정보 가져오기
  useEffect(() => {
    const fetchSelectedWork = async () => {
      if (!selectedTaskId) {
        setSelectedWork(null);
        return;
      }

      try {
        const res = await getTaskList(null, null);
        if (res.success && res.data) {
          const work = res.data.find(
            (task: Work) => task.id === selectedTaskId
          );
          setSelectedWork(work || null);
        }
      } catch (error) {
        console.error("작업 정보 조회 실패:", error);
        setSelectedWork(null);
      }
    };

    fetchSelectedWork();
  }, [selectedTaskId, refreshKey]);

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

  const handleSelectTask = (taskId: number) => {
    setSelectedTaskId(taskId);
  };

  const isAdmin = myInfo?.role === "관리자";
  const rightClassName = isAdmin
    ? "work-page-right work-page-right--admin"
    : "work-page-right work-page-right--worker";

  return (
    <div className="work-page-wrapper">
      <WorkBig
        key={refreshKey}
        onTaskUpdated={handleTaskUpdated}
        onSelectTask={handleSelectTask}
      />
      <div className={rightClassName}>
        {isAdmin ? (
          <div className="work-page-stack">
            <WorkAdd onTaskAdded={handleTaskAdded} />
            <WorkAssign onTaskReassigned={handleTaskReassigned} />
          </div>
        ) : (
          <WorkDetail work={selectedWork} />
        )}
      </div>
    </div>
  );
}

export default WorkPage;
