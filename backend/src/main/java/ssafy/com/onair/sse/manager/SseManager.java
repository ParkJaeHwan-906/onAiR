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
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Getter
@Component
public class SseManager {
    private final ConcurrentHashMap<Long, List<UserInfoDto>> companies = new ConcurrentHashMap<>();      // companyId, List<userAccountId>
    private final ConcurrentHashMap<Long, SseEmitter> emitters = new ConcurrentHashMap<>();             // userAccountId, SseEmitter
    // 메시기 재전송을 위한 큐
    private final Map<Long, List<SseMessageDto>> pendingMessages = new ConcurrentHashMap<>();           // userAccountId, List<SseMessageDto>

    public SseEmitter connSse(CustomUserDetails user) {     // 처음 연결 요청이 들어옴
        emitters.remove(user.getUserAccountId());                       // 기존 연결이 존재한다면 제거
        SseEmitter emitter = new SseEmitter(1000L*60*60);       // 1 시간의 timeout 을 잡는다.
        // sseEmitter complete 처리
        emitter.onCompletion(() -> {
            // 재전송 로직을 위해, 삭제 처리 하지 않음
//            emitters.remove(user.getUserAccountId());
//            companies.get(user.getCompanyId()).removeIf((u) -> Objects.equals(u.getUserAccountId(), user.getUserAccountId()));
            log.info("Disconnect SSE [{}]", user.getUserInfo().getEmail());
        });
        // SseEmitter timeout 발생
        emitter.onTimeout(emitter::complete);
        // SseEmitter error 발생
        emitter.onError(throwable -> {
            log.error("UnExpected SSE Disconnect [{}]", user.getUserInfo().getEmail());
            emitter.complete();
        });

        emitters.put(user.getUserAccountId(), emitter);
        companies.computeIfAbsent(user.getCompanyId(), k -> new ArrayList<>());
        List<UserInfoDto> users = companies.get(user.getCompanyId());
        if (users.stream().noneMatch(u -> u.getUserAccountId().equals(user.getUserAccountId()))) {
            users.add(user.getUserInfo());
        }

        sendSseMessage(emitter, SseMessageDto.builder()
                .eventName("connect")
                .data("connected")
                .build());
        log.info("Connect SSE [{}]", user.getUserInfo().getEmail());

        // 재접속 한 유저인지 확인
        if (pendingMessages.containsKey(user.getUserAccountId())) {
            List<SseMessageDto> queued = pendingMessages.remove(user.getUserAccountId());
            for (SseMessageDto msg : queued) {
                sendSseMessage(emitter, msg);
            }
            log.info("Re-sent {} pending messages to [{}]", queued.size(), user.getUserInfo().getEmail());
        }

        return emitter;
    }

    public void sendSseMessage(SseEmitter emitter, SseMessageDto request) {
        log.debug("sse emitter : {}", emitter);
        log.debug("sse request : {}", request);

        try {
            emitter.send(
                    SseEmitter
                            .event()
                            .name(request.getEventName())
                            .data(request.getData())
                            .comment("flush")
            );
        } catch (IOException e) {
            // 재전송을 위해 연결이 끊긴 userAccountId 찾기
            Long disConnectedUserAccountId = null;
            for(Long userAccountId : this.emitters.keySet()) {
                if(this.emitters.get(userAccountId).equals(emitter)) {
                    disConnectedUserAccountId = userAccountId;
                    break;
                }
            }
            log.error("[SSE] Failed Send Message : [{}]", request);
            emitter.complete();
            retrySendMessage(disConnectedUserAccountId, request);
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
    public void sendRequestAdminToWorker(Long targetWorkerId, Object data, String eventName) {
        sendSseMessage(emitters.get(targetWorkerId),
                SseMessageDto.builder()
                        .eventName(eventName)  // 이벤트 명 지정해주세여
                        .data(data)     // 여기에 뭔가 필요한 데이터가 있다면 넣으세여
                        .build());
    }

    /**
     * @param companyId
     * : 요청한 작업자의 회사 id
     */
    public void sendRequestWorkerToAdmin(Long companyId, Object data, String eventName) {
        UserInfoDto admin = companies.get(companyId).stream().filter((user) -> user.getRole().equals("관리자"))
                .findFirst().orElseThrow(() -> new IllegalArgumentException("관리자가 부재중입니다."));

        log.debug("receiver(admin) info : {}", admin);

        sendSseMessage(emitters.get(admin.getUserAccountId()),
                SseMessageDto.builder()
                        .eventName(eventName)
                        .data(data)
                        .build());
    }

    public void sendRtcCancelEvent(Long senderAccountId, Long receiverAccountId) {
        SseEmitter sendEmitter = findTargerSseEmitter(senderAccountId);
        SseEmitter receiveEmitter = findTargerSseEmitter(receiverAccountId);

        sendSseMessage(sendEmitter, SseMessageDto.builder()
                .eventName("rtcCanceled")
                .data(Map.of(
                        "requestUserAccountId", receiverAccountId
                ))
                .build());

        sendSseMessage(receiveEmitter, SseMessageDto.builder()
                .eventName("rtcCanceled")
                .data(Map.of(
                        "requestUserAccountId", senderAccountId
                ))
                .build());
    }

    private SseEmitter findTargerSseEmitter(Long targetAccountId) {
        return emitters.get(targetAccountId);
    }

    /**
     * SSE 연결 유지를 위해 모든 emitter에게 10초마다 heart beat 이벤트 전달
     *
     * 전달하지 못한 사용자 -> 연결이 끊긴 사용자 -> 제거 로직 추가
     */
    @Scheduled(fixedRate = 1000 * 10)
    public void sendHeartBeat() {
        List<Long> disconnected = new ArrayList<>();

        emitters.forEach((accountId, emitter) -> {
            try {
                sendSseMessage(emitter, SseMessageDto.builder()
                        .eventName("heart beat")
                        .data("timestamp: " + LocalDateTime.now())
                        .build());
                log.debug("send heartbeat to {}", accountId);
            } catch (Exception e) {
                log.warn("Detected disconnected emitter: {}", accountId);
                disconnected.add(accountId);
            }
        });

        // 한번에 사용자 제거
        for (Long accountId : disconnected) {
            emitters.remove(accountId);
            companies.forEach((companyId, users) ->
                    users.removeIf(u -> u.getUserAccountId().equals(accountId))
            );
        }
    }

    // 재전송 로직 추가
    private void retrySendMessage(Long userAccountId, SseMessageDto request) {
        if(userAccountId == null) {
            log.error("Cannot Found User");
            return;
        }
        log.info("Message Stored : {}", request);
        pendingMessages.computeIfAbsent(userAccountId, k -> new ArrayList<>()).add(request);
    }

    // 버려지는 메시지 정리
    @Scheduled(fixedRate = 1000 * 60 * 5)
    private void gcMessage() {
        List<Long> deleteTargetUserAccountId = new ArrayList<>();
        for(Long userAccountId : this.pendingMessages.keySet()) {
            if(!this.emitters.containsKey(userAccountId)) deleteTargetUserAccountId.add(userAccountId);
        }

        for(Long userAccountId : deleteTargetUserAccountId) this.pendingMessages.remove(userAccountId);
    }
}