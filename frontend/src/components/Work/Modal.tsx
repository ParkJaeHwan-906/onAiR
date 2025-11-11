import "../../styles/Modal.css";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  contentClassName?: string;
}

function Modal({ isOpen, onClose, children, contentClassName }: ModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className={`modal-content${
          contentClassName ? ` ${contentClassName}` : ""
        }`}
        onClick={(e) => e.stopPropagation()} // 모달 내부 클릭 시 닫힘 방지
      >
        {children}
      </div>
    </div>
  );
}
export default Modal;
