import { useState, useEffect, useRef } from "react";
import "../../styles/WorkAdd.css";
import { registTask, getTaskList, assignTaskToWorker } from "../../api/task";
import { getCompanyEquipmentList } from "../../api/equipment";
import { getUserList } from "../../api/user";
import { useUserStore } from "../../store/useUserStore";
import { useSSEStore } from "../../store/useSSEStore";
import type { Employee } from "../../types/employee";
import type { Work } from "../../types/work";

interface Equipment {
  id: number;
  category: string;
  name: string;
}

interface WorkAddProps {
  title?: string;
  label?: string;
  placeholder?: string;
  buttonText?: string;
  onTaskAdded?: () => void;
  onSubmit?: (text: string) => void;
  defaultEquipmentId?: number | null;
  defaultEquipmentLabel?: string;
  defaultEmployeeId?: number | null;
  defaultEmployeeLabel?: string;
}

function WorkAdd({
  title = "작업 추가",
  label = "작업 내용",
  placeholder = "작업 내용을 입력하세요",
  buttonText = "작업 등록",
  onTaskAdded,
  onSubmit,
  defaultEquipmentId = null,
  defaultEquipmentLabel,
  defaultEmployeeId = null,
  defaultEmployeeLabel,
}: WorkAddProps) {
  const [text, setText] = useState("");
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    defaultEquipmentId ?? null
  );
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(
    defaultEmployeeId ?? null
  );
  const [isEquipmentDropdownOpen, setIsEquipmentDropdownOpen] = useState(false);
  const [isEmployeeDropdownOpen, setIsEmployeeDropdownOpen] = useState(false);
  const equipmentDropdownRef = useRef<HTMLDivElement | null>(null);
  const employeeDropdownRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(false);

  const { myInfo } = useUserStore();
  const { connect: connectSSE } = useSSEStore();
  const isAdmin = myInfo?.role === "관리자";

  // 초기 데이터 로드
  useEffect(() => {
    if (isAdmin) {
      fetchEquipments();
      fetchEmployees();
    }
  }, [isAdmin]);

  useEffect(() => {
    setSelectedEquipmentId(defaultEquipmentId ?? null);
  }, [defaultEquipmentId]);

  useEffect(() => {
    setSelectedEmployeeId(defaultEmployeeId ?? null);
  }, [defaultEmployeeId]);

  const fetchEquipments = async () => {
    try {
      const res = await getCompanyEquipmentList();
      if (res.success && res.data) setEquipments(res.data);
    } catch (error) {
      console.error("장비 목록 조회 실패:", error);
    }
  };

  const fetchEmployees = async () => {
    try {
      const res = await getUserList(null);
      if (res.success && res.data) setEmployees(res.data);
    } catch (error) {
      console.error("직원 목록 조회 실패:", error);
    }
  };

  // 드롭다운 외부 클릭 닫기
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        isEquipmentDropdownOpen &&
        equipmentDropdownRef.current &&
        !equipmentDropdownRef.current.contains(target)
      ) {
        setIsEquipmentDropdownOpen(false);
      }
      if (
        isEmployeeDropdownOpen &&
        employeeDropdownRef.current &&
        !employeeDropdownRef.current.contains(target)
      ) {
        setIsEmployeeDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isEquipmentDropdownOpen, isEmployeeDropdownOpen]);

  const filteredEmployees = selectedEquipmentId
    ? [...employees].sort((a, b) => {
        const aAssigned = a.equipmentId === selectedEquipmentId ? 1 : 0;
        const bAssigned = b.equipmentId === selectedEquipmentId ? 1 : 0;
        return bAssigned - aAssigned;
      })
    : employees;

  // 메인 등록 핸들러
  const handleClick = async () => {
    if (!text.trim()) return alert("내용을 입력해주세요.");

    if (onSubmit) {
      onSubmit(text.trim());
      setText("");
      return;
    }

    if (isAdmin && (!selectedEquipmentId || !selectedEmployeeId))
      return alert("설비와 담당자를 모두 선택해주세요.");

    try {
      setLoading(true);
      const equipmentId = isAdmin ? selectedEquipmentId! : myInfo?.equipmentId;
      const requestText = text.trim();

      // 작업 등록
      const res = await registTask(equipmentId!, requestText);
      if (!res.success)
        return alert(res.message || "작업 등록에 실패했습니다.");

      // 관리자만 작업자에게 즉시 할당
      if (isAdmin && selectedEmployeeId) {
        // 담당자 정보 검증
        const selectedEmployee = employees.find(
          (e) => e.userAccountId === selectedEmployeeId
        );
        if (!selectedEmployee) return alert("담당자 정보를 찾을 수 없습니다.");
        if (!selectedEmployee.equipmentId)
          return alert("담당자에게 설비가 지정되지 않았습니다.");
        if (!selectedEmployee.online)
          return alert(
            "담당자가 오프라인 상태입니다.\n로그인 후 다시 시도해주세요."
          );

        // SSE 연결 상태 점검 및 재연결
        const sseState = useSSEStore.getState();
        let eventSource = sseState.eventSource;

        if (!eventSource || eventSource.readyState !== EventSource.OPEN) {
          // console.log("SSE 재연결 시도...");
          connectSSE();
          let retry = 0;
          while (retry < 50) {
            const current = useSSEStore.getState().eventSource;
            if (current && current.readyState === EventSource.OPEN) {
              // console.log("SSE 연결 완료");
              eventSource = current;
              break;
            }
            await new Promise((r) => setTimeout(r, 100));
            retry++;
          }
        }

        if (!eventSource || eventSource.readyState !== EventSource.OPEN) {
          alert("실시간 연결이 불안정합니다. 잠시 후 다시 시도해주세요.");
          return;
        }

        // emitter 등록 여유시간 (1초)
        await new Promise((r) => setTimeout(r, 1000));

        // 작업 ID 찾기
        const taskListRes = await getTaskList(equipmentId!, null);
        const latestTask = taskListRes.data
          ?.filter((t: Work) => t.request === requestText)
          ?.sort(
            (a: Work, b: Work) =>
              new Date(b.lastUpdateTime).getTime() -
              new Date(a.lastUpdateTime).getTime()
          )[0];

        if (!latestTask) return alert("등록된 작업을 찾을 수 없습니다.");

        // 할당 요청
        try {
          const assignRes = await assignTaskToWorker(
            latestTask.id,
            selectedEmployeeId
          );
          if (assignRes.success) {
            alert("작업이 등록되고 담당자에게 할당되었습니다.");
            onTaskAdded?.();
          } else {
            alert("작업 등록은 완료되었으나 할당 실패: " + assignRes.message);
          }
        } catch (error: any) {
          const msg =
            error.response?.data?.message ||
            error.message ||
            "서버 내부 오류 (SSE 전송 실패로 롤백된 경우일 수 있습니다.)";

          console.error("작업 할당 실패:", msg);
          alert(
            `작업 할당 실패\n\n가능한 원인:\n- 작업자 SSE 연결 미등록\n- SSE 전송 실패로 인한 롤백\n\n상세 메시지: ${msg}`
          );
        }
      } else {
        alert("작업이 등록되었습니다.");
      }

      setText("");
      setSelectedEmployeeId(null);
      onTaskAdded?.();
    } catch (error: any) {
      console.error("작업 등록 실패:", error);
      alert(
        error.response?.data?.message || "작업 등록 중 오류가 발생했습니다."
      );
    } finally {
      setLoading(false);
    }
  };

  // 렌더링
  if (!isAdmin) return null;

  const selectedEquipment = equipments.find(
    (eq) => eq.id === selectedEquipmentId
  );
  const selectedEmployee = employees.find(
    (emp) => emp.userAccountId === selectedEmployeeId
  );
  const equipmentTriggerLabel = selectedEquipment
    ? `${selectedEquipment.name} (${selectedEquipment.category})`
    : defaultEquipmentLabel ?? "설비를 선택하세요";
  const employeeTriggerLabel = selectedEmployee
    ? `${selectedEmployee.name} (${selectedEmployee.part})`
    : defaultEmployeeLabel ?? "담당자를 선택하세요";

  const isBodyScrollable = isEquipmentDropdownOpen || isEmployeeDropdownOpen;

  return (
    <div className="work-add">
      <div className="work-add-header">{title}</div>

      <div className={`work-add-body${isBodyScrollable ? " scrollable" : ""}`}>
        {/* 설비 선택 */}
        <div className="assign-header">설비</div>
        <div className="work-select-wrapper" ref={equipmentDropdownRef}>
          <button
            type="button"
            className={`work-select-trigger${
              isEquipmentDropdownOpen ? " open" : ""
            }`}
            onClick={() => setIsEquipmentDropdownOpen((prev) => !prev)}
          >
            {equipmentTriggerLabel}
          </button>
          {isEquipmentDropdownOpen && (
            <ul className="work-select-dropdown">
              {equipments.map((eq) => (
                <li key={eq.id}>
                  <button
                    type="button"
                    className={`work-select-option${
                      eq.id === selectedEquipmentId ? " selected" : ""
                    }`}
                    onClick={() => {
                      setSelectedEquipmentId(eq.id);
                      setIsEquipmentDropdownOpen(false);
                    }}
                  >
                    <span className="work-select-option-title">{eq.name}</span>
                    <span className="work-select-option-meta">
                      {eq.category}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 담당자 선택 */}
        <div className="assign-header">담당자</div>
        <div className="work-select-wrapper" ref={employeeDropdownRef}>
          <button
            type="button"
            className={`work-select-trigger${
              isEmployeeDropdownOpen ? " open" : ""
            }`}
            onClick={() => setIsEmployeeDropdownOpen((prev) => !prev)}
          >
            {employeeTriggerLabel}
          </button>
          {isEmployeeDropdownOpen && (
            <ul className="work-select-dropdown">
              {filteredEmployees.map((employee) => (
                <li key={employee.userAccountId}>
                  <button
                    type="button"
                    className={`work-select-option${
                      employee.userAccountId === selectedEmployeeId
                        ? " selected"
                        : ""
                    }`}
                    onClick={() => {
                      setSelectedEmployeeId(employee.userAccountId);
                      setIsEmployeeDropdownOpen(false);
                    }}
                  >
                    <span className="work-select-option-title">
                      {employee.name}
                    </span>
                    <span className="work-select-option-meta">
                      {employee.part}
                      {employee.equipmentName
                        ? ` · ${employee.equipmentName}`
                        : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 작업 내용 입력 */}
        <div className="assign-header">{label}</div>
        <textarea
          className="request-body"
          value={text}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          rows={4}
        />
      </div>

      <button
        type="button"
        className="add-button"
        onClick={handleClick}
        disabled={loading}
      >
        {loading ? "등록 중..." : buttonText}
      </button>
    </div>
  );
}

export default WorkAdd;
