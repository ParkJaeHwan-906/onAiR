import { NavLink } from 'react-router-dom'
import '../../styles/SideBar.css'

const navItems = [
  { id: 'home', label: '홈', icon: '/icons/home.png', to: '/home' },
  { id: 'communication', label: '커뮤니케이션 관리', icon: '/icons/text.png', to: '/communication' },
  { id: 'staff', label: '직원 관리', icon: '/icons/profile.png', to: '/employees' },
  { id: 'work', label: '작업 관리', icon: '/icons/list.png', to: '/work' },
]

function SideBar() {
  return (
    <aside className='sidebar-container'>
      <div className='logo-container'>
        <img src='/icons/logo.png' alt='logo' />
        <div className='logo-text'>
          <span className='upper'>onAiR</span>
          <span className='down'>산업 관리 시스템</span>
        </div>
      </div>

      {navItems.map((item) => (
        <NavLink
          key={item.id}
          to={item.to}
          end={item.to === '/home'}
          className={({ isActive }) => `nav-button${isActive ? ' active' : ''}`}
        >
          <img src={item.icon} alt={item.label} />
          <span className='button-text'>{item.label}</span>
        </NavLink>
      ))}
    </aside>
  )
}

export default SideBar
