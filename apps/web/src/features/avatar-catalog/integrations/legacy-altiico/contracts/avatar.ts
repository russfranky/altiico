export type LegacyAltiicoSourceAvatar = {
  id: string;
  tokenId: string | null;
  name: string | null;
  originalSourceUrl: string | null;
  thumbnailUrl: string | null;
  reachable: boolean;
  vrmValidated: boolean;
  validationScope: string;
  checkedAt: string | null;
  checkStatus: string | null;
  vrmSpec: string | null;
  fileSizeOriginal: number | null;
};
