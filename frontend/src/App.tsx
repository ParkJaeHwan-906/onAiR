import './App.css'
import HomeSmall from './components/Home/HomeSmall';
import HomeBig from './components/Home/HomeBig'

function App() {
  return (
    // <HomeSmall
    //   isGraph={true}
    //   numInfo={'15'}
    //   title={'오늘의 작업 수'}
    //   value={40}
    // />
    <HomeBig title='오늘의 작업 목록' icon='icons/profile.png'/>
  );
}

export default App
