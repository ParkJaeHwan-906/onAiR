package ssafy.com.onair.task.service;

import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.task.dto.TaskListDto;

import java.util.List;

public interface TaskService {
    Boolean registTask(CustomUserDetails user, InsertTaskRequestDto request);
    List<TaskListDto> getTaskList(CustomUserDetails user, Long equipmentId);
    Boolean assignTaskToWorker(CustomUserDetails user);
    Boolean endTask(CustomUserDetails user);
}
