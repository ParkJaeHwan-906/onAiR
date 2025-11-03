import '../../styles/EmployeeDetail.css'
import type { Employee } from '../../types/employee';

type EmployeeDetailProps = {
  employee: Employee | null;
};

function EmployeeDetail ({ employee }: EmployeeDetailProps) {
  if (!employee) {
    return (
      <div className='detail-wrapper'>
        <div className='detail-header'>직원 상세 정보</div>
        <span className='detail-empty'>직원을 선택해주세요.</span>
      </div>
    );
  }

  return (
    <div className='detail-wrapper'>
      <div className='detail-header'>직원 상세 정보</div>
      <h2 className='detail-title'>{employee.name}</h2>
      <div className='detail-status' data-online={employee.online ? 'true' : 'false'}>
        {employee.online ? '온라인' : '오프라인'}
      </div>
      <dl className='detail-list'>
        <div className='detail-item'>
          <dt>부서</dt>
          <dd>{employee.part}</dd>
        </div>
        <div className='detail-item'>
          <dt>이메일</dt>
          <dd>{employee.email}</dd>
        </div>
        <div className='detail-item'>
          <dt>연락처</dt>
          <dd>{employee.phone}</dd>
        </div>
      </dl>
      <button className='connect-button'>연결 요청</button>
    </div>
  );
}

export default EmployeeDetail
