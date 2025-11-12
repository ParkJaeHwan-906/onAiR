import Modal from "./Modal";
import "../../styles/WorkDetailModal.css";

export type WorkDetailInfo = {
  userName: string;
  request: string;
  actionStatus: string;
  lastUpdateTime: string;
  solution?: string | null;
};

interface WorkDetailModalProps {
  isOpen: boolean;
  detail: WorkDetailInfo | null;
  onClose: () => void;
}

function WorkDetailModal({ isOpen, detail, onClose }: WorkDetailModalProps) {
  if (!isOpen || !detail) {
    return null;
  }

  const { userName, request, actionStatus, lastUpdateTime, solution } = detail;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      contentClassName="modal-content--compact"
    >
      <div className="work-detail-modal" role="dialog" aria-modal="true">
        <h3 className="work-detail-modal__title">작업 상세 정보</h3>
        <div className="work-detail-modal__body">
          <div className="work-detail-modal__row">
            <span className="work-detail-modal__label">작업자</span>
            <span className="work-detail-modal__value">{userName}</span>
          </div>
          <div className="work-detail-modal__row">
            <span className="work-detail-modal__label">작업 내용</span>
            <span className="work-detail-modal__value">{request}</span>
          </div>
          <div className="work-detail-modal__row">
            <span className="work-detail-modal__label">상태</span>
            <span className="work-detail-modal__value">{actionStatus}</span>
          </div>
          <div className="work-detail-modal__row">
            <span className="work-detail-modal__label">요청 시간</span>
            <span className="work-detail-modal__value">{lastUpdateTime}</span>
          </div>
          <div className="work-detail-modal__solution">
            <span className="work-detail-modal__label">완료/취소 내용</span>
            <p className="work-detail-modal__solution-text">
              {solution?.trim() ? solution : "-"}
            </p>
          </div>
        </div>
        <button
          type="button"
          className="work-detail-modal__close"
          onClick={onClose}
        >
          닫기
        </button>
      </div>
    </Modal>
  );
}

export default WorkDetailModal;
