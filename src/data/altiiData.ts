import type {
  Collection,
  Avatar,
  CommunityMember,
  Awesome3DCollection,
  OpensourceResource,
  OpenSourceAvatarProject
} from '../types';

export const PLACEHOLDER_IMG: string = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjE0IiBmaWxsPSIjZmZmIj5JbWFnZSBVbmF2YWlsYWJsZTwvdGV4dD48L3N2Zz4=';

export const collections: Collection[] = [
  {
    name: 'VIPE Heroes',
    items: '3,000',
    banner: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/VIPEHeroes/VIPE_Heroes_Cover_2400x1600_V2.webp',
    pfp: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/VIPEHeroes_Opensea_icon_400x400.jpg',
    assets3D: '3D Ready',
    category: 'Genesis Collections',
    contract: '0x3999877754904d8542ad1845d368fa01a5e6e9a5',
    description: 'The 3,000-piece Genesis collection that pioneered the Virtual Identity Protocol.',
    metadataParam: 'asset',
    opensource: {
      registry: 'https://opensourceavatars.com',
      projectsJson: 'https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/projects.json',
    },
  },
  {
    name: 'Avastars',
    items: '25,700',
    banner: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/Avastars/Avastars_2400x1600.webp',
    pfp: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/Avastars/Avastars_400x400.jpg',
    assets3D: '3D Ready',
    category: 'Classic Meta',
    contract: '0xF12b5dd48171122709282363198fA019488b14a9',
    description: 'Generative art on the Ethereum blockchain. Fully on-chain SVGs and metadata.',
    metadataParam: 'vrm',
  },
  {
    name: 'SuperYeti',
    items: '10,000',
    banner: 'https://web.archive.org/web/20230325202804im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/07d98dfe-6028-4581-bc5a-543e1f336bc6/yeti-bomber-banner-03.jpg',
    pfp: 'https://web.archive.org/web/20230325202804im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/029401cc-8156-4dc8-b117-d1d27ac41b4f/superyeti_icon_white_padding.png',
    assets3D: 'GLB',
    category: 'Metaverse Ready',
    contract: '0x3F0785095A660fEe131eEbcD5aa243e529C21786',
    description: 'The world\'s first 10,000 3D generative NFT collection.'
  },
  {
    name: 'CryptoAvatars',
    items: 'Various',
    banner: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/web_300x248_CA.jpg',
    pfp: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/web_profile_CA-2.jpg',
    assets3D: '3D Ready · FBX',
    category: 'Avatar Standard',
    contract: '0xfeb56aaf59f8c17300f4d8306365a491b05b6602',
    description: 'A collection of unique 3D avatars for the open metaverse. Born from Polygonal Mind\'s 100 Avatars and Avatar Garden — the VRChat space that housed the series.',
    opensource: {
      repo: 'https://github.com/PolygonalMind/initiative-opensource-release',
      caWorld: 'https://github.com/PolygonalMind/initiative-opensource-release/releases/tag/230518',
      avatarGarden: 'https://github.com/PolygonalMind/initiative-opensource-release/releases/tag/230426.1',
    },
  },
  {
    name: 'Forgotten Runes',
    items: '10,000',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: '3D Ready',
    category: 'The Great Archive',
    contract: '0x521f9c7505005cfa19a8e5786a9c3c9c9f5e6f42',
    description: 'Every Wizard has a soul. Fully on-chain metadata and decentralized storytelling.',
    metadataParam: 'vrm',
  },
  {
    name: 'CloneX',
    items: '20,000',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: 'GLB',
    category: 'Fashion Meta',
    contract: '0x49cf6f5d44e70224e2e23fdcdd2c053f30ada28b',
    description: 'High-end avatars created by RTFKT and Takashi Murakami.'
  },
  {
    name: 'Meebits',
    items: '20,000',
    banner: 'https://meebits.app/static/img/meebits_banner.png',
    pfp: 'https://meebits.app/static/img/meebits_pfp.png',
    assets3D: 'Voxel · T-Pose',
    category: 'Voxel Meta',
    contract: '0x7bd29408f11d2bfc23c34f18275bbf23bb716bc7',
    description: '3D voxel characters for virtual worlds and games.',
    metadataParam: 'vrm',
  },
  {
    name: 'altiico',
    items: '10,000',
    banner: 'https://2-crypto.s3.amazonaws.com/the-beeings/gallery/Bee.png',
    pfp: 'https://2-crypto.s3.amazonaws.com/the-beeings/logo.png',
    assets3D: 'Coming Soon',
    category: 'Curated Collections',
    contract: '0x5a642e2d5f378d2dd44044eb7d21e4a5f3b4dc6a',
    description: 'Generative honey bees for the metaverse. Community-driven collection with on-chain metadata.'
  },
  {
    name: 'Azuki',
    items: '10,000',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: 'GLB',
    category: 'Fashion Meta',
    contract: '0xED5AF388653567Af2F388E6224dC7C4b3241C544',
    description: 'A collection of 10,000 avatars that give you membership access to The Garden.'
  },
  {
    name: 'Bored Ape Yacht Club',
    items: '10,000',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: 'GLB',
    category: 'Classic Meta',
    contract: '0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D',
    description: 'A collection of 10,000 unique Bored Ape NFTs on the Ethereum blockchain.'
  },
  {
    name: 'Cryptoadz by Gremplin',
    items: '7,077',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: 'GLB',
    category: 'Classic Meta',
    contract: '0x1CB1A5e65610AEFF2551A50f76a87a7d3fB649C6',
    description: 'Small, anthropomorphic beings that exist on the Ethereum blockchain.'
  },
  {
    name: '100 Avatars',
    items: '200',
    banner: 'https://raw.githubusercontent.com/PolygonalMind/initiative-opensource-release/main/images/100AvatarsR1_Cover.jpg',
    pfp: 'https://raw.githubusercontent.com/PolygonalMind/initiative-opensource-release/main/images/100AvatarsR2_Cover.jpg',
    assets3D: '3D Ready · FBX · VXR',
    category: 'Curated Collections',
    contract: '',
    description: 'CC0 character packs by Polygonal Mind. R1 (2018) and R2 (2020) — 1-avatar-per-day series. Themes: Aliens, Monsters, Adventurers, Christmas, Food. Available as .fbx, .vrm, .vxr. First step towards CryptoAvatars.',
    opensource: {
      repo: 'https://github.com/PolygonalMind/initiative-opensource-release',
      original: 'https://www.100avatars.com/',
      sketchfabR1: 'https://sketchfab.com/3d-models/100-avatars-r1-cc0-character-pack-c96f3ac9e8ee4bc192809e4a64bddfc2',
      sketchfabR2: 'https://sketchfab.com/3d-models/100-avatars-r2-cc0-character-pack-80cb24ac52cb4e839930aaa12314f716',
      release: 'https://github.com/PolygonalMind/initiative-opensource-release/releases/tag/230412.1',
      registry: 'https://opensourceavatars.com',
    },
  },
  {
    name: '3dnotjpegs',
    items: 'Various',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: '3D Ready',
    category: 'Metaverse Ready',
    contract: '',
    description: '3D avatars for the metaverse. Focus on VRM interoperability across VRChat, Hyperfy, Spatial, and open virtual worlds.'
  },
  {
    name: 'Nouns',
    items: 'Daily',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: '3D Ready',
    category: 'Curated Collections',
    contract: '0x9c8ff314c9bc7f6e59a9d9225fb22946427edc03',
    description: 'OneNoun every day, forever. CC0. VRM avatars for the open metaverse.'
  },
  {
    name: 'Boomboxheads V2',
    items: 'Various',
    banner: PLACEHOLDER_IMG,
    pfp: PLACEHOLDER_IMG,
    assets3D: '3D Ready · GLB',
    category: 'Metaverse Ready',
    contract: '0xb67ff46dfde55ad2fe05881433e5687fd1000312',
    description: 'VRM avatars. Metadata: vrm_url / description (GLB).'
  },
];

