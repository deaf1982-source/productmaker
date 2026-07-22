# productmaker — 모바일 컨트롤 패널

데스크탑에서 진행 중인 **웹/Node.js 프로젝트**를 **휴대폰 브라우저**에서 제어합니다.

- ▶️ **프로세스 시작 / 중지 / 재시작** — 개발 서버, API 서버 등 오래 도는 프로세스
- ⚡ **명령/스크립트 실행** — `npm install`, `build`, `test`, 배포 스크립트 등 (일회성)
- 📊 **실시간 상태 · 로그 모니터링** — WebSocket으로 로그가 즉시 휴대폰에 스트리밍
- 🔐 **토큰 인증** — 아무나 명령을 실행하지 못하도록 접근 토큰 필요
- 🛡️ **명령 허용목록(allowlist)** — 설정 파일에 정의한 명령만 실행 가능 (휴대폰에서 임의 셸 명령 입력 불가)

데스크탑에서 이 패널 서버를 켜 두면, 같은 Wi-Fi에 있는 휴대폰에서 웹페이지로 접속해 조작합니다.

---

## 1. 설치

```bash
git clone <이 저장소>
cd productmaker
npm install
```

Node.js 18 이상이 필요합니다.

## 2. 내 프로젝트에 맞게 설정

```bash
npm run init          # control.config.json 생성 (예시 파일 복사)
```

생성된 `control.config.json`을 열어 **본인 프로젝트에 맞게** 수정하세요:

```jsonc
{
  "projectRoot": "..",        // 제어할 실제 프로젝트 폴더 (이 저장소 기준 상대경로 또는 절대경로)
  "port": 4477,
  "host": "0.0.0.0",           // 0.0.0.0 = 휴대폰 등 같은 네트워크의 다른 기기에서 접속 허용

  "processes": [               // 시작/중지 하는 오래 도는 프로세스
    { "id": "dev", "name": "Dev Server", "command": "npm", "args": ["run", "dev"] },
    { "id": "api", "name": "API Server", "command": "node", "args": ["server.js"] }
  ],

  "commands": [                // 버튼 한 번으로 실행하는 일회성 명령
    { "id": "install", "name": "Install deps", "command": "npm", "args": ["install"] },
    { "id": "build",   "name": "Build",        "command": "npm", "args": ["run", "build"] },
    { "id": "test",    "name": "Run tests",    "command": "npm", "args": ["test"] }
  ]
}
```

각 항목 필드:

| 필드 | 설명 |
| --- | --- |
| `id` | 내부 식별자 (고유해야 함) |
| `name` | 휴대폰 화면에 보이는 이름 |
| `command` | 실행 파일 (`npm`, `node`, `python` 등) |
| `args` | 인자 배열 — 셸을 거치지 않으므로 각 인자를 따로 적습니다 |
| `cwd` | (선택) 실행 폴더. 없으면 `projectRoot` |
| `autostart` | (프로세스만, 선택) 패널 시작 시 자동 실행 |

> 보안상 명령은 셸(`shell:false`)을 거치지 않고 직접 실행됩니다. 파이프(`|`)나 `&&` 같은 셸 문법이 필요하면
> 스크립트 파일로 만들어(`"command": "bash", "args": ["scripts/deploy.sh"]`) 등록하세요.

## 3. 데스크탑에서 실행

```bash
npm start
```

터미널에 접속 주소와 **접근 토큰**이 표시됩니다:

```
  From phone   : (same Wi-Fi) open one of these
                 http://192.168.0.12:4477

  Access token (enter this on your phone):
      Xy8...접속토큰...

  Quick-open link with token embedded:
      http://192.168.0.12:4477/?token=Xy8...
```

토큰은 최초 실행 시 자동 생성되어 `.control-token` 파일에 저장됩니다(재실행해도 동일 유지).
`CONTROL_TOKEN` 환경변수로 직접 지정할 수도 있습니다.

## 4. 휴대폰에서 접속

데스크탑과 **같은 Wi-Fi**에 연결한 뒤, 휴대폰 브라우저에서:

- 터미널에 표시된 `http://192.168.0.xx:4477` 로 접속 → 토큰 입력, 또는
- `Quick-open link`(토큰 포함 주소)를 열면 바로 로그인됩니다.

토큰은 휴대폰에 저장되어 다음부터는 자동 로그인됩니다. 홈 화면에 추가하면 앱처럼 쓸 수 있습니다.

---

## 외부(집 밖)에서 접속하려면 — 터널

기본 설정(로컬 Wi-Fi)이 가장 안전하고 간단합니다. 외출 중에도 접속하려면 터널을 씌우세요.
명령 실행 권한이 있는 패널이므로 **토큰을 반드시 노출하지 말고**, 되도록 IP 화이트리스트나 추가 인증을 곁들이세요.

**Cloudflare Tunnel (무료, 추천):**

```bash
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
cloudflared tunnel --url http://localhost:4477
```

출력된 `https://....trycloudflare.com` 주소로 휴대폰에서 접속 → 토큰 입력.
HTTPS라 WebSocket(`wss`)도 자동 동작합니다.

**ngrok:**

```bash
ngrok http 4477
```

출력된 `https://....ngrok-free.app` 주소로 접속.

> ⚠️ 터널로 외부에 열면 URL을 아는 누구나 접근 시도할 수 있습니다. 토큰은 로그인 문지기일 뿐이니,
> 장시간 열어두지 말고 필요할 때만 켜고, 가능하면 터널 자체 인증(Cloudflare Access 등)을 추가하세요.

---

## 구조

```
productmaker/
├── control.config.example.json   설정 예시 (npm run init 이 이걸 복사)
├── src/
│   ├── server.js          Express + WebSocket + 인증
│   ├── config.js          설정/토큰 로딩
│   └── processManager.js  프로세스 spawn·추적·로그 스트리밍
└── public/                모바일 웹 UI (index.html / style.css / app.js)
```

- REST: `GET /api/config`, `POST /api/process/:id/{start,stop,restart}`, `POST /api/command/:id/run`, `GET /api/log/:kind/:id`
- 실시간: `GET /ws?token=...` — `snapshot` / `status` / `log` 이벤트 브로드캐스트
- 모든 `/api/*` 와 `/ws` 는 토큰(`Authorization: Bearer` 또는 `?token=`) 필요

## 보안 메모

- `control.config.json` 과 `.control-token` 은 `.gitignore` 처리되어 커밋되지 않습니다.
- 명령은 설정 파일 허용목록에만 국한됩니다 — 휴대폰에서 임의 명령을 타이핑할 수 없습니다.
- 토큰 비교는 타이밍 공격에 안전한 상수시간 비교를 사용합니다.
- 외부 노출 시에는 반드시 HTTPS 터널과 강한 토큰을 쓰세요.
