import '../../styles/WorkList.css';

type WorkListProps = {
  userName: string;
  solution: string;
  action: number;
  actionStatus: string;
  lastUpdateTime: string;
}

const backColors = ['#F4C0C0', '#F9E9B5', '#B5BFE0', '#B6E7C8']
const fontColors = ['#EF4444', '#FFBC11', '#1E40AF', '#22C55E']

function WorkList({userName, solution, action, actionStatus, lastUpdateTime}: WorkListProps) {
  const backColor = backColors[action]
  const fontColor = fontColors[action]

  return (
    <>
      <div className='work-wrapper'>
        <div className='first'>
          {userName}
        </div>
        <div className='second'>
          {solution}
        </div>
        <div className='third'>
          <div className='action-wrapper' style={{backgroundColor: backColor, color: fontColor }}>
            {actionStatus}
          </div>
        </div>
        <div className='fourth'>
          {lastUpdateTime}
        </div>
      </div>
    </>
  );
}

export default WorkList