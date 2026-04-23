// Copied from hubzz-alpha/packages/client/src/engine/misc/MixamoLoader.ts — do not edit here.

import { AnimationClip, Quaternion, Vector3, QuaternionKeyframeTrack, VectorKeyframeTrack } from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";

/**
 * A map from Mixamo rig name to VRM Humanoid bone name
 */
export const mixamoVRMRigMap = {
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
	mixamorigLeftHandThumb1: 'leftThumbMetacarpal',
	mixamorigLeftHandThumb2: 'leftThumbProximal',
	mixamorigLeftHandThumb3: 'leftThumbDistal',
	mixamorigLeftHandIndex1: 'leftIndexProximal',
	mixamorigLeftHandIndex2: 'leftIndexIntermediate',
	mixamorigLeftHandIndex3: 'leftIndexDistal',
	mixamorigLeftHandMiddle1: 'leftMiddleProximal',
	mixamorigLeftHandMiddle2: 'leftMiddleIntermediate',
	mixamorigLeftHandMiddle3: 'leftMiddleDistal',
	mixamorigLeftHandRing1: 'leftRingProximal',
	mixamorigLeftHandRing2: 'leftRingIntermediate',
	mixamorigLeftHandRing3: 'leftRingDistal',
	mixamorigLeftHandPinky1: 'leftLittleProximal',
	mixamorigLeftHandPinky2: 'leftLittleIntermediate',
	mixamorigLeftHandPinky3: 'leftLittleDistal',
	mixamorigRightShoulder: 'rightShoulder',
	mixamorigRightArm: 'rightUpperArm',
	mixamorigRightForeArm: 'rightLowerArm',
	mixamorigRightHand: 'rightHand',
	mixamorigRightHandPinky1: 'rightLittleProximal',
	mixamorigRightHandPinky2: 'rightLittleIntermediate',
	mixamorigRightHandPinky3: 'rightLittleDistal',
	mixamorigRightHandRing1: 'rightRingProximal',
	mixamorigRightHandRing2: 'rightRingIntermediate',
	mixamorigRightHandRing3: 'rightRingDistal',
	mixamorigRightHandMiddle1: 'rightMiddleProximal',
	mixamorigRightHandMiddle2: 'rightMiddleIntermediate',
	mixamorigRightHandMiddle3: 'rightMiddleDistal',
	mixamorigRightHandIndex1: 'rightIndexProximal',
	mixamorigRightHandIndex2: 'rightIndexIntermediate',
	mixamorigRightHandIndex3: 'rightIndexDistal',
	mixamorigRightHandThumb1: 'rightThumbMetacarpal',
	mixamorigRightHandThumb2: 'rightThumbProximal',
	mixamorigRightHandThumb3: 'rightThumbDistal',
	mixamorigLeftUpLeg: 'leftUpperLeg',
	mixamorigLeftLeg: 'leftLowerLeg',
	mixamorigLeftFoot: 'leftFoot',
	mixamorigLeftToeBase: 'leftToes',
	mixamorigRightUpLeg: 'rightUpperLeg',
	mixamorigRightLeg: 'rightLowerLeg',
	mixamorigRightFoot: 'rightFoot',
	mixamorigRightToeBase: 'rightToes',
};

const animationCache = {

};

