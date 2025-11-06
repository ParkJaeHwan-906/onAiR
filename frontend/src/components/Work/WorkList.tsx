import { useState } from "react";
import "../../styles/WorkList.css";
import WorkActionModal from "./WorkActionModal";
import { useUserStore } from "../../store/useUserStore";

type WorkListProps = {
  taskId: number;
  userName: string;
  request: string;
  action: number;
  actionStatus: string;
  lastUpdateTime: string;
  userAccountId: number | null; // 할당된 작업자 ID
  solution?: string | null; // 완료/취소 내용
  isAdmin?: boolean; // 관리자 여부
  onTaskUpdated?: () => void; // 작업 완료/취소 후 콜백
};

const backColors = ["#F4C0C0", "#F9E9B5", "#B5BFE0", "#B6E7C8"];
const fontColors = ["#EF4444", "#FFBC11", "#1E40AF", "#22C55E"];

function WorkList({
  taskId,
  userName,
  request,
  action,
  actionStatus,
  lastUpdateTime,
  userAccountId,
  solution,
  isAdmin = false,
  onTaskUpdated,
}: WorkListProps) {
  const { myInfo } = useUserStore();
  const [isCompleteModalOpen, setIsCompleteModalOpen] = useState(false);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);

  // action 값이 배열 범위를 벗어나지 않도록 체크
  const safeAction = action >= 0 && action < backColors.length ? action : 0;
  const backColor = backColors[safeAction];
  const fontColor = fontColors[safeAction];

  // 작업자 모드이고, 작업중 상태이며, 내가 할당받은 작업인지 확인
  const isWorker = !isAdmin;
  const isMyTask = myInfo?.userAccountId === userAccountId;
  const isInProgress = action === 2; // 작업중
  const showActionButtons = isWorker && isMyTask && isInProgress;

  const handleTaskUpdated = () => {
    if (onTaskUpdated) {
      onTaskUpdated();
    }
  };

  return (
    <>
      <div className="work-row">
        <div className="col-worker">{userName}</div>
        <div className="col-content">{request}</div>
        <div className="col-status">
          <span
            className="status-badge"
            style={{ backgroundColor: backColor, color: fontColor }}
          >
            {actionStatus}
          </span>
        </div>
        <div className="col-time">{lastUpdateTime}</div>
        {isAdmin ? (
          <div className="col-solution">{solution || "-"}</div>
        ) : (
          <div className="col-actions">
            {showActionButtons ? (
              <>
                <button
                  className="action-button complete-button"
                  onClick={() => setIsCompleteModalOpen(true)}
                >
                  완료
                </button>
                <button
                  className="action-button cancel-button"
                  onClick={() => setIsCancelModalOpen(true)}
                >
                  취소
                </button>
              </>
            ) : (
              <span className="no-action">-</span>
            )}
          </div>
        )}
      </div>

      <WorkActionModal
        isOpen={isCompleteModalOpen}
        onClose={() => setIsCompleteModalOpen(false)}
        taskId={taskId}
        action="complete"
        onSuccess={handleTaskUpdated}
      />

      <WorkActionModal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        taskId={taskId}
        action="cancel"
        onSuccess={handleTaskUpdated}
      />
    </>
  );
}

export default WorkList;
