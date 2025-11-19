import { useEffect, useState, useMemo } from "react";
import "../../styles/WorkBig.css";
import WorkList from "../Work/WorkList";
import WorkDetailModal, { type WorkDetailInfo } from "./WorkDetailModal";
import { getTaskList } from "../../api/task";
import type { Work } from "../../types/work";
import { useUserStore } from "../../store/useUserStore";

interface WorkBigProps {
  refreshKey?: number;
  onTaskUpdated?: () => void;
  onSelectTask?: (taskId: number) => void;
}

function WorkBig({ refreshKey, onSelectTask }: WorkBigProps) {
  const [tasks, setTasks] = useState<Work[]>([]);
  const [loading, setLoading] = useState(true);
  const { myInfo } = useUserStore();
  const [detailModalInfo, setDetailModalInfo] = useState<WorkDetailInfo | null>(
    null
  );
  const [isDetailModalOpen, setDetailModalOpen] = useState(false);
  const [filter, setFilter] = useState("all");

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
    const kstDate = new Date(utcDate.getTime());

    const hours = String(kstDate.getHours()).padStart(2, "0");
    const minutes = String(kstDate.getMinutes()).padStart(2, "0");

    return `${hours}시 ${minutes}분`;
  };

  // 작업 목록 조회
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

        // 업데이트 시간순으로 정렬 (최신순)
        tasksData.sort((a: Work, b: Work) => {
          const timeA = new Date(a.lastUpdateTime).getTime();
          const timeB = new Date(b.lastUpdateTime).getTime();
          return timeB - timeA; // 내림차순 (최신이 위로)
        });

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

  // 필터링된 작업 목록
  const filteredTasks = useMemo(() => {
    if (filter === "all") return tasks;
    if (filter === "progress") return tasks.filter((t) => t.action === 2);
    if (filter === "waiting") return tasks.filter((t) => t.action === 1);
    if (filter === "done") return tasks.filter((t) => t.action === 3);
    if (filter === "cancel") return tasks.filter((t) => t.action === 0);
    return tasks;
  }, [filter, tasks]);

  // 이름 오름차순, 같은 이름이면 시간 내림차순 정렬
  const sortedTasks = useMemo(() => {
    const copied = [...filteredTasks];
    copied.sort((a, b) => {
      const nameA = (a.userName || "미할당").localeCompare(
        b.userName || "미할당"
      );
      if (nameA !== 0) return nameA;
      return (
        new Date(b.lastUpdateTime).getTime() -
        new Date(a.lastUpdateTime).getTime()
      );
    });
    return copied;
  }, [filteredTasks]);

  const handleViewDetail = (info: WorkDetailInfo) => {
    setDetailModalInfo(info);
    setDetailModalOpen(true);
  };

  // 관리자 여부 확인
  const isAdmin = myInfo?.role === "관리자";

  return (
    <div className="work-big">
      <div className="work-big-header">
        <span className="work-list">작업 관리</span>
      </div>

      {/* 필터 탭 추가 */}
      <div className="work-filter-tabs">
        <button
          className={filter === "all" ? "active" : ""}
          onClick={() => setFilter("all")}
        >
          전체
        </button>
        <button
          className={filter === "progress" ? "active" : ""}
          onClick={() => setFilter("progress")}
        >
          작업중
        </button>
        <button
          className={filter === "waiting" ? "active" : ""}
          onClick={() => setFilter("waiting")}
        >
          대기중
        </button>
        <button
          className={filter === "done" ? "active" : ""}
          onClick={() => setFilter("done")}
        >
          완료
        </button>
        <button
          className={filter === "cancel" ? "active" : ""}
          onClick={() => setFilter("cancel")}
        >
          취소됨
        </button>
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
          ) : sortedTasks.length === 0 ? (
            <p className="no-data">등록된 작업이 없습니다.</p>
          ) : (
            sortedTasks.map((item) => (
              <WorkList
                key={item.id}
                taskId={item.id}
                userName={item.userName || "미할당"}
                request={item.request}
                action={item.action}
                actionStatus={item.actionStatus || getActionStatus(item.action)}
                lastUpdateTime={formatTime(item.lastUpdateTime)}
                userAccountId={item.userAccountId}
                solution={item.solution}
                isAdmin={isAdmin}
                onTaskUpdated={fetchTasks}
                onSelect={onSelectTask}
                onViewDetail={handleViewDetail}
              />
            ))
          )}
        </div>
      </div>

      <WorkDetailModal
        isOpen={isDetailModalOpen}
        detail={detailModalInfo}
        onClose={() => setDetailModalOpen(false)}
      />
    </div>
  );
}

export default WorkBig;
