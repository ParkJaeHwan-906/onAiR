package ssafy.com.onair.sse.manager;

import lombok.Getter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.sse.dto.SseMessageDto;
import ssafy.com.onair.sse.dto.TaskAssignMessageDto;
import ssafy.com.onair.sse.dto.TaskStatusChangeDto;
import ssafy.com.onair.user.dto.UserInfoDto;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Getter
@Component
public class SseManager {
    private final ConcurrentHashMap<Long, List<UserInfoDto>> companies = new ConcurrentHashMap<>();      // companyId, List<userAccountId>
    private final ConcurrentHashMap<Long, SseEmitter> emitters = new ConcurrentHashMap<>();             // userAccountId, SseEmitter

    public SseEmitter connSse(CustomUserDetails user) {     // 처음 연결 요청이 들어옴
        emitters.remove(user.getUserAccountId());                       // 기존 연결이 존재한다면 제거
        SseEmitter emitter = new SseEmitter(1000L*60*60);       // 1 시간의 timeout 을 잡는다.
        // sseEmitter complete 처리
        emitter.onCompletion(() -> {
            emitters.remove(user.getUserAccountId());
            companies.get(user.getCompanyId()).removeIf((u) -> Objects.equals(u.getUserAccountId(), user.getUserAccountId()));
            log.info("Disconnect SSE [{}]", user.getUserInfo().getEmail());
        });
        // SseEmitter timeout 발생
        emitter.onTimeout(emitter::complete);
        // SseEmitter error 발생
        emitter.onError(throwable -> emitter.complete());

        emitters.put(user.getUserAccountId(), emitter);
        companies.computeIfAbsent(user.getCompanyId(), (companyId) -> new ArrayList<>());
        companies.get(user.getCompanyId()).add(user.getUserInfo());
        sendSseMessage(emitter, SseMessageDto.builder()
                .eventName("connect")
                .data("connected")
                .build());
        log.info("Connect SSE [{}]", user.getUserInfo().getEmail());
        return emitter;
    }

    public void sendSseMessage(SseEmitter emitter, SseMessageDto request) {
        log.debug("sse emitter : {}", emitter);

        try {
            emitter.send(
                    SseEmitter
                            .event()
                            .name(request.getEventName())
                            .data(request.getData())
            );
        } catch (IOException e) {
            throw new IllegalArgumentException("SSE 전송에 실패했습니다.");
        }
    }

    public void taskAssign(Long companyId, Long equipmentId, TaskAssignMessageDto data) {
        companies.get(companyId).forEach((user) -> {
            if(user.getRole().equals("관리자") || user.getEquipmentId().equals(equipmentId)) {
                sendSseMessage(emitters.get(user.getUserAccountId()),
                        SseMessageDto.builder()
                                .eventName("taskAssign")
                                .data(data)
                                .build());
            }
        });
    }

    public void taskEnd(Long companyId, Long equipmentId, TaskStatusChangeDto data) {
        companies.get(companyId).forEach((user) -> {
            if(user.getRole().equals("관리자") || user.getEquipmentId().equals(equipmentId)) {
                sendSseMessage(emitters.get(user.getUserAccountId()),
                        SseMessageDto.builder()
                                .eventName("taskEnd")
                                .data(data)
                                .build());
            }
        });
    }

    public void taskCancel(Long companyId, Long equipmentId, TaskStatusChangeDto data) {
        companies.get(companyId).forEach((user) -> {
            if(user.getRole().equals("관리자") || user.getEquipmentId().equals(equipmentId)) {
                sendSseMessage(emitters.get(user.getUserAccountId()),
                        SseMessageDto.builder()
                                .eventName("taskCancel")
                                .data(data)
                                .build());
            }
        });
    }

    /**
     * @param targetWorkerId
     * : 연결하고자하는 작업자 id
     */
    public void sendRequestAdminToWorker(Long targetWorkerId, Object data) {
        sendSseMessage(emitters.get(targetWorkerId),
                SseMessageDto.builder()
                        .eventName("")  // 이벤트 명 지정해주세여
                        .data(data)     // 여기에 뭔가 필요한 데이터가 있다면 넣으세여
                        .build());
    }

    /**
     * @param companyId
     * : 요청한 작업자의 회사 id
     */
    public void sendRequestWorkerToAdmin(Long companyId, Object data) {
        UserInfoDto admin = companies.get(companyId).stream().filter((user) -> user.getRole().equals("관리자"))
                .findFirst().orElseThrow(() -> new IllegalArgumentException("관리자가 부재중입니다."));

        log.debug("receiver(admin) info : {}", admin);

        sendSseMessage(emitters.get(admin.getUserAccountId()),
                SseMessageDto.builder()
                        .eventName("")  // 이벤트 명 지정해주세여
                        .data(data)     // 여기에 뭔가 필요한 데이터가 있다면 넣으세여
                        .build());
    }

    /**
     * SSE 연결 유지를 위해 모든 emitter에게 30초마다 heart beat 이벤트 전달
     */
    @Scheduled(fixedRate = 30 * 1000)
    public void sendHeartBeat(){
        this.emitters.forEach((accountId, emitter) -> {
            sendSseMessage(emitter, SseMessageDto.builder()
                    .eventName("heart beat")
                    .data(null)
                    .build());
            log.debug("send heartbeat to {}", accountId);
        });
    }
}