pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = 'ocrmypdf-api'
        CONTAINER_NAME = 'ocrmypdf-api'
        APP_PORT = '8001'
    }
    
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/YOUR_USERNAME/ocrmypdf-api.git'
            }
        }
        
        stage('Stop Old Container') {
            steps {
                script {
                    sh '''
                        docker stop ${CONTAINER_NAME} || true
                        docker rm ${CONTAINER_NAME} || true
                    '''
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                sh 'docker build -t ${DOCKER_IMAGE}:latest .'
            }
        }
        
        stage('Deploy') {
            steps {
                sh '''
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        -p ${APP_PORT}:8001 \
                        --restart unless-stopped \
                        ${DOCKER_IMAGE}:latest
                '''
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    sleep 10
                    sh 'curl -f http://localhost:${APP_PORT}/health || exit 1'
                }
            }
        }
        
        stage('Cleanup Old Images') {
            steps {
                sh 'docker image prune -f'
            }
        }
    }
    
    post {
        success {
            echo 'Deployment successful!'
        }
        failure {
            echo 'Deployment failed!'
            sh 'docker logs ${CONTAINER_NAME}'
        }
    }
}
