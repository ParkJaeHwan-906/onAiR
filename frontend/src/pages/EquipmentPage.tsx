import { useEffect, useState } from "react";
import "../styles/EquipmentPage.css";
import EquipmentCategorySection from "../components/Equipment/EquipmentCategorySection";
import EquipmentRegisterSection from "../components/Equipment/EquipmentRegisterSection";
import CompanyEquipmentSection from "../components/Equipment/CompanyEquipmentSection";
import { useUserStore } from "../store/useUserStore";

function EquipmentPage() {
  const { fetchMyInfo, myInfo } = useUserStore();
  const [categoryRefreshKey, setCategoryRefreshKey] = useState(0);
  const [equipmentRefreshKey, setEquipmentRefreshKey] = useState(0);

  useEffect(() => {
    fetchMyInfo();
  }, []);

  const isAdmin = myInfo?.role === "관리자";

  const handleCategoryAdded = () => {
    setCategoryRefreshKey((prev) => prev + 1);
  };

  const handleEquipmentAdded = () => {
    setEquipmentRefreshKey((prev) => prev + 1);
  };

  if (!isAdmin) {
    return (
      <div className="equipment-page-wrapper empty">
        <div className="equipment-access-card">
          <h2 className="equipment-access-title">접근 권한이 없습니다.</h2>
          <p className="equipment-access-sub">
            설비 관리는 관리자만 이용할 수 있습니다.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="equipment-page-wrapper">
      <div className="equipment-component-wrapper">
        <EquipmentCategorySection onCategoryAdded={handleCategoryAdded} />
        <EquipmentRegisterSection
          categoryRefreshKey={categoryRefreshKey}
          onEquipmentAdded={handleEquipmentAdded}
        />
        <CompanyEquipmentSection equipmentRefreshKey={equipmentRefreshKey} />
      </div>
    </div>
  );
}

export default EquipmentPage;
