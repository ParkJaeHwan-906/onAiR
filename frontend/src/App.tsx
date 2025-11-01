import './App.css'
import WorkAdd from './components/Work/WorkAdd';
import WorkAssign from './components/Work/WorkAssign';

function App() {
  return (
    <div style={{width: '1920px', display: 'flex', flexDirection: 'column'}}>
      {/* <WorkAdd /> */}
      <WorkAssign />
    </div>
  );
}

export default App
