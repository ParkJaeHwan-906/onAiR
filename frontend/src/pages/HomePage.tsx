import "../styles/HomePage.css";
import HomeBig from "../components/Home/HomeBig";
import HomeSmall from "../components/Home/HomeSmall";

const dummysmall = [
  {
    isGraph: false,
    numInfo: 3,
    title: "오늘의 작업 수",
    value: 45,
    icon: "icons/list.png",
  },
  {
    isGraph: true,
    numInfo: 10,
    title: "작업 인원 수",
    value: 45,
    icon: "icons/profile.png",
  },
  {
    isGraph: true,
    numInfo: 5,
    title: "작업 완료율",
    value: 70,
    icon: "icons/check.png",
  },
  {
    isGraph: false,
    numInfo: 5,
    title: "신규 요청",
    value: 45,
    icon: "icons/box.png",
  },
];

function HomePage() {
  return (
    <div className="home-wrapper">
      <div className="component-wrapper">
        {dummysmall.map((item) => (
          <HomeSmall
            isGraph={item.isGraph}
            numInfo={item.numInfo}
            title={item.title}
            value={item.value}
            icon={item.icon}
          />
        ))}
      </div>
      <div className="component-wrapper">
        <HomeBig title="오늘의 작업 목록" icon="icons/check.png" />
        <HomeBig title="요청 목록" icon="icons/check.png" />
      </div>
    </div>
  );
}

export default HomePage;
