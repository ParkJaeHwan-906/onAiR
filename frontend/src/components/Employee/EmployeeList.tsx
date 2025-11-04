import '../../styles/EmployeeList.css'

type EmployeeListProps = {
  name: string;
  phone: string;
  part: string;
  email: string;
  online: boolean;
  onSelect: () => void;
}

const backColors = ['#F4C0C0', '#B6E7C8']
const fontColors = ['#EF4444', '#22C55E']

function EmployeeList ({name, phone, part, email, online, onSelect}: EmployeeListProps) {
  const backColor = online ? backColors[1] : backColors[0]
  const fontColor = online ? fontColors[1] : fontColors[0]

  return (
    <>
      <div className='employee-wrapper'>
        <div className='first'>
          {name}
        </div>
        <div className='second'>
          {part}
        </div>
        <div className='third'>
          <div className='online-wrapper' style={{backgroundColor: backColor, color: fontColor }}>
            {online ? '온라인' : '오프라인'}
          </div>
        </div>
        <div className='fourth'>
          {email}
        </div>
        <div className='fifth'>
          {phone}
        </div>
        <button type="button" onClick={onSelect}>
          보기
        </button>
      </div>
    </>
  );
}

export default EmployeeList
