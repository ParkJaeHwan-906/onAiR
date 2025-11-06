import { useEffect, useState } from "react";
import { useUserStore } from "../store/useUserStore";
import type { Employee } from "../types/employee";
import "../styles/EmployeePage.css";
import EmployeeBig from "../components/Employee/EmployeeBig";
import EmployeeDetail from "../components/Employee/EmployeeDetail";

function EmployeePage() {
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(
    null
  );

  /**
   * myInfo: 현재 로그인한 사용자 정보
   * fetchMyInfo: 내 정보 API 호출
   * fetchEmployees:: 직원 전체 목록 API 호출
   */
  const { myInfo, fetchMyInfo, fetchEmployees } = useUserStore();

  // 로그인한 사용자 정보 불러오기
  useEffect(() => {
    fetchMyInfo();
  }, []);

  // 관리자라면 직원 목록 불러오기
  useEffect(() => {
    if (myInfo?.role === "관리자") {
      fetchEmployees(null);
    }
  }, [myInfo]);

  // 관리자 여부 판단
  const isAdmin = myInfo?.role === "관리자";
  // EmployeeDetail에 보낼 영역 -> 관리자면 선택한 직원, 사용자면 내 정보
  const rightEmployee = isAdmin ? selectedEmployee : myInfo;

  return (
    <div className="employee-page-wrapper">
      <EmployeeBig onSelectEmployee={setSelectedEmployee} />
      <EmployeeDetail employee={rightEmployee} />
    </div>
  );
}

export default EmployeePage;