export function processMixamoAsset(vrm, asset, avatar=null) {
	if (!vrm?.scene) return null;
	let parent = null;
	const position = vrm.scene.position.clone();
	const rotation = vrm.scene.quaternion.clone();
	const scale = vrm.scene.scale.clone();
	let offset = 0;

	// otherwise the animation will be lowered... we need a better fix
	if(avatar && avatar.object && avatar.animation === "anim_sit") {
		offset += avatar.hipHeight / 2.5;
	}

	if(vrm.scene.parent) {
		parent = vrm.scene.parent;
		vrm.scene.parent.remove(vrm.scene);
	}

	vrm.scene.position.set(0, 0, 0);
	vrm.scene.quaternion.set(0, 0, 0, 1);
	vrm.scene.scale.set(1, 1, 1);

	const clip = AnimationClip.findByName(asset.animations, 'mixamo.com').clone(); // extract the AnimationClip

	const tracks = []; // KeyframeTracks compatible with VRM will be added here

	const restRotationInverse = new Quaternion();
	const parentRestWorldRotation = new Quaternion();
	const _quatA = new Quaternion();
	const _vec3 = new Vector3();

	// Adjust with reference to hips height.
	const hipsNode = vrm.humanoid?.getNormalizedBoneNode('hips');
	if (!hipsNode) return null;
	const motionHipsHeight = asset.getObjectByName('mixamorigHips').position.y;
	const vrmHipsY = hipsNode.getWorldPosition(_vec3).y;

	const vrmRootY = vrm.scene.getWorldPosition(_vec3).y - offset;
	const vrmHipsHeight = Math.abs(vrmHipsY - vrmRootY);
	const hipsPositionScale = vrmHipsHeight / motionHipsHeight;

	// get the world height of the tallest head bone, this is used for creating a mugshot
	const neckNode = vrm.humanoid?.getNormalizedBoneNode('neck');
	const neckY = neckNode ? neckNode.getWorldPosition(_vec3).y : vrmHipsY + 0.2;

	clip.tracks.forEach((track) => {

		// Convert each tracks for VRM use, and push to `tracks`
		const trackSplitted = track.name.split('.');
		const mixamoRigName = trackSplitted[0];
		const vrmBoneName = mixamoVRMRigMap[mixamoRigName];
		const vrmNodeName = vrm.humanoid?.getNormalizedBoneNode(vrmBoneName)?.name;
		const mixamoRigNode = asset.getObjectByName(mixamoRigName);

		if (vrmNodeName != null) {

			const propertyName = trackSplitted[1];

			// Store rotations of rest-pose.
			mixamoRigNode.getWorldQuaternion(restRotationInverse).invert();
			mixamoRigNode.parent.getWorldQuaternion(parentRestWorldRotation);

			if (track instanceof QuaternionKeyframeTrack) {

				// Retarget rotation of mixamoRig to NormalizedBone.
				for (let i = 0; i < track.values.length; i += 4) {

					const flatQuaternion = track.values.slice(i, i + 4);

					_quatA.fromArray(flatQuaternion);

					// 親のレスト時ワールド回転 * トラックの回転 * レスト時ワールド回転の逆
					_quatA
						.premultiply(parentRestWorldRotation)
						.multiply(restRotationInverse);

					_quatA.toArray(flatQuaternion);

					flatQuaternion.forEach((v, index) => {

						track.values[index + i] = v;

					});

				}

				tracks.push(
					new QuaternionKeyframeTrack(
						`${vrmNodeName}.${propertyName}`,
						track.times,
						track.values.map((v, i) => (vrm.meta?.metaVersion === '0' && i % 2 === 0 ? - v : v)),
					),
				);

			} else if (track instanceof VectorKeyframeTrack) {

				const value = track.values.map((v, i) => (vrm.meta?.metaVersion === '0' && i % 3 !== 1 ? - v : v) * hipsPositionScale);
				tracks.push(new VectorKeyframeTrack(`${vrmNodeName}.${propertyName}`, track.times, value));

			}

		}

	});

	const animClip = new AnimationClip('vrmAnimation', clip.duration, tracks);


	vrm.scene.scale.copy(scale);
	vrm.scene.position.copy(position);
	vrm.scene.quaternion.copy(rotation);
	if(parent) {
		parent.add(vrm.scene);
	}

	return { clip: animClip.optimize(), hipHeight: vrmHipsHeight, neckHeight: neckY };

}

/**
 * Returns a filtered version of the animation clip where it only affects bones where filterFunc returns true on that bone.
 * @param clip
 * @param filterFunc
 */
export function getFilteredAnimation(clip: AnimationClip, filterFunc: Function) {
	const tracks = [];

	clip.tracks.forEach((track) => {
		const trackSplitted = track.name.split('.');
		const boneName = trackSplitted[0];
		const propertyName = trackSplitted[1];

		if (filterFunc(boneName, propertyName)) {
			tracks.push(track);
		}
	});

	return new AnimationClip('vrmAnimation', clip.duration, tracks);
}

/**
 * Load Mixamo animation, convert for three-vrm use, and return it.
 *
 * @param {string} url A url of mixamo animation data
 * @param {VRM} vrm A target VRM
 * @returns {Promise<AnimationClip>} The converted AnimationClip
 */
export function loadMixamoAnimation(url, vrm, avatar=null) {

	return new Promise((resolve, reject) => {
		if (!vrm?.scene) {
			reject(new Error("VRM not loaded"));
			return;
		}
		if (animationCache[url]) {
			if (animationCache[url].asset) {
				resolve(processMixamoAsset(vrm, animationCache[url].asset.clone(), avatar));
			} else {
				animationCache[url].promise.then(asset => {
					resolve(processMixamoAsset(vrm, asset.clone(), avatar));

					return asset;
				});
			}

		} else {

			const loader = new FBXLoader(); // A loader which loads FBX
			animationCache[url] = {
				asset: null, promise: loader.loadAsync(url).then(asset => {
					animationCache[url].asset = asset;
					resolve(processMixamoAsset(vrm, asset.clone(), avatar));

					return asset;
				})
			};
		}

	});

}
