// 도면 표시 컴포넌트
import "../../styles/Communication/DrawingPreview.css";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader, OrbitControls } from "three-stdlib";

import { useRoomContext } from "@livekit/components-react";
import { Track } from "livekit-client";

const BLUEPRINT_PATH = "/models/blueprint.glb";
const AHU_PATH = "/models/air_handling_unit.glb";
const AHU_SCALE = 0.1;
const AHU_HOVER_MULTIPLIER = 1.5;
const AHU_HOVER_Y_OFFSET = 0.4;
const AHU_FOCUS_SCALE_MULTIPLIER = 3;
const AHU_FOCUS_Y_OFFSET = 1.2;
const AHU_POSITION = { x: -4.4, y: 1.15, z: 1.25 };
const AHU_ROTATION_Y = THREE.MathUtils.degToRad(90);
const CAMERA_FOCUS_DISTANCE = 6;
const CAMERA_FOCUS_HEIGHT = -0.5;
const CAMERA_ANIMATION_DURATION = 800;

const DrawingPreview = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const resetFocusRef = useRef<(() => void) | null>(null);
  // 도면(3D 모델) ON/OFF 상태 (패널은 유지
  const [showModel, setShowModel] = useState(true);

  // 라이브킷
  const room = useRoomContext();
  const trackRef = useRef<MediaStreamTrack | null>(null);

  useEffect(() => {
    if (!showModel) return; // 도면 숨기기 상태면 3D 엔진 실행 안함

    const container = containerRef.current;
    if (!container) return;
    if (!room) return;

    const { clientWidth, clientHeight } = container;
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
      45,
      clientWidth / clientHeight,
      0.1,
      1000
    );
    camera.position.set(3, 2, 5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(clientWidth, clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x00aaff, 0.0);
    container.appendChild(renderer.domElement);

    // 모델 모바일 연동 30fps
    const canvas = renderer.domElement as HTMLCanvasElement;
    const stream = canvas.captureStream(30);
    const [track] = stream.getVideoTracks();
    trackRef.current = track;

    room.localParticipant.publishTrack(track, {
      name: "blueprint-canvas",
      source: Track.Source.ScreenShare,
    });

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0, 0);

    const ambientLight = new THREE.AmbientLight(0xffffff, 1);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(5, 10, 7);
    scene.add(ambientLight, directionalLight);

    let blueprintModel: THREE.Object3D | null = null;
    let ahuGroup: THREE.Group | null = null;
    let ahuVisual: THREE.Object3D | null = null;
    let ahuHoverTargets: THREE.Object3D[] = [];
    let isAhuHovered = false;
    let isAhuFocused = false;
    let ahuBaseY = 0;
    let ahuScaleTarget = AHU_SCALE;
    let ahuCurrentScale = AHU_SCALE;
    let ahuPositionYTarget = 0;
    let ahuCurrentY = 0;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const cameraStartPosition = new THREE.Vector3();
    const cameraTargetStart = new THREE.Vector3();
    const cameraPositionEnd = new THREE.Vector3();
    const cameraTargetEnd = new THREE.Vector3();
    const cameraPreFocusPosition = new THREE.Vector3();
    const cameraPreFocusTarget = new THREE.Vector3();
    let cameraAnimationStart: number | null = null;
    let blueprintVisibilityAfterCamera: boolean | null = null;

    const setPointerFromEvent = (event: MouseEvent | PointerEvent) => {
      if (!container) return;
      const rect = container.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    };

    const loader = new GLTFLoader();

    // 층 도면 렌더링
    loader.load(
      BLUEPRINT_PATH,
      (gltf) => {
        const model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        model.position.sub(center); // center model at origin

        const size = box.getSize(new THREE.Vector3()).length();
        if (size > 0) {
          const distance = size * 0.8;
          camera.position.set(distance, distance * 0.6, distance);
          controls.target.set(0, 0, 0);
          camera.lookAt(controls.target);
        }

        blueprintModel = model;
        scene.add(model);
      },
      undefined,
      (error) => {
        console.error("Failed to load blueprint model", error);
      }
    );

    // 공조기 렌더링
    loader.load(
      AHU_PATH,
      (gltf) => {
        const ahu = gltf.scene;
        const box = new THREE.Box3().setFromObject(ahu);
        const center = box.getCenter(new THREE.Vector3());
        ahu.position.sub(center); // center model at origin
        ahu.scale.setScalar(AHU_SCALE);

        const size = box.getSize(new THREE.Vector3());
        const proxyGeometry = new THREE.BoxGeometry(size.x, size.y, size.z);
        const proxyMaterial = new THREE.MeshBasicMaterial({ visible: false });
        const proxy = new THREE.Mesh(proxyGeometry, proxyMaterial);
        proxy.position.copy(ahu.position);
        proxy.scale.setScalar(AHU_SCALE);

        const group = new THREE.Group();
        group.position.set(AHU_POSITION.x, AHU_POSITION.y, AHU_POSITION.z);
        group.rotation.y = AHU_ROTATION_Y;
        group.add(ahu);
        group.add(proxy);

        scene.add(group);

        ahuGroup = group;
        ahuVisual = ahu;
        ahuBaseY = ahu.position.y;
        ahuPositionYTarget = ahuBaseY;
        ahuCurrentY = ahuBaseY;
        ahuScaleTarget = AHU_SCALE;
        ahuCurrentScale = AHU_SCALE;
        ahuHoverTargets = [proxy, ahu];
      },
      undefined,
      (error) => {
        console.error("Failed to load air handling unit model", error);
      }
    );

    const applyHoverState = (hovered: boolean) => {
      if (!ahuVisual || isAhuFocused) return;
      if (hovered) {
        ahuScaleTarget = AHU_SCALE * AHU_HOVER_MULTIPLIER;
        ahuPositionYTarget = ahuBaseY + AHU_HOVER_Y_OFFSET;
      } else {
        ahuScaleTarget = AHU_SCALE;
        ahuPositionYTarget = ahuBaseY;
      }
    };

    const focusAhu = () => {
      if (!ahuVisual || !ahuGroup || isAhuFocused) return;
      isAhuFocused = true;
      setIsFocused(true);
      applyHoverState(false);
      isAhuHovered = false;
      if (blueprintModel) {
        blueprintVisibilityAfterCamera = false;
      }
      ahuScaleTarget = AHU_SCALE * AHU_FOCUS_SCALE_MULTIPLIER;
      ahuPositionYTarget = ahuBaseY + AHU_FOCUS_Y_OFFSET;

      const ahuWorldCenter = new THREE.Vector3();
      ahuGroup.getWorldPosition(ahuWorldCenter);
      const focusTarget = ahuWorldCenter
        .clone()
        .add(new THREE.Vector3(0, 0.5, 0));

      const frontDirection = new THREE.Vector3(0, 0, 1)
        .applyQuaternion(ahuGroup.quaternion)
        .normalize();
      const cameraPosition = ahuWorldCenter
        .clone()
        .add(frontDirection.multiplyScalar(CAMERA_FOCUS_DISTANCE))
        .add(new THREE.Vector3(0, CAMERA_FOCUS_HEIGHT, 0));

      cameraPreFocusPosition.copy(camera.position);
      cameraPreFocusTarget.copy(controls.target);
      cameraStartPosition.copy(camera.position);
      cameraTargetStart.copy(controls.target);
      cameraPositionEnd.copy(cameraPosition);
      cameraTargetEnd.copy(focusTarget);
      cameraAnimationStart = performance.now();
    };

    const resetFocus = () => {
      if (!ahuVisual || !ahuGroup || !isAhuFocused) return;
      isAhuFocused = false;
      setIsFocused(false);
      blueprintVisibilityAfterCamera = true;
      ahuScaleTarget = AHU_SCALE;
      ahuPositionYTarget = ahuBaseY;

      cameraStartPosition.copy(camera.position);
      cameraTargetStart.copy(controls.target);
      cameraPositionEnd.copy(cameraPreFocusPosition);
      cameraTargetEnd.copy(cameraPreFocusTarget);
      cameraAnimationStart = performance.now();
    };

    resetFocusRef.current = resetFocus;

    const handlePointerMove = (event: PointerEvent) => {
      if (!container || !ahuVisual || ahuHoverTargets.length === 0) return;
      setPointerFromEvent(event);
      raycaster.setFromCamera(pointer, camera);
      const intersects = raycaster.intersectObjects(ahuHoverTargets, true);

      if (intersects.length > 0) {
        if (!isAhuHovered) {
          applyHoverState(true);
          isAhuHovered = true;
        }
      } else if (isAhuHovered) {
        applyHoverState(false);
        isAhuHovered = false;
      }
    };

    const handlePointerLeave = () => {
      if (!ahuVisual || !isAhuHovered || isAhuFocused) return;
      applyHoverState(false);
      isAhuHovered = false;
    };

    const handlePointerClick = (event: MouseEvent) => {
      if (!ahuHoverTargets.length || !container || isAhuFocused) return;
      setPointerFromEvent(event);
      raycaster.setFromCamera(pointer, camera);
      const intersects = raycaster.intersectObjects(ahuHoverTargets, true);
      if (intersects.length > 0) {
        focusAhu();
      }
    };

    container.addEventListener("pointermove", handlePointerMove);
    container.addEventListener("pointerleave", handlePointerLeave);
    container.addEventListener("click", handlePointerClick);

    const handleResize = () => {
      if (!container) return;
      const { clientWidth: width, clientHeight: height } = container;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    window.addEventListener("resize", handleResize);

    let frameId: number;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      if (ahuVisual) {
        ahuCurrentScale = THREE.MathUtils.lerp(
          ahuCurrentScale,
          ahuScaleTarget,
          0.15
        );
        ahuCurrentY = THREE.MathUtils.lerp(
          ahuCurrentY,
          ahuPositionYTarget,
          0.15
        );
        ahuVisual.scale.setScalar(ahuCurrentScale);
        ahuVisual.position.y = ahuCurrentY;
      }

      if (cameraAnimationStart !== null) {
        const elapsed = performance.now() - cameraAnimationStart;
        const t = Math.min(elapsed / CAMERA_ANIMATION_DURATION, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        camera.position.lerpVectors(
          cameraStartPosition,
          cameraPositionEnd,
          eased
        );
        controls.target.lerpVectors(cameraTargetStart, cameraTargetEnd, eased);
        camera.lookAt(controls.target);
        if (t >= 1) {
          cameraAnimationStart = null;
          controls.target.copy(cameraTargetEnd);
          if (blueprintModel && blueprintVisibilityAfterCamera !== null) {
            blueprintModel.visible = blueprintVisibilityAfterCamera;
            blueprintVisibilityAfterCamera = null;
          }
        }
      }
      controls.update();
      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleResize);
      container.removeEventListener("pointermove", handlePointerMove);
      container.removeEventListener("pointerleave", handlePointerLeave);
      container.removeEventListener("click", handlePointerClick);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
      scene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          mesh.geometry.dispose();
          if (Array.isArray(mesh.material)) {
            mesh.material.forEach((material) => material.dispose?.());
          } else {
            mesh.material?.dispose?.();
          }
        }
      });

      // 라이브킷 클린업
      const track = trackRef.current;
      if (track && room) {
        room.localParticipant.unpublishTrack(track, true);
        track.stop();
      }
    };
  }, [room, showModel]);

  return (
    <div className="drawing-preview" ref={containerRef}>
      {/* 도면 ON/OFF 버튼 */}
      <button
        className="drawing-preview__toggle"
        onClick={() => setShowModel((prev) => !prev)}
      >
        {showModel ? "도면 ON" : "도면 OFF"}
      </button>
      {isFocused && (
        <button
          className="drawing-preview__back"
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            resetFocusRef.current?.();
          }}
        >
          뒤로가기
        </button>
      )}
    </div>
  );
};

export default DrawingPreview;
