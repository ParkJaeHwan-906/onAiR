pipeline {
    agent any
    
    // Jenkins가 실행하는 모든 하위 프로세스(deploy.sh, docker compose 등)에 환경변수로 전달
    environment {
        
        // ======================= Database(MySQL) =======================
        // Jenkins의 Credentials 저장소에서 ID가 SPRING_DB_USERNAME인 credential을 찾아서 가져옴
        SPRING_DB_USERNAME = credentials('SPRING_DB_USERNAME') 
        SPRING_DB_PASSWORD = credentials('SPRING_DB_PASSWORD')
        
        // ======================= Backend(Spring) =======================
        // JWT
        JWT_SECRET = credentials('JWT_SECRET')
        JWT_ACCESS_TOKEN_EXPIRATION = credentials('JWT_ACCESS_TOKEN_EXPIRATION')
        JWT_REFRESH_TOKEN_EXPIRATION = credentials('JWT_REFRESH_TOKEN_EXPIRATION')
        
        //  Company UUID
        COMPANY_UUID_EXPIRATION = credentials('COMPANY_UUID_EXPIRATION')
        
        // Spring Security
        SPRING_SECURITY_USER_NAME = credentials('SPRING_SECURITY_USER_NAME')
        SPRING_SECURITY_USER_PASSWORD = credentials('SPRING_SECURITY_USER_PASSWORD')

        // ======================= Frontend(React) =======================
        // Vite 환경변수 (빌드 타임에 주입)
        VITE_API_URL = credentials('VITE_API_URL')
        VITE_SOCKET_URL = credentials('VITE_SOCKET_URL')

        // ======================= AI(FastAPI) =======================
        // data & embedding
        JSONL_PATH = credentials('JSONL_PATH')
        FAISS_INDEX_PATH = credentials('FAISS_INDEX_PATH')
        EMB_MODEL_NAME = credentials('EMB_MODEL_NAME')

        // Hybrid / Rerank options
        ES_HOST = credentials('ES_HOST')
        ES_INDEX = credentials('ES_INDEX')
        CE_MODEL_NAME = credentials('CE_MODEL_NAME')
        
        // LLM 
        GMS_API_KEY = credentials('GMS_API_KEY')

        // TTS
        // TTS 크레덴셜 파일 경로 (EC2 서버의 절대 경로)
        // 예: /opt/secrets/tts-key.json 또는 credentials('GCP_TTS_CREDENTIALS_PATH')
        GCP_TTS_CREDENTIALS_PATH = credentials('GCP_TTS_CREDENTIALS_PATH')

        // ======================= ETC =======================
        //  LiveKit
        LIVEKIT_API_KEY = credentials('LIVEKIT_API_KEY')
        LIVEKIT_API_SECRET = credentials('LIVEKIT_API_SECRET')
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Detect Changes') {
            steps {
                script {
                    env.CHANGED_SERVICES = sh(
                        script: 'bash scripts/detect-changes.sh',
                        returnStdout: true
                    ).trim()
                    echo "Services to deploy: ${env.CHANGED_SERVICES}"
                }
            }
        }
        
        stage('Deploy') {
            when {
                expression { env.CHANGED_SERVICES != '' }
            }
            steps {
                sh "bash scripts/deploy.sh '${env.CHANGED_SERVICES}'"
            }
        }

        stage('Reload Nginx'){
            steps{
                script {
                    // nginx 컨테이너가 존재하는지 확인
                    def nginxExists = sh(
                        script: 'docker ps -q -f name=^nginx\$',
                        returnStdout: true
                    ).trim()
                    
                    if (nginxExists) {
                        echo 'Nginx 컨테이너 재시작 중...'
                        sh 'docker restart nginx'
                        echo 'Nginx 재시작 완료'
                    } else {
                        echo 'Nginx 컨테이너가 실행 중이지 않습니다.'
                    }
                }
            }
        }
    }
    
    post {
        success {
            echo "✅ Deployment successful: ${env.CHANGED_SERVICES}"
        }
        failure {
            echo "❌ Deployment failed"
            sh 'docker compose logs --tail=50 || true'
        }
        always {
            cleanWs()
        }
    }
}
