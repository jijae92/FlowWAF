# FlowWAF: Anomaly-Detection-based Web Application Firewall

FlowWAF는 로그 기반 이상 탐지를 통해 알려지지 않은 위협과 악의적인 트래픽 패턴을 식별하는 서버리스 웹 애플리케이션 방화벽입니다.

- **핵심 기능**:
  - AWS WAF, VPC Flow Logs 등 로그 데이터 분석
  - 시계열 분석(EWMA)을 통한 실시간 이상 점수(Anomaly Score) 계산
  - 탐지된 이상 행위에 대한 SNS, Slack 등 알림 기능
  - IoC(침해 지표) 기반의 위협 인텔리전스 연동

*(데모 스크린샷이나 아키텍처 다이어그램을 여기에 추가하면 좋습니다.)*

---

## 1. 빠른 시작 (Quick Start)

### 1.1. 사전 요구사항 (Prerequisites)

시작하기 전에 아래의 도구와 환경이 준비되어야 합니다.

- **Python 3.9+**
- **AWS SAM CLI**: 서버리스 애플리케이션 빌드 및 배포에 필요합니다.
  - [공식 설치 가이드](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)를 참고하여 설치하세요.
- **Python 빌드 의존성**: `pyarrow`, `numpy` 등 일부 패키지는 시스템 레벨의 빌드 도구가 필요합니다.
  - **Debian/Ubuntu**: `sudo apt-get update && sudo apt-get install -y build-essential python3-dev`
  - **macOS**: `xcode-select --install`

### 1.2. 설치 및 테스트

```bash
# 1. 저장소 복제
git clone https://github.com/jijae92/FlowWAF.git
cd FlowWAF

# 2. (권장) 가상 환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 3. 의존성 패키지 설치
make install

# 4. 단위 테스트 실행
make test
```

### 1.3. 환경변수 설정 및 배포

배포 전, `sam-template.yaml` 파일의 `Parameters` 섹션 또는 배포 시 직접 환경변수 값을 설정해야 합니다.

```bash
# 1. SAM을 이용한 애플리케이션 빌드
make build

# 2. SAM을 이용한 대화형 배포
# 이 과정에서 파라미터(환경변수) 값을 입력하라는 메시지가 표시됩니다.
make deploy
# 예시 파라미터 값:
# - Parameter AnomalySNSTopicEmail: your-email@example.com
# - Parameter SlackWebhookUrl: https://hooks.slack.com/services/YOUR/SLACK/URL
# - Parameter ConfigS3Bucket: your-config-bucket-name
# - Parameter ConfigS3Key: path/to/your/ioc.yml
```

## 2. 설정 및 구성 (Configuration)

### 주요 환경변수

Lambda 함수는 아래 환경변수를 사용하여 동작을 구성합니다.

| 환경변수 | 설명 | 필수 |
| :--- | :--- | :--- |
| `CONFIG_S3_BUCKET` | IoC 설정 파일(`ioc.yml`)이 저장된 S3 버킷 이름 | 예 |
| `CONFIG_S3_KEY` | `ioc.yml` 파일의 S3 내 객체 경로 | 예 |
| `SNS_TOPIC_ARN` | 이상 탐지 시 알림을 보낼 SNS 토픽의 ARN | 아니요 |
| `SLACK_WEBHOOK_URL`| 이상 탐지 시 알림을 보낼 Slack Webhook URL | 아니요 |

### IAM 권한

본 프로젝트는 최소 권한 원칙을 따르도록 설계되었습니다. `infra/sam-template.yaml`에 정의된 IAM 역할은 아래와 같은 주요 권한을 필요로 합니다. 실제 운영 시에는 리소스 ARN을 와일드카드(`*`) 대신 특정 리소스로 제한해야 합니다.

- `s3:GetObject`: 로그 및 설정 파일 접근
- `athena:StartQueryExecution`, `glue:GetTable` 등: Athena 쿼리 실행
- `sns:Publish`: SNS 알림 발송
- `lambda:InvokeFunction`: 다른 Lambda 함수 호출 (워밍업 등)
- `logs:CreateLogStream`, `logs:PutLogEvents`: CloudWatch 로깅

## 3. 아키텍처 개요

