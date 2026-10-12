# Trend Lab · Flutter

안드로이드와 웹을 하나의 Flutter 코드로 지원하는 첫 버전입니다. 거래 등록·수정·삭제, 검색, 실제 금액의 손익·승률, 일봉 차트와 7개 진입 추세 조건, 청산 후 5·10·20거래일 복기를 제공합니다.

## 웹에서 실행

Flutter 3.47.2 이상과 Node.js 24 이상이 필요합니다.

```powershell
cd C:\my-trading-app\apps\trend_lab_flutter
flutter pub get
flutter build web --release
cd ..\trend-lab-api
$env:APP_TOKEN = '여기에_24자_이상의_개인_연결_키를_설정'
$env:WEB_DIR = '..\trend_lab_flutter\build\web'
node server.mjs
```

브라우저에서 `http://localhost:8787`을 열고 **서버 연결하기**에 같은 주소와 연결 키를 입력합니다. 연결 키는 브라우저 번들·로컬 저장소에 저장하지 않고 실행 중 메모리에만 유지합니다. API 서버 주소만 기기에 저장합니다.

거래는 API 서버의 `data/trades.sqlite`에 영구 저장됩니다. 같은 서버에 연결된 웹과 안드로이드는 같은 기록을 읽으며 30초 주기와 앱 복귀 때 갱신합니다. 연결되지 않았을 때 가짜 거래를 표시하거나 임시 저장하지 않습니다.

## 안드로이드

```powershell
flutter run -d <안드로이드_기기_ID>
```

Android SDK 라이선스는 사용자가 `flutter doctor --android-licenses`에서 확인·동의해야 합니다. 현재 컴퓨터는 일부 라이선스가 미승인 상태입니다. 실제 휴대폰에는 공개 HTTPS API 주소가 필요합니다. `localhost`는 각 기기 자신의 주소입니다. 개발용 에뮬레이터에서는 `http://10.0.2.2:8787`을 사용합니다. HTTP 허용은 debug 빌드에만 설정했습니다.

## 배포와 데이터 이전

GitHub는 코드와 자동 검증을 관리합니다. `.github/workflows/trend-lab.yml`은 서버 테스트·Flutter 분석·화면 테스트·웹 빌드와 Android debug APK 빌드를 실행하고 결과를 아티팩트로 보관합니다. debug APK는 설치 시험용이며 스토어 출시용 서명은 별도로 필요합니다. 웹/API 공개 배포는 아직 설정하지 않았습니다. 웹과 API를 한 서버에 제공하는 Docker 배포 안내는 `deploy/trend-lab/README.md`를 참고하세요.

API는 Dockerfile로 배포할 수 있습니다. `APP_TOKEN`은 서버의 비밀 설정에 넣고 `/data`에 영구 디스크를 연결해야 합니다. 웹을 같은 서버에서 제공하려면 빌드된 웹 디렉터리를 배포하고 `WEB_DIR`를 설정합니다. 별도 웹 호스팅을 쓰면 `ALLOWED_ORIGINS`에 정확한 웹 출처를 쉼표로 구분해 등록합니다. 개인 단일 사용자용 연결 키 방식이며, 여러 사용자를 지원하려면 사용자 로그인과 기록별 접근 제어가 추가로 필요합니다.

기존 Sites의 실제 거래 DB는 아직 이전하지 않았습니다. Trading Master에서 **내보내기**로 CSV를 받은 뒤 새 앱 상단의 **기존 기록 가져오기**를 누르세요. 파일 선택 → 거래 미리보기 → 확인한 기록 가져오기 순서로 옮깁니다. 같은 파일을 다시 가져와도 중복 저장하지 않고 기존 기록을 덮어쓰지 않습니다. 날짜·금액 오류가 있는 파일은 전체 저장을 차단합니다.

종목코드는 알려진 종목명에서 연결하고, 모르는 종목은 비워둡니다. 진입일·종목코드가 없는 거래도 손익 기록으로 가져올 수 있지만, 차트 복기를 하려면 거래 수정에서 입력해야 합니다. 메모·태그·심리·규율·차트 링크를 함께 보존합니다. 기존 앱과 데이터를 변경하지 않습니다.

## 검증

```powershell
flutter analyze
flutter test
flutter build web --release
node --test ..\trend-lab-api\test.mjs ..\trend-lab-api\import-test.mjs
```

차트 복기는 기존 Trend Lab의 분석식을 재사용합니다. NAVER 일별 시세를 서버에서 요청하며, 이동평균선은 해당 날짜 이전 시세로만 계산합니다. 차트의 가격 변화는 종가 기준으로 실제 체결 수익률과 다릅니다. 시세 연결 실패와 가격 이력 부족은 화면에 표시합니다.
