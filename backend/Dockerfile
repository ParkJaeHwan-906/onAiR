# =============== Build Stage ===============

# 베이스 이미지 지정 (Gradle 8.5 + JDK 17 포함)
# Alpine 기반으로 경량화 
# AS build : 해당 스테이지를 'build'라고 지칭  
FROM gradle:8.5-jdk17-alpine AS build

# 컨테이너 내부에서 /app 디렉토리를 작업 디렉토리로 설정 
# 이후 모든 명령어가 해당 디렉토리에서 실행 
WORKDIR /app

# Gradle 설정 파일들을 컨테이너의 /app 디렉토리로 복사 
COPY build.gradle settings.gradle gradlew ./

# gradle 디렉토리 전체 복사 
COPY gradle ./gradle

# 소스코드 복사 
COPY src ./src

# Gradle 프로젝트 빌드 명령어 실행
RUN chmod +x gradlew
# 빌드 시간 단축을 위해 테스트 실행 스킵 (-x test)
RUN ./gradlew clean build -x test --no-daemon


# =============== Runtime Stage ===============

# 새로운 베이스 이미지로 시작
# JRE만 포함 -> JDK보다 더 가벼움 
FROM eclipse-temurin:17-jre-alpine

# 런타임 컨테이너에서 /app을 작업 디렉토리로 설정 
WORKDIR /app

# 빌드 스테이지에서 생성된 JAR 파일을 현재 스테이지로 가져옴 
# --from=build: 위에서 지칭한 빌드 스테이지 참조 
COPY --from=build /app/build/libs/*.jar app.jar

# 컨테이너가 8080 포트를 사용한다고 명시 (실제로 여는 것은 아님. -p 옵션으로 매핑 필요)
EXPOSE 8080

# 컨테이너가 시작될 때 실행할 명령어
ENTRYPOINT ["java", "-jar", "app.jar"]
