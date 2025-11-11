import "../../styles/TopBar.css";
import { useAuthStore } from "../../store/useAuthStore";
import { useNavigate } from "react-router-dom";
// import { Bell } from "lucide-react";
import { useState, useEffect, useRef } from "react";

function TopBar() {
  const { user, isAuthenticated, logoutUser } = useAuthStore();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleLogout = async () => {
    await logoutUser(); // async로 변경
    window.location.href = "/";
  };

  // 외부 클릭 감지해서 메뉴 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogin = () => navigate("/");

  const profileImage = "/images/default-profile.png";

  return (
    <header className="topbar-container">
      {isAuthenticated && user ? (
        <div className="topbar-right" ref={menuRef}>
          {/* 프로필 */}
          <img
            src={profileImage}
            alt="profile"
            className="topbar-profile"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          />

          {/* 이름 */}
          <span className="topbar-name">{user.name}</span>

          {/* 드롭다운 메뉴 */}
          {isMenuOpen && (
            <div className="profile-menu">
              <p onClick={handleLogout}>로그아웃</p>
            </div>
          )}
        </div>
      ) : (
        <div className="topbar-right">
          <span className="topbar-login-link" onClick={handleLogin}>
            로그인
          </span>
        </div>
      )}
    </header>
  );
}

export default TopBar;
