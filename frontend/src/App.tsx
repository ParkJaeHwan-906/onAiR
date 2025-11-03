import './App.css'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import HomePage from './pages/HomePage'
import EmployeePage from './pages/EmployeePage'
import WorkPage from './pages/WorkPage'
import { CommunicationPage } from './pages/CommunicationPage'
import LoginPage from './pages/LoginPage'

function App() {
<<<<<<< HEAD

  return (
    <>
      <RouterProvider router={router} />
    </>
=======
  return (
    <Routes>
      <Route path='/' element={<LoginPage />} />
      <Route element={<AppLayout />}>
        <Route path='home' element={<HomePage />} />
        <Route path='communication' element={<CommunicationPage />} />
        <Route path='employees' element={<EmployeePage />} />
        <Route path='work' element={<WorkPage />} />
        <Route path='*' element={<Navigate to='/home' replace />} />
      </Route>
      <Route path='*' element={<Navigate to='/' replace />} />
    </Routes>
>>>>>>> origin/develop
  )
}

export default App;
