package ssafy.com.onair.user.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import ssafy.com.onair.user.dto.AttendanceDto;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Mapper
public interface AttendanceRepository {
    @Select("""
        SELECT * FROM attendance
        WHERE user_account_id = #{userAccountId} AND work_date = #{workDate}
    """)
    AttendanceDto findByUserAndDate(Long userAccountId, LocalDate workDate);

    @Insert("""
        INSERT INTO attendance (user_account_id, work_date, check_in_time)
        VALUES (#{userAccountId}, #{workDate}, #{checkInTime})
    """)
    void insertCheckIn(Long userAccountId, LocalDate workDate, LocalDateTime checkInTime);

    @Update("""
        UPDATE attendance
        SET check_out_time = #{checkOutTime}, total_work_minutes = #{totalWorkMinutes}
        WHERE user_account_id = #{userAccountId} AND work_date = #{workDate}
    """)
    void updateCheckOut(Long userAccountId, LocalDate workDate, LocalDateTime checkOutTime, int totalWorkMinutes);
}