1.  **데이터 수집**: AWS WAF, VPC Flow Logs 등의 로그가 S3 버킷에 저장됩니다.
2.  **탐지 트리거**: S3에 새 로그 파일이 생성되면 S3 Event Notification이 `Detector` Lambda 함수를 트리거합니다.
3.  **데이터 분석**: `Detector` Lambda는 Athena를 사용하여 로그를 쿼리하고, 시계열 분석(EWMA)을 통해 이상 점수를 계산합니다.
4.  **위협 평가**: 계산된 데이터는 `ioc.yml`에 정의된 침해 지표(IP, CIDR 등)와 비교 분석됩니다.
5.  **알림**: 이상 점수가 임계치를 초과하거나 IoC와 일치하는 경우, SNS 또는 Slack으로 알림을 보냅니다.

**의존 AWS 서비스**: S3, Lambda, Athena, Glue, SNS, CloudWatch

## 4. 운영 방법 (Operations)

- **로깅**: 모든 Lambda 함수의 실행 로그는 AWS CloudWatch Logs에 저장됩니다. `sam deploy` 시 생성된 로그 그룹을 확인하세요.
- **모니터링**: CloudWatch Metrics에서 `Detector` Lambda의 `Invocations`, `Errors`, `Duration` 지표를 모니터링하여 서비스 상태를 확인할 수 있습니다.
- **주요 장애 및 복구**:
  - **`AccessDeniedException`**: IAM 역할의 권한이 부족한 경우입니다. CloudWatch 로그를 확인하여 어떤 리소스에 대한 접근이 거부되었는지 파악하고 `sam-template.yaml`의 IAM 정책을 수정하세요.
  - **환경변수 누락**: 함수 로그에 `KeyError` 또는 설정 파일 로드 실패 메시지가 나타납니다. AWS Lambda 콘솔에서 함수의 환경변수 설정을 확인하고 수정하세요.
  - **Athena 쿼리 실패**: SQL 문법 오류 또는 Glue 테이블/파티션 문제일 수 있습니다. Athena 콘솔에서 직접 쿼리를 실행하여 디버깅하세요.

## 5. 보안 및 컴플라이언스

- **비밀 관리**: `SLACK_WEBHOOK_URL`과 같은 민감한 정보는 환경변수 대신 **AWS Secrets Manager** 또는 **Parameter Store**를 사용하여 안전하게 관리하고, Lambda 함수에서 런타임에 읽어오도록 수정하는 것을 강력히 권장합니다.
- **최소 권한 원칙**: `infra/sam-template.yaml`의 IAM 권한을 실제 운영 환경에 맞게 특정 리소스 ARN으로 제한하여 최소 권한 원칙을 준수하세요.
- **데이터 보존**: S3에 저장되는 로그는 조직의 컴플라이언스 요구사항에 따라 데이터 보존 기간(Lifecycle Policy)을 설정하세요.
- **취약점 신고**: 보안 취약점을 발견한 경우, GitHub 저장소의 "Security" 탭을 통해 비공개로 보고해 주십시오. (저장소에 `SECURITY.md` 파일을 생성하여 정책을 명시하세요.)

## 6. 기여 가이드 (Contribution Guide)

- **브랜치 전략**: `main` 브랜치로 직접 푸시하는 것을 지양하고, `feature/<기능이름>`과 같은 브랜치를 생성하여 작업한 후 Pull Request(PR)를 생성합니다.
- **코드 스타일**: 일관된 코드 스타일을 위해 `black`, `flake8` 같은 린터를 도입하는 것을 권장합니다.
- **커밋 메시지**: [Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따라 커밋 메시지를 작성하면 변경 이력을 쉽게 추적할 수 있습니다. (예: `feat: Add Slack notification feature`)
- **테스트**: 새로운 기능을 추가하거나 버그를 수정할 경우, 반드시 관련 단위 테스트(`pytest`)를 추가하거나 수정해야 합니다.

## 7. 라이선스 (License)

본 프로젝트는 [MIT License](LICENSE)를 따릅니다. (라이선스 파일을 추가하고, 원하는 라이선스를 명시하세요.)

## 8. 변경 이력 (Changelog)

모든 주요 변경 사항은 [GitHub Releases](https://github.com/jijae92/FlowWAF/releases) 페이지에 문서화됩니다.
