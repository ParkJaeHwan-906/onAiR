import { useState, useEffect, useRef } from 'react';
import '../../styles/CompanyEquipmentSection.css';
import {
  getEquipmentList,
  getCompanyEquipmentList,
  registCompanyEquipment,
} from '../../api/equipment';

interface Equipment {
  id: number;
  category: string;
  name: string;
}

interface CompanyEquipmentSectionProps {
  equipmentRefreshKey?: number;
}

function CompanyEquipmentSection({ equipmentRefreshKey = 0 }: CompanyEquipmentSectionProps) {
  const [allEquipments, setAllEquipments] = useState<Equipment[]>([]);
  const [companyEquipments, setCompanyEquipments] = useState<Equipment[]>([]);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<number | null>(
    null
  );
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchAllEquipments();
    fetchCompanyEquipments();
  }, [equipmentRefreshKey]);

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

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen]);

  const fetchAllEquipments = async () => {
    try {
      const res = await getEquipmentList();
      if (res.success && res.data) {
        setAllEquipments(res.data);
      }
    } catch (error) {
      console.error('설비 목록 조회 실패:', error);
    }
  };

  const fetchCompanyEquipments = async () => {
    try {
      const res = await getCompanyEquipmentList();
      if (res.success && res.data) {
        setCompanyEquipments(res.data);
      }
    } catch (error) {
      console.error('회사 설비 목록 조회 실패:', error);
    }
  };

  const handleAssign = async () => {
    if (!selectedEquipmentId) {
      alert('설비를 선택해주세요.');
      return;
    }

    // 이미 등록된 설비인지 확인
    const isAlreadyRegistered = companyEquipments.some(
      (eq) => eq.id === selectedEquipmentId
    );

    if (isAlreadyRegistered) {
      alert('이미 등록된 설비입니다.');
      return;
    }

    try {
      setLoading(true);
      const res = await registCompanyEquipment(selectedEquipmentId);
      if (res.success) {
        setSelectedEquipmentId(null);
        await fetchAllEquipments();
        await fetchCompanyEquipments();
        alert('설비가 등록되었습니다.');
      } else {
        alert(res.message || '설비 등록에 실패했습니다.');
      }
    } catch (error: any) {
      console.error('설비 등록 실패:', error);
      alert(error.response?.data?.message || '설비 등록에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 회사에 등록되지 않은 설비만 필터링
  const availableEquipments = allEquipments.filter(
    (eq) => !companyEquipments.some((ceq) => ceq.id === eq.id)
  );

  const selectedEquipment = allEquipments.find(
    (eq) => eq.id === selectedEquipmentId
  );

  return (
    <div className="company-equipment-section">
      <div className="section-header">회사 설비 지정</div>
      <div className="assign-form">
        <div className="form-label">설비 선택</div>
        <div className="work-select-wrapper" ref={dropdownRef}>
          <button
            type="button"
            className={`work-select-trigger${isDropdownOpen ? ' open' : ''}`}
            onClick={() => setIsDropdownOpen((prev) => !prev)}
          >
            {selectedEquipment
              ? `${selectedEquipment.name} (${selectedEquipment.category})`
              : '설비를 선택하세요'}
          </button>
          {isDropdownOpen && (
            <ul className="work-select-dropdown">
              {availableEquipments.length === 0 ? (
                <li style={{ padding: '10px', textAlign: 'center', color: '#9CA3AF' }}>
                  등록 가능한 설비가 없습니다.
                </li>
              ) : (
                availableEquipments.map((equipment) => (
                  <li key={equipment.id}>
                    <button
                      type="button"
                      className={`work-select-option${
                        equipment.id === selectedEquipmentId ? ' selected' : ''
                      }`}
                      onClick={() => {
                        setSelectedEquipmentId(equipment.id);
                        setIsDropdownOpen(false);
                      }}
                    >
                      <span className="work-select-option-title">
                        {equipment.name}
                      </span>
                      <span className="work-select-option-meta">
                        {equipment.category}
                      </span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>

        <button
          className="assign-button"
          onClick={handleAssign}
          disabled={loading || !selectedEquipmentId}
        >
          {loading ? '등록 중...' : '회사에 설비 등록'}
        </button>
      </div>

      <div className="company-equipment-list">
        <div className="list-header">등록된 회사 설비</div>
        <div className="list-body">
          {companyEquipments.length === 0 ? (
            <div className="empty-message">등록된 설비가 없습니다.</div>
          ) : (
            companyEquipments.map((equipment) => (
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

export default CompanyEquipmentSection;

