import "../../styles/EmployeeList.css";
import { formatPhone } from "../../utils/formatPhone";

type EmployeeListProps = {
  name: string;
  phone: string;
  part: string;
  email: string;
  online: boolean;
  equipmentName: string;
  onSelect: () => void;
};

function EmployeeList({
  name,
  phone,
  part,
  email,
  online,
  equipmentName,
  onSelect,
}: EmployeeListProps) {
  return (
    <div className="employee-row">
      <div className="col-name">{name}</div>
      <div className="col-phone">{formatPhone(phone)}</div>
      <div className="col-part">{part}</div>
      <div className="col-email">{email}</div>
      <div className="col-equipment">{equipmentName}</div>
      <div className="col-status">
        <span className={online ? "online" : "offline"}>
          {online ? "온라인" : "오프라인"}
        </span>
      </div>
      <div className="col-view">
        <button className="view-btn" onClick={onSelect}>
          보기
        </button>
      </div>
    </div>
  );
}

export default EmployeeList;