const avatarsData: Avatar[] = [
  {
    id: 1,
    name: 'VIPE Hero #001',
    collection: 'VIPE Heroes',
    image: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/VIPEHeroes_Opensea_icon_400x400.jpg',
    vrm: '3D Ready',
    vrmUrl: 'https://dweb.link/ipfs/Qma1z2WUWv33JHb4gJTKChUWs3z9M2dnpiPWAHidmruu4z/default_1.vrm',
    interop: ['Hyperfy', 'Spatial', 'VRChat'],
    opensea: 'https://opensea.io/assets/ethereum/0x3999877754904d8542ad1845d368fa01a5e6e9a5/1',
    traits: {
      'Skin': 'Golden',
      'Class': 'Vanguard',
      'Suit': 'Genesis'
    }
  },
  {
    id: 0,
    name: 'Avastar #0',
    collection: 'Avastars',
    image: 'https://avastars.io/media/0',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://ipfs.io/ipfs/QmWXa41YRBdJpZUwwYiXakTAkza2efT8hzbS5t8imXyTpC/Avastar_Founder_0.vrm',
    opensea: 'https://opensea.io/assets/ethereum/0xF12b5dd48171122709282363198fA019488b14a9/0',
    traits: {
      'Gender': 'female',
      'Generation': '1',
      'Series': '0',
      'Serial': '0',
      'Skin Tone': 'Lavender Rose',
      'Hair Color': 'Neon Pink',
      'Eye Color': 'Blue De France',
      'Background': 'Soft Lavender',
      'Backdrop': 'Backdrop 50',
      'Ears': 'Attached Bitcoin Earrings',
      'Face': 'Female Face 10',
      'Nose': 'Cyborg',
      'Mouth': 'Gold Grill',
      'Facial Feature': 'Cyborg',
      'Eyes': 'Cyborg',
      'Hair Style': 'Queen\'s Crown',
    }
  },
  {
    id: 1,
    name: 'Avastar #1',
    collection: 'Avastars',
    image: 'https://avastars.io/media/1',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://ipfs.io/ipfs/QmWXa41YRBdJpZUwwYiXakTAkza2efT8hzbS5t8imXyTpC/Avastar_Founder_1.vrm',
    opensea: 'https://opensea.io/assets/ethereum/0xF12b5dd48171122709282363198fA019488b14a9/1',
    traits: {
      'Gender': 'male',
      'Generation': '1',
      'Series': '0',
      'Serial': '1',
      'Skin Tone': 'Alien',
      'Hair Color': 'Red Berry',
      'Eye Color': 'Golden',
      'Background': 'Blush',
      'Backdrop': 'Backdrop 50',
      'Ears': 'Attached Bitcoin Earring',
      'Face': 'Male Face 10',
      'Nose': 'Cyborg',
      'Mouth': 'Gold Grill',
      'Facial Feature': 'Zeus\'s Beard',
      'Eyes': 'Steampunk',
      'Hair Style': 'King\'s Crown',
    }
  },
  {
    id: 2,
    name: 'Avastar #2',
    collection: 'Avastars',
    image: 'https://avastars.io/media/2',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://ipfs.io/ipfs/QmWXa41YRBdJpZUwwYiXakTAkza2efT8hzbS5t8imXyTpC/Avastar_Founder_2.vrm',
    opensea: 'https://opensea.io/assets/ethereum/0xF12b5dd48171122709282363198fA019488b14a9/2',
    traits: {
      'Gender': 'female',
      'Generation': '1',
      'Series': '0',
      'Serial': '2',
      'Skin Tone': 'Alien',
      'Hair Color': 'White Blonde',
      'Eye Color': 'Bright Pink',
      'Background': 'Sugar Cane',
      'Backdrop': 'Backdrop 35',
      'Ears': 'Attached Bitcoin Earrings',
      'Face': 'Female Face 7',
      'Nose': 'Mona Lisa',
      'Mouth': 'Big Smile',
      'Facial Feature': 'None v2',
      'Eyes': 'Sad',
      'Hair Style': 'Admiral\'s Hat',
    }
  },
  {
    id: 3,
    name: 'Avastar #3',
    collection: 'Avastars',
    image: 'https://avastars.io/media/3',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://ipfs.io/ipfs/QmWXa41YRBdJpZUwwYiXakTAkza2efT8hzbS5t8imXyTpC/Avastar_Founder_3.vrm',
    opensea: 'https://opensea.io/assets/ethereum/0xF12b5dd48171122709282363198fA019488b14a9/3',
    traits: {
      'Gender': 'male',
      'Generation': '1',
      'Series': '0',
      'Serial': '3',
      'Skin Tone': 'Zombie',
      'Hair Color': 'Dark Auburn',
      'Eye Color': 'Baby',
      'Background': 'Blue Bubbles',
      'Backdrop': 'Backdrop 35',
      'Ears': 'Attached Bitcoin Earring',
      'Face': 'Male Face 8',
      'Nose': 'Mona Lisa',
      'Mouth': 'Spliff',
      'Facial Feature': 'Thin Sideburns',
      'Eyes': 'Pirate Patch',
      'Hair Style': 'Pirate',
    }
  },
  {
    id: 4,
    name: 'Avastar #4',
    collection: 'Avastars',
    image: 'https://avastars.io/media/4',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://ipfs.io/ipfs/QmWXa41YRBdJpZUwwYiXakTAkza2efT8hzbS5t8imXyTpC/Avastar_Founder_4.vrm',
    opensea: 'https://opensea.io/assets/ethereum/0xF12b5dd48171122709282363198fA019488b14a9/4',
    traits: {
      'Gender': 'female',
      'Generation': '1',
      'Series': '0',
      'Serial': '4',
      'Skin Tone': 'Amber Brown',
      'Hair Color': 'Neon Pink',
      'Eye Color': 'Bright Pink',
      'Background': 'Solitude',
      'Backdrop': 'Backdrop 51',
      'Ears': 'Attached Bitcoin Earrings',
      'Face': 'Female Face 2',
      'Nose': 'Greek Stud',
      'Mouth': 'Spliff',
      'Facial Feature': 'Butterfly Tattoo',
      'Eyes': 'Trippy',
      'Hair Style': 'Police Hat',
    }
  },
  {
    id: 101,
    name: 'Avastar #101',
    collection: 'Avastars',
    image: 'https://avastars.io/media/101',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://ipfs.io/ipfs/QmYsSqHpgGGwm9XncVNbA7rf9zPRzbVPMgkGWqn6XZ2k8Q/Avastar_Exclusive_101.vrm',
    opensea: 'https://opensea.io/assets/ethereum/0xF12b5dd48171122709282363198fA019488b14a9/101',
    traits: {
      'Gender': 'male',
      'Generation': '1',
      'Series': '0',
      'Serial': '101',
      'Skin Tone': 'Amber Brown - burned',
      'Hair Color': 'Blue - burned',
      'Eye Color': 'Bright Pink - burned',
      'Background': 'Violet Chalk - burned',
      'Backdrop': 'Backdrop 27 - burned',
      'Ears': 'Elf Ethereum Stud - burned',
      'Face': 'Male Face 8 - burned',
      'Nose': 'Nubian Nosering - burned',
      'Mouth': 'Simple Smile - burned',
      'Facial Feature': 'Hipster Beard - burned',
      'Eyes': 'Hero Mask - burned',
      'Hair Style': 'Afro - burned',
    }
  },
  {
    id: 500,
    name: 'SuperYeti #500',
    collection: 'SuperYeti',
    image: 'https://web.archive.org/web/20230325202804im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/4b60a200-7785-4beb-b9bc-781e9bd6f805/2pink.png',
    vrm: 'Interactive Avatar',
    vrmUrl: 'https://arweave.net/gfVzs1oH_aPaHVxpQK86HT_rqzyrFPOUKUrDJ30yprs',
    opensea: 'https://opensea.io/assets/ethereum/0x3F0785095A660fEe131eEbcD5aa243e529C21786/500',
    traits: {
      'Tribe': 'Frost',
      'Skin': 'Pink',
      'Eyes': 'Laser',
      'Head': 'Crown'
    }
  },
  {
    id: 1001,
    name: 'CryptoAvatar #1001',
    collection: 'CryptoAvatars',
    image: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/web_profile_CA-2.jpg',
    vrm: '3D Ready',
    vrmUrl: 'https://arweave.net/gfVzs1oH_aPaHVxpQK86HT_rqzyrFPOUKUrDJ30yprs',
    interop: ['VRChat', 'WebXR'],
    opensea: 'https://opensea.io/assets/ethereum/0xfeb56aaf59f8c17300f4d8306365a491b05b6602/1001',
    traits: {
      'Artist': 'Polycount',
      'Series': 'Genesis',
      'Type': 'Humanoid'
    }
  },
  {
    id: 7362,
    name: 'Wizard #7362',
    collection: 'Forgotten Runes',
    image: PLACEHOLDER_IMG,
    vrm: '3D Ready',
    vrmUrl: 'https://arweave.net/jPOg-G0MPH55ZQmamFhT9f8cHn-hjeAQ0mRO5gWeKMQ',
    opensea: 'https://opensea.io/assets/ethereum/0x521f9c7505005cfa19a8e5786a9c3c9c9f5e6f42/7362',
    traits: {
      'Head': 'Fire Hat',
      'Robe': 'Crimson Robe',
      'Staff': 'Crystal Staff'
    }
  },
  {
    id: 9552,
    name: 'CloneX #9552',
    collection: 'CloneX',
    image: PLACEHOLDER_IMG,
    vrm: 'Interactive Avatar',
    opensea: 'https://opensea.io/assets/ethereum/0x49cf6f5d44e70224e2e23fdcdd2c053f30ada28b/9552',
    traits: {
      'DNA': 'Human',
      'Clothing': 'Cyber Jacket',
      'Eye': 'Neon Blue'
    }
  },
  {
    id: 42,
    name: 'Beeing #42',
    collection: 'altiico',
    image: 'https://2-crypto.s3.amazonaws.com/the-beeings/gallery/Bee.png',
    vrm: 'Pending',
    opensea: 'https://opensea.io/collection/the-beeings',
    traits: {
      'Species': 'Honey Bee',
      'Accessory': 'Antennas',
      'Mood': 'Happy'
    }
  }
];

