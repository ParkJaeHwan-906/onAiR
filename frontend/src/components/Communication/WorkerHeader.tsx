// 프로필, 이름, 부서, 상태 “대기중” 부분
import React, { useEffect, useState } from "react";
import { TextAlignJustify } from "lucide-react";
import "../../styles/Communication/WorkerHeader.css";

interface UserData {
  userAccountId: number;
  name: string;
  equipmentName: string;
  role: string;
}

const WorkerHeader = () => {
  // 현재 사용자 통신 상태
  const [status, setStatus] = useState<"대기중" | "통신중">("대기중");

  // 리스트 드롭여부
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // 대기자 목록 (더미) -> 추후 api 연결 예정
  const [waitingList, setWaitingList] = useState<UserData[]>([]);

  // 더미 데이터
  useEffect(() => {
    const dummyData: UserData[] = [
      {
        userAccountId: 1,
        name: "최선우",
        equipmentName: "CNC1호기",
        role: "작업자",
      },
      {
        userAccountId: 2,
        name: "손동현",
        equipmentName: "CNC5호기",
        role: "작업자",
      },
      {
        userAccountId: 3,
        name: "손흥민",
        equipmentName: "아디다스1호기",
        role: "관리자",
      },
    ];
    setWaitingList(dummyData);
  }, []);

  // 통신 상태 토글 (임시)
  const toggleStatus = () => {
    setStatus((prev) => (prev === "대기중" ? "통신중" : "대기중"));
  };

  // 리스트 클릭 -> 열기 / 닫기
  const toggleDropdown = () => setIsDropdownOpen((prev) => !prev);

  return (
    <div className="worker-card">
      <div className="worker-info">
        <div className="worker-profile">
          <div className="profile-icon" />
          <div className="worker-texts">
            <div className="top-row">
              <span className="worker-name">홍길동</span>
              <span className="worker-position">부서</span>
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
          <TextAlignJustify size={20} />
          <TextAlignJustify />
        </button>
      </div>

      {/* 대기자 리스트 */}
      {isDropdownOpen && (
        <div className="dropdown-list">
          {waitingList.map((user) => (
            <div key={user.userAccountId} className="dropdown-item">
              <span className="dropdown-name">{user.name}</span>
              <span className="dropdown-equip">{user.equipmentName}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default WorkerHeader;
