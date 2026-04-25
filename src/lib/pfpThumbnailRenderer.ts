/**
 * VRM → PFP thumbnail renderer for altiico batch pipeline.
 *
 * Ported from packages/admin/src/lib/emote-thumbnail-renderer.ts — same
 * framing / lighting / retargeting math so batch-rendered thumbnails in
 * altiico match what the admin dashboard produces today.
 *
 * Differences from the admin version:
 *   - Animation FBX path defaults to `/animations/<stem>.fbx` (altiico layout)
 *     instead of `/models/fbx/<stem>.fbx` (hubzz-admin layout).
 *   - No `robot_head.vrm` fallback — callers always pass a real vrmUrl.
 *   - Same captureEmoteThumbnail(...) API shape so the port is drop-in.
 *
 * Used by AnimationPreviewPage's batch-render loop to produce pfp PNGs that
 * feed into the collection manifest (pfpThumbnailUrl field).
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';
import { OutlineEffect } from 'three/examples/jsm/effects/OutlineEffect.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

const AVATAR_BODY_HEIGHT = 0.85;
const AVATAR_FLOOR_Y = -0.45;
const AVATAR_MAX_WIDTH = 0.95;
const CAMERA_HALF = 0.6;

function fitToCamera(
  object: THREE.Object3D,
  bodyHeight: number = AVATAR_BODY_HEIGHT,
  maxWidth: number = AVATAR_MAX_WIDTH,
  floorY: number = AVATAR_FLOOR_Y,
) {
  object.updateMatrixWorld(true);

  const posed = new THREE.Vector3();
  const max = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
  const min = new THREE.Vector3(+Infinity, +Infinity, +Infinity);

  object.traverse((child: any) => {
    if (!(child as any).isSkinnedMesh) return;
    const skinned = child as THREE.SkinnedMesh;
    const positionAttr = skinned.geometry.attributes.position;
    if (!positionAttr) return;
    for (let i = 0; i < positionAttr.count; i++) {
      posed.fromBufferAttribute(positionAttr, i);
      skinned.applyBoneTransform(i, posed);
      posed.applyMatrix4(skinned.matrixWorld);
      min.min(posed);
      max.max(posed);
    }
  });

  const size = new THREE.Vector3().subVectors(max, min);
  if (!isFinite(size.y) || size.y <= 0 || !isFinite(size.x) || size.x <= 0) {
    console.warn('[pfp-renderer] fitToCamera: no SkinnedMesh bounds found');
    return;
  }

  const heightFit = bodyHeight / size.y;
  const widthFit = maxWidth / size.x;
  const scale = Math.min(heightFit, widthFit);

  object.scale.setScalar(scale);
  const centerX = (max.x + min.x) * 0.5;
  const centerZ = (max.z + min.z) * 0.5;
  object.position.set(
    -centerX * scale,
    floorY - min.y * scale,
    -centerZ * scale,
  );
}

const MIXAMO_VRM_BONE_MAP: Record<string, string> = {
  mixamorigHips: 'hips',
  mixamorigSpine: 'spine',
  mixamorigSpine1: 'chest',
  mixamorigSpine2: 'upperChest',
  mixamorigNeck: 'neck',
  mixamorigHead: 'head',
  mixamorigLeftShoulder: 'leftShoulder',
  mixamorigLeftArm: 'leftUpperArm',
  mixamorigLeftForeArm: 'leftLowerArm',
  mixamorigLeftHand: 'leftHand',
  mixamorigRightShoulder: 'rightShoulder',
  mixamorigRightArm: 'rightUpperArm',
  mixamorigRightForeArm: 'rightLowerArm',
  mixamorigRightHand: 'rightHand',
  mixamorigLeftUpLeg: 'leftUpperLeg',
  mixamorigLeftLeg: 'leftLowerLeg',
  mixamorigLeftFoot: 'leftFoot',
  mixamorigLeftToeBase: 'leftToes',
  mixamorigRightUpLeg: 'rightUpperLeg',
  mixamorigRightLeg: 'rightLowerLeg',
  mixamorigRightFoot: 'rightFoot',
  mixamorigRightToeBase: 'rightToes',
};

function retargetMixamoClip(
  clip: THREE.AnimationClip,
  fbxAsset: THREE.Object3D,
  vrm: any,
): THREE.AnimationClip {
  if (!vrm?.humanoid) return clip;

  const hipsNode = vrm.humanoid.getNormalizedBoneNode('hips');
  const mixamoHips = fbxAsset.getObjectByName('mixamorigHips') as THREE.Object3D | undefined;
  if (!hipsNode || !mixamoHips) {
    console.warn('[pfp-renderer] Cannot retarget — missing hips bone');
    return clip;
  }

  const savedPosition = vrm.scene.position.clone();
  const savedQuaternion = vrm.scene.quaternion.clone();
  const savedScale = vrm.scene.scale.clone();
  vrm.scene.position.set(0, 0, 0);
  vrm.scene.quaternion.set(0, 0, 0, 1);
  vrm.scene.scale.set(1, 1, 1);
  vrm.scene.updateMatrixWorld(true);

  const _vec3 = new THREE.Vector3();
  const _quatA = new THREE.Quaternion();
  const restRotationInverse = new THREE.Quaternion();
  const parentRestWorldRotation = new THREE.Quaternion();

  const motionHipsHeight = mixamoHips.position.y;
  const vrmHipsY = hipsNode.getWorldPosition(_vec3).y;
  const vrmRootY = vrm.scene.getWorldPosition(_vec3).y;
  const vrmHipsHeight = Math.abs(vrmHipsY - vrmRootY);
  const hipsPositionScale = motionHipsHeight > 0 ? vrmHipsHeight / motionHipsHeight : 1;
  const isVRM0 = vrm.meta?.metaVersion === '0';

  const tracks: THREE.KeyframeTrack[] = [];
  let retargetedCount = 0;

  for (const track of clip.tracks) {
    const dotIndex = track.name.indexOf('.');
    if (dotIndex === -1) continue;
    const mixamoRigName = track.name.slice(0, dotIndex);
    const propertyName = track.name.slice(dotIndex + 1);
    const vrmBoneName = MIXAMO_VRM_BONE_MAP[mixamoRigName];
    if (!vrmBoneName) continue;
    const vrmNode = vrm.humanoid.getNormalizedBoneNode(vrmBoneName);
    if (!vrmNode) continue;
    const mixamoRigNode = fbxAsset.getObjectByName(mixamoRigName);
    if (!mixamoRigNode || !mixamoRigNode.parent) continue;

    mixamoRigNode.getWorldQuaternion(restRotationInverse).invert();
    mixamoRigNode.parent.getWorldQuaternion(parentRestWorldRotation);

    if (track instanceof THREE.QuaternionKeyframeTrack) {
      const values = new Float32Array(track.values.length);
      for (let i = 0; i < track.values.length; i += 4) {
        _quatA.fromArray(track.values as unknown as number[], i);
        _quatA.premultiply(parentRestWorldRotation).multiply(restRotationInverse);
        _quatA.toArray(values as unknown as number[], i);
      }
      if (isVRM0) {
        for (let i = 0; i < values.length; i += 2) values[i] = -values[i];
      }
      tracks.push(new THREE.QuaternionKeyframeTrack(
        `${vrmNode.name}.${propertyName}`,
        Array.from(track.times),
        Array.from(values),
      ));
      retargetedCount++;
    } else if (track instanceof THREE.VectorKeyframeTrack) {
      const values = new Float32Array(track.values.length);
      for (let i = 0; i < track.values.length; i++) {
        const flipSign = isVRM0 && i % 3 !== 1;
        values[i] = (flipSign ? -track.values[i] : track.values[i]) * hipsPositionScale;
      }
      tracks.push(new THREE.VectorKeyframeTrack(
        `${vrmNode.name}.${propertyName}`,
        Array.from(track.times),
        Array.from(values),
      ));
      retargetedCount++;
    }
  }

  vrm.scene.position.copy(savedPosition);
  vrm.scene.quaternion.copy(savedQuaternion);
  vrm.scene.scale.copy(savedScale);
  vrm.scene.updateMatrixWorld(true);

  if (retargetedCount === 0) {
    console.warn('[pfp-renderer] Retargeting produced 0 tracks — avatar will T-pose');
    return clip;
  }

  return new THREE.AnimationClip(clip.name, clip.duration, tracks);
}

export interface ThumbnailOptions {
  captureTime?: number;
  outputSize?: number;
  vrmUrl: string;
  bodyHeight?: number;
  maxWidth?: number;
  floorY?: number;
  cameraHalf?: number;
  animation?: string;
}

/**
 * Render one VRM to a PNG dataUrl. Consumer is responsible for uploading.
 */
