import {
  Video,
  House,
  Users,
  ListChecks,
  Wrench,
  Cctv,
  // AlertTriangle,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import "../../styles/SideBar.css";

const navItems = [
  { id: "home", label: "홈", icon: House, to: "/home" },
  {
    id: "communication",
    label: "커뮤니케이션",
    icon: Video,
    to: "/communication",
  },
  {
    id: "staff",
    label: "직원 관리",
    icon: Users,
    to: "/employees",
  },
  { id: "work", label: "작업 현황", icon: ListChecks, to: "/work" },
  {
    id: "equipment",
    label: "설비 관리",
    icon: Wrench,
    to: "/equipment",
  },
  {
    id: "cctv",
    label: "CCTV 모니터링",
    icon: Cctv,
    to: "/cctv",
  },
  // {
  //   id: "anomaly",
  //   label: "이상탐지 모니터링",
  //   icon: AlertTriangle,
  //   to: "/anomaly",
  // },
];

function SideBar() {
  return (
    <aside className="sidebar-container">
      <div className="logo-container">
        <img src="/icons/logo.png" alt="logo" />
        <div className="logo-text">
          <span className="upper">onAiR</span>
          <span className="down">산업 관리 시스템</span>
        </div>
      </div>

      {navItems.map((item) => {
        const Icon = item.icon;

        return (
          <NavLink
            key={item.id}
            to={item.to}
            end={item.to === "/home"}
            className={({ isActive }) =>
              `nav-button${isActive ? " active" : ""}`
            }
          >
            <Icon className="nav-icon" />
            <span className="button-text">{item.label}</span>
          </NavLink>
        );
      })}
    </aside>
  );
}

export default SideBar;
