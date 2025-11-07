import { useEffect, useState } from "react";
import "../styles/HomePage.css";
import HomeBig from "../components/Home/HomeBig";
import HomeSmall from "../components/Home/HomeSmall";
import { getTaskList } from "../api/task";
import { getUserList } from "../api/user";
import { useUserStore } from "../store/useUserStore";
import { useSSEStore } from "../store/useSSEStore";
import { useWebRtcRequestStore } from "../store/useWebRtcRequestStore";
import type { Work } from "../types/work";

function HomePage() {
  const { myInfo } = useUserStore();
  const { eventSource } = useSSEStore();
  const { requestCount, addRequest, updateRequestStatus, calculateTodayCount } = useWebRtcRequestStore();

  const [todayTaskCount, setTodayTaskCount] = useState(0);
  const [totalEmployees, setTotalEmployees] = useState(0);
  const [onlineEmployees, setOnlineEmployees] = useState(0);
  const [completionRate, setCompletionRate] = useState(0);
  const [todayTasks, setTodayTasks] = useState<Work[]>([]);
  const [loading, setLoading] = useState(true);

  // 시간 포맷팅 함수
  const formatTime = (dateTimeString: string) => {
    if (!dateTimeString) return "-";
    const utcDate = new Date(dateTimeString);
    const kstDate = new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
    const hours = String(kstDate.getHours()).padStart(2, "0");
    const minutes = String(kstDate.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  };

  // 통계 데이터 가져오기
  const fetchStatistics = async () => {
    try {
      setLoading(true);

      // 1. 오늘의 작업 수 (할당된 작업만)
      const taskRes = await getTaskList(null, null);
      if (taskRes.success && taskRes.data) {
        const assignedTasks = taskRes.data.filter((task: Work) => task.userAccountId !== null);
        setTodayTaskCount(assignedTasks.length);
        setTodayTasks(assignedTasks);

        // 3. 작업 완료율 계산
        const completedTasks = assignedTasks.filter((task: Work) => task.action === 3).length;
        const rate = assignedTasks.length > 0 
          ? Math.round((completedTasks / assignedTasks.length) * 100) 
          : 0;
        setCompletionRate(rate);
      }

      // 2. 작업 인원 수 (전체 및 온라인)
      const userRes = await getUserList(null);
      if (userRes.success && userRes.data) {
        const employees = userRes.data;
        setTotalEmployees(employees.length);
        const onlineCount = employees.filter((emp: any) => emp.online === true).length;
        setOnlineEmployees(onlineCount);
      }
    } catch (error) {
      console.error("통계 데이터 조회 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  // SSE 이벤트 리스닝 (webrtc 요청 감지)
  useEffect(() => {
    if (!eventSource || !myInfo || myInfo.role !== "관리자") return;

    const handleSSEMessage = (event: MessageEvent) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        
        // SenderInfoDto 형태의 데이터인지 확인 (webrtc 요청)
        if (data.senderAccountId && data.name && data.role === "사용자") {
          console.log("📞 WebRTC 요청 감지:", data);
          addRequest({
            senderAccountId: data.senderAccountId,
            name: data.name,
            phone: data.phone || "",
            equipmentName: data.equipmentName || null,
          });
          calculateTodayCount();
        }
        
        // SseResponseDto 형태의 데이터인지 확인 (webrtc 응답)
        if (data.acceptConnection !== undefined && data.accessToken) {
          console.log("✅ WebRTC 응답 감지:", data);
          // senderAccountId를 찾기 위해 최근 pending 요청 확인
          // 실제로는 백엔드에서 senderAccountId를 포함해서 보내줘야 하지만,
          // 현재 구조상 가장 최근 pending 요청에 매칭
          const requests = useWebRtcRequestStore.getState().requests;
          const pendingRequest = requests
            .filter((req) => req.status === "pending")
            .sort((a, b) => new Date(b.requestTime).getTime() - new Date(a.requestTime).getTime())[0];
          
          if (pendingRequest) {
            updateRequestStatus(
              pendingRequest.senderAccountId,
              data.acceptConnection,
              data.accessToken
            );
          }
        }
      } catch (error) {
        // JSON 파싱 실패 시 무시 (다른 이벤트일 수 있음)
      }
    };

    // eventSource에 직접 리스너 추가
    if (eventSource.addEventListener) {
      eventSource.addEventListener("message", handleSSEMessage);
    } else if (eventSource.onmessage) {
      // fallback: onmessage 사용
      const originalOnMessage = eventSource.onmessage;
      eventSource.onmessage = (event: MessageEvent) => {
        if (originalOnMessage) {
          originalOnMessage(event);
        }
        handleSSEMessage(event);
      };
    }

    return () => {
      if (eventSource.removeEventListener) {
        eventSource.removeEventListener("message", handleSSEMessage);
      }
    };
  }, [eventSource, myInfo, addRequest, updateRequestStatus, calculateTodayCount]);

  // 초기 데이터 로드
  useEffect(() => {
    fetchStatistics();
    calculateTodayCount();
  }, []);

  // 작업 인원 온라인 비율 계산
  const onlinePercentage = totalEmployees > 0 
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
      numInfo: totalEmployees,
      title: "작업 인원 수",
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
      <div className="component-wrapper">
        {loading ? (
          <div>로딩 중...</div>
        ) : (
          stats.map((item, index) => (
            <HomeSmall
              key={index}
              isGraph={item.isGraph}
              numInfo={item.numInfo}
              title={item.title}
              value={item.value}
              icon={item.icon}
            />
          ))
        )}
      </div>
      <div className="component-wrapper">
        <HomeBig 
          title="오늘의 작업 목록" 
          icon="icons/check.png"
          tasks={todayTasks}
          formatTime={formatTime}
        />
        <HomeBig 
          title="요청 목록" 
          icon="icons/box.png"
          isRequestList={true}
        />
      </div>
    </div>
  );
}

export default HomePage;
