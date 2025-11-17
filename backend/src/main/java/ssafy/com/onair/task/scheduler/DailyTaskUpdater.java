package ssafy.com.onair.task.scheduler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import ssafy.com.onair.task.repository.TasksRepository;

@Slf4j
@Component
@RequiredArgsConstructor
public class DailyTaskUpdater {

    private final TasksRepository tasksRepository;

    // 매일 00:00:10 실행
    @Scheduled(cron = "10 0 0 * * *")
    public void updateTodayTasks() {
        Integer updatedTasks = tasksRepository.updateTodayTasks();
        log.info("{} Tasks Updated", updatedTasks);
    }
}
