import { useState } from 'react';
import './App.css'
import EmployeeBig from './components/Employee/EmployeeBig';
import EmployeeDetail from './components/Employee/EmployeeDetail';
import type { Employee } from './types/employee';

function App() {
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);

  return (
    <div style={{width: '1920px', display: 'flex', flexDirection: 'row'}}>
      <EmployeeBig onSelectEmployee={setSelectedEmployee} />
      <EmployeeDetail employee={selectedEmployee} />
    </div>
  );
}

export default App
