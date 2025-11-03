import '../styles/WorkPage.css'
import WorkBig from '../components/Work/WorkBig'
import WorkAdd from '../components/Work/WorkAdd'
import WorkAssign from '../components/Work/WorkAssign'

function WorkPage () {
  return (
    <div className='work-page-wrapper'>
      <WorkBig />
      <div className='work-page-left'>
        <WorkAdd />
        <WorkAssign />
      </div>
    </div>
  );
}

export default WorkPage;