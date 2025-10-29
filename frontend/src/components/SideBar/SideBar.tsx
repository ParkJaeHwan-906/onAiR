import { useState } from 'react';
import '../styles/SideBar.css';

const navItems = [
  { id: 'home', label: '홈', icon: 'assets/home.png' },
  { id: 'communication', label: '커뮤니케이션 관리', icon: 'assets/text.png' },
  { id: 'staff', label: '직원 관리', icon: 'assets/human.png' },
  { id: 'work', label: '작업 관리', icon: 'assets/list.png' },
];

function SideBar() {
  const [activeItem, setActiveItem] = useState(navItems[0]?.id ?? '');

  return (
    <div className='sidebar-container'>
      <div className='logo-container'>
        <img src="assets/logo.png" alt="logo" />
        <div className='logo-text'>
          <span className='upper'>onAiR</span>
          <span className='down'>산업 관리 시스템</span>
        </div>
      </div>

      {navItems.map((item) => (
        <button
          key={item.id}
          type='button'
          className={`nav-button${activeItem === item.id ? ' active' : ''}`}
          onClick={() => setActiveItem(item.id)}
        >
          <img src={item.icon} alt={item.label} />
          <span className='button-text'>{item.label}</span>
        </button>
      ))}
    </div>
  );
}

export default SideBar;
