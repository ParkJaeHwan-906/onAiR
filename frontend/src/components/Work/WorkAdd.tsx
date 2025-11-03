import '../../styles/WorkAdd.css'

function WorkAdd () {
  return (
    <div className='work-add'>
      <div className='work-add-header'>작업 추가</div>
      <div className='request-header'>작업 내용</div>
      <textarea
        className='request-body'
        placeholder='작업 내용을 입력하세요'
      ></textarea>
      <button className='add-button'>
        작업 등록
      </button>
    </div>
  );
}

export default WorkAdd;