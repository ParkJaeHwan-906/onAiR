import '../../styles/HomeBig.css';
import '../../styles/WorkList.css';
import { useWebRtcRequestStore } from '../../store/useWebRtcRequestStore';
import type { Work } from '../../types/work';

const backColors = ["#F4C0C0", "#F9E9B5", "#B5BFE0", "#B6E7C8"];
const fontColors = ["#EF4444", "#FFBC11", "#1E40AF", "#22C55E"];

type HomeBigProps = {
  title: string;
  icon: string;
  tasks?: Work[];
  formatTime?: (time: string) => string;
  isRequestList?: boolean;
}

function HomeBig({ title, icon, tasks = [], formatTime, isRequestList = false }: HomeBigProps) {
  const { getTodayRequests } = useWebRtcRequestStore();
  const requests = isRequestList ? getTodayRequests() : [];

  // action 값을 actionStatus 문자열로 변환
  const getActionStatus = (action: number): string => {
    switch (action) {
      case 0:
        return "취소됨";
      case 1:
        return "대기중";
      case 2:
        return "작업중";
      case 3:
        return "완료";
      default:
        return "대기중";
    }
  };

  // 요청 상태를 한글로 변환
  const getRequestStatus = (status: string): string => {
    switch (status) {
      case "pending":
        return "대기중";
      case "accepted":
        return "수락됨";
      case "rejected":
        return "거절됨";
      default:
        return "대기중";
    }
  };

  // 요청 상태 색상
  const getRequestStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return { bg: "#F9E9B5", color: "#FFBC11" };
      case "accepted":
        return { bg: "#B6E7C8", color: "#22C55E" };
      case "rejected":
        return { bg: "#F4C0C0", color: "#EF4444" };
      default:
        return { bg: "#F9E9B5", color: "#FFBC11" };
    }
  };

  // 요청 시간 포맷팅
  const formatRequestTime = (timeString: string) => {
    if (!timeString) return "-";
    const date = new Date(timeString);
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  };

  return (
    <div className="home-big">
      <div className='home-big-header'>
        <span className='title'>{title}</span>
        <img src={icon} alt="list" />
      </div>
      <div className="home-table">
        <div className='list-header'>
          {isRequestList ? (
            <>
              <div className='col-worker'>작업자</div>
              <div className='col-content'>설비</div>
              <div className='col-status'>상태</div>
              <div className='col-time'>요청시간</div>
            </>
          ) : (
            <>
              <div className='col-worker'>작업자</div>
              <div className='col-content'>작업 내용</div>
              <div className='col-status'>상태</div>
              <div className='col-time'>시간</div>
            </>
          )}
        </div>
        <div className='list-body'>
        {isRequestList ? (
          requests.length === 0 ? (
            <p className="no-data">오늘의 요청이 없습니다.</p>
          ) : (
            requests.map((request) => {
              const statusColor = getRequestStatusColor(request.status);
              return (
                <div key={request.id} className="work-row">
                  <div className="col-worker">{request.name}</div>
                  <div className="col-content">{request.equipmentName || "-"}</div>
                  <div className="col-status">
                    <span
                      className="status-badge"
                      style={{ backgroundColor: statusColor.bg, color: statusColor.color }}
                    >
                      {getRequestStatus(request.status)}
                    </span>
                  </div>
                  <div className="col-time">{formatRequestTime(request.requestTime)}</div>
                </div>
              );
            })
          )
        ) : (
          tasks.length === 0 ? (
            <p className="no-data">오늘의 작업이 없습니다.</p>
          ) : (
            tasks.map((task) => {
              const actionStatus = task.actionStatus && task.actionStatus.trim()
                ? task.actionStatus
                : getActionStatus(task.action);
              const formattedTime = formatTime ? formatTime(task.lastUpdateTime) : task.lastUpdateTime;
              
              return (
                <div key={task.id} className="work-row">
                  <div className="col-worker">{task.userName || "미할당"}</div>
                  <div className="col-content">{task.request}</div>
                  <div className="col-status">
                    <span
                      className="status-badge"
                      style={{ 
                        backgroundColor: backColors[task.action >= 0 && task.action < backColors.length ? task.action : 0], 
                        color: fontColors[task.action >= 0 && task.action < fontColors.length ? task.action : 0] 
                      }}
                    >
                      {actionStatus}
                    </span>
                  </div>
                  <div className="col-time">{formattedTime}</div>
                </div>
              );
            })
          )
        )}
        </div>
      </div>
    </div>
  );
};

export default HomeBig;
