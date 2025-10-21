package ssafy.com.onair.task.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface TasksRepository {
    @Insert("""
            INSERT INTO `tasks`(`company_id`, `equipment_id`, `request`) VALUES
            (#{companyId}, #{equipmentId}, #{request});
            """)
    Integer insertTasks(Long companyId, Long equipmentId, String request);
}
