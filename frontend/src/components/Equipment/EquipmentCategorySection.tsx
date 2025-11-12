import { useState, useEffect } from "react";
import "../../styles/EquipmentCategorySection.css";
import {
  getEquipmentCategoryList,
  registEquipmentCategory,
} from "../../api/equipment";

interface Category {
  id: number;
  name: string;
}

interface EquipmentCategorySectionProps {
  onCategoryAdded?: () => void;
}

function EquipmentCategorySection({
  onCategoryAdded,
}: EquipmentCategorySectionProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [newCategory, setNewCategory] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchCategories = async () => {
    try {
      const res = await getEquipmentCategoryList();
      if (res.success && res.data) {
        setCategories(res.data);
      }
    } catch (error) {
      console.error("카테고리 목록 조회 실패:", error);
    }
  };

  useEffect(() => {
    fetchCategories();
  }, []);

  const handleAddCategory = async () => {
    if (!newCategory.trim()) {
      alert("카테고리 이름을 입력해주세요.");
      return;
    }

    try {
      setLoading(true);
      const res = await registEquipmentCategory(newCategory.trim());
      if (res.success) {
        setNewCategory("");
        await fetchCategories();
        if (onCategoryAdded) {
          onCategoryAdded();
        }
        alert("카테고리가 등록되었습니다.");
      } else {
        alert(res.message || "카테고리 등록에 실패했습니다.");
      }
    } catch (error: any) {
      console.error("카테고리 등록 실패:", error);
      alert(error.response?.data?.message || "카테고리 등록에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="equipment-category-section">
      <div className="section-header">설비 카테고리 관리</div>
      <div className="category-add-form">
        <input
          type="text"
          className="category-input"
          placeholder="카테고리 이름을 입력하세요"
          value={newCategory}
          onChange={(e) => setNewCategory(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleAddCategory();
            }
          }}
        />
        <button
          className="category-add-button"
          onClick={handleAddCategory}
          disabled={loading}
        >
          {loading ? "등록 중..." : "추가"}
        </button>
      </div>
      <div className="category-list">
        {categories.length === 0 ? (
          <div className="empty-message">등록된 카테고리가 없습니다.</div>
        ) : (
          categories.map((category) => (
            <div key={category.id} className="category-item">
              {category.name}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default EquipmentCategorySection;
