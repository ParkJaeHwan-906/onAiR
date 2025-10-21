package ssafy.com.onair.task.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.task.repository.TasksRepository;

@Service
@RequiredArgsConstructor
public class TaskServiceImpl implements TaskService {
    private final TasksRepository tasksRepository;

    @Override
    public Boolean registTask(CustomUserDetails user, InsertTaskRequestDto request) {
        return tasksRepository.insertTasks(user.getCompanyId(), request.getEquipmentId(), request.getRequest()) == 1;
    }
}
