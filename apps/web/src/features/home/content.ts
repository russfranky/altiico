export const homeSystemModules = [
  { index: '01', icon: 'ii' as const, title: 'BROWSE THE LINEUP.', descriptor: 'PUBLIC AVATAR DISCOVERY', action: 'OPEN DISCOVERY', href: '/explore/avatar-sets' },
  { index: '02', icon: 'crosshair' as const, title: 'SEE ENGINE TRUTH.', descriptor: 'RIG / SCALE / ANIMATION', action: 'VIEW VERIFICATION', href: '#verification' },
  { index: '03', icon: 'cube' as const, title: 'MOVE ASSETS FORWARD.', descriptor: 'SETS / EMOTES / PIPELINE', action: 'VIEW OPERATIONS', href: '#operations' },
];

export const homeFlowStages = [
  { index: '01', title: 'SOURCE', copy: 'Bring an avatar set into a documented intake path with its identity and provenance intact.' },
  { index: '02', title: 'PREPARE', copy: 'Normalize the asset, imagery, metadata, and supporting files without changing what makes the set distinct.' },
  { index: '03', title: 'VERIFY', copy: 'Check the avatar against the same camera, scale, animation, and visual rules used inside Hubzz.' },
  { index: '04', title: 'RELEASE', copy: 'Move a verified set into the published catalog and make it available for use in the world.' },
];

export const homeRouteBoundaries = [
  { route: '/explore/avatar-sets', surface: 'PUBLIC DISCOVERY', state: 'LIVE / T-004' },
  { route: '/studio', surface: 'ENGINE-TRUE STUDIO', state: 'PLANNED / T-005+' },
  { route: '/submit', surface: 'CREATOR INTAKE', state: 'PLANNED / T-006' },
];
