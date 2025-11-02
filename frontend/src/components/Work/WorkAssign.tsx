import { useEffect, useMemo, useRef, useState } from 'react';
import '../../styles/WorkAssign.css'

const dummyemployees = [
  {
    "userAccountId": 1,
    "name": "김민재",
    "phone": "010-2345-6789",
    "email": "minjae.kim@company.com",
    "part": "생산관리팀",
    "equipmentId": "EQ-001",
    "equipmentName": "냉각수 펌프 A",
    "online": true
  },
  {
    "userAccountId": 2,
    "name": "이서현",
    "phone": "010-9988-7766",
    "email": "seohyun.lee@company.com",
    "part": "설비유지보수팀",
    "equipmentId": "EQ-002",
    "equipmentName": "컨베이어 라인 3호기",
    "online": false
  },
  {
    "userAccountId": 3,
    "name": "박지훈",
    "phone": "010-5566-4433",
    "email": "jihoon.park@company.com",
    "part": "전기안전팀",
    "equipmentId": "EQ-003",
    "equipmentName": "전력 분배반 B",
    "online": true
  },
  {
    "userAccountId": 4,
    "name": "정유나",
    "phone": "010-1122-3344",
    "email": "yuna.jung@company.com",
    "part": "품질관리팀",
    "equipmentId": "EQ-004",
    "equipmentName": "압축기 모듈 C",
    "online": false
  },
  {
    "userAccountId": 5,
    "name": "최현우",
    "phone": "010-6677-8899",
    "email": "hyunwoo.choi@company.com",
    "part": "기계설계팀",
    "equipmentId": "EQ-005",
    "equipmentName": "자동포장기 2호기",
    "online": true
  }
]

const dummyworks = [
  {
    "id": 1,
    "equipmentId": "EQ-001",
    "equipmentName": "냉각수 펌프 A",
    "request": "냉각수 압력이 정상보다 낮음",
    "userAccountId": 1,
    "userName": "김민재",
    "action": 2,
    "actionStatus": "작업중",
    "solution": "펌프 밸브 점검 및 오염 필터 교체",
    "lastUpdateTime": "2025-11-01T09:45:00Z"
  },
  {
    "id": 2,
    "equipmentId": "EQ-002",
    "equipmentName": "컨베이어 라인 3호기",
    "request": "라인 작동 중 진동 감지",
    "userAccountId": 2,
    "userName": "이서현",
    "action": 1,
    "actionStatus": "대기중",
    "solution": "베어링 상태 점검 예정",
    "lastUpdateTime": "2025-10-31T17:10:00Z"
  },
  {
    "id": 3,
    "equipmentId": "EQ-003",
    "equipmentName": "전력 분배반 B",
    "request": "전류 이상 감지 경보 발생",
    "userAccountId": 3,
    "userName": "박지훈",
    "action": 3,
    "actionStatus": "완료",
    "solution": "퓨즈 교체 및 절연 저항 확인 완료",
    "lastUpdateTime": "2025-11-01T08:30:00Z"
  },
  {
    "id": 4,
    "equipmentId": "EQ-004",
    "equipmentName": "압축기 모듈 C",
    "request": "압축기 온도 상승 경고",
    "userAccountId": 4,
    "userName": "정유나",
    "action": 0,
    "actionStatus": "취소됨",
    "solution": "센서 오작동으로 판명, 작업 취소",
    "lastUpdateTime": "2025-10-30T14:55:00Z"
  },
  {
    "id": 5,
    "equipmentId": "EQ-005",
    "equipmentName": "자동포장기 2호기",
    "request": "포장 필름 걸림 현상 발생",
    "userAccountId": 5,
    "userName": "최현우",
    "action": 2,
    "actionStatus": "작업중",
    "solution": "롤러 분리 및 이물 제거 중",
    "lastUpdateTime": "2025-11-01T10:20:00Z"
  }
]

function WorkAssign () {
  const [selectedWorkId, setSelectedWorkId] = useState<number | null>(dummyworks[0]?.id ?? null);
  const [isWorkDropdownOpen, setIsWorkDropdownOpen] = useState(false);
  const workDropdownRef = useRef<HTMLDivElement | null>(null);

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(dummyemployees[0]?.userAccountId ?? null);
  const [isEmployeeDropdownOpen, setIsEmployeeDropdownOpen] = useState(false);
  const employeeDropdownRef = useRef<HTMLDivElement | null>(null);

  const selectedWork = useMemo(
    () => dummyworks.find((work) => work.id === selectedWorkId) ?? null,
    [selectedWorkId]
  );

  const selectedEmployee = useMemo(
    () => dummyemployees.find((employee) => employee.userAccountId === selectedEmployeeId) ?? null,
    [selectedEmployeeId]
  );

  useEffect(() => {
    if (!isWorkDropdownOpen && !isEmployeeDropdownOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;

      if (isWorkDropdownOpen && workDropdownRef.current && !workDropdownRef.current.contains(target)) {
        setIsWorkDropdownOpen(false);
      }

      if (isEmployeeDropdownOpen && employeeDropdownRef.current && !employeeDropdownRef.current.contains(target)) {
        setIsEmployeeDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isWorkDropdownOpen, isEmployeeDropdownOpen]);

  return (
    <div className='work-assign'>
      <div className='work-assign-header'>작업 재할당</div>

      <div className='assign-header'>작업</div>
      <div className='work-select-wrapper' ref={workDropdownRef}>
        <button
          type='button'
          className={`work-select-trigger${isWorkDropdownOpen ? ' open' : ''}`}
          onClick={() => setIsWorkDropdownOpen((prev) => !prev)}
        >
          {selectedWork ? `${selectedWork.equipmentName} (${selectedWork.id})` : '작업을 선택하세요'}
        </button>
        {isWorkDropdownOpen && (
          <ul className='work-select-dropdown'>
            {dummyworks.map((work) => (
              <li key={work.id}>
                <button
                  type='button'
                  className={`work-select-option${work.id === selectedWorkId ? ' selected' : ''}`}
                  onClick={() => {
                    setSelectedWorkId(work.id);
                    setIsWorkDropdownOpen(false);
                  }}
                >
                  <span className='work-select-option-title'>{work.equipmentName}</span>
                  <span className='work-select-option-meta'>#{work.id} · {work.actionStatus}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className='assign-header'>담당자</div>
      <div className='work-select-wrapper' ref={employeeDropdownRef}>
        <button
          type='button'
          className={`work-select-trigger${isEmployeeDropdownOpen ? ' open' : ''}`}
          onClick={() => setIsEmployeeDropdownOpen((prev) => !prev)}
        >
          {selectedEmployee ? `${selectedEmployee.name} (${selectedEmployee.part})` : '담당자를 선택하세요'}
        </button>
        {isEmployeeDropdownOpen && (
          <ul className='work-select-dropdown'>
            {dummyemployees.map((employee) => (
              <li key={employee.userAccountId}>
                <button
                  type='button'
                  className={`work-select-option${employee.userAccountId === selectedEmployeeId ? ' selected' : ''}`}
                  onClick={() => {
                    setSelectedEmployeeId(employee.userAccountId);
                    setIsEmployeeDropdownOpen(false);
                  }}
                >
                  <span className='work-select-option-title'>{employee.name}</span>
                  <span className='work-select-option-meta'>#{employee.userAccountId} · {employee.part} · {employee.online ? '온라인' : '오프라인'}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <button className='assign-button'>
        작업 재할당
      </button>
    </div>
  );
}

export default WorkAssign
