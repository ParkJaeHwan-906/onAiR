import { useEffect, useState, useRef } from "react";
import { TextAlignJustify } from "lucide-react";
import WorkerCard from "./WorkerCard";
import { useUserStore } from "../../store/useUserStore";
import "../../styles/Communication/WorkerHeader.css";

interface UserData {
  userAccountId: number;
  name: string;
  equipmentName: string;
  role: string;
}

interface PartnerInfo {
  senderAccountId: number;
  name: string;
  phone: string;
  equipmentName: string | null;
}

interface WorkerHeaderProps {
  partnerInfo?: PartnerInfo | null;
}

const WorkerHeader = ({ partnerInfo }: WorkerHeaderProps) => {
  const { myInfo } = useUserStore();
  const [status, setStatus] = useState<"대기중" | "통신중">("통신중");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  // const [waitingList, setWaitingList] = useState<UserData[]>([]);
  const [waitingList, ] = useState<UserData[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // 상대방 정보가 있으면 통신중 상태로 설정
  useEffect(() => {
    if (partnerInfo) {
      setStatus("통신중");
    }
  }, [partnerInfo]);

  const toggleStatus = () => {
    setStatus((prev) => (prev === "대기중" ? "통신중" : "대기중"));
  };

  const toggleDropdown = () => setIsDropdownOpen((prev) => !prev);

  // 카드 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="worker-header-container" ref={containerRef}>
      {/* 상단 메인 카드 */}
      <div className="worker-card default">
        <div className="worker-info">
          <div className="worker-profile">
            <div className="profile-icon" />
            <div className="worker-texts">
              <div className="top-row">
                <span className="worker-name">
                  {partnerInfo ? partnerInfo.name : myInfo?.name || "사용자"}
                </span>
                <span className="worker-position">
                  {partnerInfo ? (partnerInfo.equipmentName || "설비 미지정") : (myInfo?.part || "부서")}
                </span>
              </div>
              <div className="bottom-row">
                <span
                  className={`status-text ${
                    status === "대기중" ? "waiting" : "active"
                  }`}
                  onClick={toggleStatus}
                >
                  {status}
                </span>
              </div>
            </div>
          </div>

          <button
            className={`dropdown-icon ${isDropdownOpen ? "open" : ""}`}
            onClick={toggleDropdown}
          >
            <TextAlignJustify size={25} />
          </button>
        </div>
      </div>

      {/* 대기자 목록 */}
      {isDropdownOpen && (
        <div className="dropdown-overlay">
          <div className="dropdown-list">
            <div className="dropdown-title">대기자 목록</div>
            {waitingList.map((user) => (
              <WorkerCard
                key={user.userAccountId}
                name={user.name}
                role={user.role}
                equipmentName={user.equipmentName}
                size="small"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkerHeader;
