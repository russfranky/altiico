export type CatalogReconciliationKeyKind =
  | 'chain-contract'
  | 'source-collection'
  | 'chain-contract-token'
  | 'source-asset'
  | 'source-uri';

export type CatalogReconciliationKey = Readonly<{
  kind: CatalogReconciliationKeyKind;
  value: string;
  priority: 1 | 2 | 3;
}>;
