import { useState, useEffect, useRef } from "react";
import "../../styles/EquipmentRegisterSection.css";
import {
  getEquipmentCategoryList,
  getEquipmentList,
  registEquipment,
} from "../../api/equipment";

interface Category {
  id: number;
  name: string;
}

interface Equipment {
  id: number;
  category: string;
  name: string;
}

interface EquipmentRegisterSectionProps {
  categoryRefreshKey?: number;
  onEquipmentAdded?: () => void;
}

function EquipmentRegisterSection({
  categoryRefreshKey = 0,
  onEquipmentAdded,
}: EquipmentRegisterSectionProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(
    null
  );
  const [equipmentName, setEquipmentName] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchCategories();
    fetchEquipments();
  }, [categoryRefreshKey]);

  useEffect(() => {
    if (!isDropdownOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        isDropdownOpen &&
        dropdownRef.current &&
        !dropdownRef.current.contains(target)
      ) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isDropdownOpen]);

  const fetchCategories = async () => {
    try {
      const res = await getEquipmentCategoryList();
      if (res.success && res.data) {
        setCategories(res.data);
        // 기본 선택값 없음 - "카테고리를 선택하세요" 표시
        setSelectedCategoryId(null);
      }
    } catch (error) {
      console.error("카테고리 목록 조회 실패:", error);
    }
  };

  const fetchEquipments = async () => {
    try {
      const res = await getEquipmentList();
      if (res.success && res.data) {
        setEquipments(res.data);
      }
    } catch (error) {
      console.error("설비 목록 조회 실패:", error);
    }
  };

  const handleRegister = async () => {
    if (!selectedCategoryId) {
      alert("카테고리를 선택해주세요.");
      return;
    }

    if (!equipmentName.trim()) {
      alert("설비 이름을 입력해주세요.");
      return;
    }

    try {
      setLoading(true);
      const res = await registEquipment(
        selectedCategoryId,
        equipmentName.trim()
      );
      if (res.success) {
        setEquipmentName("");
        await fetchEquipments();
        if (onEquipmentAdded) {
          onEquipmentAdded();
        }
        alert("설비가 등록되었습니다.");
      } else {
        alert(res.message || "설비 등록에 실패했습니다.");
      }
    } catch (error: any) {
      console.error("설비 등록 실패:", error);
      alert(error.response?.data?.message || "설비 등록에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const selectedCategory = categories.find(
    (cat) => cat.id === selectedCategoryId
  );

  return (
    <div className="equipment-register-section">
      <div className="section-header">설비 등록</div>
      <div className="register-form">
        <div className="form-label">카테고리</div>
        <div className="work-select-wrapper" ref={dropdownRef}>
          <button
            type="button"
            className={`work-select-trigger${isDropdownOpen ? " open" : ""}`}
            onClick={() => setIsDropdownOpen((prev) => !prev)}
          >
            {selectedCategory ? selectedCategory.name : "카테고리를 선택하세요"}
          </button>
          {isDropdownOpen && (
            <ul className="work-select-dropdown">
              {categories.map((category) => (
                <li key={category.id}>
                  <button
                    type="button"
                    className={`work-select-option${
                      category.id === selectedCategoryId ? " selected" : ""
                    }`}
                    onClick={() => {
                      setSelectedCategoryId(category.id);
                      setIsDropdownOpen(false);
                    }}
                  >
                    <span className="work-select-option-title">
                      {category.name}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="form-label">설비 이름</div>
        <input
          type="text"
          className="equipment-name-input"
          placeholder="설비 이름을 입력하세요"
          value={equipmentName}
          onChange={(e) => setEquipmentName(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              handleRegister();
            }
          }}
        />

        <button
          className="register-button"
          onClick={handleRegister}
          disabled={loading}
        >
          {loading ? "등록 중..." : "설비 등록"}
        </button>
      </div>

      <div className="equipment-list">
        <div className="list-header">전체 설비 목록</div>
        <div className="list-body">
          {equipments.length === 0 ? (
            <div className="empty-message">등록된 설비가 없습니다.</div>
          ) : (
            equipments.map((equipment) => (
              <div key={equipment.id} className="equipment-item">
                <span className="equipment-name">{equipment.name}</span>
                <span className="equipment-category">{equipment.category}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default EquipmentRegisterSection;
