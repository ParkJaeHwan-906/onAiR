## 1. `helloar` (메인 AR 앱 로직)

앱의 핵심이며, ARCore와 안드로이드 시스템, 그리고 3D 렌더링을 '연결'하는 부분입니다.

- `HelloArActivity`
    - **역할: 📱 앱의 메인 화면이자 총책임자.**
    - 안드로이드 **Activity**입니다. 앱의 생명 주기(시작, 정지, 재시작)를 관리합니다.
    - `HelloArView`와 `HelloArRenderer`를 생성하고 관리합니다.
    - 사용자의 터치 이벤트(탭)를 `TapHelper`로부터 받아 `HelloArRenderer`에 전달합니다.
    - 모든 `Helper` 클래스(권한, 스낵바 등)를 소유하고 제어합니다.
- `HelloArRenderer.kt`
    - **역할: 🧠 ARCore와 3D 렌더러를 잇는 두뇌.**
    - 가장 중요한 클래스 중 하나입니다. **`GLSurfaceView.Renderer`** 를 구현합니다.
    - **매 프레임**(`onDrawFrame`)마다 호출됩니다.
    - **ARCore**로부터 최신 정보("지금 폰이 어디 있는지?", "바닥이 어디 감지됐는지?")를 받아옵니다.
    - `samplerenderer`를 사용해 "카메라 배경 화면을 그려라", "감지된 평면을 그려라", "사용자가 탭한 곳에 3D 모델(앵커)을 그려라"라고 명령합니다.
- `HelloArView`
    - **역할: 🎨 3D 그림을 그릴 캔버스(화면).**
    - 안드로이드 **`GLSurfaceView`** 를 상속받습니다.
    - OpenGL ES(3D 그래픽 라이브러리)를 사용할 수 있는 화면 영역을 제공합니다.
    - `HelloArRenderer`가 그림을 그릴 수 있도록 렌더링 환경을 설정하고, 터치 이벤트를 `TapHelper`로 전달합니다.

---

## 2. `samplerenderer` (미니 3D 렌더링 엔진)

ARCore는 3D 모델을 직접 그리지 않습니다. "어디에" 그릴지만 알려줄 뿐입니다. 이 `samplerenderer`는 OpenGL ES를 사용해 3D 객체를 **실제로 화면에 그리는** 경량 3D 엔진입니다.

- `SampleRenderer`
    - **역할: 🖌️ 3D 렌더링 총괄 매니저.**
    - `HelloArRenderer`로부터 "이 3D 모델(Mesh)을, 이 텍스처(Texture)와 쉐이더(Shader)를 사용해, 저기(특정 좌표)에 그려줘"라는 명령을 받아 실행합니다.
- `Mesh`
    - **역할: 🧊 3D 모델의 뼈대 (형상).**
    - 3D 객체의 형상 데이터입니다. (예: 큐브, 구, 안드로이드 로봇 모델)
    - `VertexBuffer` (정점 좌표)와 `IndexBuffer` (그리는 순서)를 가집니다.
- `VertexBuffer` / `IndexBuffer` / `GpuBuffer`
    - **역할: 💾 3D 모델 데이터를 GPU에 전송하는 통로.**
    - 3D 모델의 좌표(Vertex), 순서(Index) 등의 데이터를 CPU 메모리에서 GPU(그래픽 카드) 메모리로 효율적으로 전달하는 버퍼입니다.
- `Shader`
    - **역할: 🌈 3D 모델의 재질과 조명을 결정하는 프로그램.**
    - GPU에서 직접 실행되는 작은 코드입니다.
    - "이 3D 모델의 표면을 어떤 색으로 칠할지", "빛을 받았을 때 어떻게 반짝이게 할지" 등을 정의합니다.
- `Texture`
    - **역할: 🖼️ 3D 모델에 입히는 이미지(껍데기).**
    - 3D 모델의 표면에 입히는 2D 이미지 파일입니다. (예: 안드로이드 로봇의 초록색 피부 이미지)
- `Framebuffer`
    - **역할: ✨ 특수 효과를 위한 보조 캔버스.**
    - 화면에 직접 그리지 않고, 메모리상의 다른 곳에 임시로 렌더링할 때 사용합니다. (예: 그림자 효과, 후처리)
- `GLError`
    - **역할: 🔍 3D 렌더링 오류 탐지기.**
    - 디버깅이 까다로운 OpenGL 오류를 확인하고 로그를 남기는 유틸리티입니다.

---

## 3. `common.helpers` (편의 기능 도우미)

AR 로직과는 직접 관련 없지만, 안드로이드 앱을 만드는 데 필요한 귀찮은 작업들(권한, UI 등)을 처리해주는 도우미 클래스 모음입니다.

- `ARCoreSessionLifecycleHelper`
    - **역할: 💡 ARCore 세션 생명 주기 관리자.**
    - `HelloArActivity`의 생명 주기(Activity Lifecycle)에 맞춰 ARCore **`Session`*을 안전하게 `resume()`(시작/재시작)하고 `pause()`(일시정지)하는 매우 중요한 역할을 합니다. (배터리 관리, 앱 안정성)
- `CameraPermissionHelper` / `LocationPermissionHelper`
    - **역할: 👮‍♀️ 권한 요청 담당자.**
    - 사용자에게 "카메라 사용을 허용하시겠습니까?", "위치 정보를 사용하시겠습니까?"라고 묻는 팝업을 띄우고 결과를 처리합니다.
- `SnackbarHelper`
    - **역할: 💬 사용자 알림 메시지 담당.**
    - 화면 하단에 "평면을 찾는 중입니다..." 같은 간단한 메시지(스낵바)를 보여줍니다.
- `TrackingStateHelper`
    - **역<b>할: 📡 ARCore 상태 감시자.</b>**
    - ARCore가 현재 공간을 잘 추적하고 있는지(`TRACKING`), 아니면 잠시 멈췄는지(`PAUSED`) 상태를 확인하고, `SnackbarHelper`를 통해 사용자에게 알려줍니다.
- `TapHelper`
    - **역할: 👆 터치 이벤트 처리기.**
    - `HelloArView`에서 발생한 터치 이벤트를 감지하여 큐(Queue)에 저장했다가, `HelloArActivity`가 가져갈 수 있게 합니다. (메인 스레드와 렌더링 스레드 간의 충돌 방지)
- `DisplayRotationHelper`
    - **역할: 🔄 화면 회전 감지기.**
    - 사용자가 폰을 가로/세로로 돌리는 것을 감지하여 ARCore와 렌더러에게 알려줍니다.
- `FullScreenHelper`
    - **역할: 🎬 전체 화면 모드 설정.**
    - 앱을 몰입감 있게 사용할 수 있도록 상단 상태표시줄과 하단 내비게이션 바를 숨깁니다.
- `DepthSettings` / `EisSettings` / `InstantPlacementSettings`
    - **역할: ⚙️ ARCore 고급 기능 설정.**
    - Depth API(깊이) 사용 여부, EIS(전자식 손떨림 방지) 사용 여부, Instant Placement(평면 감지 전 즉시 배치) 사용 여부 등 ARCore의 세부 옵션을 관리합니다.