import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { signup, checkEmail, checkPassword } from "../api/auth";
import "../styles/SignupPage.css";

function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    birth: "",
    phone: "",
    companyName: "",
    part: "",
    email: "",
    password: "",
    passwordConfirm: "",
  });

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [emailChecked, setEmailChecked] = useState(false);

  const validateEmail = (value: string) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm({ ...form, [name]: value });
    setError("");
    setSuccess("");
  };

  // 이메일 중복 확인
  const checkEmailDuplicate = async () => {
    // 매번 누를 때마다 이전 메시지 초기화
    setError("");
    setSuccess("");

    if (!form.email) return setError("이메일을 입력해주세요.");
    if (!validateEmail(form.email))
      return setError("올바른 이메일 형식이 아닙니다.");

    try {
      const res = await checkEmail(form.email);

      if (res.success) {
        setSuccess(res.message);
        setEmailChecked(true);
      } else {
        setError(res.message);
        setEmailChecked(false);
      }
    } catch {
      setError("이메일 중복 확인 중 오류가 발생했습니다.");
    }
  };

  // 비밀번호 유효성 검사
  const checkPasswordValid = async () => {
    if (!form.password) return;

    try {
      const res = await checkPassword(form.password);
      if (!res.success) {
        setError(res.message);
        setError("");
      } else {
        setError(res.message);
        setSuccess("");
      }
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        console.log("비밀번호 검증 에러:", error.response?.data);
        const msg =
          error.response?.data?.message ||
          "비밀번호 검증 중 오류가 발생했습니다.";
        setError(msg);
      } else {
        setError("비밀번호 검증 중 알 수 없는 오류가 발생했습니다.");
      }
      setSuccess("");
    }
  };

  // 회원가입 요청
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (
      !form.email ||
      !form.password ||
      !form.name ||
      !form.birth ||
      !form.phone
    ) {
      setError("모든 필수 항목을 입력해주세요.");
      return;
    }

    if (!validateEmail(form.email)) {
      setError("올바른 이메일 형식이 아닙니다.");
      return;
    }

    if (!emailChecked) {
      setError("이메일 중복 확인을 먼저 해주세요.");
      return;
    }

    if (form.password !== form.passwordConfirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }

    try {
      const pwRes = await checkPassword(form.password);
      if (!pwRes.success) {
        setError(pwRes.message);
        return;
      }
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        const msg =
          error.response?.data?.message ||
          "비밀번호 검증 중 오류가 발생했습니다.";
        setError(msg);
      } else {
        setError("비밀번호 검증 중 알 수 없는 오류가 발생했습니다.");
      }
      return;
    }

    const signupData = {
      name: form.name,
      birth: form.birth,
      phone: form.phone,
      companyName: form.companyName || "",
      part: form.part,
      email: form.email,
      password: form.password,
    };

    try {
      const res = await signup(signupData);
      if (res.success) {
        setSuccess(res.message);
        setTimeout(() => navigate("/"), 2000);
      } else {
        setError(res.message);
      }
    } catch (error: any) {
      const msg = error.response?.data?.message;
      setError(msg);
    }
  };

  return (
    <div className="signup-page-wrapper">
      <form className="signup-form" onSubmit={handleSubmit} noValidate>
        <div className="signup-logo">
          <img src="/icons/loginlogo.png" alt="onAiR 로고" />
        </div>

        {/* 이메일 */}
        <label className="signup-label">
          이메일
          <div className="signup-email-wrap">
            <input
              name="email"
              className="signup-input"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="이메일을 입력하세요"
            />
            <button
              type="button"
              className="signup-submit-redundancy"
              onClick={checkEmailDuplicate}
            >
              중복확인
            </button>
          </div>
        </label>

        {/* 비밀번호 */}
        <label className="signup-label">
          비밀번호
          <input
            name="password"
            className="signup-input"
            type="password"
            value={form.password}
            onChange={handleChange}
            onBlur={checkPasswordValid}
            placeholder="비밀번호를 입력하세요"
          />
        </label>

        {/* 비밀번호 확인 */}
        <label className="signup-label">
          비밀번호 확인
          <input
            name="passwordConfirm"
            className="signup-input"
            type="password"
            value={form.passwordConfirm}
            onChange={handleChange}
            placeholder="비밀번호를 다시 입력하세요"
          />
        </label>

        {/* 이름 */}
        <label className="signup-label">
          이름
          <input
            name="name"
            className="signup-input"
            value={form.name}
            onChange={handleChange}
            placeholder="이름을 입력하세요"
          />
        </label>

        {/* 생년월일 */}
        <label className="signup-label">
          생년월일
          <input
            name="birth"
            className="signup-input"
            value={form.birth}
            onChange={handleChange}
            placeholder="YYYY-MM-DD"
          />
        </label>

        {/* 전화번호 */}
        <label className="signup-label">
          전화번호
          <input
            name="phone"
            className="signup-input"
            value={form.phone}
            onChange={handleChange}
            placeholder="010-0000-0000"
          />
        </label>

        {/* 회사명 */}
        <label className="signup-label">
          회사명 (관리자일 경우)
          <input
            name="companyName"
            className="signup-input"
            value={form.companyName}
            onChange={handleChange}
            placeholder="회사명을 입력하세요 (선택)"
          />
        </label>

        {/* 부서명 */}
        <label className="signup-label">
          부서명
          <input
            name="part"
            className="signup-input"
            value={form.part}
            onChange={handleChange}
            placeholder="부서를 입력하세요 (선택)"
          />
        </label>

        {/* 에러 / 성공 메시지 */}
        {error && <p className="signup-error">{error}</p>}
        {success && <p className="signup-success">{success}</p>}

        {/* 버튼 */}
        <button className="signup-submit" type="submit">
          회원가입
        </button>
      </form>
    </div>
  );
}

export default SignupPage;
