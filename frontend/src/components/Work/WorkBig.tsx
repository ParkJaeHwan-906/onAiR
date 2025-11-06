import { useEffect, useState } from "react";
import "../../styles/WorkBig.css";
import WorkList from "../Work/WorkList";
import { getTaskList } from "../../api/task";
import type { Work } from "../../types/work";
import { useUserStore } from "../../store/useUserStore";

interface WorkBigProps {
  refreshKey?: number;
  onTaskUpdated?: () => void;
}

function WorkBig({ refreshKey, onTaskUpdated }: WorkBigProps) {
  const [tasks, setTasks] = useState<Work[]>([]);
  const [loading, setLoading] = useState(true);
  const { myInfo } = useUserStore();

  // action 값을 actionStatus 문자열로 변환
  const getActionStatus = (action: number): string => {
    switch (action) {
      case 0:
        return "취소됨";
      case 1:
        return "대기중";
      case 2:
        return "작업중";
      case 3:
        return "완료";
      default:
        return "대기중";
    }
  };

  // 변경시간을 대한민국 시간(KST)으로 변환
  const formatTime = (dateTimeString: string) => {
    if (!dateTimeString) return "-";

    const utcDate = new Date(dateTimeString); // 백엔드에서 UTC 기준으로 전달됨
    const kstDate = new Date(utcDate.getTime() + 9 * 60 * 60 * 1000); // +9시간

    const hours = String(kstDate.getHours()).padStart(2, "0");
    const minutes = String(kstDate.getMinutes()).padStart(2, "0");

    return `${hours}시 ${minutes}분`;
  };

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const res = await getTaskList(null, null);
      if (res.success) {
        let tasksData = res.data || [];

        // 작업자 모드일 경우 자신에게 할당된 작업만 필터링
        if (myInfo?.role !== "관리자" && myInfo?.userAccountId) {
          tasksData = tasksData.filter(
            (task: Work) => task.userAccountId === myInfo.userAccountId
          );
        }

        setTasks(tasksData);
      }
    } catch (error) {
      console.error("작업 목록 조회 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [refreshKey, myInfo]);

  const isAdmin = myInfo?.role === "관리자";

  return (
    <div className="work-big">
      <div className="work-big-header">
        <span className="work-list">작업 관리</span>
      </div>

      <div className="work-table">
        <div className="list-header">
          <div className="col-worker">작업자</div>
          <div className="col-content">작업 내용</div>
          <div className="col-status">상태</div>
          <div className="col-time">요청시간</div>
          {isAdmin ? (
            <div className="col-solution">완료/취소 내용</div>
          ) : (
            <div className="col-actions-header">완료 / 취소</div>
          )}
        </div>

        <div className="list-body">
          {loading ? (
            <p className="loading-text">작업 정보를 불러오는 중...</p>
          ) : tasks.length === 0 ? (
            <p className="no-data">등록된 작업이 없습니다.</p>
          ) : (
            tasks.map((item) => {
              // actionStatus가 없거나 빈 문자열이면 action 값으로 변환
              const statusText =
                item.actionStatus && item.actionStatus.trim()
                  ? item.actionStatus
                  : getActionStatus(item.action);

              return (
                <WorkList
                  key={item.id}
                  taskId={item.id}
                  userName={item.userName || "미할당"}
                  request={item.request}
                  action={item.action}
                  actionStatus={statusText}
                  lastUpdateTime={formatTime(item.lastUpdateTime)}
                  userAccountId={item.userAccountId}
                  solution={item.solution}
                  isAdmin={isAdmin}
                  onTaskUpdated={() => {
                    fetchTasks();
                    if (onTaskUpdated) {
                      onTaskUpdated();
                    }
                  }}
                />
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default WorkBig;
