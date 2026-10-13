# 웹과 API를 함께 배포하기

저장소 루트에서 Flutter 웹을 빌드한 다음 Docker 이미지를 만듭니다.

```powershell
cd apps/trend_lab_flutter
flutter build web --release
cd ../..
docker build -f deploy/trend-lab/Dockerfile -t trend-lab .
docker run --env APP_TOKEN --publish 8787:8787 --mount type=volume,source=trend-lab-data,target=/data trend-lab
```

`APP_TOKEN`은 실행 전 환경변수에 설정합니다. Docker 이미지에는 넣지 않습니다. `/data`는 영구 디스크에 연결하며 `trades.sqlite`와 WAL 파일을 함께 보존합니다. 운영 서버는 HTTPS 역방향 프록시 또는 호스팅 제공자의 TLS를 사용해야 합니다.

한 서버가 웹과 API를 모두 제공하므로 앱의 연결 화면에는 해당 HTTPS 주소를 입력하면 됩니다. 웹 코드만 GitHub Pages에 올리면 거래기록 서버는 별도로 필요합니다. 현재 공개 서버와 도메인은 선택되지 않았습니다.

## Render 배포 준비

루트의 `render.yaml`은 싱가포르의 유료 0.5 CPU / 512MB 서버와 1GB 영구 디스크 한 개를 선언합니다. `Dockerfile.render`는 GitHub 소스에서 Flutter 웹을 빌드하고 API와 함께 제공합니다. 거래 DB는 `/data`에 보관하고 연결 키는 Render가 비밀 환경변수로 생성합니다. 코드에는 키가 포함되지 않습니다.

1. Render 계정을 만들고 GitHub 저장소 접근을 연결합니다.
2. Blueprint에서 `hbb7896/my-trading-app`의 `feat/trend-lab-flutter` 브랜치와 `render.yaml`을 선택합니다.
3. 서버·디스크의 요금을 확인하고 승인한 뒤 생성합니다. 계정 연결만으로 생성하지 않습니다.
4. 배포 성공 후 실제 `onrender.com` 주소를 확인합니다. 새 웹 앱은 현재 웹 주소를 API 기본 주소로 사용합니다. 안드로이드에서는 같은 HTTPS 주소를 입력합니다.
5. Render의 서버 환경설정에서 개인 연결 키를 확인해 앱 연결 화면에 직접 입력합니다. GitHub, 화면 캡처, 대화 메시지에 키를 넣지 않습니다.

현재 Blueprint는 배포 제안 파일이며 서비스 생성이나 청구가 시작된 상태가 아닙니다. 서버 기본 요금에 1GB 디스크 비용이 추가됩니다. 사용량 초과와 세금은 별도이며 생성 직전 대시보드의 실제 요금을 다시 확인해야 합니다.

재배포는 GitHub 검증이 통과한 변경에 대해 실행하도록 설정했습니다. 영구 디스크로 인해 서비스 교체 시 잠깐 중단될 수 있습니다. 실제 거래 이전 전에는 SQLite DB 백업 절차도 운영 환경에서 확인합니다.
