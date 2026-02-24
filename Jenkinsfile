#!/usr/bin/env groovy

node {

    imageVersion = 'registry.cn-shanghai.aliyuncs.com/transformer/trans-parser:1.0.0-' + env.JOB_BASE_NAME + '-' + env.BUILD_NUMBER
    stage('checkout') {
         def scmVars = checkout scm
         env.GIT_COMMIT = scmVars.GIT_COMMIT
         env.GIT_URL = scmVars.GIT_URL
    }

    stage('login docker repository') {
        sh "chmod +x build.sh"
        sh "docker login -u admin@magfin.cn -p qwertyuiop1 registry.cn-shanghai.aliyuncs.com"
    }

    stage('build image') {
        sh "sh build.sh"
        sh "docker build --no-cache -t " + imageVersion + " ./src"
    }

    stage('push image') {
        sh "docker push " + imageVersion
    }

    stage('trigger deploy') {
         build job: 'mf023-trans-parser-external-deploy',
                            parameters: [
                                string(name: 'DOCKER_TAG_NUMBER', value: "${BUILD_ID}")
                            ]
    }
}