export async function renderPfpThumbnail(options: ThumbnailOptions): Promise<string> {
  const {
    captureTime = 3.0,
    outputSize = 256,
    vrmUrl,
    bodyHeight = AVATAR_BODY_HEIGHT,
    maxWidth = AVATAR_MAX_WIDTH,
    floorY = AVATAR_FLOOR_Y,
    cameraHalf = CAMERA_HALF,
    animation = 'anim_idle',
  } = options;

  const animUrl = animation === 'NONE'
    ? null
    : animation.startsWith('http')
      ? animation
      : `/animations/${animation}.fbx`;

  const canvas = document.createElement('canvas');
  canvas.width = outputSize;
  canvas.height = outputSize;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(outputSize, outputSize);
  renderer.setPixelRatio(1);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.autoClear = true;

  const outline = new OutlineEffect(renderer);
  const scene = new THREE.Scene();

  const camera = new THREE.OrthographicCamera(-cameraHalf, cameraHalf, cameraHalf, -cameraHalf, 0.1, 1000);
  camera.position.set(0, 0, 1);
  camera.lookAt(0, 0, 0);

  const p1 = new THREE.PointLight(0xffffff, 1, 100); p1.position.set(10, 10, 10); scene.add(p1);
  const p2 = new THREE.PointLight(0xffffff, 1, 100); p2.position.set(-10, 10, 10); scene.add(p2);
  const p3 = new THREE.PointLight(0xffffff, 1, 100); p3.position.set(0, -10, 10); scene.add(p3);
  const hemi = new THREE.HemisphereLight(0xffffff, 0x888888, 0.9); scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 1.0); dir.position.set(0, 0, 1); scene.add(dir);
  const fill = new THREE.SpotLight(0xffffff, 0.5); fill.position.set(0, 0, 1); scene.add(fill);

  try {
    const gltfLoader = new GLTFLoader();
    gltfLoader.register((parser) => new VRMLoaderPlugin(parser));
    const gltf = await gltfLoader.loadAsync(vrmUrl);
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error('VRM data not found');

    VRMUtils.rotateVRM0(vrm);

    let retargeted: THREE.AnimationClip | null = null;
    if (animUrl) {
      const fbxLoader = new FBXLoader();
      const fbx = await fbxLoader.loadAsync(animUrl);
      if (fbx.animations.length > 0) {
        retargeted = retargetMixamoClip(fbx.animations[0], fbx, vrm);
      }
    }

    const wrapper = new THREE.Group();
    wrapper.add(vrm.scene);
    scene.add(wrapper);

    if (retargeted) {
      const mixer = new THREE.AnimationMixer(vrm.scene);
      const action = mixer.clipAction(retargeted);
      action.play();
      const delta = animUrl ? captureTime : 0.5;
      mixer.update(delta);
      vrm.update(delta);
    }

    fitToCamera(wrapper, bodyHeight, maxWidth, floorY);

    renderer.clear();
    outline.render(scene, camera);
    return canvas.toDataURL('image/png');
  } finally {
    scene.traverse((obj: any) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) obj.material.forEach((m: any) => m.dispose());
        else obj.material.dispose();
      }
    });
    renderer.dispose();
    scene.clear();
  }
}
