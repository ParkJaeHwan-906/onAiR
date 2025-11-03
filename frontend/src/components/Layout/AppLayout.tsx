import { Outlet } from 'react-router-dom'
import '../../styles/AppLayout.css'
import SideBar from '../SideBar/SideBar'
import TopBar from '../TopBar/TopBar'

function AppLayout() {
  return (
    <div className='app-layout'>
      <SideBar />
      <div className='app-layout-content'>
        <TopBar />
        <main className='app-layout-main'>
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
