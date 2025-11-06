import "../../styles/Communication/WorkerCard.css";

interface WorkerCardProps {
  name: string;
  role: string;
  equipmentName: string;
  status?: "대기중" | "통신중";
  size?: "default" | "small";
}

const WorkerCard = ({
  name,
  role,
  equipmentName,
  status,
  size = "default",
}: WorkerCardProps) => {
  return (
    <div className={`worker-card ${size}`}>
      <div className="worker-info">
        <div className="worker-profile">
          <div className="profile-icon" />
          <div className="worker-texts">
            <div className="top-row">
              <span className="worker-name">{name}</span>
              {size === "default" && (
                <span className="worker-position">{role}</span>
              )}
            </div>
            {size === "default" ? (
              <div className="bottom-row">
                <span
                  className={`status-text ${
                    status === "대기중" ? "waiting" : "active"
                  }`}
                >
                  {status}
                </span>
              </div>
            ) : (
              <span className="worker-role-small">{role}</span>
            )}
          </div>
        </div>
        <span className="worker-equipment">{equipmentName}</span>
      </div>
    </div>
  );
};

export default WorkerCard;
