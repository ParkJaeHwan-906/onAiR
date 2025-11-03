import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../styles/LoginPage.css'

function LoginPage () {
  const navigate = useNavigate()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    // 로그인 API 연동
    navigate('/home')
  }

  return (
    <div className='login-page-wrapper'>
      <form className='login-form' onSubmit={handleSubmit}>
        <div className='login-logo'>
          <img src="/icons/loginlogo.png" alt="onAiR 로고" />
        </div>
        <label className='login-label'>
          아이디
          <input
            className='login-input'
            type='text'
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder='아이디를 입력하세요'
            required
          />
        </label>
        <label className='login-label'>
          비밀번호
          <input
            className='login-input'
            type='password'
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder='비밀번호를 입력하세요'
            required
          />
        </label>
        <button className='login-submit' type='submit'>로그인</button>
      </form>
    </div>
  )
}

export default LoginPage
