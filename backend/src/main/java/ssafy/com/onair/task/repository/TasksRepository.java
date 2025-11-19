package ssafy.com.onair.task.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import ssafy.com.onair.task.dto.TaskListDto;

import java.util.List;
import java.util.Optional;

@Mapper
public interface TasksRepository {
    @Insert("""
            INSERT INTO `tasks`(`company_id`, `equipment_id`, `request`) VALUES
            (#{companyId}, #{equipmentId}, #{request});
            """)
    Integer insertTasks(Long companyId, Long equipmentId, String request);

    @Select("""
            <script>
            SELECT
            t.id AS 'id',
            t.equipment_id AS 'equipmentId',
            e.`name` AS 'equipmentName',
            t.`request` AS 'request',
            t.user_account_id AS 'userAccountId',
            u.`name` AS 'userName',
            t.`action` AS 'action',
            t.`solution` AS 'solution',
            t.updated_at AS 'lastUpdateTime'
            FROM `tasks` t
            JOIN `equipments` e ON e.id = t.equipment_id
            LEFT JOIN `user_accounts` ua ON ua.id = t.user_account_id
            LEFT JOIN `users` u ON u.id = ua.user_id
            WHERE t.company_id = #{companyId}
            AND DATE_FORMAT(t.created_at, "%Y-%m-%d") = DATE_FORMAT(NOW(), "%Y-%m-%d")
            <if test="equipmentId != null">
                AND t.equipment_id = #{equipmentId}
            </if>
            <if test="action != null">
                AND t.action = #{action}
            </if>
            </script>
            """)
    List<TaskListDto> getTaskListAsAdmin(Long companyId, Long equipmentId, Integer action);

    @Select("""
            <script>
            SELECT
            t.id AS 'id',
            t.equipment_id AS 'equipmentId',
            e.`name` AS 'equipmentName',
            t.`request` AS 'request',
            t.user_account_id AS 'userAccountId',
            u.`name` AS 'userName',
            t.`action` AS 'action',
            t.`solution` AS 'solution',
            t.updated_at AS 'lastUpdateTime'
            FROM `tasks` t
            JOIN `equipments` e ON e.id = t.equipment_id
            LEFT JOIN `user_accounts` ua ON ua.id = t.user_account_id
            LEFT JOIN `users` u ON u.id = ua.user_id
            WHERE t.company_id = #{companyId}
            AND DATE_FORMAT(t.created_at, "%Y-%m-%d") = DATE_FORMAT(NOW(), "%Y-%m-%d")
            AND t.user_account_id = #{userAccountId}
            <if test="equipmentId != null">
                AND t.equipment_id = #{equipmentId}
            </if>
            <if test="action != null">
                AND t.action = #{action}
            </if>
            </script>
            """)
    List<TaskListDto> getTaskListAsWorker(Long companyId, Long equipmentId, Long userAccountId, Integer action);

    @Select("""
            SELECT id FROM `tasks`
            WHERE `action` = 1
            AND `company_id` = #{companyId}
            AND `equipment_id` = #{equipmentId}
            ORDER BY `created_at` ASC
            LIMIT 1;
            """)
    Optional<Long> getRemainTaskId(Long companyId, Long equipmentId);

    @Update("""
            UPDATE `tasks` SET
                `user_account_id` = #{userAccountId},
                `action` = 2
            WHERE `id` = #{taskId};
            """)
    Integer assignTaskToWorker(Long userAccountId, Long taskId);

    @Update("""
            UPDATE `tasks` SET
                `action` = 3,
                `solution` = #{solution}
            WHERE `id` = #{taskId};
            """)
    Integer endTaskAsAdmin(Long taskId, String solution);

    @Update("""
            UPDATE `tasks` SET
                `action` = 0,
                `solution` = #{solution}
            WHERE `id` = #{taskId};
            """)
    Integer cancelTaskAsAdmin(Long taskId, String solution);

    @Update("""
            UPDATE `tasks` SET
                `action` = 3,
                `solution` = #{solution}
            WHERE `id` = #{taskId}
            AND `user_account_id` = #{userAccountId};
            """)
    Integer endTaskAsWorker(Long userAccountId, Long taskId, String solution);

    @Update("""
            UPDATE `tasks` SET
                `action` = 0,
                `solution` = #{solution}
            WHERE `id` = #{taskId}
            AND `user_account_id` = #{userAccountId};
            """)
    Integer cancelTaskAsWorker(Long userAccountId, Long taskId, String solution);

    @Select("""
            SELECT
            `equipment_id`
            FROM `tasks`
            WHERE id = #{taskId};
            """)
    Optional<Long> selectEquipmentIdById(Long taskId);

    @Select("""
            SELECT
            t.id AS 'id',
            t.equipment_id AS 'equipmentId',
            e.`name` AS 'equipmentName',
            t.`request` AS 'request',
            t.user_account_id AS 'userAccountId',
            u.`name` AS 'userName',
            t.`action` AS 'action',
            t.`solution` AS 'solution',
            t.updated_at AS 'lastUpdateTime'
            FROM `tasks` t
            JOIN `equipments` e ON e.id = t.equipment_id
            LEFT JOIN `user_accounts` ua ON ua.id = t.user_account_id
            LEFT JOIN `users` u ON u.id = ua.user_id
            WHERE t.id = #{taskId}
            """)
    TaskListDto getTaskDetail(Long taskId);

    @Update("""
            UPDATE tasks SET solution = NULL, `action`=1;
            """)
    Integer resetTask();

    @Update("UPDATE tasks SET `created_at`=NOW(), `updated_at`=NOW()")
    Integer updateTodayTasks();
}
