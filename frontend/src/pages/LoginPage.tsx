import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/useAuthStore";
import "../styles/LoginPage.css";

function LoginPage() {
  const navigate = useNavigate();
  const { loginUser, isAuthenticated, restoreSession } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // 새로고침 시 세션 복원
  useEffect(() => {
    restoreSession();
  }, []);

  // 로그인 후 홈으로 이동
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/home");
    }
  }, [isAuthenticated, navigate]);

  // 이메일 형식 검증 함수
  const validateEmail = (value: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");

    // 로그인 기본 검증 단계
    if (!email && !password) {
      setError("이메일과 비밀번호를 입력해주세요.");
      return;
    }

    if (!email) {
      setError("이메일을 입력해주세요.");
      return;
    }

    if (!validateEmail(email)) {
      setError("올바른 이메일 형식이 아닙니다.");
      return;
    }

    if (!password) {
      setError("비밀번호를 입력해주세요.");
      return;
    }

    // 로그인 요청
    try {
      await loginUser(email, password);
      navigate("/home");
    } catch (err: any) {
      setError(err.message || "아이디 또는 비밀번호를 확인해주세요.");
    }
  };

  return (
    <div className="login-page-wrapper">
      <form className="login-form" onSubmit={handleSubmit} noValidate>
        <div className="login-logo">
          <img src="/icons/loginlogo.png" alt="onAiR 로고" />
        </div>

        <label className="login-label">
          이메일
          <input
            className="login-input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="이메일을 입력하세요"
          />
        </label>

        <label className="login-label">
          비밀번호
          <input
            className="login-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="비밀번호를 입력하세요"
          />
        </label>

        {error && <p className="login-error">{error}</p>}

        <button className="login-submit" type="submit">
          로그인
        </button>

        <div className="login-signup-link">
          <span>아직 계정이 없으신가요?</span>
          <span onClick={() => navigate("/signup")} className="login-link">
            가입하기
          </span>
        </div>
      </form>
    </div>
  );
}

export default LoginPage;
