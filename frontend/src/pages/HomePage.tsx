import { useEffect, useState } from "react";
import "../styles/HomePage.css";
import HomeBig from "../components/Home/HomeBig";
import HomeSmall from "../components/Home/HomeSmall";
import { getTaskList } from "../api/task";
import { getUserList } from "../api/user";
import { useUserStore } from "../store/useUserStore";
import { useWebRtcRequestStore } from "../store/useWebRtcRequestStore";
import type { Work } from "../types/work";

function HomePage() {
  const { myInfo } = useUserStore();
  const { requestCount, calculateTodayCount } = useWebRtcRequestStore();

  const [todayTaskCount, setTodayTaskCount] = useState(0);
  const [totalEmployees, setTotalEmployees] = useState(0);
  const [onlineEmployees, setOnlineEmployees] = useState(0);
  const [completionRate, setCompletionRate] = useState(0);
  const [todayTasks, setTodayTasks] = useState<Work[]>([]);
  // const [loading, setLoading] = useState(false);
  const [, setLoading] = useState(false);

  const formatTime = (dateTimeString: string) => {
    if (!dateTimeString) return "-";
    const utcDate = new Date(dateTimeString);
    const kstDate = new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
    const hours = String(kstDate.getHours()).padStart(2, "0");
    const minutes = String(kstDate.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  };

  const buildTaskSummary = (tasks: Work[]) => {
    setTodayTasks(tasks);
    setTodayTaskCount(tasks.length);

    const completedTasks = tasks.filter((task) => task.action === 3).length;
    const rate =
      tasks.length > 0 ? Math.round((completedTasks / tasks.length) * 100) : 0;
    setCompletionRate(rate);
  };

  const fetchStatistics = async () => {
    try {
      setLoading(true);

      const taskRes = await getTaskList(null, null);
      if (taskRes.success && taskRes.data) {
        let filteredTasks: Work[] = taskRes.data;

        if (myInfo) {
          filteredTasks =
            myInfo.role === "관리자"
              ? filteredTasks.filter((task) => task.userAccountId !== null)
              : filteredTasks.filter(
                  (task) => task.userAccountId === myInfo.userAccountId
                );
        }

        buildTaskSummary(filteredTasks);
      }

      const userRes = await getUserList(null);
      if (userRes.success && userRes.data) {
        const employees = userRes.data;
        setTotalEmployees(employees.length);
        const onlineCount = employees.filter(
          (emp: any) => emp.online === true
        ).length;
        setOnlineEmployees(onlineCount);
      }
    } catch (error) {
      console.error("통계 데이터 조회 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatistics();
    calculateTodayCount();
  }, []);

  useEffect(() => {
    if (!myInfo) return;
    fetchStatistics();
  }, [myInfo]);

  // 작업 인원 온라인 비율 계산
  const onlinePercentage =
    totalEmployees > 0
      ? Math.round((onlineEmployees / totalEmployees) * 100)
      : 0;

  const stats = [
    {
      isGraph: false,
      numInfo: todayTaskCount,
      title: "오늘의 작업 수",
      value: todayTaskCount,
      icon: "icons/list.png",
    },
    {
      isGraph: true,
      numInfo: onlineEmployees,
      totalInfo: totalEmployees,
      title: "작업 인원 수", // 변경: "전체 작업 인원" → "작업 인원 수"
      value: onlinePercentage,
      icon: "icons/profile.png",
    },
    {
      isGraph: true,
      numInfo: completionRate,
      title: "작업 완료율",
      value: completionRate,
      icon: "icons/check.png",
    },
    {
      isGraph: false,
      numInfo: requestCount,
      title: "신규 요청",
      value: requestCount,
      icon: "icons/box.png",
    },
  ];

  return (
    <div className="home-wrapper">
      <div className="home-row home-small-row">
        {stats.map((item, index) => (
          <HomeSmall
            key={index}
            isGraph={item.isGraph}
            numInfo={item.numInfo}
            totalInfo={item.totalInfo}
            title={item.title}
            value={item.value}
            icon={item.icon}
          />
        ))}
      </div>
      <div className="home-row home-big-row">
        <HomeBig
          title="오늘의 작업 목록"
          icon="icons/check.png"
          tasks={todayTasks}
          formatTime={formatTime}
        />
        <HomeBig title="요청 목록" icon="icons/box.png" isRequestList={true} />
      </div>
    </div>
  );
}

export default HomePage;
