import '../../styles/EmployeeBig.css'
import EmployeeList from './EmployeeList'
import type { Employee } from '../../types/employee';

const dummyEmployee: Employee[] = [
  {id: 1, name: '손동현', part: '하드웨어', online: true, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 3, name: '손동현', part: '하드웨어', online: true, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 4, name: '손동현', part: '하드웨어', online: false, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 5, name: '손동현', part: '하드웨어', online: true, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 6, name: '손동현', part: '하드웨어', online: false, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 7, name: '손동현', part: '하드웨어', online: false, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 8, name: '손동현', part: '하드웨어', online: true, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 9, name: '손동현', part: '하드웨어', online: false, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 10, name: '손동현', part: '하드웨어', online: true, phone: '010-1234-5678', email: 'email@email.com'},
  {id: 11, name: '손동현', part: '하드웨어', online: false, phone: '010-1234-5678', email: 'email@email.com'},
];

type EmployeeBigProps = {
  onSelectEmployee: (employee: Employee) => void;
};

function EmployeeBig ({ onSelectEmployee }: EmployeeBigProps) {
  return (
    <div className='employee-big'>
      <div className='employee-big-header'>
        <span className='title'>직원 목록</span>
      </div>
      <input className='search-bar' placeholder='직원 검색 ...' type="text" />
      <div className='list-header'>
        <div className='first'>
          이름
        </div>
        <div className='second'>
          부서
        </div>
        <div className='third'>
          근무 상태
        </div>
        <div className='fourth'>
          이메일
        </div>
        <div className='fifth'>
          연락처
        </div>
      </div>
      <div className='list-body'>
        {dummyEmployee.map((item) => (
          <EmployeeList 
            key={item.id}
            name={item.name}
            part={item.part}
            online={item.online}
            email={item.email}
            phone={item.phone}
            onSelect={() => onSelectEmployee(item)}
          />
        ))}
      </div>
    </div>
  )
}

export default EmployeeBig