// Generate 10,000 SuperYeti avatars lazily — only when avatars are first accessed
const superYetiImages = [
  'https://web.archive.org/web/20220308191038im_/http://static1.squarespace.com/static/6078a567cd564058f99c3281/t/60b94a8ad907090435b9ec54/1622755978562/yeti-wifey2.png?format=1500w',
  'https://web.archive.org/web/20220308191038im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/13422fb9-e800-481f-aecc-f5d080835ef3/finalyeti13.png',
  'https://web.archive.org/web/20220308191038im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/1623757821537-TEDCMEW33UEKSZIOQFTJ/Test_superYeti_photographer_23.jpg',
  'https://web.archive.org/web/20230325202804im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/4b60a200-7785-4beb-b9bc-781e9bd6f805/2pink.png'
];

let _fullAvatars: Avatar[] | null = null;

function getAvatarsWithSuperYeti(): Avatar[] {
  if (_fullAvatars) return _fullAvatars;
  _fullAvatars = [...avatarsData];
  for (let i = 0; i < 10000; i++) {
    if (_fullAvatars.some(a => a.collection === 'SuperYeti' && a.id === i)) continue;
    _fullAvatars.push({
      id: i,
      name: `SuperYeti #${i}`,
      collection: 'SuperYeti',
      image: superYetiImages[i % superYetiImages.length],
      vrm: 'Pending',
      opensea: `https://opensea.io/assets/ethereum/0x3F0785095A660fEe131eEbcD5aa243e529C21786/${i}`,
      traits: {
        'Generated': 'Yes',
        'Role': i % 3 === 0 ? 'Wifey' : i % 3 === 1 ? 'Yeti' : 'Photographer'
      }
    });
  }
  return _fullAvatars;
}

