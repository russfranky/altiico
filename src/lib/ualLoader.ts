/**
 * Quaternius Universal Animation Library (UAL) loader.
 *
 * UAL ships as a single GLB with ~45 named AnimationClips on an Unreal Mannequin
 * skeleton (pelvis, upperarm_l, etc). This loader mirrors mixamoLoader.ts:
 * it loads the GLB once, caches it, then retargets a named clip onto the
 * provided VRM humanoid skeleton.
 *
 * License: CC0 1.0 (public domain).
 */
import {
  AnimationClip,
  Quaternion,
  Vector3,
  QuaternionKeyframeTrack,
  VectorKeyframeTrack,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

/** Unreal Mannequin → VRM humanoid bone map. */
export const ualVRMRigMap: Record<string, string> = {
  pelvis: 'hips',
  spine_01: 'spine',
  spine_02: 'chest',
  spine_03: 'upperChest',
  neck_01: 'neck',
  Head: 'head',

  clavicle_l: 'leftShoulder',
  upperarm_l: 'leftUpperArm',
  lowerarm_l: 'leftLowerArm',
  hand_l: 'leftHand',
  thumb_01_l: 'leftThumbMetacarpal',
  thumb_02_l: 'leftThumbProximal',
  thumb_03_l: 'leftThumbDistal',
  index_01_l: 'leftIndexProximal',
  index_02_l: 'leftIndexIntermediate',
  index_03_l: 'leftIndexDistal',
  middle_01_l: 'leftMiddleProximal',
  middle_02_l: 'leftMiddleIntermediate',
  middle_03_l: 'leftMiddleDistal',
  ring_01_l: 'leftRingProximal',
  ring_02_l: 'leftRingIntermediate',
  ring_03_l: 'leftRingDistal',
  pinky_01_l: 'leftLittleProximal',
  pinky_02_l: 'leftLittleIntermediate',
  pinky_03_l: 'leftLittleDistal',

  clavicle_r: 'rightShoulder',
  upperarm_r: 'rightUpperArm',
  lowerarm_r: 'rightLowerArm',
  hand_r: 'rightHand',
  thumb_01_r: 'rightThumbMetacarpal',
  thumb_02_r: 'rightThumbProximal',
  thumb_03_r: 'rightThumbDistal',
  index_01_r: 'rightIndexProximal',
  index_02_r: 'rightIndexIntermediate',
  index_03_r: 'rightIndexDistal',
  middle_01_r: 'rightMiddleProximal',
  middle_02_r: 'rightMiddleIntermediate',
  middle_03_r: 'rightMiddleDistal',
  ring_01_r: 'rightRingProximal',
  ring_02_r: 'rightRingIntermediate',
  ring_03_r: 'rightRingDistal',
  pinky_01_r: 'rightLittleProximal',
  pinky_02_r: 'rightLittleIntermediate',
  pinky_03_r: 'rightLittleDistal',

  thigh_l: 'leftUpperLeg',
  calf_l: 'leftLowerLeg',
  foot_l: 'leftFoot',
  ball_l: 'leftToes',
  thigh_r: 'rightUpperLeg',
  calf_r: 'rightLowerLeg',
  foot_r: 'rightFoot',
  ball_r: 'rightToes',
};

const ROOT_BONE = 'pelvis';

type GLBCache = {
  asset: any | null;
  promise: Promise<any>;
};

const glbCache: Record<string, GLBCache> = {};

function loadGLB(url: string): Promise<any> {
  if (glbCache[url]?.asset) return Promise.resolve(glbCache[url].asset);
  if (glbCache[url]?.promise) return glbCache[url].promise;

  const loader = new GLTFLoader();
  const promise = loader.loadAsync(url).then((gltf) => {
    glbCache[url].asset = gltf;
    return gltf;
  });
  glbCache[url] = { asset: null, promise };
  return promise;
}

function processUALClip(vrm: any, asset: any, clipName: string, avatar: any = null) {
  if (!vrm?.scene) return null;

  const sourceClip = AnimationClip.findByName(asset.animations, clipName);
  if (!sourceClip) {
    console.warn(`[ualLoader] clip not found: ${clipName}`);
    console.warn('[ualLoader] available clips:', asset.animations?.map((a: any) => a.name));
    return null;
  }

  console.log(`[ualLoader] loading ${clipName} — source tracks: ${sourceClip.tracks.length}`);
  console.log('[ualLoader] first track names:', sourceClip.tracks.slice(0, 3).map((t: any) => t.name));
  console.log('[ualLoader] VRM humanoid sample: hips ->', vrm.humanoid?.getNormalizedBoneNode('hips')?.name);

  // Reset VRM transform for retarget math, restore after (same as MixamoLoader).
  let parent: any = null;
  const position = vrm.scene.position.clone();
  const rotation = vrm.scene.quaternion.clone();
  const scale = vrm.scene.scale.clone();

  let offset = 0;
  if (avatar?.object && avatar?.animation === 'anim_sit') {
    offset += avatar.hipHeight / 2.5;
  }

  if (vrm.scene.parent) {
    parent = vrm.scene.parent;
    vrm.scene.parent.remove(vrm.scene);
  }
  vrm.scene.position.set(0, 0, 0);
  vrm.scene.quaternion.set(0, 0, 0, 1);
  vrm.scene.scale.set(1, 1, 1);

  // Source skeleton root node. UAL hierarchy: Armature → root → pelvis → spine_01…
  // The `root` node carries an Unreal Z-up→Y-up conversion quaternion, so we
  // must read the pelvis's WORLD position (not local) to get its true Y height.
  // Also ensure the armature is updated before reading world transforms.
  asset.scene.updateWorldMatrix(true, true);

  const sourceRoot = asset.scene.getObjectByName(ROOT_BONE);
  if (!sourceRoot) {
    console.warn('[ualLoader] pelvis bone not found in UAL skeleton');
    if (parent) parent.add(vrm.scene);
    return null;
  }

  const hipsNode = vrm.humanoid?.getNormalizedBoneNode('hips');
  if (!hipsNode) {
    if (parent) parent.add(vrm.scene);
    return null;
  }

  const _vec3 = new Vector3();
  const motionHipsHeight = Math.abs(sourceRoot.getWorldPosition(_vec3).y);
  const vrmHipsY = hipsNode.getWorldPosition(_vec3).y;
  const vrmRootY = vrm.scene.getWorldPosition(_vec3).y - offset;
  const vrmHipsHeight = Math.abs(vrmHipsY - vrmRootY);
  let hipsPositionScale = motionHipsHeight > 0.01 ? vrmHipsHeight / motionHipsHeight : 1;
  if (!isFinite(hipsPositionScale) || hipsPositionScale <= 0) hipsPositionScale = 1;
  console.log(`[ualLoader] hips heights — motion: ${motionHipsHeight.toFixed(3)}, vrm: ${vrmHipsHeight.toFixed(3)}, scale: ${hipsPositionScale.toFixed(3)}`);

  const neckNode = vrm.humanoid?.getNormalizedBoneNode('neck');
  const neckY = neckNode ? neckNode.getWorldPosition(_vec3).y : vrmHipsY + 0.2;

  const restRotationInverse = new Quaternion();
  const parentRestWorldRotation = new Quaternion();
  const _quatA = new Quaternion();
  const tracks: any[] = [];

  let matched = 0;
  let skipped = 0;

  sourceClip.tracks.forEach((track) => {
    const [sourceBoneName, propertyName] = track.name.split('.');

    // Skip scale tracks — they'd distort the VRM rig.
    if (propertyName === 'scale') return;

    // Strip root motion: UAL bakes horizontal hip translation into clips, so
    // Walk_Loop, Idle_Loop, Sitting_*, etc. drift the avatar off the tile.
    // Only the hips are allowed to retain translation (so crouch/jump bob still
    // reads), and only on the Y axis.
    if (propertyName === 'translation' && sourceBoneName !== ROOT_BONE) return;

    const vrmBoneName = ualVRMRigMap[sourceBoneName];
    if (!vrmBoneName) { skipped++; return; }

    const vrmNode = vrm.humanoid?.getNormalizedBoneNode(vrmBoneName);
    if (!vrmNode) { skipped++; return; }

    const sourceNode = asset.scene.getObjectByName(sourceBoneName);
    if (!sourceNode) { skipped++; return; }

    matched++;

    sourceNode.getWorldQuaternion(restRotationInverse).invert();
    sourceNode.parent?.getWorldQuaternion(parentRestWorldRotation);

    if (track instanceof QuaternionKeyframeTrack) {
      const values = track.values.slice();
      for (let i = 0; i < values.length; i += 4) {
        _quatA.fromArray(values, i);
        _quatA
          .premultiply(parentRestWorldRotation)
          .multiply(restRotationInverse);
        _quatA.toArray(values, i);
      }

      const vrm0Mirror = vrm.meta?.metaVersion === '0';
      const finalValues = vrm0Mirror
        ? values.map((v: number, i: number) => (i % 2 === 0 ? -v : v))
        : values;

      tracks.push(
        new QuaternionKeyframeTrack(
          `${vrmNode.name}.${propertyName}`,
          track.times,
          finalValues,
        ),
      );
    } else if (track instanceof VectorKeyframeTrack) {
      // Only hips translation survives (see strip-root-motion guard above).
      // Zero out X/Z so the avatar stays tile-centered; keep Y for vertical bob.
      const vrm0Mirror = vrm.meta?.metaVersion === '0';
      const values = track.values.slice();
      for (let i = 0; i < values.length; i += 3) {
        values[i] = 0;                                   // X
        const mirrorY = vrm0Mirror ? -values[i + 1] : values[i + 1];
        values[i + 1] = mirrorY * hipsPositionScale;     // Y
        values[i + 2] = 0;                               // Z
      }
      tracks.push(
        new VectorKeyframeTrack(
          `${vrmNode.name}.${propertyName}`,
          track.times,
          values,
        ),
      );
    }
  });

  console.log(`[ualLoader] ${clipName}: matched ${matched} tracks, skipped ${skipped}, duration ${sourceClip.duration.toFixed(2)}s, hipScale ${hipsPositionScale.toFixed(3)}`);

  const animClip = new AnimationClip('vrmAnimation', sourceClip.duration, tracks);

  vrm.scene.scale.copy(scale);
  vrm.scene.position.copy(position);
  vrm.scene.quaternion.copy(rotation);
  if (parent) parent.add(vrm.scene);

  return { clip: animClip.optimize(), hipHeight: vrmHipsHeight, neckHeight: neckY };
}

/**
 * Load a named clip from a UAL GLB and retarget it onto the VRM.
 *
 * @param url - GLB url (the whole animation library)
 * @param clipName - name of the clip inside the GLB (e.g. "Idle_Loop")
 * @param vrm - target VRM
 */
export async function loadUALAnimation(
  url: string,
  clipName: string,
  vrm: any,
  avatar: any = null,
) {
  if (!vrm?.scene) throw new Error('VRM not loaded');
  const asset = await loadGLB(url);
  return processUALClip(vrm, asset, clipName, avatar);
}
