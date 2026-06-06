import { Group, Mesh, MeshStandardMaterial, SphereGeometry } from "three";

/**
 * Avatar loading effect — big pulsing emissive sphere + N orbiting smaller ones.
 *
 * Ported verbatim from hubzz-alpha:
 *   packages/client/src/engine/entities/avatar/AvatarLoadingFX.ts
 *
 * Kept in sync so altiico's preview surface matches the in-world experience
 * users see when their avatar is loading. If the hubzz version changes
 * (color, motion, sphere count), update this file to match.
 *
 * Usage:
 *   const fx = new AvatarLoadingFX(6);
 *   scene.add(fx);
 *   // per frame:
 *   fx.update();
 *   // when VRM arrives:
 *   scene.remove(fx);
 *   fx.traverse(c => { if (c instanceof Mesh) { c.geometry.dispose(); (c.material as MeshStandardMaterial).dispose(); } });
 */
export default class AvatarLoadingFX extends Group {
    sphere: Mesh;
    spheres: Mesh[] = [];
    sphereGroup: Group = new Group();

    constructor(count: number = 6) {
        super();
        this.sphere = this.createMainSphere();
        this.createSpheres(count);
        this.add(this.sphere);
        this.add(this.sphereGroup);
    }

    createMainSphere() {
        const geometry = new SphereGeometry(1, 32, 32);
        const material = new MeshStandardMaterial({ color: 0x1c7cff, emissive: 0x1c7cff, emissiveIntensity: 2.5 });
        const sphere = new Mesh(geometry, material);
        sphere.name = "mainSphere";
        sphere.scale.set(0.5, 0.5, 0.5);
        return sphere;
    }

    createSpheres(count: number = 6) {
        for (let i = 0; i < count; i += 1) {
            const geometry = new SphereGeometry(1, 32, 32);
            const material = new MeshStandardMaterial({ color: 0x1c7cff, emissive: 0x1c7cff, emissiveIntensity: 2.5 });
            const sphere = new Mesh(geometry, material);
            const scale = Math.random() * 0.05 + 0.1;
            sphere.userData = {
                orbit: Math.random() * Math.PI * 2000.0,
                speed: Math.random() * 0.01 + 0.01,
                slant: Math.random() * Math.PI * 20000.0,
                scale: scale,
                r: Math.random() * 100000000.0,
            };
            sphere.scale.set(scale, scale, scale);
            sphere.position.set(0, 0, 0);
            this.sphereGroup.add(sphere);
            this.spheres.push(sphere);
        }
    }

    update() {
        const t = performance.now();
        const scale = 0.5;
        this.sphere.userData.height = 0;
        this.sphere.scale.set(scale, scale, scale);
        this.sphere.position.set(0, this.sphere.userData.height + (Math.sin(t * 0.005) * 0.1), 0);
        this.sphereGroup.rotation.y += 0.01;

        this.spheres.forEach((sphere) => {
            sphere.position.set(
                Math.cos(sphere.userData.orbit + t * 0.005) * 0.75,
                Math.sin(sphere.userData.orbit + t * 0.005) * 1.0,
                Math.sin(sphere.userData.slant + t * 0.005) * 0.75,
            );
            const s = Math.abs(Math.sin((t + sphere.userData.r) * 0.01) * 0.5) + 0.5;
            sphere.scale.set(s * sphere.userData.scale, s * sphere.userData.scale, s * sphere.userData.scale);
        });
    }

    /** Dispose all GPU resources. Call after removing from scene. */
    dispose() {
        this.sphere.geometry.dispose();
        (this.sphere.material as MeshStandardMaterial).dispose();
        for (const s of this.spheres) {
            s.geometry.dispose();
            (s.material as MeshStandardMaterial).dispose();
        }
    }
}