export { getAvatarsWithSuperYeti as getAvatars };
export const avatars = avatarsData;

export const communityMembers: CommunityMember[] = [
  { name: 'altiico', pfp: 'https://2-crypto.s3.amazonaws.com/the-beeings/logo.png', role: 'Core Team' },
  { name: 'Polygonal Mind', pfp: 'https://raw.githubusercontent.com/PolygonalMind/initiative-opensource-release/main/images/PolygonalMind_Logo.jpg', role: '100 Avatars · CryptoAvatars' },
  { name: 'CryptoAvatars', pfp: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/web_profile_CA-2.jpg', role: 'Avatar Standard' },
  { name: 'Avastars', pfp: 'https://web.archive.org/web/20230922060200im_/https://storage.cryptoavatars.io/marketingImages/Avastars/Avastars_400x400.jpg', role: 'Classic Meta' },
  { name: 'SuperYeti', pfp: 'https://web.archive.org/web/20230325202804im_/https://images.squarespace-cdn.com/content/v1/6078a567cd564058f99c3281/029401cc-8156-4dc8-b117-d1d27ac41b4f/superyeti_icon_white_padding.png', role: 'Metaverse Ready' },
];

/** Curated list of tokenized 3D avatar collections (Ethereum, VRM) — from awesome-3D-avatar-collections */
export const awesome3dCollections: Awesome3DCollection[] = [
  { name: 'Nouns', url: 'https://nouns.wtf/', contract: '0x9c8ff314c9bc7f6e59a9d9225fb22946427edc03', vrm: true },
  { name: 'Voltz', url: 'https://voltz.me/en/', contract: '0xea377cfd0ceab570569d8d37a910071d9e9eb1d4', vrm: true },
  { name: 'Cyberbrokers Genesis Mechs', url: 'https://www.cyberbrokers.com/', contract: '0xb286ac8eff9f44e2c377c6770cad5fc78bff9ed6', vrm: true, metadataParam: 'vrm_url / files:glb' },
  { name: 'Boomboxheads V2', url: 'https://gm3.github.io/boomboxheads-v2/', contract: '0xb67ff46dfde55ad2fe05881433e5687fd1000312', vrm: true, metadataParam: 'vrm_url / description' },
  { name: 'Allstarz PSX', url: 'https://allstarz.world/', contract: '0x6120991c423f3566753d3c6c91a5b50d7d2461b4', vrm: true, metadataParam: 'vrm_url' },
  { name: 'Woodies', url: 'https://woodiesofficial.com/', contract: '0x134460d32fc66a6d84487c20dcd9fdcf92316017', vrm: true },
  { name: 'DickButt Verse', url: 'https://www.dickbuttverse.com/', contract: '0xd47d8672e45a7204057baaa3622a3fa276d651e3', vrm: true, metadataParam: 'vrm_url / animation_url' },
  { name: 'PixelBeasts', url: 'https://www.pixelbeasts.co/', contract: '0xd539a3a5edb713e6587e559a9d007ffff92bd9ab', vrm: true, metadataParam: 'model/vrm' },
];

/** CC0 opensource packs from Polygonal Mind — 100 Avatars, CryptoAvatars, Avatar Garden */
export const opensourceResources: OpensourceResource[] = [
  { label: '100 Avatars R1 & R2', href: 'https://github.com/PolygonalMind/initiative-opensource-release/releases/tag/230412.1', description: 'Character packs · VRM, FBX, VXR' },
  { label: 'Avatar Garden', href: 'https://github.com/PolygonalMind/initiative-opensource-release/releases/tag/230426.1', description: 'VRChat space · 130 assets' },
  { label: 'CA World', href: 'https://github.com/PolygonalMind/initiative-opensource-release/releases/tag/230518', description: 'CryptoAvatars world · 65 elements' },
  { label: 'Cryptoavatars Retro Booth', href: 'https://github.com/PolygonalMind/initiative-opensource-release', description: 'CC0 asset pack' },
  { label: 'Initiative repo', href: 'https://github.com/PolygonalMind/initiative-opensource-release', description: 'All packs · CC0' },
  { label: 'Awesome 3D Avatar Collections', href: 'https://github.com/itsmetamike/awesome-3D-avatar-collections', description: 'VRM collections index' },
  { label: 'Open Source Avatars', href: 'https://opensourceavatars.com', description: 'Free VRM registry · CC0/CC-BY' },
  { label: 'Open Source Avatars (repo)', href: 'https://github.com/ToxSam/open-source-avatars', description: 'projects.json · avatars/*.json' },
];

/** Open Source Avatars registry — free VRM avatars with direct download links */
export const openSourceAvatarsProjects: OpenSourceAvatarProject[] = [
  { id: '100avatars-r1', name: '100Avatars R1', license: 'CC0', url: 'https://opensourceavatars.com' },
  { id: '100avatars-r2', name: '100Avatars R2', license: 'CC0', url: 'https://opensourceavatars.com' },
  { id: '100avatars-r3', name: '100Avatars R3', license: 'CC0', url: 'https://opensourceavatars.com' },
  { id: 'vipe-heroes-genesis', name: 'VIPE Heroes Genesis', license: 'CC-BY', url: 'https://opensourceavatars.com', contract: '0x3999877754904d8542ad1845d368fa01a5e6e9a5' },
  { id: 'grifters-squaddies', name: 'Grifters Squaddies', license: 'CC0', url: 'https://opensourceavatars.com', contract: '0xa94c652c16525e6b7cac82a34eab18b5174ad23c' },
  { id: 'toxsam', name: 'ToxSam', license: 'CC0', url: 'https://opensourceavatars.com' },
  { id: 'halloween-rising', name: 'Halloween Rising', license: 'CC0', url: 'https://opensourceavatars.com', contract: '0x0ad4c869d0019df7460b33ca852610c9cb0a5647' },
  { id: 'xmas-chibis', name: 'Xmas Chibis', license: 'CC0', url: 'https://opensourceavatars.com', contract: '0x831079839bd0e6bf8e37e8cdfb5479fc1b2ef483' },
];
