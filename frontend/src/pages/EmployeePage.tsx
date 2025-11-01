import { useState } from 'react';
import type { Employee } from '../types/employee';
import '../styles/EmployeePage.css'
import EmployeeBig from '../components/Employee/EmployeeBig';
import EmployeeDetail from '../components/Employee/EmployeeDetail';

function EmployeePage () {
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);

  return (
    <div className='employee-page-wrapper'>
      <EmployeeBig onSelectEmployee={setSelectedEmployee} />
      <EmployeeDetail employee={selectedEmployee} />
    </div>
  );
}

export default EmployeePage