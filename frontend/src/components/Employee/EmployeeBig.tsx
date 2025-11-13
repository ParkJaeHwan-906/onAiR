import "../../styles/EmployeeBig.css";
import EmployeeList from "./EmployeeList";
import type { Employee } from "../../types/employee";
import { useUserStore } from "../../store/useUserStore";
import { useState } from "react";

type EmployeeBigProps = {
  onSelectEmployee: (employee: Employee) => void;
};

function EmployeeBig({ onSelectEmployee }: EmployeeBigProps) {
  const { employees, myInfo, loading, error } = useUserStore();
  const isAdmin = myInfo?.role === "관리자";
  const [searchTerm, setSearchTerm] = useState("");

  // 검색 필터
  const filtered = employees.filter((emp) => {
    if (!searchTerm) return true;
    // 원본 전화번호 (DB)
    const rawPhone = emp.phone ?? "";
    // 표시되는 전화번호 (커스텀 포맷)
    const formattedPhone = rawPhone.replace(
      /(\d{3})(\d{4})(\d{4})/,
      "$1-$2-$3"
    );
    return (
      emp.name.includes(searchTerm) ||
      rawPhone.includes(searchTerm) ||
      formattedPhone.includes(searchTerm) ||
      (emp.email ?? "").includes(searchTerm) ||
      (emp.part ?? "").includes(searchTerm)
    );
  });

  return (
    <div className="employee-big">
      <div className="employee-big-header">
        <span className="employee-list">직원 목록</span>
      </div>

      <input
        className="search-bar"
        placeholder="직원 검색 ..."
        type="text"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
      />

      <div className="employee-table">
        <div className="list-header">
          <div className="col-name">이름</div>
          <div className="col-phone">연락처</div>
          <div className="col-part">부서</div>
          <div className="col-email">이메일</div>
          <div className="col-equipment">담당 설비</div>
          <div className="col-status">출근 여부</div>
          <div className="col-view"></div>
        </div>

        <div className="list-body">
          {loading && (
            <p className="loading-text">직원 정보를 불러오는 중...</p>
          )}
          {error && <p className="error-text">{error}</p>}

          {isAdmin ? (
            employees.length > 0 ? (
              filtered.map((item) => (
                <EmployeeList
                  key={item.userAccountId}
                  name={item.name}
                  phone={item.phone}
                  part={item.part}
                  email={item.email}
                  online={!!item.online}
                  equipmentName={item.equipmentName || "미지정"}
                  onSelect={() => onSelectEmployee(item)}
                />
              ))
            ) : (
              <p className="no-data">등록된 직원이 없습니다.</p>
            )
          ) : (
            <div className="no-access-box">
              <p className="no-access-title">관리자 전용 영역입니다.</p>
              <p className="no-access-sub">
                현재 계정은 본인 정보만 열람할 수 있습니다.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default EmployeeBig;
