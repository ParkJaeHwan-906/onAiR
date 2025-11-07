import "../../styles/EmployeeBig.css";
import EmployeeList from "./EmployeeList";
import type { Employee } from "../../types/employee";
import { useUserStore } from "../../store/useUserStore";

type EmployeeBigProps = {
  onSelectEmployee: (employee: Employee) => void;
};

function EmployeeBig({ onSelectEmployee }: EmployeeBigProps) {
  const { employees, myInfo, loading, error } = useUserStore();
  const isAdmin = myInfo?.role === "관리자";

  return (
    <div className="employee-big">
      <div className="employee-big-header">
        <span className="employee-list">직원 목록</span>
      </div>

      <input className="search-bar" placeholder="직원 검색 ..." type="text" />

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
              employees.map((item) => (
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
