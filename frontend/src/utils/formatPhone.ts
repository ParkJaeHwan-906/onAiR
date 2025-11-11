// 전화번호 포맷팅 함수
export const formatPhone = (phone: string) => {
  if (!phone) return "";
  // 숫자만 남기기
  const digits = phone.replace(/\D/g, "");
  if (digits.length === 11) {
    // 01012341234 → 010-1234-1234
    return digits.replace(/(\d{3})(\d{4})(\d{4})/, "$1-$2-$3");
  } else if (digits.length === 10) {
    // 02로 시작하는 경우 대비 (서울 번호 등)
    return digits.replace(/(\d{2,3})(\d{3,4})(\d{4})/, "$1-$2-$3");
  }
  return phone; // 포맷 안 맞으면 그대로 출력
};
