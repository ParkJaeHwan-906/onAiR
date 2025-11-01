import './App.css'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import HomePage from './pages/HomePage'
import EmployeePage from './pages/EmployeePage'
import WorkPage from './pages/WorkPage'
import { CommunicationPage } from './pages/CommunicationPage'

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path='communication' element={<CommunicationPage />} />
        <Route path='employees' element={<EmployeePage />} />
        <Route path='work' element={<WorkPage />} />
        <Route path='*' element={<Navigate to='/' replace />} />
      </Route>
    </Routes>
  )
}

export default App
