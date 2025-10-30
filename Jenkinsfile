pipeline {
    agent any
    
    // Jenkins가 실행하는 모든 하위 프로세스(deploy.sh, docker compose 등)에 환경변수로 전달
    environment {
        
        // Database
        // Jenkins의 Credentials 저장소에서 ID가 SPRING_DB_USERNAME인 credential을 찾아서 가져옴
        SPRING_DB_USERNAME = credentials('SPRING_DB_USERNAME') 
        SPRING_DB_PASSWORD = credentials('SPRING_DB_PASSWORD')
        
        // JWT
        JWT_SECRET = credentials('JWT_SECRET')
        JWT_ACCESS_TOKEN_EXPIRATION = credentials('JWT_ACCESS_TOKEN_EXPIRATION')
        JWT_REFRESH_TOKEN_EXPIRATION = credentials('JWT_REFRESH_TOKEN_EXPIRATION')
        
        //  LiveKit
        LIVEKIT_API_KEY = credentials('LIVEKIT_API_KEY')
        LIVEKIT_API_SECRET = credentials('LIVEKIT_API_SECRET')
        
        //  Company UUID
        COMPANY_UUID_EXPIRATION = credentials('COMPANY_UUID_EXPIRATION')
        
        // Spring Security
        SPRING_SECURITY_USER_NAME = credentials('SPRING_SECURITY_USER_NAME')
        SPRING_SECURITY_USER_PASSWORD = credentials('SPRING_SECURITY_USER_PASSWORD')
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

