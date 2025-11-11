export interface Employee {
  userAccountId: number; // 사용자 고유 ID
  companyId?: number; // 소속 회사 ID
  company?: string; // 소속 회사 이름
  name: string; // 이름
  phone: string; // 전화번호
  birth?: string; // 생년월일
  email: string; // 이메일
  part: string; // 부서명
  role?: string; // 권한 (관리자 / 사용자)
  equipmentId: number | null; // 담당 설비 ID
  equipmentName: string | null; // 담당 설비 이름
  equipmentCategoryId?: number | null; // 담당 설비 카테고리 ID
  equipmentCategoryName?: string | null; // 담당 설비 카테고리 이름
  online?: boolean; // 근무 상태 (온라인 / 오프라인)
}
