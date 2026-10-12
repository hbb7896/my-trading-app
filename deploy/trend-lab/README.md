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
