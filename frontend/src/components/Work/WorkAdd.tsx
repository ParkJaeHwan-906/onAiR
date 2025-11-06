import { useState } from "react";
import "../../styles/WorkAdd.css";

interface WorkAddProps {
  title?: string; // 상단 제목 (기본값: '작업 추가')
  label?: string; // textarea 라벨 (기본값: '작업 내용')
  placeholder?: string; // placeholder 텍스트
  buttonText?: string; // 버튼 텍스트
  onSubmit?: (text: string) => void; // 버튼 클릭 시 실행 함수
}

function WorkAdd({
  title = "작업 추가",
  label = "작업 내용",
  placeholder = "작업 내용을 입력하세요",
  buttonText = "작업 등록",
  onSubmit,
}: WorkAddProps) {
  const [text, setText] = useState("");

  const handleClick = () => {
    if (!text.trim()) {
      alert("내용을 입력해주세요.");
      return;
    }
    if (onSubmit) onSubmit(text);
    setText("");
  };

  return (
    <div className="work-add">
      <div className="work-add-header">{title}</div>
      <div className="request-header">{label}</div>
      <textarea
        className="request-body"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
      ></textarea>
      <button className="add-button" onClick={handleClick}>
        {buttonText}
      </button>
    </div>
  );
}

export default WorkAdd;
