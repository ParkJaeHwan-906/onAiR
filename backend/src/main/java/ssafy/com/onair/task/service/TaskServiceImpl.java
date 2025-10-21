package ssafy.com.onair.task.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.task.dto.ReAssignTaskRequestDto;
import ssafy.com.onair.task.dto.TaskListDto;
import ssafy.com.onair.task.dto.TaskStatusChangeRequestDto;
import ssafy.com.onair.task.repository.TasksRepository;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TaskServiceImpl implements TaskService {
    private final TasksRepository tasksRepository;

    @Transactional
    @Override
    public Boolean registTask(CustomUserDetails user, InsertTaskRequestDto request) {
        return tasksRepository.insertTasks(user.getCompanyId(), request.getEquipmentId(), request.getRequest()) == 1;
    }

    @Override
    public List<TaskListDto> getTaskList(CustomUserDetails user, Long equipmentId) {
        return user.getUserInfo().getRole().equals("관리자") ? tasksRepository.getTaskListAsAdmin(user.getCompanyId(), equipmentId) :
                tasksRepository.getTaskListAsWorker(user.getCompanyId(), equipmentId);
    }

    @Transactional
    @Override
    public Boolean assignTaskToWorker(CustomUserDetails user) {
        Long assignTargetTaskId = tasksRepository.getRemainTaskId(user.getCompanyId(), user.getUserInfo().getEquipmentId())
                .orElseThrow(() -> new IllegalArgumentException("남아있는 업무가 없습니다."));
        if(tasksRepository.assignTaskToWorker(user.getUserAccountId(), assignTargetTaskId) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        return true;
    }

    @Transactional
    @Override
    public Boolean endTask(CustomUserDetails user, TaskStatusChangeRequestDto request) {
        //        TODO : 상태 확인은 나중에 추가
        if((user.getUserInfo().getRole().equals("관리자") ? tasksRepository.endTaskAsAdmin(request.getTaskId()) : tasksRepository.endTaskAsWorker(user.getUserAccountId(), request.getTaskId())) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        return true;
    }

    @Transactional
    @Override
    public Boolean cancelTask(CustomUserDetails user, TaskStatusChangeRequestDto request) {
        //        TODO : 상태 확인은 나중에 추가
        if((user.getUserInfo().getRole().equals("관리자") ? tasksRepository.cancelTaskAsAdmin(request.getTaskId()) : tasksRepository.cancelTaskAsWorker(user.getUserAccountId(), request.getTaskId())) == 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        return true;
    }

    @Override
    public Boolean reAssignTask(ReAssignTaskRequestDto request) {
        if(tasksRepository.reAssignTaskToWorker(request.getUserAccountId(), request.getTaskId()) != 1) throw new IllegalArgumentException("잘못된 요청입니다.");
        return true;
    }
}
