import { useState } from "react";
import "../../styles/WorkActionModal.css";
import { completeTask, cancelTask } from "../../api/task";

interface WorkActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: number;
  action: "complete" | "cancel"; // 완료 또는 취소
  onSuccess: () => void;
}

function WorkActionModal({
  isOpen,
  onClose,
  taskId,
  action,
  onSuccess,
}: WorkActionModalProps) {
  const [solution, setSolution] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!solution.trim()) {
      alert(`${action === "complete" ? "완료" : "취소"} 내용을 입력해주세요.`);
      return;
    }

    try {
      setLoading(true);
      const res =
        action === "complete"
          ? await completeTask(taskId, solution.trim())
          : await cancelTask(taskId, solution.trim());

      if (res.success) {
        alert(`작업이 ${action === "complete" ? "완료" : "취소"}되었습니다.`);
        setSolution("");
        onSuccess();
        onClose();
      } else {
        alert(
          res.message ||
            `작업 ${action === "complete" ? "완료" : "취소"}에 실패했습니다.`
        );
      }
    } catch (error: any) {
      alert(
        error.response?.data?.message ||
          `작업 ${
            action === "complete" ? "완료" : "취소"
          } 중 오류가 발생했습니다.`
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setSolution("");
    onClose();
  };

  return (
    <div className="work-action-modal-overlay" onClick={handleCancel}>
      <div className="work-action-modal" onClick={(e) => e.stopPropagation()}>
        <div className="work-action-modal-header">
          <h3>작업 {action === "complete" ? "완료" : "취소"}</h3>
          <button className="close-button" onClick={handleCancel}>
            ×
          </button>
        </div>
        <div className="work-action-modal-body">
          <label>
            {action === "complete" ? "완료" : "취소"} 내용
            <textarea
              value={solution}
              onChange={(e) => setSolution(e.target.value)}
              placeholder={`${
                action === "complete" ? "완료" : "취소"
              } 내용을 입력하세요...`}
              rows={5}
            />
          </label>
        </div>
        <div className="work-action-modal-footer">
          <button
            className="cancel-button"
            onClick={handleCancel}
            disabled={loading}
          >
            취소
          </button>
          <button
            className={`submit-button ${
              action === "complete" ? "complete" : "cancel"
            }`}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? "처리 중..." : action === "complete" ? "완료" : "취소"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default WorkActionModal;
