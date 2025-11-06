package ssafy.com.onair.task.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.sse.dto.TaskAssignMessageDto;
import ssafy.com.onair.sse.dto.TaskStatusChangeDto;
import ssafy.com.onair.sse.manager.SseManager;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.task.dto.ReAssignTaskRequestDto;
import ssafy.com.onair.task.dto.TaskListDto;
import ssafy.com.onair.task.dto.TaskStatusChangeRequestDto;
import ssafy.com.onair.task.repository.TasksRepository;
import ssafy.com.onair.user.repository.UsersRepository;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TaskServiceImpl implements TaskService {
    private final UsersRepository usersRepository;
    private final TasksRepository tasksRepository;
    private final SseManager sseManager;

    @Transactional
    @Override
    public Boolean registTask(CustomUserDetails user, InsertTaskRequestDto request) {
        return tasksRepository.insertTasks(user.getCompanyId(), request.getEquipmentId(), request.getRequest()) == 1;
    }

    @Override
    public List<TaskListDto> getTaskList(CustomUserDetails user, Long equipmentId, Integer action) {
        return user.getUserInfo().getRole().equals("관리자") ? tasksRepository.getTaskListAsAdmin(user.getCompanyId(), equipmentId, action) :
                tasksRepository.getTaskListAsWorker(user.getCompanyId(), user.getUserInfo().getEquipmentId(), user.getUserAccountId(), action);
    }

    @Transactional
    @Override
    public Boolean assignTaskToWorker(CustomUserDetails user) {
        Long assignTargetTaskId = tasksRepository.getRemainTaskId(user.getCompanyId(), user.getUserInfo().getEquipmentId())
                .orElseThrow(() -> new IllegalArgumentException("남아있는 업무가 없습니다."));
        if(tasksRepository.assignTaskToWorker(user.getUserAccountId(), assignTargetTaskId) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        sseManager.taskAssign(user.getCompanyId(), user.getUserInfo().getEquipmentId(), mkTaskAssignMessage(assignTargetTaskId, user.getUserAccountId(), user.getUsername()));
        return true;
    }

    private TaskAssignMessageDto mkTaskAssignMessage(Long taskId, Long userAccountId, String userName) {
        return TaskAssignMessageDto.builder()
                .assignedTaskId(taskId)
                .assignedUserAccountId(userAccountId)
                .assignedUserName(userName)
                .build();
    }

    @Transactional
    @Override
    public Boolean endTask(CustomUserDetails user, TaskStatusChangeRequestDto request) {
        //        TODO : 상태 확인은 나중에 추가
        if((user.getUserInfo().getRole().equals("관리자") ? tasksRepository.endTaskAsAdmin(request.getTaskId(), request.getSolution()) : tasksRepository.endTaskAsWorker(user.getUserAccountId(), request.getTaskId(), request.getSolution())) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        sseManager.taskEnd(user.getCompanyId(), user.getUserInfo().getEquipmentId(), mkTaskStatusChange(request.getTaskId()));
        return true;
    }

    @Transactional
    @Override
    public Boolean cancelTask(CustomUserDetails user, TaskStatusChangeRequestDto request) {
        //        TODO : 상태 확인은 나중에 추가
        if((user.getUserInfo().getRole().equals("관리자") ? tasksRepository.cancelTaskAsAdmin(request.getTaskId()) : tasksRepository.cancelTaskAsWorker(user.getUserAccountId(), request.getTaskId())) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        sseManager.taskCancel(user.getCompanyId(), user.getUserInfo().getEquipmentId(), mkTaskStatusChange(request.getTaskId()));
        return true;
    }

    private TaskStatusChangeDto mkTaskStatusChange(Long taskId) {
        return TaskStatusChangeDto.builder()
                .taskId(taskId)
                .build();
    }

    @Transactional
    @Override
    public Boolean reAssignTask(CustomUserDetails user, ReAssignTaskRequestDto request) {
        if(tasksRepository.assignTaskToWorker(request.getUserAccountId(), request.getTaskId()) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        sseManager.taskAssign(user.getCompanyId(),
                tasksRepository.selectEquipmentIdById(request.getTaskId())
                        .orElseThrow(() -> new IllegalArgumentException("잘못된 요청입니다.")),
                mkTaskAssignMessage(request.getTaskId(), request.getUserAccountId(),
                        usersRepository.selectUserNameByUserAccountId(request.getUserAccountId())
                                .orElseThrow(() -> new IllegalArgumentException("잘못된 요청입니다."))));
        return true;
    }
}
